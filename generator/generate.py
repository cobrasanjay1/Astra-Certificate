"""
Astra Certificate Generator — Pillow-based certificate image creation.

Takes the certificate template PNG and overlays participant-specific data:
  - Participant name (large, centered)
  - Body paragraph (college, event, fest, date)

Usage:
    python generate.py --event-id 1
    python generate.py --data-file ../data/attendees.json
    python generate.py --test  # Generate a single test certificate
"""

import io
import os
import sys
import json
import argparse
import textwrap
import logging
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

# Add parent to path for config import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    TEMPLATE_FILE, OUTPUT_DIR, DATA_DIR, FONT_DIR, SITE_DIR,
    FONTS, FALLBACK_FONTS, TEXT_REGIONS, BODY_TEMPLATE,
    TEMPLATE_WIDTH, TEMPLATE_HEIGHT, CERT_ID_PREFIX,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("cert-gen")


# ── Font Loading ──────────────────────────────────────────────────────────

def _load_font(font_key, size_override=None):
    """Load a font by config key, with fallback chain."""
    cfg = FONTS.get(font_key, {})
    path = cfg.get("path", "")
    size = size_override or cfg.get("size", 24)

    if path and os.path.exists(path):
        try:
            return ImageFont.truetype(path, size)
        except (OSError, IOError):
            pass

    # Fallback
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
    """Load a specific font variant: 'regular', 'bold', 'bold_italic'."""
    variants = {
        "regular": os.path.join(FONT_DIR, "Montserrat-SemiBold.ttf"),
        "bold": os.path.join(FONT_DIR, "Montserrat-Bold.ttf"),
        "bold_italic": os.path.join(FONT_DIR, "Montserrat-BoldItalic.ttf"),
    }
    path = variants.get(variant, variants["regular"])
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        return _load_font("body", size)


# ── Text Rendering Helpers ────────────────────────────────────────────────

