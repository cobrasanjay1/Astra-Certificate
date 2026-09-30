"""
Configuration for the Astra Certificate Generator.

Text positions are in absolute pixels for the current 1536×1086 template.
Adjust these if the template changes.
"""

import os

# ── Paths ─────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")
FONT_DIR = os.path.join(BASE_DIR, "generator", "fonts")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DATA_DIR = os.path.join(BASE_DIR, "data")
SITE_DIR = os.path.join(BASE_DIR, "site")

# Template filename (blank version — no sample name/event baked in)
# Prefer the newly uploaded PNG template. Keep fallbacks for older checkouts.
_TEMPLATE_CANDIDATES = [
    os.path.join(TEMPLATE_DIR, os.environ.get("TEMPLATE_FILENAME", "1.png")),
    os.path.join(TEMPLATE_DIR, "astra_certificate_template.png"),
    os.path.join(TEMPLATE_DIR, "astra_certificate_template.webp"),
]
TEMPLATE_FILE = next((path for path in _TEMPLATE_CANDIDATES if os.path.isfile(path)), _TEMPLATE_CANDIDATES[0])

# ── Template Dimensions ───────────────────────────────────────────────────
TEMPLATE_WIDTH = 1536
TEMPLATE_HEIGHT = 1086

# ── Font Configuration ────────────────────────────────────────────────────
# Primary fonts from generator/fonts (DroidSerif & CanvaSans)
FONTS = {
    "name": {
        "path": os.path.join(FONT_DIR, "DroidSerif-Regular.ttf"),
        "size": 74,  # scaled for the 1536×1086 reference template
    },
    "body": {
        "path": os.path.join(FONT_DIR, "CanvaSans-Medium.otf"),
        "size": 25,  # scaled for the 1536×1086 reference template
    },
    "body_bold": {
        "path": os.path.join(FONT_DIR, "CanvaSans-Bold.otf"),
        "size": 25,
    },
    "body_italic": {
        "path": os.path.join(FONT_DIR, "CanvaSans-BoldItalic.otf"),
        "size": 25,
    },
    "label": {
        "path": os.path.join(FONT_DIR, "CanvaSans-Regular.otf"),
        "size": 15,
    },
}

# Fallback fonts
FALLBACK_FONTS = {
    "serif": [
        os.path.join(FONT_DIR, "DroidSerif-Regular.ttf"),
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ],
    "serif_bold": [
        os.path.join(FONT_DIR, "DroidSerif-Bold.ttf"),
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    ],
    "sans": [
        os.path.join(FONT_DIR, "CanvaSans-Regular.otf"),
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "sans_bold": [
        os.path.join(FONT_DIR, "CanvaSans-Bold.otf"),
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ],
}


# ── Text Placement (absolute pixel coordinates on 1536×1086) ──────────────
# These coordinates define WHERE dynamic text is rendered on the template.
#
# The template has these regions that get COVERED (white rectangle) and
# re-drawn with dynamic data:
#
#   1. Participant Name area  — large text below "AWARDED TO"
#   2. Body paragraph area    — "OF {COLLEGE}, FOR PARTICIPATING IN..."
#   3. Date area              — "ON {DATE}."

TEXT_REGIONS = {
    # Participant Name box & position
    # Calibrated: DroidSerif size=96 renders "Midlaj Jaleel" at ~568px wide,
    # matching reference x=82..650. Position y=665 → glyph top at ~680 (reference).
    "name": {
        "cover": (54, 499, 1229, 607),
        "position": (63, 511),
        "color": (30, 30, 30),
        "font_key": "name",
        "font_size": 74,
        "max_width": 1152,
    },

    # Full Body paragraph region (covers and re-types the entire paragraph below the name)
    # Calibrated against the reference template by direct pixel measurement:
    #   - CanvaSans-Medium size=32 -> cap-height 25px, matching the reference
    #     ("OCTOBER" glyph bbox is exactly y=1020..1045 in the reference).
    #   - tracking=9.0, word_space=22.0 -> the unjustified last line
    #     ("ON 6 OCTOBER 2026.") renders at 477px, matching the reference
    #     exactly, AND these values reproduce the reference's exact 5-line
    #     word-wrap grouping (7 / 7 / 11 / 6 / 4 tokens per line).
    #   - max_width=1426 -> matches the reference's justified line width
    #     (measured 1425-1427px across all 4 full lines).
    # Position y=805 → CanvaSans bbox top-offset=11 → glyph starts at y=816 (reference).
    "body": {
        "cover": (46, 614, 1306, 814),
        "position": (62, 618),
        "color": (30, 30, 30),
        "font_size": 25,
        "line_height": 39,
        "tracking": 7.0,
        "word_space": 17.0,
        "max_width": 1095,
    },


}

# ── Body Paragraph Template ───────────────────────────────────────────────
# The paragraph below the name. Placeholders are replaced with actual values.
# Words wrapped in ** are rendered in CanvaSans-BoldItalic (college/event/fest names).
#
# Punctuation spacing rule (matches the reference template exactly, including
# its one inconsistency): punctuation glued directly to a ** boundary with no
# space (e.g. "**{event}**,") attaches to the neighboring word with no gap
# ("DECODE,"). Punctuation separated from a ** boundary by a space (e.g.
# "**{college}** ,") stays a standalone word with normal spacing on both
# sides ("MANAGEMENT , FOR") — this is exactly how the reference renders it.
# Do not "fix" that inconsistency; it's what the reference actually shows.
BODY_TEMPLATE = (
    "OF **{college}** , FOR PARTICIPATING IN **{event}**, "
    "HELD AS PART OF THE FEST \u2018**{fest}**\u2019, OF DEPARTMENT OF "
    "COMPUTER SCIENCE AND ENGINEERING (CYBER SECURITY), "
    "ON {date}."
)


# ── Database & Supabase Configuration ─────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))

# The fest date/name are the same across every event in a run, and aren't
# stored per-registration — set them once here (or via env vars) rather
# than per participant.
FEST_NAME = os.environ.get("FEST_NAME", "ZERO DAY")
EVENT_DATE_STR = os.environ.get("EVENT_DATE_STR", "")  # e.g. "6 OCTOBER 2026"


def safe_id(value):
    """Turn an event title into a filesystem-safe identifier used in filenames
    (data/event_{id}_attendees.json, etc). Used consistently by
    fetch_attendees.py, generate.py, send_emails.py and build_site.py so a
    title-based identifier round-trips through every stage of the pipeline."""
    return (value or "event").strip().replace("/", "-")

# ── Email Configuration ───────────────────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "ASTRA Events <contact@astraietm.in>")
CERT_VERIFY_BASE_URL = os.environ.get(
    "CERT_VERIFY_BASE_URL", "https://cert.astraietm.in"
)

# ── Certificate ID Format ─────────────────────────────────────────────────
# Format: CERT-{YEAR}-{SEQUENTIAL_ID}
CERT_ID_PREFIX = "CERT"