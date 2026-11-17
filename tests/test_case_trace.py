from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest
from conftest import BASE, raw
from hypothesis import given, settings
from hypothesis import strategies as st

from freezereq import CaseError, case_from, trace
from freezereq.networks import valid_address, valid_tx

D_ADDR = BASE["targets"][0]["address"]
C_ADDR = BASE["targets"][1]["address"]


def test_example_traces() -> None:
    tr = trace(case_from(raw()))
    assert tr.total_origin == {("ethereum", "USDC"): Decimal("249000")}
    assert tr.at("base", D_ADDR, "USDC") == (Decimal("149985.5"), Decimal("129985.5"))
    assert tr.at("ethereum", C_ADDR, "USDT") == (Decimal("98950.25"), Decimal("38950.25"))
    assert tr.at("ethereum", C_ADDR, "USDC") == (Decimal("99000"), Decimal(0))
    assert tr.at("ethereum", C_ADDR.upper().replace("0X", "0x"), "USDT")[1] == Decimal("38950.25")


def hop(i: int, frm: str, to: str, amount: str, **kw: Any) -> dict[str, Any]:
    return {
        "tx": "0x" + f"{i:064x}",
        "network": "ethereum",
        "time": f"2026-11-12T{10 + i // 60:02d}:{i % 60:02d}:00Z",
        "from": frm,
        "to": to,
        "symbol": "USDC",
        "amount": amount,
        **kw,
    }


V, S1, S2, S3 = ("0x" + c * 40 for c in "1234")


def test_stolen_first_and_unconnected_hops() -> None:
    hops = [
        hop(1, V, S1, "100"),
        hop(2, S2, S1, "50", note="other money"),
        hop(3, S1, S3, "120"),
        hop(4, S2, S3, "10"),
    ]
    c = case_from(
        raw(
            addresses=[{"network": "ethereum", "address": V, "role": "victim"}],
            hops=hops,
            targets=[
                {"network": "ethereum", "address": S3, "symbol": "USDC", "amount": "130", "reason": "x"}
            ],
            balances=[],
        )
    )
    tr = trace(c)
    assert [th.traced_in for th in tr.hops] == [Decimal(100), Decimal(0), Decimal(100), Decimal(0)]
    assert [th.connected for th in tr.hops] == [True, False, True, False]
    assert tr.at("ethereum", S3, "USDC") == (Decimal(100), Decimal(100))


def test_swap_scales_and_rounds_down() -> None:
    c = case_from(
        raw(
            addresses=[],
            hops=[
                hop(1, V, S1, "3", origin=True),
                hop(2, S1, S1, "1", kind="swap", to_symbol="USDT", amount_out="0.999999"),
                hop(3, S1, S2, "2"),
            ],
            targets=[{"network": "ethereum", "address": S1, "symbol": "USDT", "amount": "1", "reason": "x"}],
            balances=[],
        )
    )
    tr = trace(c)
    assert tr.at("ethereum", S1, "USDT") == (Decimal("0.999999"), Decimal("0.999999"))
    assert tr.at("ethereum", S2, "USDC")[0] == Decimal(2)


@pytest.mark.parametrize(
    "changes",
    [
        {"purpose": "revenge"},
        {"case_id": "has spaces"},
        {"prepared_by": {"org": "x"}},
        {"tokens": []},
        {"tokens": [{"symbol": "USDC", "network": "ethereum", "contract": "0x12", "decimals": 6}]},
        {"hops": [hop(1, V, S1, "1.0000001")]},
        {"hops": [hop(1, V, S1, "-5")]},
        {"hops": [hop(1, V, S1, 5)]},
        {"hops": [hop(1, V, S1, "NaN")]},
        {"hops": [{**hop(1, V, S1, "1"), "time": "2026-11-12T10:00:00"}]},
        {"hops": [{**hop(1, V, S1, "1"), "tx": "0xabc"}]},
        {"hops": [{**hop(1, V, S1, "1"), "network": "dogechain"}]},
        {"hops": [hop(1, V, S1, "1", kind="bridge")]},
        {"hops": [hop(1, V, S1, "1", kind="swap")]},
        {"hops": [hop(1, V, S1, "1", amount_out="1")]},
        {"hops": [hop(1, V, S1, "1", origin="yes")]},
        {"hops": [{**hop(1, V, S1, "1"), "symbol": "DAI"}]},
        {"targets": []},
        {"order": {"authority_kind": "court"}},
        {"funding": [{"rail": "wire", "date": "2026-11-12", "amount_cents": 1.5, "currency": "USD"}]},
        {"surprise": True},
    ],
)
def test_bad_cases(changes: dict[str, Any]) -> None:
    with pytest.raises(CaseError):
        case_from(raw(**changes))


def test_address_formats() -> None:
    assert valid_address("tron", "T" + "A" * 33)
    assert not valid_address("tron", "T" + "0" * 33)
    assert valid_address("solana", "So11111111111111111111111111111111111111112")
    assert valid_tx("tron", "ab" * 32) and not valid_tx("tron", "0x" + "ab" * 32)


amounts = st.decimals(min_value=Decimal("0.01"), max_value=Decimal(10**6), places=2)


@settings(max_examples=150, deadline=None)
@given(st.lists(st.tuples(st.integers(0, 3), st.integers(0, 3), amounts), min_size=1, max_size=12), amounts)
def test_tracing_never_creates_money(moves: list[tuple[int, int, Decimal]], start: Decimal) -> None:
    addrs = [S1, S2, S3, "0x" + "5" * 40]
    hops = [hop(0, V, S1, str(start), origin=True)]
    hops += [hop(i + 1, addrs[a], addrs[b], str(amt)) for i, (a, b, amt) in enumerate(moves) if a != b]
    c = case_from(
        raw(
            addresses=[],
            hops=hops,
            targets=[{"network": "ethereum", "address": S1, "symbol": "USDC", "amount": "1", "reason": "x"}],
            balances=[],
        )
    )
    tr = trace(c)
    assert sum(tr.remaining.values()) == start
    assert all(v >= 0 for v in tr.remaining.values())
    for th in tr.hops[1:]:
        assert 0 <= th.traced_in <= th.hop.amount
