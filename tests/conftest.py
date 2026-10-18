import copy
import datetime as dt
from pathlib import Path

import pytest

from scripts.seed_demo_db import seed
from spm_sr.core.config import load_all

AS_OF = dt.date(2026, 10, 19)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for k in ("DB_URL", "DATABASE_URL", "DATABASE_URL_LOCAL", "DB_TARGET", "TELEGRAM_TOKEN", "TELEGRAM_ID",
              "ADMIN_TELEGRAM_CHAT_ID", "TELEGRAM_CHAT_ID", "LLM_ENABLED", "SCOPE", "DRY_RUN", "ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN",
              "REDIRECT_TELEGRAM_CHAT_ID", "RUNS_DIR", "RECIPIENTS_FILE"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def cfg(tmp_path: Path):
    settings, schema_map, thresholds, recipients = load_all()
    settings = copy.deepcopy(settings)
    db = seed(tmp_path / "test.db", AS_OF)
    settings["db"]["url"] = f"sqlite:///{db}"
    settings["db"]["backoff_s"] = [0, 0, 0]
    settings["runs_dir"] = str(tmp_path / "runs")
    settings["llm"]["enabled"] = False
    return settings, schema_map, thresholds, recipients, tmp_path


def no_sleep(_s):
    return None
