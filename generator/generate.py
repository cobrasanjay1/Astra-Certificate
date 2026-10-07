"""
Astra Certificate Generator — Pillow-based certificate image creation.

Takes the certificate template PNG (templates/1.png) and writes three things
onto it:
  - Participant name  -> first line
  - College name      -> second line
  - Event name        -> the blank between the quotes in
                         "FOR PARTICIPATING IN THE EVENT ‘ ’ ..."

Usage:
    python generate.py --event-id "Cypher Decode"
    python generate.py --data-file ../data/attendees.json
    python generate.py --test  # Generate a single test certificate
"""

import io
import os
import sys
import json
import argparse
import logging
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    TEMPLATE_FILE, OUTPUT_DIR, DATA_DIR, FONT_DIR,
    FONTS, FALLBACK_FONTS, TEXT_REGIONS,
    TEMPLATE_WIDTH, TEMPLATE_HEIGHT, CERT_ID_PREFIX, safe_id, DEFAULT_FEST_NAME,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("cert-gen")


def _load_font(font_key, size_override=None):
    cfg = FONTS.get(font_key, {})
    path = cfg.get("path", "")
    size = size_override or cfg.get("size", 24)
    if path and os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            pass
    fallback_key = "sans" if "body" in font_key or "label" in font_key else "serif"
    if "bold" in font_key:
        fallback_key += "_bold"
    for fb_path in FALLBACK_FONTS.get(fallback_key, []):
        try:
            return ImageFont.truetype(fb_path, size)
        except (OSError, IOError):
            continue
    logger.warning(f"No font found for '{font_key}', using default")
    return ImageFont.load_default()


def _load_font_variant(variant, size):
    variants = {
        "regular": os.path.join(FONT_DIR, "CanvaSans-Medium.otf"),
        "bold": os.path.join(FONT_DIR, "CanvaSans-Bold.otf"),
        "bold_italic": os.path.join(FONT_DIR, "CanvaSans-BoldItalic.otf"),
    }
    path = variants.get(variant, variants["regular"])
    if os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            pass
    return _load_font("body", size)


def _measure_tracked(draw, text, font, tracking=0.0):
    if not text:
        return 0.0
    if not tracking:
        return draw.textlength(text, font=font)
    return sum(draw.textlength(ch, font=font) for ch in text) + tracking * (len(text) - 1)


def _fit_font(draw, text, font_loader, size, min_size, max_width, tracking=0.0):
    while True:
        font = font_loader(size)
        w = _measure_tracked(draw, text, font, tracking)
        if w <= max_width or size <= min_size:
            return font, w
        size -= 1


def _draw_tracked(draw, x, baseline_y, text, font, color, tracking=0.0):
    if not tracking:
        draw.text((x, baseline_y), text, fill=color, font=font, anchor="ls")
        return
    for ch in text:
        draw.text((round(x), baseline_y), ch, fill=color, font=font, anchor="ls")
        x += draw.textlength(ch, font=font) + tracking


def _draw_line_text(draw, text, region):
    text = (text or "").strip()
    if region.get("uppercase"):
        text = text.upper()
    if not text:
        return
    x, baseline_y = region["baseline"]
    font, _ = _fit_font(
        draw, text,
        lambda sz: _load_font(region["font_key"], sz),
        region["font_size"], region.get("min_font_size", 24), region["max_width"],
    )
    _draw_tracked(draw, x, baseline_y, text, font, region["color"])


def _draw_event(draw, event_name, region):
    text = (event_name or "").strip()
    if region.get("uppercase"):
        text = text.upper()
    if not text:
        return
    gap_l, gap_r = region["gap"]
    pad = region.get("padding", 0)
    avail = (gap_r - gap_l) - 2 * pad
    base_size = region["font_size"]
    min_size = region.get("min_font_size", 12)
    base_tracking = region.get("tracking", 0.0)
    size = base_size
    while True:
        font = _load_font_variant("bold_italic", size)
        tracking = base_tracking * size / base_size
        w = _measure_tracked(draw, text, font, tracking)
        if w <= avail or size <= min_size:
            break
        size -= 1
    if size < base_size * 0.65:
        logger.warning(
            f"Event name '{text}' is long for the template gap; rendered at {size}px."
        )
    x = gap_l + ((gap_r - gap_l) - w) / 2
    _draw_tracked(draw, x, region["baseline_y"], text, font, region["color"], tracking)


def generate_certificate(participant, event_info, cert_id):
    """Generate one certificate PNG without covering the printed template artwork."""
    if not os.path.exists(TEMPLATE_FILE):
        raise FileNotFoundError(f"Template not found: {TEMPLATE_FILE}")
    try:
        img = Image.open(TEMPLATE_FILE).convert("RGBA")
    except Exception as exc:
        raise RuntimeError(
            f"Unable to open certificate template '{TEMPLATE_FILE}'. Use a valid PNG/JPEG/WebP image."
        ) from exc

    sx = img.width / TEMPLATE_WIDTH
    sy = img.height / TEMPLATE_HEIGHT
    sf = (sx + sy) / 2

    def scale(region):
        r = dict(region)
        for key in ("baseline", "gap"):
            if key in r:
                r[key] = tuple(round(v * (sx if i == 0 else sy)) for i, v in enumerate(r[key]))
        if "baseline_y" in r:
            r["baseline_y"] = round(r["baseline_y"] * sy)
        for key in ("font_size", "min_font_size", "max_width", "padding", "tracking"):
            if key in r:
                r[key] = r[key] * sf
        return r

    draw = ImageDraw.Draw(img)
    _draw_line_text(draw, participant.get("name") or "Unknown Participant", scale(TEXT_REGIONS["name"]))
    _draw_line_text(draw, participant.get("college"), scale(TEXT_REGIONS["college"]))
    _draw_event(draw, event_info.get("title") or "", scale(TEXT_REGIONS["event"]))

    img_rgb = img.convert("RGB")
    buffer = io.BytesIO()
    img_rgb.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer.getvalue()


