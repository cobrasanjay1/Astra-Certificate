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



# ── Text Rendering Helpers ────────────────────────────────────────────────

def _measure_text(draw, text, font):
    """Measure text width and height."""
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_name(draw, name, region):
    """Draw participant name, auto-scaling if too wide."""
    max_w = region["max_width"]
    color = region["color"]
    x, y = region["position"]

    font_size = region.get("font_size", FONTS[region["font_key"]]["size"])
    font = _load_font(region["font_key"], font_size)

    # Auto-scale down if name is too wide
    while font_size > 24:
        font = _load_font(region["font_key"], font_size)
        w, h = _measure_text(draw, name, font)
        if w <= max_w:
            break
        font_size -= 2

    draw.text((x, y), name, fill=color, font=font)
    return font


def _tokenize_body(body_str):
    parts = body_str.split("**")
    raw_tokens = []
    for idx, part in enumerate(parts):
        is_bi = (idx % 2 == 1)
        words = part.split(" ")
        for w in words:
            if w:
                raw_tokens.append((w, is_bi))

    merged = []
    for word, is_bi in raw_tokens:
        if merged and word in [",", ".", "',", "'"]:
            prev_word, prev_bi = merged.pop()
            merged.append((prev_word + word, prev_bi))
        elif merged and word.startswith((",", ".", "'")):
            punc = word[0]
            rest = word[1:]
            prev_word, prev_bi = merged.pop()
            merged.append((prev_word + punc, prev_bi))
            if rest:
                merged.append((rest, is_bi))
        else:
            merged.append((word, is_bi))
    return merged


def _measure_word_with_tracking(draw, word, font, tracking=11.5):
    """Measure total pixel width of a word rendered with letter tracking."""
    w = 0
    for char in word:
        bbox = draw.textbbox((0, 0), char, font=font)
        cw = bbox[2] - bbox[0]
        w += cw + tracking
    return w - tracking if word else 0


def _draw_body(draw, participant, event_info, region):
    """Render the body paragraph with full justification to match the reference template.

    Each full line is stretched to max_width by distributing extra space evenly
    across word gaps. The last (partial) line is left-aligned.
    """
    college = (participant.get("college") or "KMCT INSTITUTE OF EMERGING TECHNOLOGY AND MANAGEMENT").strip().upper()
    event = (event_info.get("title") or "CYPHER DECODE").strip().upper()
    fest = (event_info.get("fest_name") or "ZERO DAY").strip().upper()
    date = (participant.get("date") or event_info.get("date_str") or "6 OCTOBER 2026").strip().upper()

    body_str = BODY_TEMPLATE.format(
        college=college,
        event=event,
        fest=fest,
        date=date,
    )

    tokens = _tokenize_body(body_str)

    font_size = region.get("font_size", 32)
    font_reg = _load_font_variant("regular", font_size)
    font_bold_italic = _load_font_variant("bold_italic", font_size)

    x_start, y_start = region["position"]
    max_w = region.get("max_width", 1430)
    line_height = region.get("line_height", 51)
    tracking = region.get("tracking", 13.0)
    word_space = region.get("word_space", 26.0)
    color = region.get("color", (30, 30, 30))

    def word_px_width(word, font):
        """Pixel width of a word with per-character tracking applied."""
        return _measure_word_with_tracking(draw, word, font, tracking)

    # ── Phase 1: lay out tokens into lines ───────────────────────────────
    lines = []          # list of lists of (word, is_bi)
    current_line = []
    current_w = 0.0

    for word, is_bi in tokens:
        font = font_bold_italic if is_bi else font_reg
        w = word_px_width(word, font)

        if current_line:
            # Cost to append: word_space + word_width
            needed = current_w + word_space + w
        else:
            needed = w

        if needed > max_w and current_line:
            lines.append(current_line)
            current_line = [(word, is_bi)]
            current_w = w
        else:
            current_line.append((word, is_bi))
            current_w = needed

    if current_line:
        lines.append(current_line)

    # ── Phase 2: render each line ─────────────────────────────────────────
    for line_idx, line_tokens in enumerate(lines):
        is_last = (line_idx == len(lines) - 1)
        y = y_start + line_idx * line_height

        if len(line_tokens) <= 1 or is_last:
            # Left-align (last line or single word)
            x = x_start
            for word, is_bi in line_tokens:
                font = font_bold_italic if is_bi else font_reg
                for char in word:
                    draw.text((x, y), char, fill=color, font=font)
                    bbox = draw.textbbox((0, 0), char, font=font)
                    x += (bbox[2] - bbox[0]) + tracking
                x += word_space
        else:
            # Full justify: distribute remaining space across word gaps
            # Measure total word widths on this line
            total_word_w = sum(word_px_width(w, font_bold_italic if bi else font_reg)
                               for w, bi in line_tokens)
            n_gaps = len(line_tokens) - 1
            justify_space = (max_w - total_word_w) / n_gaps if n_gaps > 0 else word_space

            x = float(x_start)
            for wi, (word, is_bi) in enumerate(line_tokens):
                font = font_bold_italic if is_bi else font_reg
                for char in word:
                    draw.text((int(x), y), char, fill=color, font=font)
                    bbox = draw.textbbox((0, 0), char, font=font)
                    x += (bbox[2] - bbox[0]) + tracking
                if wi < n_gaps:
                    x += justify_space




