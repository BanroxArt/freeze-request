"""Follow the stolen funds through the listed hops with one stated rule.

Rule (stolen-first): when an address sends, the stolen funds it holds are
counted as leaving before any other funds. Only hops in the case count; the
kit knows nothing else about an address's balance. The result is the most
that can be traced to each address under that rule. It is a way to size a
request, not proof of where any particular coin went, and courts use several
different tracing rules.

Where the funds start: a hop marked `origin`, or any hop sent from an address
whose role is `victim`, carries stolen funds for its whole amount.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal

from .case import Case, Hop
from .networks import key

Slot = tuple[str, str, str]  # network, address key, symbol

RULE = (
    "stolen-first: when an address sends, the stolen funds it holds leave before any other funds; only "
    "the hops in this case are counted"
)


@dataclass(frozen=True)
class TracedHop:
    hop: Hop
    traced_in: Decimal
    traced_out: Decimal
    connected: bool


@dataclass(frozen=True)
class Trace:
    hops: tuple[TracedHop, ...]
    received: dict[Slot, Decimal]
    remaining: dict[Slot, Decimal]
    sent: dict[Slot, Decimal]
    total_origin: dict[tuple[str, str], Decimal]

    def at(self, network: str, address: str, symbol: str) -> tuple[Decimal, Decimal]:
        s = (*key(network, address), symbol)
        return self.received.get(s, Decimal(0)), self.remaining.get(s, Decimal(0))


def slot(network: str, address: str, symbol: str) -> Slot:
    return (*key(network, address), symbol)


def trace(case: Case) -> Trace:
    victims = {key(a.network, a.address) for a in case.addresses if a.role == "victim"}
    bal: dict[Slot, Decimal] = defaultdict(Decimal)
    received: dict[Slot, Decimal] = defaultdict(Decimal)
    sent: dict[Slot, Decimal] = defaultdict(Decimal)
    origin: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    out = []
    for h in case.hops:
        src = slot(h.network, h.sender, h.symbol)
        is_origin = h.origin or key(h.network, h.sender) in victims
        if is_origin:
            moved = h.amount
            origin[(h.network, h.symbol)] += h.amount
        else:
            moved = min(h.amount, bal[src])
            bal[src] -= moved
        sent[src] += moved
        arrived = moved if h.amount_out is None else moved * h.amount_out / h.amount
        tok = case.token(h.out_network, h.out_symbol)
        if tok is not None:
            arrived = arrived.quantize(Decimal(1).scaleb(-tok.decimals), rounding=ROUND_DOWN)
        dst = slot(h.out_network, h.recipient, h.out_symbol)
        if arrived:
            bal[dst] += arrived
            received[dst] += arrived
        out.append(TracedHop(h, moved, arrived, is_origin or moved > 0))
    return Trace(
        tuple(out),
        {k: v for k, v in received.items() if v},
        {k: v for k, v in bal.items() if v},
        {k: v for k, v in sent.items() if v},
        dict(origin),
    )
