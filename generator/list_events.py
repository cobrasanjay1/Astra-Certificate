"""
List events from the Astra Supabase database and resolve an event selection.

Used by the GitHub Action so an admin can see what is in the database and
choose which events to send certificates for, before anything is sent.

For every row in events_event it reports:
    attended  attendees whose registration status is ATTENDED
    sent      of those, certificates already emailed (certificate_sent = true)
    pending   of those, certificates still to be emailed

Examples:
    python list_events.py                    # print the table
    python list_events.py --summary          # also write the GitHub job summary
    python list_events.py --select 3,7       # validate a selection
    python list_events.py --select all       # every event that has attendees

--select exits non-zero (so the workflow stops before generating or emailing
anything) if the selection is empty, malformed, or names an unknown event.

Outputs (when --select succeeds):
    data/selected_events.json
    $GITHUB_OUTPUT: ids=<space separated event ids>, tag=<artifact-safe label>
"""

import argparse
import json
import logging
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR
from fetch_attendees import (
    EVENT_DATE_COL,
    EVENT_ID_COL,
    EVENT_TITLE_COL,
    EVENTS_TABLE,
    fetch_all,
    fetch_all_rows,
    format_event_date,
    get_client,
)

logger = logging.getLogger("list_events")


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def load_events():
    """Return every event in the DB with its attendance / certificate counts."""
    client = get_client()

    rows = fetch_all_rows(
        client,
        EVENTS_TABLE,
        columns=f"{EVENT_ID_COL},{EVENT_TITLE_COL},{EVENT_DATE_COL}",
    )

    # Attended participants, grouped per event, with certificate_sent state.
    stats = {}
    for batch in fetch_all():
        attendees = batch["attendees"]
        pending = sum(1 for a in attendees if not a.get("certificate_sent"))
        stats[str(batch["event"]["id"])] = (len(attendees), pending)

    events = []
    for row in rows:
        event_id = row.get(EVENT_ID_COL)
        if event_id is None:
            continue
        attended, pending = stats.get(str(event_id), (0, 0))
        events.append(
            {
                "id": int(event_id),
                "title": (row.get(EVENT_TITLE_COL) or "Untitled Event").strip(),
                "date": format_event_date(row.get(EVENT_DATE_COL)) if row.get(EVENT_DATE_COL) else "",
                "attended": attended,
                "sent": attended - pending,
                "pending": pending,
            }
        )

    events.sort(key=lambda e: e["id"])
    return events


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

class SelectionError(Exception):
    pass


def parse_selection(raw, events):
    """
    Turn the workflow input ("3,7" or "all") into a list of event dicts.

    Events with no attended participants are skipped (there is nothing to
    generate for them); the rest keep the order the admin typed them in.
    """
    raw = (raw or "").strip()
    if not raw:
        raise SelectionError(
            "No events selected. Enter event IDs (e.g. 3,7) or 'all'. "
            "Run this workflow with mode = list to see the IDs."
        )

    if raw.lower() == "all":
        chosen = [e for e in events if e["attended"] > 0]
    else:
        try:
            ids = [int(part) for part in re.split(r"[,\s]+", raw) if part]
        except ValueError:
            raise SelectionError(
                f"Could not read event IDs from {raw!r}. "
                "Use numbers separated by commas, e.g. 3,7"
            )

        by_id = {e["id"]: e for e in events}
        unknown = [i for i in ids if i not in by_id]
        if unknown:
            raise SelectionError(
                "Unknown event ID(s): " + ", ".join(map(str, unknown))
                + ". Run this workflow with mode = list to see valid IDs."
            )

        chosen = []
        for event_id in dict.fromkeys(ids):  # de-duplicate, keep order
            event = by_id[event_id]
            if event["attended"] == 0:
                logger.warning(
                    "Skipping event %s (%s): no attended participants.",
                    event["id"], event["title"],
                )
                continue
            chosen.append(event)

    if not chosen:
        raise SelectionError("None of the selected events have attended participants.")

    return chosen


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _md_cell(text):
    return str(text).replace("|", "\\|")


def render_console(events):
    lines = [f"{'ID':>4}  {'EVENT':<40}  {'DATE':<16}  {'ATTENDED':>8}  {'SENT':>5}  {'PENDING':>7}"]
    for e in events:
        lines.append(
            f"{e['id']:>4}  {e['title'][:40]:<40}  {e['date']:<16}  "
            f"{e['attended']:>8}  {e['sent']:>5}  {e['pending']:>7}"
        )
    return "\n".join(lines)


def render_markdown(events, heading="Events in the database"):
    lines = [
        f"### {heading}",
        "",
        "| ID | Event | Date | Attended | Sent | Pending |",
        "| --: | --- | --- | --: | --: | --: |",
    ]
    for e in events:
        lines.append(
            f"| {e['id']} | {_md_cell(e['title'])} | {e['date']} | "
            f"{e['attended']} | {e['sent']} | {e['pending']} |"
        )
    return "\n".join(lines) + "\n"


def append_summary(markdown):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(markdown + "\n")


def write_outputs(chosen, select_all):
    ids = [str(e["id"]) for e in chosen]
    tag = "all" if select_all else "-".join(ids)

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "selected_events.json"), "w", encoding="utf-8") as f:
        json.dump(chosen, f, indent=2, ensure_ascii=False)

    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"ids={' '.join(ids)}\n")
            f.write(f"tag={tag}\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="List Astra events / validate an event selection.")
    parser.add_argument("--summary", action="store_true", help="Write the table to the GitHub job summary")
    parser.add_argument(
        "--select",
        metavar="IDS",
        help="Comma-separated event IDs, or 'all'. Validates the selection and writes outputs.",
    )
    args = parser.parse_args()

    events = load_events()

    if args.select is None:
        print(render_console(events))
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(os.path.join(DATA_DIR, "events_index.json"), "w", encoding="utf-8") as f:
            json.dump(events, f, indent=2, ensure_ascii=False)

        if args.summary:
            md = render_markdown(events)
            md += (
                "\nTo send certificates, run this workflow again with **mode = send** and "
                "put the IDs you want in **events** (e.g. `3,7`, or `all`).\n"
            )
            append_summary(md)
        return

    try:
        chosen = parse_selection(args.select, events)
    except SelectionError as exc:
        logger.error("❌ %s", exc)
        append_summary(f"### ❌ Invalid event selection\n\n{exc}\n")
        sys.exit(1)

    select_all = args.select.strip().lower() == "all"
    print("Selected events:")
    print(render_console(chosen))

    append_summary(render_markdown(chosen, heading="Selected events"))
    write_outputs(chosen, select_all)


if __name__ == "__main__":
    main()
