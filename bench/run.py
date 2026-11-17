"""Time tracing, checks and package building on synthetic chains."""

from __future__ import annotations

import copy
import json
import time
from pathlib import Path

from freezereq import case_from, document, markdown, review

EX = Path(__file__).resolve().parents[1] / "examples"


def chain(n: int) -> dict[str, object]:
    base = json.loads((EX / "case.json").read_text())
    d = copy.deepcopy(base)
    addrs = ["0x" + f"{i + 1:040x}" for i in range(n + 1)]
    d["addresses"] = []
    d["hops"] = [
        {
            "tx": "0x" + f"{i + 1:064x}",
            "network": "ethereum",
            "time": f"2026-11-12T{i // 3600 % 24:02d}:{i // 60 % 60:02d}:{i % 60:02d}Z",
            "from": addrs[i],
            "to": addrs[i + 1],
            "symbol": "USDC",
            "amount": "1000",
            "origin": i == 0,
        }
        for i in range(n)
    ]
    d["targets"] = [
        {"network": "ethereum", "address": addrs[-1], "symbol": "USDC", "amount": "1000", "reason": "end"}
    ]
    d["balances"] = []
    return d


def main() -> None:
    for n in (10, 1_000, 10_000):
        raw = chain(n)
        t0 = time.perf_counter()
        case = case_from(raw)
        rv = review(case)
        doc = document(case, rv, "law_enforcement")
        markdown(doc, rv)
        print(f"{n:>6} hops: parse, trace, check, JSON and Markdown in {time.perf_counter() - t0:.3f} s")


if __name__ == "__main__":
    main()
