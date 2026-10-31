"""Runtime settings, read once from the environment (see .env.example)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    """Read KEY=VALUE lines from .env into the environment. Real environment variables win."""
    if os.environ.get("CIVIC_SKIP_DOTENV") or not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip().strip('"').strip("'")
        if value:
            os.environ.setdefault(key.strip(), value)


_load_dotenv(ROOT / ".env")


def _default_provider() -> str:
    """aimlapi when only an AIML API key is configured; otherwise Anthropic's own API."""
    if os.environ.get("AIMLAPI_KEY") and not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return "aimlapi"
    return "anthropic"


def _bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    data_dir: Path = field(default_factory=lambda: Path(os.environ.get("CIVIC_DATA_DIR", ROOT / ".data")))
    registry_dir: Path = field(default_factory=lambda: Path(os.environ.get("CIVIC_REGISTRY_DIR", ROOT / "registry")))
    public_url: str = field(default_factory=lambda: os.environ.get("CIVIC_PUBLIC_URL", "http://127.0.0.1:8000"))
    sandbox_url: str = field(default_factory=lambda: os.environ.get("SANDBOX_URL", "http://127.0.0.1:8100"))
    # Service-to-service key for Part 1 / Part 2. Empty disables the check (local dev only).
    api_key: str = field(default_factory=lambda: os.environ.get("CIVIC_API_KEY", ""))
    webhook_secret: str = field(default_factory=lambda: os.environ.get("CIVIC_WEBHOOK_SECRET", "dev-webhook-secret"))
    vault_key: str = field(default_factory=lambda: os.environ.get("CIVIC_VAULT_KEY", ""))
    vault_ttl_s: int = field(default_factory=lambda: int(os.environ.get("CIVIC_VAULT_TTL_S", "86400")))
    headless: bool = field(default_factory=lambda: _bool("CIVIC_HEADLESS", True))
    # Playwright traces hold DOM snapshots with typed values, so they are only
    # recorded for the sandbox unless explicitly enabled.
    trace_live_portals: bool = field(default_factory=lambda: _bool("CIVIC_TRACE_LIVE", False))
    step_timeout_ms: int = field(default_factory=lambda: int(os.environ.get("CIVIC_STEP_TIMEOUT_MS", "20000")))
    human_timeout_s: int = field(default_factory=lambda: int(os.environ.get("CIVIC_HUMAN_TIMEOUT_S", "600")))
    approval_timeout_s: int = field(default_factory=lambda: int(os.environ.get("CIVIC_APPROVAL_TIMEOUT_S", "600")))
    task_budget_s: int = field(default_factory=lambda: int(os.environ.get("CIVIC_TASK_BUDGET_S", "900")))
    # Tier 2 limits (per repair).
    heal_max_actions: int = field(default_factory=lambda: int(os.environ.get("CIVIC_HEAL_MAX_ACTIONS", "25")))
    heal_max_seconds: int = field(default_factory=lambda: int(os.environ.get("CIVIC_HEAL_MAX_SECONDS", "120")))
    llm_enabled: bool = field(default_factory=lambda: _bool("CIVIC_LLM_ENABLED", True))
    llm_provider: str = field(default_factory=lambda: os.environ.get("CIVIC_LLM_PROVIDER", _default_provider()))
    aimlapi_base_url: str = field(default_factory=lambda: os.environ.get("AIMLAPI_BASE_URL", "https://api.aimlapi.com"))
    llm_model: str = field(default_factory=lambda: os.environ.get("CIVIC_LLM_MODEL", "claude-opus-5-5"))
    llm_effort: str = field(default_factory=lambda: os.environ.get("CIVIC_LLM_EFFORT", "low"))
    drift_threshold: float = field(default_factory=lambda: float(os.environ.get("CIVIC_DRIFT_THRESHOLD", "0.3")))
    part1_api_url: str = field(default_factory=lambda: os.environ.get("PART1_API_URL", ""))
    part2_api_url: str = field(default_factory=lambda: os.environ.get("PART2_API_URL", ""))
    repair_engine: str = field(default_factory=lambda: os.environ.get("CIVIC_REPAIR_ENGINE", "builtin"))
    explore_engine: str = field(default_factory=lambda: os.environ.get("CIVIC_EXPLORE_ENGINE", "builtin"))
    public_starts_per_hour: int = field(default_factory=lambda: int(os.environ.get("CIVIC_PUBLIC_STARTS_PER_HOUR", "30")))
    # Agent console: web search providers tried in order ("duckduckgo", "site" = the portal's own search page).
    search_providers: list[str] = field(default_factory=lambda: [p.strip() for p in os.environ.get("CIVIC_SEARCH", "duckduckgo,site").split(",") if p.strip()])
    console_max_steps: int = field(default_factory=lambda: int(os.environ.get("CIVIC_CONSOLE_MAX_STEPS", "14")))
    console_max_seconds: int = field(default_factory=lambda: int(os.environ.get("CIVIC_CONSOLE_MAX_SECONDS", "240")))

    @property
    def db_path(self) -> Path:
        return self.data_dir / "civic.db"

    @property
    def evidence_dir(self) -> Path:
        return self.data_dir / "evidence"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def traces_dir(self) -> Path:
        return self.data_dir / "traces"

    @property
    def runs_dir(self) -> Path:
        return self.data_dir / "runs"

    @property
    def llm_log_path(self) -> Path:
        return self.data_dir / "llm_requests.jsonl"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.evidence_dir, self.uploads_dir, self.traces_dir, self.runs_dir):
            d.mkdir(parents=True, exist_ok=True)


settings = Settings()
