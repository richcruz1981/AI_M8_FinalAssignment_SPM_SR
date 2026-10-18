from __future__ import annotations

import json
import logging
from pathlib import Path


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "agent": getattr(record, "agent", record.name),
            "run_id": getattr(record, "run_id", None),
            "msg": record.getMessage(),
        }
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(run_dir: Path | None = None, level: int = logging.INFO) -> logging.Logger:
    log = logging.getLogger("spm_sr")
    log.setLevel(level)
    for h in list(log.handlers):
        log.removeHandler(h)
        h.close()
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s", "%H:%M:%S"))
    log.addHandler(console)
    if run_dir is not None:
        run_dir.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(run_dir / "run.log", encoding="utf-8")
        fh.setFormatter(JsonFormatter())
        log.addHandler(fh)
    log.propagate = False
    return log