def _measure_text(draw, text, font):
    """Measure text width and height."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_name(draw, name, region):
    """Draw the 'AWARDED TO' label and participant name, auto-scaling if too wide."""
    font = _load_font(region["font_key"])
    max_w = region["max_width"]
    color = region["color"]

    # Draw "AWARDED TO" label
    label_pos = region.get("position", (90, 470))
    label_color = region.get("label_color", (60, 60, 60))
    label_font = _load_font_variant("regular", 18)
    draw.text(label_pos, "AWARDED TO", fill=label_color, font=label_font)

    # Draw participant name below the label
    name_pos = region.get("name_position", (90, 520))
    x, y = name_pos

    # Auto-scale down if name is too wide
    font_size = FONTS[region["font_key"]]["size"]
    while font_size > 30:
        font = _load_font(region["font_key"], font_size)
        w, h = _measure_text(draw, name, font)
        if w <= max_w:
            break
        font_size -= 2

    draw.text((x, y), name, fill=color, font=font)
    return h


def _parse_body_segments(template_text):
    """
    Parse the body template into segments.
    Text between ** markers is bold+italic.
    Returns list of (text, is_bold_italic) tuples.
    """
    segments = []
    parts = template_text.split("**")
    for i, part in enumerate(parts):
        if part:
            segments.append((part, i % 2 == 1))
    return segments


def _draw_body_paragraph(draw, body_text, region):
    """
    Draw the body paragraph with mixed bold/italic formatting.
    Handles word-wrapping across the max_width.
    """
    font_regular = _load_font_variant("regular", FONTS["body"]["size"])
    font_emphasis = _load_font_variant("bold_italic", FONTS["body_italic"]["size"])

    segments = _parse_body_segments(body_text)
    max_w = region["max_width"]
    x_start, y_start = region["position"]
    line_spacing = region.get("line_spacing", 38)
    color = region["color"]

    # Flatten segments into individual words with their styles
    words = []
    for text, is_emphasis in segments:
        for word in text.split():
            if word:
                words.append((word, is_emphasis))

    # Word-wrap and draw
    x = x_start
    y = y_start

    for word_text, is_emphasis in words:
        font = font_emphasis if is_emphasis else font_regular
        word_w, word_h = _measure_text(draw, word_text + " ", font)

        if x + word_w > x_start + max_w and x > x_start:
            # Wrap to next line
            x = x_start
            y += line_spacing

        draw.text((x, y), word_text, fill=color, font=font)
        # Add space after word
        space_w, _ = _measure_text(draw, " ", font)
        x += word_w + space_w - _measure_text(draw, " ", font)[0] + 2

    return y - y_start + line_spacing


# ── Certificate Generation ────────────────────────────────────────────────

def generate_certificate(participant, event_info, cert_id):
    """
    Generate a single certificate PNG.

    Args:
        participant: dict with keys: name, email, college
        event_info: dict with keys: title, fest_name, date_str
        cert_id: str like "CERT-2026-0042"

    Returns:
        PNG bytes
    """
    # Load template
    if not os.path.exists(TEMPLATE_FILE):
        raise FileNotFoundError(f"Template not found: {TEMPLATE_FILE}")

    img = Image.open(TEMPLATE_FILE).convert("RGBA")

    # Create a drawing overlay (so we can composite with transparency)
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    # ── Cover dynamic text regions with white ──────────────────────────
    name_region = TEXT_REGIONS["name"]
    body_region = TEXT_REGIONS["body"]

    # White-out the name area
    x1, y1, x2, y2 = name_region["cover"]
    draw.rectangle([x1, y1, x2, y2], fill=(255, 255, 255, 255))

    # White-out the body paragraph area
    x1, y1, x2, y2 = body_region["cover"]
    draw.rectangle([x1, y1, x2, y2], fill=(255, 255, 255, 255))

    # Composite the white overlay onto the template
    img = Image.alpha_composite(img, overlay)

    # Now draw the new text
    draw = ImageDraw.Draw(img)

    # ── Draw participant name ──────────────────────────────────────────
    name = participant.get("name", "Unknown Participant")
    _draw_name(draw, name, name_region)

    # ── Draw body paragraph ────────────────────────────────────────────
    college = participant.get("college", "Unknown College")
    event_name = event_info.get("title", "Event")
    fest_name = event_info.get("fest_name", "ZERO DAY")
    date_str = event_info.get("date_str", "2026")

    body_text = BODY_TEMPLATE.format(
        college=college.upper(),
        event=event_name.upper(),
        fest=fest_name.upper(),
        date=date_str.upper(),
    )

    _draw_body_paragraph(draw, body_text, body_region)

    # ── Convert to RGB and export ──────────────────────────────────────
    img_rgb = img.convert("RGB")
    buffer = io.BytesIO()
    img_rgb.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer.getvalue()


def generate_certificate_to_file(participant, event_info, cert_id, output_dir=None):
    """Generate and save a certificate to disk."""
    out_dir = output_dir or OUTPUT_DIR
    os.makedirs(out_dir, exist_ok=True)

    png_bytes = generate_certificate(participant, event_info, cert_id)

    filename = f"{cert_id}.png"
    filepath = os.path.join(out_dir, filename)
    with open(filepath, "wb") as f:
        f.write(png_bytes)

    logger.info(f"✅ Generated: {filepath} ({len(png_bytes)} bytes)")
    return filepath


def make_cert_id(event_year, index):
    """Generate a certificate ID like CERT-2026-0042."""
    return f"{CERT_ID_PREFIX}-{event_year}-{str(index).zfill(4)}"


# ── Batch Generation ──────────────────────────────────────────────────────

def generate_batch(data_file=None, event_id=None):
    """
    Generate certificates for all attendees.

    Reads from either:
    - A JSON data file (from fetch_attendees.py)
    - Direct event_id (looks for data/{event_id}_attendees.json)

    Returns list of (cert_id, filepath, participant) tuples.
    """
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
        logger.warning("No attendees found — nothing to generate")
        return []

    # Determine event year for cert IDs
    event_date = event_info.get("event_date", "")
    try:
        year = datetime.fromisoformat(event_date.replace("Z", "+00:00")).year
    except (ValueError, AttributeError):
        year = datetime.now().year

    results = []
    # Also build a manifest for the verification site
    manifest = {
        "event": event_info,
        "generated_at": datetime.now().isoformat(),
        "certificates": [],
    }

    for i, attendee in enumerate(attendees, start=1):
        cert_id = make_cert_id(year, i)
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
            "event": event_info.get("title", ""),
            "date": event_info.get("date_str", ""),
        })

    # Save manifest for email sender and site builder
    manifest_path = os.path.join(DATA_DIR, f"event_{event_info.get('id', 'unknown')}_manifest.json")
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    logger.info(f"📋 Manifest saved: {manifest_path}")

    logger.info(f"\n🎉 Generated {len(results)} certificates!")
    return results


def generate_test():
    """Generate a single test certificate with sample data."""
    participant = {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "college": "KMCT Institute of Emerging Technology and Management",
    }
    event_info = {
        "title": "Cypher Decode",
        "fest_name": "ZERO DAY",
        "date_str": "6 OCTOBER 2026",
    }
    cert_id = make_cert_id(2026, 9999)
    filepath = generate_certificate_to_file(participant, event_info, cert_id)
    logger.info(f"🧪 Test certificate: {filepath}")
    return filepath


# ── CLI Entry Point ───────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Astra Certificate Generator")
    parser.add_argument("--event-id", type=int, help="Event ID from the database")
    parser.add_argument("--data-file", help="Path to attendees JSON file")
    parser.add_argument("--test", action="store_true", help="Generate a test certificate")
    args = parser.parse_args()

    if args.test:
        generate_test()
    elif args.event_id or args.data_file:
        generate_batch(data_file=args.data_file, event_id=args.event_id)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