# ── Certificate Generation ────────────────────────────────────────────────

def generate_certificate(participant, event_info, cert_id):
    """
    Generate a single certificate PNG by updating Participant Name and the entire Body paragraph.

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
    draw_overlay = ImageDraw.Draw(overlay)

    # ── Cover dynamic text regions with white ──────────────────────────
    name_region = TEXT_REGIONS["name"]
    body_region = TEXT_REGIONS["body"]

    # White-out the name area
    x1, y1, x2, y2 = name_region["cover"]
    draw_overlay.rectangle([x1, y1, x2, y2], fill=(255, 255, 255, 255))

    # White-out the entire body paragraph area
    x1, y1, x2, y2 = body_region["cover"]
    draw_overlay.rectangle([x1, y1, x2, y2], fill=(255, 255, 255, 255))

    # Composite the white overlay onto the template
    img = Image.alpha_composite(img, overlay)

    # Now draw the new text
    draw = ImageDraw.Draw(img)

    # ── Draw participant name ──────────────────────────────────────────
    name = participant.get("name", "Unknown Participant")
    _draw_name(draw, name, name_region)

    # ── Draw full body paragraph ───────────────────────────────────────
    _draw_body(draw, participant, event_info, body_region)

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

def generate_batch(data_file=None, event_id=None, start_index=1):
    """
    Generate certificates for attendees of a specific event or data file.

    Reads from either:
    - A JSON data file (from fetch_attendees.py)
    - Direct event_id (looks for data/event_{event_id}_attendees.json)

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
        logger.warning(f"No attendees found for event #{event_info.get('id', 'unknown')} — nothing to generate")
        return []

    # Determine event year for cert IDs
    event_date = event_info.get("event_date", "")
    try:
        year = datetime.fromisoformat(event_date.replace("Z", "+00:00")).year
    except (ValueError, AttributeError):
        year = datetime.now().year

    results = []
    manifest = {
        "event": event_info,
        "generated_at": datetime.now().isoformat(),
        "certificates": [],
    }

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
    """
    Find all event attendee files in DATA_DIR and generate certificates for ALL events.
    Also creates a unified all_manifest.json.
    """
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
                m = json.load(f)
                combined_certificates.extend(m.get("certificates", []))

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
    """Generate a single test certificate with sample data matching the reference."""
    participant = {
        "name": "Midlaj Jaleel",
        "email": "midlaj@example.com",
        "college": "KMCT INSTITUTE OF EMERGING TECHNOLOGY AND MANAGEMENT",
    }
    event_info = {
        "title": "CYPHER DECODE",
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
    parser.add_argument("--all-events", action="store_true", help="Generate certificates for ALL events")
    parser.add_argument("--test", action="store_true", help="Generate a test certificate")
    args = parser.parse_args()

    if args.test:
        generate_test()
    elif args.event_id or args.data_file:
        generate_batch(data_file=args.data_file, event_id=args.event_id)
    else:
        generate_all_events()


if __name__ == "__main__":
    main()

