# 🎓 Astra Certificate Distribution System

Automated certificate generation & email distribution for **ASTRA IETM** events.

## How It Works

```
Event Ends → Admin Triggers GitHub Action → Certificates Generated → Emails Sent
                                              ↓
                                    Verification Site Deployed
                                    (cert.astraietm.in)
```

1. **Event ends** → Admin marks participants as `ATTENDED` in the database
2. **Admin triggers** the GitHub Action (`workflow_dispatch`) with the event ID
3. **Action fetches** attendees from the API, generates personalized certificates
4. **Verification site** deployed to `cert.astraietm.in` via GitHub Pages
5. **Emails sent** via Resend with certificate PNG attached + verify link

## Quick Start (Local Testing)

```bash
# Install dependencies
pip install -r generator/requirements.txt

# Fetch attendees for ALL events (or use --sample for test data)
python3 generator/fetch_attendees.py --sample

# Generate certificates for ALL events
python3 generator/generate.py

# Build verification site for ALL events
python3 generator/build_site.py

# Dry-run emails for ALL events (doesn't send emails)
python3 generator/send_emails.py --dry-run

# Check queue status across all events
python3 generator/send_emails.py --status
```

> **Note:** You can still target a single event by passing `--event-id <id>` to any command above.

## Email Queue & Retry

The email sender uses a **persistent file-based queue** that survives crashes:

```bash
# First run — sends emails for all events
python3 generator/send_emails.py

# Resume after crash/timeout
python3 generator/send_emails.py --resume

# Retry only failed emails
python3 generator/send_emails.py --retry-failed

# Custom max retries + delay
python3 generator/send_emails.py --max-retries 5 --delay 1.0
```

Queue state is saved to `data/all_queue.json` (or `data/event_{id}_queue.json` for single event runs) after every operation.

## GitHub Action

Trigger from the **Actions** tab → **Send Certificates** → **Run workflow**.

It is a two-step flow so you choose the events *before* anything is sent:

1. **Run with `mode = list`** — reads `events_event` from Supabase and prints a table
   (ID, title, date, attended / sent / pending) in the run summary. Nothing is generated or emailed.
2. **Run with `mode = send`** and put the IDs you want in `events` (e.g. `3,7`, or `all`).
   The selection is validated first; an empty, malformed or unknown selection stops the run
   before any certificate is generated.

| Input          | Description                                                                 |
| -------------- | --------------------------------------------------------------------------- |
| `mode`         | `list` = show events only, `send` = process the selected events             |
| `events`       | `send` only. Event IDs, comma-separated (`3,7`), or `all`. Blank is rejected |
| `dry_run`      | Generate without sending emails or deploying the site (default: on)         |
| `max_retries`  | Max send attempts per email (default: 3)                                    |

Re-running an event is safe: `certificate_sent` in Supabase is the source of truth, so people who
already received their certificate are skipped. Runs are serialized so two sends can never overlap.

### Required Secrets

| Secret | Description |
|--------|-------------|
| `SUPABASE_URL` | Your Supabase Project URL (e.g., `https://xyz.supabase.co`) |
| `SUPABASE_KEY` | Supabase Service Role Key or API Key |
| `DATABASE_URL` | *(Optional)* Direct PostgreSQL connection string |
| `RESEND_API_KEY` | Resend API key for sending emails |

## DNS Setup

Add a CNAME record for `cert.astraietm.in`:

```
Type:  CNAME
Name:  cert
Value: <your-github-username>.github.io
TTL:   Auto
```

## Project Structure

```
Astra-Certificate/
├── .github/workflows/
│   └── send-certificates.yml    # GitHub Actions workflow
├── generator/
│   ├── config.py                # Configuration (positions, fonts, API)
│   ├── generate.py              # Certificate image generator (Pillow)
│   ├── fetch_attendees.py       # Fetch attendees from API
│   ├── list_events.py           # List events from DB + validate event selection
│   ├── send_emails.py           # Email queue with retry logic
│   ├── build_site.py            # Verification site builder
│   ├── requirements.txt         # Python dependencies
│   └── fonts/                   # Downloaded Google Fonts
├── templates/
│   └── 1.png
├── site/                        # Generated verification site
│   └── index.html               # Landing page
├── output/                      # Generated certificates
└── data/                        # Fetched data & queue state
```

## Certificate Template

The generator overlays dynamic text onto the template image at these regions:
- **Participant Name** — below "AWARDED TO" label
- **Body Paragraph** — college, event, fest, date

To use a blank template (recommended), remove the sample text and save as
`templates/astra_certificate_template.png`.

## API Endpoint

The backend exposes a staff-only endpoint:

```
GET /api/certificates/attendees/?event_id=<id>
Authorization: Bearer <staff-jwt-token>
```

Returns:
```json
{
  "event": { "id": 1, "title": "Cypher Decode", "date_str": "6 OCTOBER 2026" },
  "attendees": [
    { "full_name": "Jane Doe", "email": "jane@example.com", "college": "..." }
  ],
  "count": 42
}
```
