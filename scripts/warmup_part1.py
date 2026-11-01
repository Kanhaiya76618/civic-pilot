"""Prepare the Part 1 demo: read each demo document and explain it once, so the live demo answers instantly.

The answers are real (made from the documents now) and saved on the server's disk, so a restart keeps them.
In the demo, say these were prepared earlier, and still explain one new document live.

  uv run python scripts/warmup_part1.py                        # http://127.0.0.1:8000, scripts/demo_part1.json
  uv run python scripts/warmup_part1.py https://my-space.hf.space my-demo.json
"""

import json
import sys
import time
from pathlib import Path

import httpx

base = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
items = json.loads(Path(sys.argv[2] if len(sys.argv) > 2 else Path(__file__).with_name("demo_part1.json")).read_text())["items"]
ok = True
with httpx.Client(base_url=base, timeout=600) as c:
    for it in items:
        label = f"{it['url'].rsplit('/', 1)[-1][:40]} [{it['language']}] {it['question'][:40] or '(no question)'}"
        t0 = time.monotonic()
        try:
            doc = c.post("/app/part1/api/documents", data={"url": it["url"]})
            doc.raise_for_status()
            ans = c.post("/app/part1/api/explain", json={"doc_id": doc.json()["doc_id"], "question": it["question"], "language": it["language"]})
            ans.raise_for_status()
            body = ans.json()
            again = c.post("/app/part1/api/explain", json={"doc_id": doc.json()["doc_id"], "question": it["question"], "language": it["language"]}).json()
            print(f"ready  {time.monotonic() - t0:5.0f}s  {'(already prepared)' if body.get('cached') else ''} audio={'yes' if body.get('audio_url') else 'NO'}"
                  f" repeat-instant={again.get('cached')}  {label}")
        except httpx.HTTPStatusError as e:
            ok = False
            print(f"FAILED {e.response.status_code} {e.response.text[:120]}  {label}")
        except httpx.HTTPError as e:
            ok = False
            print(f"FAILED {type(e).__name__}  {label}")
sys.exit(0 if ok else 1)