def generate_certificate_to_file(participant, event_info, cert_id, output_dir=None):
    out_dir = output_dir or OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)
    png_bytes = generate_certificate(participant, event_info, cert_id)
    filepath = os.path.join(out_dir, f"{cert_id}.png")
    with open(filepath, "wb") as f:
        f.write(png_bytes)
    logger.info(f"✅ Generated: {filepath} ({len(png_bytes)} bytes)")
    return filepath


def make_cert_id(event_year, index):
    return f"{CERT_ID_PREFIX}-{event_year}-{str(index).zfill(4)}"


def generate_batch(data_file=None, event_id=None, start_index=1):
    if data_file and os.path.exists(data_file):
        with open(data_file) as f:
            data = json.load(f)
    elif event_id:
        expected_file = os.path.join(DATA_DIR, f"event_{event_id}_attendees.json")
        if not os.path.exists(expected_file):
            logger.error(f"Data file not found: {expected_file}")
            logger.info("Run fetch_attendees.py first, or provide --data-file")
            sys.exit(1)
        with open(expected_file) as f:
            data = json.load(f)
    else:
        logger.error("Provide either --data-file or --event-id")
        sys.exit(1)

    event_info = data.get("event", {})
    attendees = data.get("attendees", [])
    if not attendees:
        logger.warning(f"No attendees found for event #{event_info.get('id', 'unknown')} — nothing to generate")
        return []

    event_date = event_info.get("event_date", "")
    try:
        year = datetime.fromisoformat(event_date.replace("Z", "+00:00")).year
    except (ValueError, AttributeError):
        year = datetime.now().year

    results = []
    manifest = {"event": event_info, "generated_at": datetime.now().isoformat(), "certificates": []}
    for idx, attendee in enumerate(attendees, start=start_index):
        cert_id = make_cert_id(year, idx)
        participant = {
            "name": attendee.get("full_name", attendee.get("name", "")),
            "email": attendee.get("email", ""),
            "college": attendee.get("college", ""),
        }
        filepath = generate_certificate_to_file(participant, event_info, cert_id)
        results.append((cert_id, filepath, participant))
        manifest["certificates"].append({
            "cert_id": cert_id,
            "name": participant["name"],
            "email": participant["email"],
            "college": participant["college"],
            "participant_id": attendee.get("participant_id"),
            "registration_id": attendee.get("registration_id"),
            "certificate_sent": bool(attendee.get("certificate_sent", False)),
            "event_id": event_info.get("id", ""),
            "event": event_info.get("title", ""),
            "date": event_info.get("date_str", ""),
        })

    manifest_path = os.path.join(DATA_DIR, f"event_{event_info.get('id', 'unknown')}_manifest.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"📋 Manifest saved: {manifest_path}")
    logger.info(f"🎉 Generated {len(results)} certificates for event '{event_info.get('title')}'!")
    return results


def generate_all_events():
    import glob
    attendees_files = sorted(glob.glob(os.path.join(DATA_DIR, "event_*_attendees.json")))
    if not attendees_files:
        logger.error(f"No event attendee files found in {DATA_DIR}")
        logger.info("Run fetch_attendees.py first to fetch all events")
        sys.exit(1)

    logger.info(f"🚀 Found {len(attendees_files)} event data files. Generating certificates for ALL events...")
    all_results = []
    combined_certificates = []
    current_counter = 1
    for filepath in attendees_files:
        with open(filepath) as f:
            data = json.load(f)
        event_info = data.get("event", {})
        attendees = data.get("attendees", [])
        if not attendees:
            continue
        results = generate_batch(data_file=filepath, start_index=current_counter)
        all_results.extend(results)
        current_counter += len(results)
        manifest_path = os.path.join(DATA_DIR, f"event_{event_info.get('id', 'unknown')}_manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                combined_certificates.extend(json.load(f).get("certificates", []))

    all_manifest = {
        "event": {"id": "all", "title": "All Events"},
        "generated_at": datetime.now().isoformat(),
        "certificates": combined_certificates,
    }
    all_manifest_path = os.path.join(DATA_DIR, "all_manifest.json")
    with open(all_manifest_path, "w") as f:
        json.dump(all_manifest, f, indent=2)
    logger.info(f"\n✨ COMPLETE: Generated {len(all_results)} total certificates across all events!")
    logger.info(f"📋 Unified manifest saved: {all_manifest_path}")
    return all_results


def generate_test():
    participant = {"name": "Test", "email": "test@example.com", "college": "test"}
    event_info = {"title": "CYPHER DECODE", "fest_name": DEFAULT_FEST_NAME, "date_str": "6 OCTOBER 2026"}
    cert_id = make_cert_id(2026, 9999)
    filepath = generate_certificate_to_file(participant, event_info, cert_id)
    logger.info(f"🧪 Test certificate: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Astra Certificate Generator")
    parser.add_argument("--event-id", help="Event title (or its saved identifier) from fetch_attendees.py")
    parser.add_argument("--data-file", help="Path to attendees JSON file")
    parser.add_argument("--all-events", action="store_true", help="Generate certificates for ALL events")
    parser.add_argument("--test", action="store_true", help="Generate a test certificate")
    args = parser.parse_args()
    if args.test:
        generate_test()
    elif args.event_id or args.data_file:
        event_id = safe_id(args.event_id) if args.event_id else None
        generate_batch(data_file=args.data_file, event_id=event_id)
    else:
        generate_all_events()


if __name__ == "__main__":
    main()
