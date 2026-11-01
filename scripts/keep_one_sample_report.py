"""Keep exactly one report on the public board, clearly labelled as a team sample, and delete the rest.

Why: the 18 reports in the database were created by server/seed.py (invented addresses, stock photos), and the
receipts are test escalations made on them. The hackathon forbids dummy data, so the board keeps one honest,
labelled sample of the workflow and otherwise shows only real reports filed through the app.

What it does, in one transaction (all or nothing):
  1. writes a full backup of reports, report events and receipts to .data/backups/
  2. keeps the "faulty streetlight, Pune" report (status ASSIGNED, no photos) and labels its description
  3. deletes every other report, their events, and all receipts

  uv run python scripts/keep_one_sample_report.py           # shows what would change, changes nothing
  uv run python scripts/keep_one_sample_report.py --apply   # does it
"""

import datetime
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(".env")
from sqlalchemy import inspect  # noqa: E402

from server.db import ReceiptModel, Report, ReportEvent, SessionLocal  # noqa: E402

LABEL = "[Sample report added by the Swayam-sevak team to show the workflow] "
apply = "--apply" in sys.argv
db = SessionLocal()


def rows(model):
    return [{c.key: getattr(o, c.key) for c in inspect(model).mapper.column_attrs} for o in db.query(model).all()]


keep = [r for r in db.query(Report).all() if r.category == "streetlights" and r.city == "Pune" and r.status == "ASSIGNED"]
if len(keep) != 1:
    sys.exit(f"Expected exactly one Pune streetlight report to keep, found {len(keep)}. Nothing changed.")
kid = str(keep[0].id)
others = [str(r.id) for r in db.query(Report).all() if str(r.id) != kid]
print(f"Keep:   {kid}  {keep[0].description[:80]}")
print(f"Delete: {len(others)} reports, their events, and {db.query(ReceiptModel).count()} receipts")
if not apply:
    sys.exit("Dry run: nothing changed. Add --apply to do it.")

backup = Path(".data/backups") / f"before-cleanup-{datetime.datetime.now():%Y%m%d-%H%M%S}.json"
backup.parent.mkdir(parents=True, exist_ok=True)
backup.write_text(json.dumps({"reports": rows(Report), "report_events": rows(ReportEvent), "receipts": rows(ReceiptModel)},
                             default=str, ensure_ascii=False, indent=1))
print(f"Backup: {backup}")
try:
    n_receipts = db.query(ReceiptModel).delete(synchronize_session=False)
    n_events = db.query(ReportEvent).filter(ReportEvent.report_id.in_(others)).delete(synchronize_session=False)
    db.query(Report).filter(Report.duplicate_of.in_(others)).update({Report.duplicate_of: None}, synchronize_session=False)
    n_reports = db.query(Report).filter(Report.id.in_(others)).delete(synchronize_session=False)
    kept = db.query(Report).filter(Report.id == kid).one()
    kept.duplicate_of = None
    if not (kept.description or "").startswith(LABEL):
        kept.description = LABEL + (kept.description or "")
    db.commit()
except Exception:
    db.rollback()
    raise
print(f"Done: deleted {n_reports} reports, {n_events} events, {n_receipts} receipts. "
      f"Left: {db.query(Report).count()} report (the labelled sample).")
