"""Write the five shared contracts to /contracts as JSON Schema.

  uv run python scripts/export_contracts.py

Part 2 (TypeScript) can generate types with:
  npx json-schema-to-typescript@15.0.4 -i contracts -o web/src/contracts
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from executor.models import ApplicationTask, CitizenProfile, ConsentRecord, Receipt, TaskEvent  # noqa: E402

for model in (CitizenProfile, ConsentRecord, ApplicationTask, TaskEvent, Receipt):
    path = ROOT / "contracts" / f"{model.__name__}.schema.json"
    path.write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")
    print("wrote", path.relative_to(ROOT))
