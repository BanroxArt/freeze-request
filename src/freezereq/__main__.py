"""freezereq: check a case and build the freeze evidence package."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

from .build import AUDIENCES, document, markdown
from .case import CaseError, case_from
from .checks import review
from .issuers import ISSUERS


def _load(path: str) -> object:
    return json.loads(Path(path).read_text())


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="freezereq", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("check", "build"):
        c = sub.add_parser(name)
        c.add_argument("case")
        c.add_argument("--now", help="time to judge balance checks against, ISO 8601 (default now)")
        c.add_argument("--max-balance-age", type=float, default=24.0, help="hours (default 24)")
        if name == "build":
            c.add_argument("--audience", choices=AUDIENCES)
            c.add_argument("--out", required=True, help="directory for <case_id>-<audience>.json and .md")
    sub.add_parser("issuers", help="print the issuer policies on file")
    a = p.parse_args(argv)

    if a.cmd == "issuers":
        for i in ISSUERS.values():
            print(f"{i.name} ({', '.join(i.tokens)}), checked {i.checked}")
            for x in i.acts_on:
                print(f"  acts on: {x}")
            print(f"  {i.own_discretion}")
            print(f"  on-chain check: {i.onchain_check or 'not on file'}")
            for s in i.sources:
                print(f"  source: {s}")
        return 0

    try:
        raw = _load(a.case)
        if not isinstance(raw, dict):
            raise CaseError("the case file must be a JSON object")
        case = case_from(raw)
        now = dt.datetime.fromisoformat(a.now) if a.now else None
        if now is not None and now.tzinfo is None:
            raise CaseError("--now needs an offset, for example 2026-11-16T20:00:00Z")
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    rv = review(case, now, a.max_balance_age)
    for f in rv.findings:
        print(f"{f.level.upper():5} {f.rule}: {f.message}" + (f" [{f.source}]" if f.source else ""))
    if a.cmd == "check":
        return 2 if rv.blocked else 0
    if rv.blocked:
        print("not built: fix the blocks first", file=sys.stderr)
        return 2
    audience = a.audience or ("issuer" if case.purpose == "issuer_review" else "law_enforcement")
    doc = document(case, rv, audience)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{case.case_id}-{audience}"
    (out / f"{stem}.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
    (out / f"{stem}.md").write_text(markdown(doc, rv))
    print(f"wrote {out / stem}.json and .md (sha256 {doc['sha256']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
