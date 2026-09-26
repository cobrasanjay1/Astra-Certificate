"""
Configuration for the Astra Certificate Generator.

Text positions are in absolute pixels for a 2000×1414 template.
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
TEMPLATE_FILE = os.path.join(TEMPLATE_DIR, "astra_certificate_template.png")

# ── Template Dimensions ───────────────────────────────────────────────────
TEMPLATE_WIDTH = 2000
TEMPLATE_HEIGHT = 1414

# ── Font Configuration ────────────────────────────────────────────────────
# Primary fonts from generator/fonts (DroidSerif & CanvaSans)
FONTS = {
    "name": {
        "path": os.path.join(FONT_DIR, "DroidSerif-Regular.ttf"),
        "size": 96,  # calibrated to match reference template
    },
    "body": {
        "path": os.path.join(FONT_DIR, "CanvaSans-Medium.otf"),
        "size": 32,  # calibrated: glyph h=25px matching reference
    },
    "body_bold": {
        "path": os.path.join(FONT_DIR, "CanvaSans-Bold.otf"),
        "size": 32,
    },
    "body_italic": {
        "path": os.path.join(FONT_DIR, "CanvaSans-BoldItalic.otf"),
        "size": 32,
    },
    "label": {
        "path": os.path.join(FONT_DIR, "CanvaSans-Regular.otf"),
        "size": 20,
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


# ── Text Placement (absolute pixel coordinates on 2000×1414) ──────────────
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
        "cover": (70, 650, 1600, 790),
        "position": (82, 665),
        "color": (30, 30, 30),
        "font_key": "name",
        "font_size": 96,
        "max_width": 1500,
    },

    # Full Body paragraph region (covers and re-types the entire paragraph below the name)
    # Calibrated: CanvaSans size=32 → glyph h=25px (matches reference).
    # tracking=13, word_space=26 → matches reference character spacing.
    # max_width=1600 → produces exactly 5 lines matching the reference template.
    # Position y=805 → CanvaSans bbox top-offset=11 → glyph starts at y=816 (reference).
    "body": {
        "cover": (60, 800, 1700, 1060),
        "position": (81, 805),
        "color": (30, 30, 30),
        "font_size": 32,
        "line_height": 51,
        "tracking": 13.0,
        "word_space": 26.0,
        "max_width": 1600,
    },


}

# ── Body Paragraph Template ───────────────────────────────────────────────
# The paragraph below the name. Placeholders are replaced with actual values.
# Words wrapped in ** are rendered in CanvaSans-BoldItalic (college/event/fest names).
BODY_TEMPLATE = (
    "OF **{college}**, FOR PARTICIPATING IN **{event}**, "
    "HELD AS PART OF THE FEST '**{fest}**', OF DEPARTMENT OF "
    "COMPUTER SCIENCE AND ENGINEERING (CYBER SECURITY), "
    "ON {date}."
)


# ── Database & Supabase Configuration ─────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))
DATABASE_URL = os.environ.get("DATABASE_URL", os.environ.get("SUPABASE_DB_URL", ""))

# Legacy API config (fallback)
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.astraietm.in")
API_TOKEN = os.environ.get("API_TOKEN", "")

# ── Email Configuration ───────────────────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "ASTRA Events <contact@astraietm.in>")
CERT_VERIFY_BASE_URL = os.environ.get(
    "CERT_VERIFY_BASE_URL", "https://cert.astraietm.in"
)

# ── Certificate ID Format ─────────────────────────────────────────────────
# Format: CERT-{YEAR}-{SEQUENTIAL_ID}
CERT_ID_PREFIX = "CERT"
