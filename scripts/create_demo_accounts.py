"""Demo accounts, so hackathon judges can try both sides without waiting for a confirmation email.

Creates in Supabase Auth (or, for an account that already exists, sets a new password):
  officer.demo@example.org   Municipal desk. The officer role is app metadata set with the server key; users can never
                             give it to themselves, which is why the desk has no "create account".
  citizen.demo@example.org   Citizen.
Each gets a new random password, written to .data/demo-accounts.txt (never printed, never committed). Give them to the
judges in the submission form, not on the website: anyone with the officer password can resolve reports and publish
proof photos on the public board.

  uv run python scripts/create_demo_accounts.py           # shows what it would do, changes nothing
  uv run python scripts/create_demo_accounts.py --apply   # creates the accounts / sets new passwords
"""

import os
import secrets
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

ACCOUNTS = [
    {"email": "officer.demo@example.org", "name": "Demo Officer (Municipal desk)", "role": "admin"},
    {"email": "citizen.demo@example.org", "name": "Demo Citizen", "role": "citizen"},
]
OUT = ROOT / ".data" / "demo-accounts.txt"
apply = "--apply" in sys.argv

url, key = os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SECRET_KEY")
if not url or not key:
    sys.exit("SUPABASE_URL and SUPABASE_SECRET_KEY must be set in .env. Nothing changed.")
from supabase import create_client  # noqa: E402

admin = create_client(url, key).auth.admin
existing, page = {}, 1
while True:
    batch = admin.list_users(page=page, per_page=1000)
    existing.update({(u.email or "").lower(): u for u in batch})
    if len(batch) < 1000:
        break
    page += 1

for a in ACCOUNTS:
    print(f"{'set a new password for' if a['email'] in existing else 'create'}: {a['email']}  ({'municipal desk' if a['role'] == 'admin' else 'citizen'})")
if not apply:
    sys.exit("Dry run: nothing changed. Add --apply to do it.")

lines = ["Swayam-sevak demo accounts (give these to the judges privately; do not put them on the website)", ""]
for a in ACCOUNTS:
    password = "Demo-" + secrets.token_urlsafe(9)
    attrs = {"password": password, "email_confirm": True, "user_metadata": {"name": a["name"]},
             "app_metadata": {"civic_role": a["role"]}}
    user = existing.get(a["email"])
    if user:
        admin.update_user_by_id(user.id, attrs)
    else:
        admin.create_user({"email": a["email"], **attrs})
    lines.append(f"{'Municipal desk' if a['role'] == 'admin' else 'Citizen':15} {a['email']:28} {password}")
OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text("\n".join(lines) + "\n")
OUT.chmod(0o600)
print(f"Done. The emails and passwords are in {OUT.relative_to(ROOT)} (open it with: open -e {OUT.relative_to(ROOT)})")
