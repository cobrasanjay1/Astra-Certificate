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
}

# ── Certificate paragraph (drawn dynamically) ─────────────────────────────
# The paragraph is now built from DB values:
#   FOR PARTICIPATING IN THE <LEVEL> EVENT ‘<EVENT>’, ORGANIZED BY ASTRA
#   ASSOCIATION PROGRAM ‘LEVEL-404’, OF COMPUTER SCIENCE AND ENGINEERING
#   (CYBER SECURITY) DEPARTMENT OF KMCT IETM ON <DATE>.
# Edit PARAGRAPH_PARTS to change the wording. "r" = regular, "b" = bold italic.
# Placeholders: {level} {event} {fest} {date}
PARAGRAPH_PARTS = [
    ("FOR PARTICIPATING IN THE ", "r"),
    ("{level}", "b"),
    (" EVENT ", "r"),
    ("\u2018{event}\u2019", "b"),
    (", ORGANIZED BY ", "r"),
    ("ASTRA ASSOCIATION", "b"),
    (" PROGRAM ", "r"),
    ("\u2018{fest}\u2019", "b"),
    (", OF COMPUTER SCIENCE AND ENGINEERING (CYBER SECURITY) DEPARTMENT OF KMCT IETM ON ", "r"),
    ("{date}", "b"),
    (".", "r"),
]

PARAGRAPH = {
    "x": (69, 1592),                 # left / right edge (justified)
    "baselines": [897, 943, 989, 1035],  # max 4 lines (signatures sit below)
    "font_size": 35,
    "min_font_size": 26,
    "tracking": 4.0,
    "color": (30, 30, 30),
}

# templates/1.png has the old paragraph (blank event, "LEVEL-404", fixed date)
# baked into the picture. When ERASE_BAKED_PARAGRAPH is on, the generator
# rebuilds those rows from the watermark pattern before drawing the new text.
# Set ERASE_BAKED_PARAGRAPH=0 if you switch to a template that is already blank.
ERASE_BAKED_PARAGRAPH = os.environ.get("ERASE_BAKED_PARAGRAPH", "1") != "0"
PARAGRAPH_ERASE = {
    "x": (50, 1600),
    "y": (858, 1056),
    "pattern_src_y": 695,   # clean watermark rows used as the source
    "pattern_period": 50,   # watermark repeats every 50px vertically
}

# ── Event level ───────────────────────────────────────────────────────────
# Read from events_event.event_level ("College Level" / "District Level" /
# "State Level"). Nothing is hardcoded; an empty value is simply left out.
def event_level_text(event):
    return " ".join(str((event or {}).get("event_level") or "").split()).upper()


# ── Database & Supabase Configuration ─────────────────────────────────────
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""))
DEFAULT_FEST_NAME = "LEVEL 404"
FEST_NAME = (os.environ.get("FEST_NAME") or "").strip() or DEFAULT_FEST_NAME
# Fest label printed inside the certificate paragraph (as it appeared on the old template).
CERT_FEST_LABEL = (os.environ.get("CERT_FEST_LABEL") or "").strip() or "LEVEL-404"


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
