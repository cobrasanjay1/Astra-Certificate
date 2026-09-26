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
# Primary fonts (downloaded Google Fonts)
FONTS = {
    "name": {
        "path": os.path.join(FONT_DIR, "LibreBaskerville-Regular.ttf"),
        "size": 78,
    },
    "body": {
        "path": os.path.join(FONT_DIR, "Montserrat-SemiBold.ttf"),
        "size": 24,
    },
    "body_bold": {
        "path": os.path.join(FONT_DIR, "Montserrat-Bold.ttf"),
        "size": 24,
    },
    "body_italic": {
        "path": os.path.join(FONT_DIR, "Montserrat-BoldItalic.ttf"),
        "size": 24,
    },
    "label": {
        "path": os.path.join(FONT_DIR, "Montserrat-Regular.ttf"),
        "size": 20,
    },
}

# Fallback system fonts
FALLBACK_FONTS = {
    "serif": [
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    ],
    "serif_bold": [
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    ],
    "sans": [
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ],
    "sans_bold": [
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
    # Participant Name box & position (leaves "AWARDED TO" untouched at y=570-615)
    "name": {
        "cover": (70, 650, 1600, 785),
        "position": (75, 665),
        "color": (30, 30, 30),
        "font_key": "name",
        "font_size": 78,
        "max_width": 1500,
    },

    # Event Title box & position (replaces CYPHER DECODE with exact Montserrat-BoldItalic font & tracking)
    "event": {
        "cover": (1055, 852, 1495, 902),
        "position": (1065, 864),
        "color": (0, 0, 0),
        "font_key": "body_italic",
        "font_size": 27,
        "tracking": 12.0,
        "word_spacing": 25,
        "max_width": 430,
    },
}

# ── Body Paragraph Template ───────────────────────────────────────────────
# The paragraph below the name. Placeholders are replaced with actual values.
# Words wrapped in ** are rendered in bold+italic (event/fest names).
BODY_TEMPLATE = (
    "OF  **{college}** ,  FOR  PARTICIPATING  IN  **{event}**, "
    "HELD  AS  PART  OF  THE  FEST  '**{fest}**',  OF  DEPARTMENT  OF "
    "COMPUTER  SCIENCE  AND  ENGINEERING  (CYBER  SECURITY), "
    "ON  {date}."
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
