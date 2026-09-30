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

> **Note:** You can still target a single event by passing `--title "<event title>"` to
> `fetch_attendees.py`, and `--event-id "<event title>"` to `generate.py` / `build_site.py` /
> `send_emails.py` (the event's "id" is just its title, made filename-safe).

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

Trigger from the **Actions** tab → **Send Certificates** → **Run workflow**:

| Input | Description |
|-------|-------------|
| `event_title` | Event title, matched exactly against the DB (leave blank for ALL events) |
| `dry_run` | Generate without sending emails |
| `retry_failed` | Retry only previously failed emails |
| `max_retries` | Max send attempts per email (default: 3) |

### Required Secrets

| Secret | Description |
|--------|-------------|
| `SUPABASE_URL` | Your Supabase Project URL (e.g., `https://xyz.supabase.co`) |
| `SUPABASE_KEY` | Supabase Service Role Key or API Key |
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
│   ├── send_emails.py           # Email queue with retry logic
│   ├── build_site.py            # Verification site builder
│   ├── requirements.txt         # Python dependencies
│   └── fonts/                   # Downloaded Google Fonts
├── templates/
│   └── astra_certificate_template.webp
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

## Database Schema

`fetch_attendees.py` reads two Supabase tables directly (no backend API involved):

1. **Profiles table** — one row per authenticated user: `id`, `email`.
2. **Registrations table** — one row per event registration, holding the three
   fields collected on the registration form and that vary per participant
   (`name`, `college`, `event_title`), plus an `attended` flag set once the
   event has happened.

Only registrations with `attended = true` become certificates, grouped by
`event_title`. The exact table and column names are constants at the top of
`fetch_attendees.py` — rename them to match your schema:

```python
PROFILES_TABLE = "profiles"
PROFILES_ID_COL = "id"
PROFILES_EMAIL_COL = "email"

REGISTRATIONS_TABLE = "event_registrations"
REG_USER_ID_COL = "user_id"      # FK -> PROFILES_TABLE.id
REG_NAME_COL = "name"
REG_COLLEGE_COL = "college"
REG_TITLE_COL = "event_title"
REG_ATTENDED_COL = "attended"
REG_ATTENDED_VALUE = True        # change to e.g. "ATTENDED" if it's a status string
```

The fest name and date shown on the certificate body are the same for every
event in a run and aren't stored per registration — set them once via the
`FEST_NAME` / `EVENT_DATE_STR` environment variables (or their defaults in
`config.py`) rather than per participant.
