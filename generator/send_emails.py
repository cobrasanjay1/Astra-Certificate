"""
Certificate email sender with persistent queue and retry logic.

Features:
  - File-based persistent queue (survives crashes / Action timeouts)
  - Exponential backoff retry (1s → 2s → 4s → ... up to max)
  - Resume from where it left off (--resume)
  - Retry only failed items (--retry-failed)
  - Per-item status tracking: PENDING → SENDING → SENT / FAILED
  - Detailed summary report at the end

Usage:
    python send_emails.py --event-id "Cypher Decode"                  # First run
    python send_emails.py --event-id "Cypher Decode" --resume         # Resume after crash
    python send_emails.py --event-id "Cypher Decode" --retry-failed   # Retry failures
    python send_emails.py --event-id "Cypher Decode" --dry-run        # Test without sending
    python send_emails.py --event-id "Cypher Decode" --max-retries 5  # Custom retry limit
"""

import os
import sys
import json
import base64
import argparse
import logging
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    RESEND_API_KEY, FROM_EMAIL, CERT_VERIFY_BASE_URL,
    SUPABASE_URL, SUPABASE_KEY,
    DATA_DIR, OUTPUT_DIR, safe_id,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("email-queue")

STATUS_PENDING = "PENDING"
STATUS_SENDING = "SENDING"
STATUS_SENT = "SENT"
STATUS_FAILED = "FAILED"


def _fetch_event_title_from_db(event_id):
    """Fetch the canonical event title from events_event using its DB id."""
    if not event_id or not SUPABASE_URL or not SUPABASE_KEY:
        return None

    try:
        from supabase import create_client

        client = create_client(SUPABASE_URL, SUPABASE_KEY)
        response = (
            client.table("events_event")
            .select("id,title,event_date")
            .eq("id", event_id)
            .limit(1)
            .execute()
        )

        if response.data:
            row = response.data[0]
            title = (row.get("title") or "").strip()
            if title:
                return {
                    "title": title,
                    "event_date": row.get("event_date", ""),
                }
    except Exception as exc:
        logger.warning("Could not fetch event %s from Supabase: %s", event_id, exc)

    return None


