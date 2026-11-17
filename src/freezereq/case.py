"""The case file an investigator fills in, and its validation.

Amounts are decimal strings in token units ("90000.25"), never floats. Times
are ISO 8601 with an offset and are kept in UTC.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from .networks import NETWORKS, valid_address, valid_tx

PURPOSES = ("issuer_review", "law_enforcement_referral")
HOP_KINDS = ("transfer", "bridge", "swap")
ADDRESS_ROLES = ("victim", "suspect", "intermediate", "exchange_deposit", "bridge", "otc", "unknown")
ORDER_AUTHORITIES = ("court", "federal_agency", "state_agency", "foreign", "other")
RAILS = ("wire", "ach", "rtp", "fednow", "card", "check", "cash", "other")


class CaseError(ValueError):
    pass


@dataclass(frozen=True)
class Token:
    symbol: str
    network: str
    contract: str
    decimals: int


@dataclass(frozen=True)
class Address:
    network: str
    address: str
    role: str
    label: str = ""
    service: str = ""
    evidence: str = ""


@dataclass(frozen=True)
class Hop:
    tx: str
    network: str
    time: dt.datetime
    sender: str
    recipient: str
    symbol: str
    amount: Decimal
    kind: str = "transfer"
    to_network: str = ""
    to_symbol: str = ""
    amount_out: Decimal | None = None
    note: str = ""
    origin: bool = False

    @property
    def out_network(self) -> str:
        return self.to_network or self.network

    @property
    def out_symbol(self) -> str:
        return self.to_symbol or self.symbol

    @property
    def received(self) -> Decimal:
        return self.amount if self.amount_out is None else self.amount_out


@dataclass(frozen=True)
class Funding:
    rail: str
    date: dt.date
    amount_cents: int
    currency: str
    sender_institution: str
    receiver_institution: str
    refs: dict[str, str]
    note: str = ""


@dataclass(frozen=True)
class Target:
    network: str
    address: str
    symbol: str
    amount: Decimal
    reason: str


@dataclass(frozen=True)
class BalanceCheck:
    network: str
    address: str
    symbol: str
    amount: Decimal
    as_of: dt.datetime
    source: str


@dataclass(frozen=True)
class Order:
    authority_kind: str
    authority: str
    reference: str
    date: dt.date
    final: bool
    reviewable: bool
    addresses: tuple[tuple[str, str], ...]
    attached: bool


@dataclass(frozen=True)
class Event:
    time: dt.datetime
    what: str


@dataclass(frozen=True)
class Case:
    case_id: str
    purpose: str
    prepared_by: dict[str, str]
    prepared_on: dt.date
    summary: str
    tokens: tuple[Token, ...]
    addresses: tuple[Address, ...]
    hops: tuple[Hop, ...]
    targets: tuple[Target, ...]
    funding: tuple[Funding, ...] = ()
    balances: tuple[BalanceCheck, ...] = ()
    events: tuple[Event, ...] = ()
    order: Order | None = None
    victim: dict[str, str] = field(default_factory=dict)
    reported_to: tuple[str, ...] = ()

    def token(self, network: str, symbol: str) -> Token | None:
        for t in self.tokens:
            if t.network == network and t.symbol == symbol:
                return t
        return None


def _s(d: dict[str, Any], k: str, where: str, required: bool = True) -> str:
    v = d.get(k, "")
    if not isinstance(v, str) or (required and not v.strip()):
        raise CaseError(f"{where}: {k} must be a non-empty string")
    return v.strip()


def _time(v: Any, where: str) -> dt.datetime:
    try:
        t = dt.datetime.fromisoformat(str(v))
    except ValueError as e:
        raise CaseError(f"{where}: bad time {v!r}") from e
    if t.tzinfo is None:
        raise CaseError(f"{where}: time {v!r} has no offset; write it with Z or +00:00")
    return t.astimezone(dt.UTC)


def _date(v: Any, where: str) -> dt.date:
    try:
        return dt.date.fromisoformat(str(v))
    except ValueError as e:
        raise CaseError(f"{where}: bad date {v!r}") from e


def _amount(v: Any, where: str, decimals: int | None = None) -> Decimal:
    if not isinstance(v, str):
        raise CaseError(f"{where}: amount must be a decimal string, not {type(v).__name__}")
    try:
        a = Decimal(v)
    except InvalidOperation as e:
        raise CaseError(f"{where}: bad amount {v!r}") from e
    if not a.is_finite() or a <= 0:
        raise CaseError(f"{where}: amount must be positive")
    if decimals is not None and -a.as_tuple().exponent > decimals:  # type: ignore[operator]
        raise CaseError(f"{where}: {v} has more than {decimals} decimal places")
    return a


def _net(v: Any, where: str) -> str:
    if v not in NETWORKS:
        raise CaseError(f"{where}: unknown network {v!r}; known: {', '.join(NETWORKS)}")
    return str(v)


def _addr(network: str, v: Any, where: str) -> str:
    if not isinstance(v, str) or not valid_address(network, v):
        raise CaseError(f"{where}: {v!r} is not a {network} address")
    return v


def _choice(v: Any, options: tuple[str, ...], where: str) -> str:
    if v not in options:
        raise CaseError(f"{where}: {v!r} is not one of {', '.join(options)}")
    return str(v)


def _bool(d: dict[str, Any], k: str, where: str) -> bool:
    v = d.get(k, False)
    if not isinstance(v, bool):
        raise CaseError(f"{where}: {k} must be true or false")
    return v


def _list(d: dict[str, Any], k: str, where: str, required: bool = False) -> list[dict[str, Any]]:
    v = d.get(k, [])
    if not isinstance(v, list) or not all(isinstance(x, dict) for x in v):
        raise CaseError(f"{where}: {k} must be a list of objects")
    if required and not v:
        raise CaseError(f"{where}: {k} is empty")
    return v


KNOWN = {
    "case_id",
    "purpose",
    "prepared_by",
    "prepared_on",
    "summary",
    "tokens",
    "addresses",
    "hops",
    "targets",
    "funding",
    "balances",
    "events",
    "order",
    "victim",
    "reported_to",
}


def case_from(d: dict[str, Any]) -> Case:
    extra = set(d) - KNOWN
    if extra:
        raise CaseError(f"unknown fields: {', '.join(sorted(extra))}")
    case_id = _s(d, "case_id", "case")
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", case_id):
        raise CaseError("case: case_id may use letters, digits, '.', '_' and '-' only")
    purpose = _choice(d.get("purpose"), PURPOSES, "case.purpose")
    pb = d.get("prepared_by")
    if not isinstance(pb, dict) or not all(
        isinstance(pb.get(k), str) and pb[k].strip() for k in ("org", "contact")
    ):
        raise CaseError("case.prepared_by needs org and contact")

    tokens = []
    for i, t in enumerate(_list(d, "tokens", "case", required=True)):
        w = f"tokens[{i}]"
        net = _net(t.get("network"), w)
        dec = t.get("decimals")
        if not isinstance(dec, int) or isinstance(dec, bool) or not 0 <= dec <= 30:
            raise CaseError(f"{w}: decimals must be an integer 0-30")
        tokens.append(Token(_s(t, "symbol", w).upper(), net, _addr(net, t.get("contract"), w), dec))
    decs = {(t.network, t.symbol): t.decimals for t in tokens}
    if len(decs) != len(tokens):
        raise CaseError("tokens: the same symbol is listed twice on one network")

    def dec_of(net: str, sym: str, w: str) -> int:
        if (net, sym) not in decs:
            raise CaseError(f"{w}: {sym} on {net} is not in tokens")
        return decs[(net, sym)]

    addresses = []
    for i, a in enumerate(_list(d, "addresses", "case")):
        w = f"addresses[{i}]"
        net = _net(a.get("network"), w)
        addresses.append(
            Address(
                net,
                _addr(net, a.get("address"), w),
                _choice(a.get("role", "unknown"), ADDRESS_ROLES, w),
                _s(a, "label", w, False),
                _s(a, "service", w, False),
                _s(a, "evidence", w, False),
            )
        )

    hops = []
    for i, h in enumerate(_list(d, "hops", "case", required=True)):
        w = f"hops[{i}]"
        net = _net(h.get("network"), w)
        kind = _choice(h.get("kind", "transfer"), HOP_KINDS, w)
        sym = _s(h, "symbol", w).upper()
        to_net = _net(h["to_network"], w) if h.get("to_network") else ""
        to_sym = _s(h, "to_symbol", w, False).upper()
        if kind == "transfer" and (to_net or to_sym or "amount_out" in h):
            raise CaseError(f"{w}: a transfer has no to_network, to_symbol or amount_out")
        if kind == "bridge" and not to_net:
            raise CaseError(f"{w}: a bridge hop needs to_network")
        if kind == "swap" and not to_sym:
            raise CaseError(f"{w}: a swap hop needs to_symbol")
        out_net, out_sym = to_net or net, to_sym or sym
        tx = _s(h, "tx", w)
        if not valid_tx(net, tx):
            raise CaseError(f"{w}: {tx!r} is not a {net} transaction hash")
        hops.append(
            Hop(
                tx=tx,
                network=net,
                time=_time(h.get("time"), w),
                sender=_addr(net, h.get("from"), w),
                recipient=_addr(out_net, h.get("to"), w),
                symbol=sym,
                amount=_amount(h.get("amount"), w, dec_of(net, sym, w)),
                kind=kind,
                to_network=to_net,
                to_symbol=to_sym,
                amount_out=_amount(h["amount_out"], w, dec_of(out_net, out_sym, w))
                if "amount_out" in h
                else None,
                note=_s(h, "note", w, False),
                origin=_bool(h, "origin", w),
            )
        )

    targets = []
    for i, t in enumerate(_list(d, "targets", "case", required=True)):
        w = f"targets[{i}]"
        net = _net(t.get("network"), w)
        sym = _s(t, "symbol", w).upper()
        targets.append(
            Target(
                net,
                _addr(net, t.get("address"), w),
                sym,
                _amount(t.get("amount"), w, dec_of(net, sym, w)),
                _s(t, "reason", w),
            )
        )

    funding = []
    for i, f in enumerate(_list(d, "funding", "case")):
        w = f"funding[{i}]"
        cents = f.get("amount_cents")
        if not isinstance(cents, int) or isinstance(cents, bool) or cents <= 0:
            raise CaseError(f"{w}: amount_cents must be a positive integer")
        cur = _s(f, "currency", w)
        if not re.fullmatch(r"[A-Z]{3}", cur):
            raise CaseError(f"{w}: currency must be an ISO 4217 code")
        refs = f.get("refs", {})
        if not isinstance(refs, dict) or not all(isinstance(v, str) for v in refs.values()):
            raise CaseError(f"{w}: refs must map names to strings")
        funding.append(
            Funding(
                _choice(f.get("rail"), RAILS, w),
                _date(f.get("date"), w),
                cents,
                cur,
                _s(f, "sender_institution", w),
                _s(f, "receiver_institution", w),
                dict(refs),
                _s(f, "note", w, False),
            )
        )

    balances = []
    for i, b in enumerate(_list(d, "balances", "case")):
        w = f"balances[{i}]"
        net = _net(b.get("network"), w)
        sym = _s(b, "symbol", w).upper()
        amt = b.get("amount")
        bal = Decimal(0) if amt == "0" else _amount(amt, w, dec_of(net, sym, w))
        balances.append(
            BalanceCheck(
                net, _addr(net, b.get("address"), w), sym, bal, _time(b.get("as_of"), w), _s(b, "source", w)
            )
        )

    events = [
        Event(_time(e.get("time"), f"events[{i}]"), _s(e, "what", f"events[{i}]"))
        for i, e in enumerate(_list(d, "events", "case"))
    ]

    order = None
    if d.get("order") is not None:
        o = d["order"]
        if not isinstance(o, dict):
            raise CaseError("order must be an object")
        w = "order"
        addrs = []
        for j, a in enumerate(_list(o, "addresses", w)):
            net = _net(a.get("network"), f"{w}.addresses[{j}]")
            addrs.append((net, _addr(net, a.get("address"), f"{w}.addresses[{j}]")))
        for k in ("final", "reviewable", "attached"):
            if not isinstance(o.get(k), bool):
                raise CaseError(f"{w}: {k} must be true or false")
        order = Order(
            _choice(o.get("authority_kind"), ORDER_AUTHORITIES, w),
            _s(o, "authority", w),
            _s(o, "reference", w),
            _date(o.get("date"), w),
            bool(o["final"]),
            bool(o["reviewable"]),
            tuple(addrs),
            bool(o["attached"]),
        )

    victim = d.get("victim", {})
    if not isinstance(victim, dict) or not all(isinstance(v, str) for v in victim.values()):
        raise CaseError("victim must map names to strings")
    rep = d.get("reported_to", [])
    if not isinstance(rep, list) or not all(isinstance(x, str) for x in rep):
        raise CaseError("reported_to must be a list of strings")

    return Case(
        case_id=case_id,
        purpose=purpose,
        prepared_by={k: str(v) for k, v in pb.items()},
        prepared_on=_date(d.get("prepared_on"), "case"),
        summary=_s(d, "summary", "case"),
        tokens=tuple(tokens),
        addresses=tuple(addresses),
        hops=tuple(sorted(hops, key=lambda h: h.time)),
        targets=tuple(targets),
        funding=tuple(funding),
        balances=tuple(balances),
        events=tuple(sorted(events, key=lambda e: e.time)),
        order=order,
        victim=dict(victim),
        reported_to=tuple(rep),
    )
