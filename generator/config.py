"""
Configuration for the Astra Certificate Generator.

Text positions are in absolute pixels for the current 2000×1414 template
(templates/1.png). Adjust these if the template changes.
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
]
TEMPLATE_FILE = next((path for path in _TEMPLATE_CANDIDATES if os.path.isfile(path)), _TEMPLATE_CANDIDATES[0])

# ── Template Dimensions ───────────────────────────────────────────────────
TEMPLATE_WIDTH = 2000
TEMPLATE_HEIGHT = 1414

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


# ── Text Placement (absolute pixel coordinates on 2000×1414) ──────────────
# templates/1.png is a ready-made form: the heading, the "FOR PARTICIPATING
# IN THE EVENT ‘ ’ ..." paragraph, fest name, date and signatures are all
# already printed on it. The generator only fills in three things:
#
#   1. Participant name  — written on the FIRST line under "AWARDED TO"
#   2. College name      — written on the SECOND line
#   3. Event name        — written in the blank between the quotes after
#                          "FOR PARTICIPATING IN THE EVENT"
#
# Nothing is covered/whited-out any more, so the template artwork (watermark,
# blue design on the right) stays untouched.
#
# "baseline" is the y of the bottom of the capital letters (text is anchored
# on its baseline, so it sits cleanly on the printed line).
TEXT_REGIONS = {
    "name": {
        "baseline": (74, 736),
        "color": (30, 30, 30),
        "font_key": "name",
        "font_size": 80,
        "min_font_size": 36,
        "max_width": 1440,
    },
    "college": {
        "baseline": (74, 810),
        "color": (30, 30, 30),
        "font_key": "name",
        "font_size": 38,
        "min_font_size": 22,
        "max_width": 1440,
        "uppercase": True,
    },
    "event": {
        "gap": (821, 1096),
        "baseline_y": 896,
        "padding": 10,
        "color": (30, 30, 30),
        "font_size": 32,
        "min_font_size": 12,
        "tracking": 2.0,
        "uppercase": True,
    },
}

# ── Database & Supabase Configuration ─────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))
DEFAULT_FEST_NAME = "LEVEL 404"
FEST_NAME = (os.environ.get("FEST_NAME") or "").strip() or DEFAULT_FEST_NAME
EVENT_DATE_STR = os.environ.get("EVENT_DATE_STR", "")


def safe_id(value):
    """Turn an event title into a filesystem-safe identifier used in filenames."""
    return (value or "event").strip().replace("/", "-")

# ── Email Configuration ───────────────────────────────────────────────────
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "ASTRA Events <contact@aietm.in>")
CERT_VERIFY_BASE_URL = os.environ.get(
    "CERT_VERIFY_BASE_URL", "https://cert.astraietm.in"
)

# ── Certificate ID Format ─────────────────────────────────────────────────
CERT_ID_PREFIX = "CERT"
