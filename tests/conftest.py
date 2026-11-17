from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path
from typing import Any

EX = Path(__file__).resolve().parents[1] / "examples"
NOW = dt.datetime(2026, 11, 14, 18, 0, tzinfo=dt.UTC)
BASE: dict[str, Any] = json.loads((EX / "case.json").read_text())


def raw(**changes: Any) -> dict[str, Any]:
    d = copy.deepcopy(BASE)
    d.update(copy.deepcopy(changes))
    return d
