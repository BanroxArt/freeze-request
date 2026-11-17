from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from conftest import BASE, EX, NOW, raw

from freezereq import case_from, document, for_token, markdown, review
from freezereq.__main__ import main
from freezereq.build import canonical

D_ADDR = BASE["targets"][0]["address"]
C_ADDR = BASE["targets"][1]["address"]
F_ADDR = BASE["addresses"][5]["address"]
ORDER = {
    "authority_kind": "court",
    "authority": "U.S. District Court (synthetic)",
    "reference": "0:26-mj-00000",
    "date": "2026-11-15",
    "final": True,
    "reviewable": True,
    "attached": True,
    "addresses": [{"network": "base", "address": D_ADDR}, {"network": "ethereum", "address": C_ADDR}],
}


def rules(now: dt.datetime = NOW, **changes: Any) -> list[tuple[str, str]]:
    return [(f.rule, f.level) for f in review(case_from(raw(**changes)), now).findings]


def test_example_is_clean_apart_from_no_order() -> None:
    r = rules()
    assert ("FR-ORDER", "warn") in r
    assert {x for x in r if x[1] != "info"} == {("FR-ORDER", "warn")}
    assert ("FR-ORDER", "info") in rules(purpose="law_enforcement_referral")


def test_good_order_clears_order_warnings() -> None:
    assert not [x for x in rules(order=ORDER) if x[1] != "info"]


@pytest.mark.parametrize(
    ("change", "expect"),
    [
        ({"authority_kind": "state_agency"}, "FR-ORDER"),
        ({"authority_kind": "foreign"}, "FR-ORDER"),
        ({"final": False}, "FR-ORDER"),
        ({"reviewable": False}, "FR-ORDER"),
        ({"attached": False}, "FR-ORDER"),
        ({"addresses": [{"network": "base", "address": D_ADDR}]}, "FR-PARTICULARITY"),
        (
            {
                "addresses": [
                    {"network": "ethereum", "address": D_ADDR},
                    {"network": "ethereum", "address": C_ADDR},
                ]
            },
            "FR-PARTICULARITY",
        ),
    ],
)
def test_order_elements(change: dict[str, Any], expect: str) -> None:
    assert (expect, "warn") in rules(order={**ORDER, **change})


def test_order_matches_evm_addresses_without_case() -> None:
    o = {
        **ORDER,
        "addresses": [
            {"network": "base", "address": D_ADDR.upper().replace("0X", "0x")},
            {"network": "ethereum", "address": C_ADDR},
        ],
    }
    assert ("FR-PARTICULARITY", "warn") not in rules(order=o)


def test_unreported_issuer_request() -> None:
    assert ("FR-REPORTED", "warn") in rules(reported_to=[])
    assert ("FR-REPORTED", "warn") not in rules(reported_to=[], purpose="law_enforcement_referral")


def test_targets() -> None:
    t = BASE["targets"]
    over = [{**t[0], "amount": "140000"}, t[1]]
    assert ("FR-TARGET", "warn") in rules(targets=over)
    victimish = [{**t[0], "address": "0x" + "7" * 40}]
    assert ("FR-TARGET", "block") in rules(targets=victimish)
    svc = [{"network": "ethereum", "address": F_ADDR, "symbol": "USDT", "amount": "60000", "reason": "x"}]
    assert ("FR-CUSTODIAL", "warn") in rules(targets=svc)
    assert ("FR-BALANCE", "warn") in rules(targets=svc)


def test_balances() -> None:
    assert ("FR-BALANCE", "warn") in rules(now=NOW + dt.timedelta(hours=30))
    b = BASE["balances"]
    assert ("FR-BALANCE", "warn") in rules(balances=[{**b[0], "amount": "0"}, b[1]])
    assert ("FR-BALANCE", "warn") in rules(balances=[{**b[0], "amount": "5"}, b[1]])


def test_no_origin_blocks() -> None:
    hops = [{k: v for k, v in h.items() if k != "origin"} for h in BASE["hops"]]
    r = rules(hops=hops)
    assert ("FR-ORIGIN", "block") in r and ("FR-PATH", "warn") in r


def test_issuer_lookup() -> None:
    assert for_token("usdc") is not None and for_token("PYUSD") is not None
    assert for_token("DAI") is None


def test_documents_by_audience() -> None:
    case = case_from(raw())
    rv = review(case, NOW)
    iss = document(case, rv, "issuer")
    le = document(case, rv, "law_enforcement")
    body = {k: v for k, v in iss.items() if k != "sha256"}
    assert iss["sha256"] == hashlib.sha256(canonical(body)).hexdigest()
    assert "victim" not in iss and "funding" not in iss
    assert le["victim"]["name"] == "Example Manufacturing Co"
    assert le["funding"][0]["refs"]["uetr"].startswith("6f1c2a8e")
    assert not any(f["level"] == "warn" for f in iss["findings"])
    assert [t["traced_remaining"] for t in iss["targets"]] == ["129985.5", "38950.25"]
    assert {o["service"] for o in iss["offramps"]} == {"Example Base Exchange", "Example Offshore Exchange"}
    assert iss["targets"][0]["chain_id"] == 8453
    assert "reasonable particularity" in iss["legal_basis"]["genius_act"]["sec_2_16"]
    md_i = markdown(iss, rv)
    md_l = markdown(le, rv)
    assert "Example Manufacturing" not in md_i and "Example Manufacturing" in md_l
    assert "evidence, not an order" in md_i
    assert "Notes for the sender" in md_i
    assert "money moved to a brand-new account" in md_i
    with pytest.raises(ValueError):
        document(case, rv, "press")


def test_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    case = str(EX / "case.json")
    now = ["--now", "2026-11-14T18:00:00Z"]
    assert main(["check", case, *now]) == 0
    out = tmp_path / "out"
    assert main(["build", case, *now, "--out", str(out)]) == 0
    doc = json.loads((out / "ECB-FRZ-2026-0007-issuer.json").read_text())
    assert doc["audience"] == "issuer"
    assert main(["build", case, *now, "--out", str(out), "--audience", "law_enforcement"]) == 0
    assert (out / "ECB-FRZ-2026-0007-law_enforcement.md").exists()
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw(targets=[{**BASE["targets"][0], "address": "0x" + "7" * 40}])))
    assert main(["check", str(bad), *now]) == 2
    assert main(["build", str(bad), *now, "--out", str(out)]) == 2
    assert main(["check", str(tmp_path / "missing.json")]) == 1
    assert main(["check", case, "--now", "2026-11-14T18:00:00"]) == 1
    capsys.readouterr()
    assert main(["issuers"]) == 0
    assert "isBlacklisted" in capsys.readouterr().out