def _mark_certificate_sent(participant_id=None, registration_id=None):
    """Persist successful certificate delivery for the individual recipient."""
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Missing Supabase credentials")
    if not participant_id and not registration_id:
        raise RuntimeError("Missing participant_id or registration_id")

    from supabase import create_client

    client = create_client(SUPABASE_URL, SUPABASE_KEY)
    if participant_id:
        response = (
            client.table("events_registrationparticipant")
            .update({
                "certificate_sent": True,
                "certificate_sent_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", participant_id)
            .eq("certificate_sent", False)
            .select("id, registration_id, certificate_sent, certificate_sent_at")
            .execute()
        )
        if response.data:
            return response.data[0]
        raise RuntimeError(
            f"Could not mark participant {participant_id} as certificate_sent"
        )

    if registration_id:
        response = (
            client.table("events_registration")
            .update({
                "certificate_sent": True,
                "certificate_sent_at": datetime.now(timezone.utc).isoformat(),
            })
            .eq("id", registration_id)
            .eq("certificate_sent", False)
            .select("id, certificate_sent, certificate_sent_at")
            .execute()
        )
        if response.data:
            return response.data[0]

    raise RuntimeError(
        f"Could not mark certificate sent for participant {participant_id or registration_id}"
    )


def _build_email_html(participant, event, cert_id):
    """Build the HTML email body for a certificate delivery."""
    name = participant.get("name", "Participant")
    event_title = event.get("title", "Event")
    fest_name = event.get("fest_name", "")
    verify_url = f"{CERT_VERIFY_BASE_URL}/verify/{cert_id}/"

    return f"""\
<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#f0f4f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;">
<div style="max-width:600px;margin:40px auto;background:#fff;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.12);">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#0f172a 0%,#1e3a5f 50%,#0f172a 100%);padding:40px 30px;text-align:center;">
    <div style="display:inline-block;background:rgba(250,204,21,0.15);border:1px solid rgba(250,204,21,0.3);border-radius:8px;padding:4px 14px;margin-bottom:16px;">
      <span style="color:#facc15;font-size:12px;font-weight:600;letter-spacing:1px;">ASTRA IETM 2026</span>
    </div>
    <h1 style="color:#fff;margin:0;font-size:26px;font-weight:700;">🎓 Your Certificate is Ready!</h1>
    <p style="color:rgba(255,255,255,0.8);margin:12px 0 0;font-size:15px;">Thank you for participating in {event_title}</p>
  </div>

  <!-- Body -->
  <div style="padding:36px 30px;">
    <p style="color:#1f2937;font-size:16px;margin:0 0 18px;">Hi <strong>{name}</strong>,</p>
    <p style="color:#4b5563;font-size:15px;line-height:1.7;margin:0 0 28px;">
      Congratulations! 🎉 Your <strong>Certificate of Participation</strong> for
      <strong style="color:#1e40af;">{event_title}</strong>
      {f'(part of <strong>{fest_name}</strong> fest)' if fest_name else ''}
      is attached to this email as a PNG image.
    </p>

    <!-- Certificate Preview Box -->
    <div style="background:#f8fafc;border:2px solid #e2e8f0;border-radius:12px;padding:22px;margin:0 0 28px;text-align:center;">
      <p style="color:#64748b;font-size:13px;margin:0 0 8px;letter-spacing:0.5px;">CERTIFICATE ID</p>
      <p style="color:#0f172a;font-size:20px;font-weight:700;margin:0;font-family:monospace;">{cert_id}</p>
    </div>

    <!-- Verify Button -->
    <div style="text-align:center;margin:28px 0;">
      <a href="{verify_url}" style="display:inline-block;background:linear-gradient(135deg,#1e40af,#3b82f6);color:#fff;text-decoration:none;padding:14px 32px;border-radius:10px;font-weight:600;font-size:15px;box-shadow:0 4px 14px rgba(30,64,175,0.3);">
        🔗 Verify Certificate Online
      </a>
    </div>

    <p style="color:#6b7280;font-size:13px;margin:28px 0 0;line-height:1.6;">
      <strong>How to use:</strong><br>
      • Save the attached certificate image to your device<br>
      • Share the verification link with recruiters or institutions<br>
      • Add it to your LinkedIn profile or resume
    </p>
  </div>

  <!-- Footer -->
  <div style="background:#f8fafc;padding:20px 30px;text-align:center;border-top:1px solid #e2e8f0;">
    <p style="color:#9ca3af;font-size:12px;margin:0;">
      © 2026 ASTRA IETM · KMCT Institute of Emerging Technology and Management<br>
      <a href="{verify_url}" style="color:#3b82f6;text-decoration:none;">Verify this certificate</a>
    </p>
  </div>

</div>
</body>
</html>"""


class EmailQueue:
    """Persistent file-based email queue with retry support."""

    def __init__(self, queue_file):
        self.queue_file = queue_file
        self.items = []
        self._load()

    def _load(self):
        if os.path.exists(self.queue_file):
            with open(self.queue_file) as f:
                data = json.load(f)
            self.items = data.get("items", [])
            logger.info(f"📂 Loaded queue: {len(self.items)} items from {self.queue_file}")
        else:
            self.items = []

    def _save(self):
        data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "summary": self.get_summary(),
            "items": self.items,
        }
        os.makedirs(os.path.dirname(self.queue_file) or ".", exist_ok=True)
        with open(self.queue_file, "w") as f:
            json.dump(data, f, indent=2)

    def add(self, cert_id, email, name, cert_filepath, event, participant, registration_id=None, participant_id=None):
        existing = next((i for i in self.items if i["cert_id"] == cert_id), None)
        if existing:
            return

        self.items.append({
            "cert_id": cert_id,
            "email": email,
            "name": name,
            "cert_filepath": cert_filepath,
            "registration_id": registration_id,
            "participant_id": participant_id,
            "event": event,
            "participant": participant,
            "status": STATUS_PENDING,
            "attempts": 0,
            "max_attempts_reached": False,
            "last_error": None,
            "sent_at": None,
            "resend_id": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save()

    def get_pending(self):
        return [i for i in self.items if i["status"] in (STATUS_PENDING, STATUS_SENDING)]

    def get_failed(self):
        return [i for i in self.items if i["status"] == STATUS_FAILED and not i.get("max_attempts_reached")]

    def get_all_failed(self):
        return [i for i in self.items if i["status"] == STATUS_FAILED]

    def mark_sending(self, cert_id):
        item = self._find(cert_id)
        if item:
            item["status"] = STATUS_SENDING
            item["attempts"] += 1
            self._save()

    def mark_sent(self, cert_id, resend_id=None):
        item = self._find(cert_id)
        if item:
            item["status"] = STATUS_SENT
            item["sent_at"] = datetime.now(timezone.utc).isoformat()
            item["resend_id"] = resend_id
            item["last_error"] = None
            self._save()

    def mark_failed(self, cert_id, error, max_retries):
        item = self._find(cert_id)
        if item:
            item["status"] = STATUS_FAILED
            item["last_error"] = str(error)
            item["max_attempts_reached"] = item["attempts"] >= max_retries
            self._save()

    def reset_failed_for_retry(self):
        count = 0
        for item in self.items:
            if item["status"] == STATUS_FAILED:
                item["status"] = STATUS_PENDING
                item["max_attempts_reached"] = False
                count += 1
        if count:
            self._save()
        return count

    def get_summary(self):
        summary = {STATUS_PENDING: 0, STATUS_SENDING: 0, STATUS_SENT: 0, STATUS_FAILED: 0}
        for item in self.items:
            summary[item["status"]] = summary.get(item["status"], 0) + 1
        summary["total"] = len(self.items)
        return summary

    def _find(self, cert_id):
        return next((i for i in self.items if i["cert_id"] == cert_id), None)


def _send_single(item, dry_run=False):
    """Attempt to send a single certificate email via Resend."""
    email = item["email"]
    cert_id = item["cert_id"]
    cert_filepath = item["cert_filepath"]
    event = item["event"]
    participant = item["participant"]

    if not email:
        return False, None, "No email address"

    if not os.path.exists(cert_filepath):
        return False, None, f"Certificate file not found: {cert_filepath}"

    if dry_run:
        logger.info(f"  🏜️  [DRY RUN] Would send to {email} — {cert_id}")
        return True, "dry-run", None

    subject = f"🎓 Your Certificate — {event.get('title', 'Event')} · ASTRA IETM"
    html = _build_email_html(participant, event, cert_id)

    with open(cert_filepath, "rb") as f:
        cert_bytes = f.read()
    cert_b64 = base64.b64encode(cert_bytes).decode("utf-8")

    clean_title = event.get("title", "Event").replace(" ", "_").replace("/", "-")
    attachment_name = f"ASTRA_Certificate_{clean_title}_{cert_id}.png"

    payload = {
        "from": FROM_EMAIL,
        "to": [email],
        "subject": subject,
        "html": html,
        "attachments": [
            {
                "filename": attachment_name,
                "content": cert_b64,
            }
        ],
    }

    try:
        import resend
        resend.api_key = RESEND_API_KEY
        response = resend.Emails.send(payload)
        resend_id = response.get("id", "unknown")
        return True, resend_id, None
    except Exception as e:
        return False, None, str(e)


def _backoff_delay(attempt, base=1.0, max_delay=30.0):
    delay = min(base * (2 ** (attempt - 1)), max_delay)
    return delay


def process_queue(queue, max_retries=3, delay=0.5, dry_run=False):
    """Process all pending items in the queue with retry logic."""
    pending = queue.get_pending()
    if not pending:
        logger.info("✅ No pending items in queue")
        return

    total = len(pending)
    logger.info(f"\n📬 Processing {total} items (max_retries={max_retries}, dry_run={dry_run})\n")

    for idx, item in enumerate(pending, 1):
        cert_id = item["cert_id"]
        email = item["email"]
        attempt = item["attempts"] + 1
        attempt_label = f"[{idx}/{total}]"

        logger.info(f"{attempt_label} {cert_id} → {email} (attempt {attempt}/{max_retries})")

        queue.mark_sending(cert_id)
        success, resend_id, error = _send_single(item, dry_run=dry_run)

        if success:
            if dry_run:
                queue.mark_sent(cert_id, resend_id=resend_id)
                logger.info(f"  🧪 Dry run: {cert_id} not written to database")
            else:
                try:
                    _mark_certificate_sent(item.get("participant_id"), item.get("registration_id"))
                except Exception as db_error:
                    queue.mark_failed(cert_id, f"DB update failed: {db_error}", max_retries)
                    logger.error(f"  ❌ Email sent, but DB update failed: {db_error}")
                else:
                    queue.mark_sent(cert_id, resend_id=resend_id)
                    logger.info(f"  ✅ Sent and marked certificate_sent=true (id={resend_id})")
        else:
            queue.mark_failed(cert_id, error, max_retries)
            logger.warning(f"  ❌ Failed: {error}")

            if item["attempts"] < max_retries:
                backoff = _backoff_delay(item["attempts"])
                logger.info(f"  ⏳ Retrying in {backoff:.1f}s...")
                time.sleep(backoff)

                while item["attempts"] < max_retries:
                    retry_num = item["attempts"] + 1
                    logger.info(f"  🔄 Retry {retry_num}/{max_retries} for {cert_id}")

                    queue.mark_sending(cert_id)
                    success, resend_id, error = _send_single(item, dry_run=dry_run)

                    if success:
                        if dry_run:
                            queue.mark_sent(cert_id, resend_id=resend_id)
                            logger.info(f"  🧪 Dry run: {cert_id} not written to database")
                        else:
                            try:
                                _mark_certificate_sent(
                                    item.get("participant_id"),
                                    item.get("registration_id"),
                                )
                            except Exception as db_error:
                                queue.mark_failed(
                                    cert_id,
                                    f"DB update failed: {db_error}",
                                    max_retries,
                                )
                                logger.error(
                                    f"  ❌ Email sent, but DB update failed: {db_error}"
                                )
                            else:
                                queue.mark_sent(cert_id, resend_id=resend_id)
                                logger.info(
                                    f"  ✅ Sent on retry and marked certificate_sent=true "
                                    f"(id={resend_id})"
                                )
                        break
                    else:
                        queue.mark_failed(cert_id, error, max_retries)
                        logger.warning(f"  ❌ Retry failed: {error}")
                        if item["attempts"] < max_retries:
                            backoff = _backoff_delay(item["attempts"])
                            logger.info(f"  ⏳ Next retry in {backoff:.1f}s...")
                            time.sleep(backoff)

        if not dry_run and delay > 0 and idx < total:
            time.sleep(delay)

    _print_summary(queue)


def _print_summary(queue):
    summary = queue.get_summary()
    total = summary["total"]
    sent = summary[STATUS_SENT]
    failed = summary[STATUS_FAILED]
    pending = summary[STATUS_PENDING]

    logger.info("\n" + "=" * 60)
    logger.info("📊 EMAIL QUEUE SUMMARY")
    logger.info("=" * 60)
    logger.info(f"  Total:   {total}")
    logger.info(f"  ✅ Sent:    {sent}")
    logger.info(f"  ❌ Failed:  {failed}")
    logger.info(f"  ⏳ Pending: {pending}")
    logger.info("=" * 60)

    if failed > 0:
        logger.info("\n❌ Failed items:")
        for item in queue.get_all_failed():
            logger.info(
                f"  • {item['cert_id']} → {item['email']} "
                f"(attempts: {item['attempts']}, error: {item['last_error']})"
            )
        logger.info("\n💡 To retry failed items, run with --retry-failed")

    if sent == total:
        logger.info("\n🎉 All certificates sent successfully!")


def init_queue_from_manifest(manifest_path, queue_file):
    """Load a manifest and create/update the email queue."""
    if not os.path.exists(manifest_path):
        logger.error(f"Manifest not found: {manifest_path}")
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    event = manifest.get("event", {})
    certificates = manifest.get("certificates", [])

    if not certificates:
        logger.warning("No certificates in manifest — nothing to queue")
        return None

    queue = EmailQueue(queue_file)

    for cert in certificates:
        cert_id = cert["cert_id"]
        cert_filepath = os.path.join(OUTPUT_DIR, f"{cert_id}.png")
        participant = {
            "name": cert.get("name", ""),
            "email": cert.get("email", ""),
            "college": cert.get("college", ""),
        }

        cert_event = dict(event)
        event_id = cert.get("event_id")
        db_event = _fetch_event_title_from_db(event_id)
        if db_event:
            cert_event["title"] = db_event["title"]
            cert_event["event_date"] = db_event.get("event_date", "")
        elif cert.get("event"):
            cert_event["title"] = cert["event"]

        if cert.get("date"):
            cert_event["date_str"] = cert["date"]

        if cert.get("certificate_sent", False):
            logger.info(
                "⏭️ Skipping %s: certificate already marked sent in DB",
                cert_id,
            )
            continue

        queue.add(
            cert_id=cert_id,
            email=cert.get("email", ""),
            name=cert.get("name", ""),
            cert_filepath=cert_filepath,
            event=cert_event,
            participant=participant,
            registration_id=cert.get("registration_id"),
            participant_id=cert.get("participant_id"),
        )

    logger.info(f"📋 Queue initialized: {len(certificates)} certificates")
    summary = queue.get_summary()
    logger.info(
        f"   {summary[STATUS_PENDING]} pending, "
        f"{summary[STATUS_SENT]} already sent, "
        f"{summary[STATUS_FAILED]} failed"
    )
    return queue


def main():
    parser = argparse.ArgumentParser(
        description="Send certificate emails with queue and retry support"
    )
    parser.add_argument("--event-id", help="Event title (or its saved identifier) — looks for manifest in data/")
    parser.add_argument("--manifest", help="Path to manifest JSON")
    parser.add_argument("--all-events", action="store_true", help="Send emails for ALL events")
    parser.add_argument("--dry-run", action="store_true", help="Log without sending emails")
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume processing from existing queue (skip already SENT items)"
    )
    parser.add_argument(
        "--retry-failed", action="store_true",
        help="Reset FAILED items to PENDING and retry them"
    )
    parser.add_argument(
        "--max-retries", type=int, default=3,
        help="Max send attempts per email (default: 3)"
    )
    parser.add_argument(
        "--delay", type=float, default=0.5,
        help="Delay between emails in seconds (default: 0.5)"
    )
    parser.add_argument("--status", action="store_true", help="Show queue status and exit")
    args = parser.parse_args()

    if args.event_id and not args.all_events:
        event_id = safe_id(args.event_id)
        manifest_path = os.path.join(DATA_DIR, f"event_{event_id}_manifest.json")
        queue_file = os.path.join(DATA_DIR, f"event_{event_id}_queue.json")
    elif args.manifest:
        manifest_path = args.manifest
        queue_file = args.manifest.replace("_manifest.json", "_queue.json")
    else:
        manifest_path = os.path.join(DATA_DIR, "all_manifest.json")
        queue_file = os.path.join(DATA_DIR, "all_queue.json")

    if args.status:
        if os.path.exists(queue_file):
            queue = EmailQueue(queue_file)
            _print_summary(queue)
        else:
            logger.info("No queue file found. Run without --status to initialize.")
        return

    if not args.dry_run and not RESEND_API_KEY:
        logger.error(
            "❌ RESEND_API_KEY not set!\n"
            "   Set it via: export RESEND_API_KEY='re_xxxxx'\n"
            "   Or use --dry-run to test without sending."
        )
        sys.exit(1)

    if args.resume and os.path.exists(queue_file):
        logger.info("🔄 Resuming from existing queue...")
        queue = EmailQueue(queue_file)
    elif args.retry_failed and os.path.exists(queue_file):
        logger.info("🔄 Retrying failed items...")
        queue = EmailQueue(queue_file)
        reset_count = queue.reset_failed_for_retry()
        logger.info(f"   Reset {reset_count} failed items back to PENDING")
    else:
        queue = init_queue_from_manifest(manifest_path, queue_file)

    if queue is None:
        return

    process_queue(
        queue,
        max_retries=args.max_retries,
        delay=args.delay,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
