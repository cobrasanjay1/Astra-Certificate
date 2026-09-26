"""
Build the static verification site for cert.astraietm.in.

Generates:
  - Individual verification pages for each certificate
  - A certificates.json data file for client-side lookup
  - Copies certificate PNGs to the site directory

Usage:
    python build_site.py --event-id 1
    python build_site.py --manifest ../data/event_1_manifest.json
"""

import os
import sys
import json
import shutil
import argparse
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DATA_DIR, OUTPUT_DIR, SITE_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("site-builder")


def _verify_page_html(cert, event):
    """Generate the HTML for an individual certificate verification page."""
    cert_id = cert["cert_id"]
    name = cert.get("name", "Participant")
    college = cert.get("college", "")
    event_title = event.get("title", "Event")
    fest_name = event.get("fest_name", "")
    date_str = cert.get("date", event.get("date_str", ""))

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Certificate Verification — {cert_id} | ASTRA IETM</title>
  <meta name="description" content="Verified certificate of participation for {name} — {event_title}, ASTRA IETM 2026">
  <meta name="robots" content="noindex">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: #0f172a;
      min-height: 100vh;
      color: #e2e8f0;
    }}

    .bg-pattern {{
      position: fixed; inset: 0; z-index: 0;
      background:
        radial-gradient(circle at 20% 20%, rgba(59,130,246,0.08) 0%, transparent 50%),
        radial-gradient(circle at 80% 80%, rgba(16,185,129,0.06) 0%, transparent 50%);
    }}

    .container {{
      position: relative; z-index: 1;
      max-width: 800px; margin: 0 auto;
      padding: 40px 20px;
    }}

    /* Header */
    .header {{
      text-align: center; margin-bottom: 32px;
    }}
    .header .brand {{
      display: inline-flex; align-items: center; gap: 8px;
      background: rgba(250,204,21,0.1);
      border: 1px solid rgba(250,204,21,0.2);
      border-radius: 8px; padding: 6px 16px;
      margin-bottom: 20px;
    }}
    .header .brand span {{
      color: #facc15; font-size: 13px; font-weight: 600;
      letter-spacing: 1.5px;
    }}
    .header h1 {{
      font-size: 28px; font-weight: 800; color: #f8fafc;
      margin-bottom: 8px;
    }}
    .header p {{ color: #94a3b8; font-size: 15px; }}

    /* Verified Badge */
    .verified-badge {{
      display: flex; align-items: center; justify-content: center; gap: 10px;
      background: linear-gradient(135deg, rgba(16,185,129,0.15), rgba(16,185,129,0.05));
      border: 1px solid rgba(16,185,129,0.3);
      border-radius: 12px; padding: 14px 24px;
      margin-bottom: 28px;
    }}
    .verified-badge .icon {{
      width: 28px; height: 28px;
      background: #10b981; border-radius: 50%;
      display: flex; align-items: center; justify-content: center;
      font-size: 16px; color: white;
    }}
    .verified-badge .text {{
      font-size: 16px; font-weight: 700; color: #10b981;
      letter-spacing: 0.5px;
    }}

    /* Certificate Card */
    .cert-card {{
      background: rgba(30, 41, 59, 0.8);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(148, 163, 184, 0.1);
      border-radius: 16px; overflow: hidden;
      box-shadow: 0 20px 60px rgba(0,0,0,0.3);
    }}

    .cert-image {{
      width: 100%; display: block;
      border-bottom: 1px solid rgba(148, 163, 184, 0.1);
    }}

    .cert-details {{
      padding: 28px;
    }}
    .cert-details h2 {{
      font-size: 22px; font-weight: 700; color: #f1f5f9;
      margin-bottom: 20px;
    }}

    .detail-grid {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }}
    @media (max-width: 600px) {{
      .detail-grid {{ grid-template-columns: 1fr; }}
    }}

    .detail-item {{
      background: rgba(15, 23, 42, 0.5);
      border: 1px solid rgba(148, 163, 184, 0.08);
      border-radius: 10px; padding: 14px 16px;
    }}
    .detail-item .label {{
      font-size: 11px; font-weight: 600; color: #64748b;
      text-transform: uppercase; letter-spacing: 1px;
      margin-bottom: 6px;
    }}
    .detail-item .value {{
      font-size: 15px; font-weight: 600; color: #e2e8f0;
    }}

    .cert-id-item {{
      grid-column: 1 / -1;
      background: rgba(59, 130, 246, 0.08);
      border-color: rgba(59, 130, 246, 0.15);
    }}
    .cert-id-item .value {{
      font-family: 'JetBrains Mono', monospace;
      color: #60a5fa; font-size: 18px;
    }}

    /* Footer */
    .footer {{
      text-align: center; margin-top: 32px;
      padding: 20px;
    }}
    .footer p {{
      color: #475569; font-size: 12px; line-height: 1.6;
    }}
    .footer a {{ color: #3b82f6; text-decoration: none; }}
    .footer a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div class="bg-pattern"></div>
  <div class="container">

    <div class="header">
      <div class="brand"><span>ASTRA IETM 2026</span></div>
      <h1>Certificate Verification</h1>
      <p>This certificate has been verified by ASTRA IETM</p>
    </div>

    <div class="verified-badge">
      <div class="icon">✓</div>
      <div class="text">VERIFIED — Authentic Certificate</div>
    </div>

    <div class="cert-card">
      <img class="cert-image" src="../../certificates/{cert_id}.png"
           alt="Certificate of Participation — {name}">

      <div class="cert-details">
        <h2>Certificate Details</h2>
        <div class="detail-grid">
          <div class="detail-item cert-id-item">
            <div class="label">Certificate ID</div>
            <div class="value">{cert_id}</div>
          </div>
          <div class="detail-item">
            <div class="label">Participant</div>
            <div class="value">{name}</div>
          </div>
          <div class="detail-item">
            <div class="label">Event</div>
            <div class="value">{event_title}{f' — {fest_name}' if fest_name else ''}</div>
          </div>
          <div class="detail-item">
            <div class="label">College</div>
            <div class="value">{college or 'N/A'}</div>
          </div>
          <div class="detail-item">
            <div class="label">Date</div>
            <div class="value">{date_str}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="footer">
      <p>
        Issued by <strong>ASTRA</strong> — Department of Computer Science &amp; Engineering (Cyber Security)<br>
        KMCT Institute of Emerging Technology and Management<br>
        <a href="https://astraietm.in">astraietm.in</a>
      </p>
    </div>

  </div>
</body>
</html>"""


def _landing_page_html():
    """Generate the landing page for cert.astraietm.in."""
    return """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Certificate Verification | ASTRA IETM</title>
  <meta name="description" content="Verify ASTRA IETM event certificates online. Enter your certificate ID to check authenticity.">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
      background: #0f172a;
      min-height: 100vh;
      display: flex; flex-direction: column;
      align-items: center; justify-content: center;
      color: #e2e8f0;
    }

    .bg-pattern {
      position: fixed; inset: 0; z-index: 0;
      background:
        radial-gradient(circle at 30% 30%, rgba(59,130,246,0.1) 0%, transparent 50%),
        radial-gradient(circle at 70% 70%, rgba(250,204,21,0.06) 0%, transparent 50%);
    }

    .container {
      position: relative; z-index: 1;
      max-width: 520px; width: 100%;
      padding: 40px 24px; text-align: center;
    }

    .logo {
      display: inline-flex; align-items: center; gap: 10px;
      background: rgba(250,204,21,0.1);
      border: 1px solid rgba(250,204,21,0.2);
      border-radius: 10px; padding: 8px 20px;
      margin-bottom: 32px;
    }
    .logo .a-box {
      background: #facc15; color: #0f172a;
      font-weight: 800; font-size: 18px;
      width: 32px; height: 32px;
      display: flex; align-items: center; justify-content: center;
      border-radius: 6px;
    }
    .logo span {
      color: #facc15; font-size: 14px; font-weight: 700;
      letter-spacing: 2px;
    }

    h1 {
      font-size: 36px; font-weight: 800; color: #f8fafc;
      margin-bottom: 12px;
      background: linear-gradient(135deg, #f8fafc, #94a3b8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }
    .subtitle { color: #64748b; font-size: 15px; margin-bottom: 40px; line-height: 1.6; }

    .search-box {
      background: rgba(30, 41, 59, 0.8);
      backdrop-filter: blur(12px);
      border: 1px solid rgba(148, 163, 184, 0.15);
      border-radius: 16px; padding: 28px;
      text-align: left;
    }
    .search-box label {
      display: block; font-size: 13px; font-weight: 600;
      color: #94a3b8; margin-bottom: 10px;
      text-transform: uppercase; letter-spacing: 1px;
    }
    .input-row { display: flex; gap: 10px; }
    .search-box input {
      flex: 1; padding: 14px 16px;
      background: rgba(15, 23, 42, 0.8);
      border: 1px solid rgba(148, 163, 184, 0.15);
      border-radius: 10px; color: #e2e8f0;
      font-size: 16px; font-family: 'JetBrains Mono', monospace;
      outline: none; transition: border-color 0.2s;
    }
    .search-box input:focus {
      border-color: #3b82f6;
    }
    .search-box input::placeholder { color: #475569; }
    .search-box button {
      padding: 14px 24px;
      background: linear-gradient(135deg, #1e40af, #3b82f6);
      color: white; border: none; border-radius: 10px;
      font-size: 15px; font-weight: 600;
      cursor: pointer; transition: transform 0.1s, box-shadow 0.2s;
      white-space: nowrap;
    }
    .search-box button:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(30, 64, 175, 0.4);
    }

    .error-msg {
      margin-top: 14px; padding: 10px 14px;
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid rgba(239, 68, 68, 0.2);
      border-radius: 8px; color: #fca5a5;
      font-size: 13px; display: none;
    }

    .footer {
      margin-top: 48px; color: #334155; font-size: 12px; line-height: 1.6;
    }
    .footer a { color: #3b82f6; text-decoration: none; }
  </style>
</head>
<body>
  <div class="bg-pattern"></div>
  <div class="container">

    <div class="logo">
      <div class="a-box">A</div>
      <span>ASTRA IETM</span>
    </div>

    <h1>Certificate Verification</h1>
    <p class="subtitle">
      Enter your certificate ID to verify its authenticity.<br>
      Certificate IDs look like: <strong style="color:#60a5fa;">CERT-2026-0042</strong>
    </p>

    <div class="search-box">
      <label for="cert-id">Certificate ID</label>
      <div class="input-row">
        <input type="text" id="cert-id" placeholder="CERT-2026-XXXX"
               autocomplete="off" spellcheck="false">
        <button onclick="verifyCert()">Verify</button>
      </div>
      <div class="error-msg" id="error-msg"></div>
    </div>

    <div class="footer">
      <p>
        © 2026 ASTRA IETM · KMCT Institute of Emerging Technology and Management<br>
        <a href="https://astraietm.in">astraietm.in</a>
      </p>
    </div>

  </div>

  <script>
    function verifyCert() {
      const input = document.getElementById('cert-id');
      const errEl = document.getElementById('error-msg');
      const certId = input.value.trim().toUpperCase();

      errEl.style.display = 'none';

      if (!certId) {
        errEl.textContent = 'Please enter a certificate ID.';
        errEl.style.display = 'block';
        return;
      }

      // Navigate to the verify page
      window.location.href = `/verify/${certId}/`;
    }

    // Enter key support
    document.getElementById('cert-id').addEventListener('keypress', (e) => {
      if (e.key === 'Enter') verifyCert();
    });
  </script>
</body>
</html>"""


def _not_found_page_html():
    """404 page for invalid certificate IDs."""
    return """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Certificate Not Found | ASTRA IETM</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
  <style>
    body {
      font-family: 'Inter', sans-serif; background: #0f172a;
      min-height: 100vh; display: flex; align-items: center; justify-content: center;
      color: #e2e8f0; margin: 0;
    }
    .container { text-align: center; padding: 40px; max-width: 480px; }
    .icon { font-size: 64px; margin-bottom: 20px; }
    h1 { font-size: 28px; color: #f8fafc; margin-bottom: 12px; }
    p { color: #94a3b8; line-height: 1.6; margin-bottom: 28px; }
    a {
      display: inline-block; padding: 12px 28px;
      background: linear-gradient(135deg, #1e40af, #3b82f6);
      color: white; text-decoration: none; border-radius: 10px;
      font-weight: 600;
    }
  </style>
</head>
<body>
  <div class="container">
    <div class="icon">🔍</div>
    <h1>Certificate Not Found</h1>
    <p>The certificate ID you entered doesn't match our records. Please double-check the ID and try again.</p>
    <a href="/">← Back to Verification</a>
  </div>
</body>
</html>"""


def build_site(manifest_path):
    """
    Build the static verification site from a manifest.

    Creates:
      site/
      ├── index.html                         # Landing page
      ├── 404.html                           # Not found page
      ├── certificates/                      # Certificate PNGs
      │   ├── CERT-2026-0001.png
      │   └── ...
      └── verify/
          ├── CERT-2026-0001/
          │   └── index.html                 # Individual verify page
          └── ...
    """
    if not os.path.exists(manifest_path):
        logger.error(f"Manifest not found: {manifest_path}")
        sys.exit(1)

    with open(manifest_path) as f:
        manifest = json.load(f)

    event = manifest.get("event", {})
    certificates = manifest.get("certificates", [])

    if not certificates:
        logger.warning("No certificates in manifest — nothing to build")
        return

    # Ensure site directories exist
    certs_dir = os.path.join(SITE_DIR, "certificates")
    verify_dir = os.path.join(SITE_DIR, "verify")
    os.makedirs(certs_dir, exist_ok=True)
    os.makedirs(verify_dir, exist_ok=True)

    # 1. Landing page
    landing_path = os.path.join(SITE_DIR, "index.html")
    with open(landing_path, "w") as f:
        f.write(_landing_page_html())
    logger.info(f"📄 Landing page: {landing_path}")

    # 2. 404 page
    notfound_path = os.path.join(SITE_DIR, "404.html")
    with open(notfound_path, "w") as f:
        f.write(_not_found_page_html())
    logger.info(f"📄 404 page: {notfound_path}")

    # 3. Individual verify pages + copy certificate PNGs
    for cert in certificates:
        cert_id = cert["cert_id"]

        # Copy certificate PNG
        src = os.path.join(OUTPUT_DIR, f"{cert_id}.png")
        dst = os.path.join(certs_dir, f"{cert_id}.png")
        if os.path.exists(src):
            shutil.copy2(src, dst)
        else:
            logger.warning(f"⚠️  Certificate PNG not found: {src}")

        # Create verify page: site/verify/CERT-2026-XXXX/index.html
        page_dir = os.path.join(verify_dir, cert_id)
        os.makedirs(page_dir, exist_ok=True)
        page_path = os.path.join(page_dir, "index.html")
        with open(page_path, "w") as f:
            f.write(_verify_page_html(cert, event))

    # 4. CNAME file for GitHub Pages
    cname_path = os.path.join(SITE_DIR, "CNAME")
    with open(cname_path, "w") as f:
        f.write("cert.astraietm.in\n")

    # 5. .nojekyll (tells GitHub Pages to skip Jekyll processing)
    nojekyll_path = os.path.join(SITE_DIR, ".nojekyll")
    with open(nojekyll_path, "w") as f:
        f.write("")

    logger.info(f"\n🌐 Site built: {len(certificates)} verify pages in {SITE_DIR}")
    logger.info(f"   Landing:  {SITE_DIR}/index.html")
    logger.info(f"   Verify:   {SITE_DIR}/verify/CERT-XXXX/")
    logger.info(f"   Certs:    {SITE_DIR}/certificates/")


def build_all_site():
    """Build verification site incorporating all event manifests."""
    import glob

    all_manifest_path = os.path.join(DATA_DIR, "all_manifest.json")
    if os.path.exists(all_manifest_path):
        manifest_path = all_manifest_path
    else:
        manifest_files = sorted(glob.glob(os.path.join(DATA_DIR, "event_*_manifest.json")))
        if not manifest_files:
            logger.error(f"No manifest files found in {DATA_DIR}")
            logger.info("Run generate.py first to generate certificates")
            sys.exit(1)

        combined_certs = []
        for mf in manifest_files:
            with open(mf) as f:
                data = json.load(f)
                combined_certs.extend(data.get("certificates", []))

        combined_manifest = {
            "event": {"id": "all", "title": "All Events"},
            "generated_at": datetime.now().isoformat(),
            "certificates": combined_certs,
        }
        manifest_path = os.path.join(DATA_DIR, "all_manifest.json")
        with open(manifest_path, "w") as f:
            json.dump(combined_manifest, f, indent=2)

    build_site(manifest_path)


def main():
    parser = argparse.ArgumentParser(description="Build the certificate verification site")
    parser.add_argument("--event-id", type=int, help="Event ID")
    parser.add_argument("--manifest", help="Path to manifest JSON")
    parser.add_argument("--all-events", action="store_true", help="Build site for ALL events")
    args = parser.parse_args()

    if args.manifest:
        build_site(args.manifest)
    elif args.event_id and not args.all_events:
        manifest_path = os.path.join(
            DATA_DIR, f"event_{args.event_id}_manifest.json"
        )
        build_site(manifest_path)
    else:
        build_all_site()


if __name__ == "__main__":
    main()

