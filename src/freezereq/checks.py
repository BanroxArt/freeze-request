"""Checks run on a case before the package goes out.

Levels: block (the package is not built), warn (printed in the notes for the
sender), info (kept in the package).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from .case import Case
from .issuers import for_token
from .networks import key, same_address
from .trace import Trace, trace

GENIUS = "GENIUS Act, Pub. L. 119-27"
SERVICE_ROLES = ("exchange_deposit", "otc", "bridge")


@dataclass(frozen=True)
class Finding:
    rule: str
    level: str
    message: str
    source: str = ""


@dataclass(frozen=True)
class Review:
    findings: tuple[Finding, ...]
    trace: Trace

    @property
    def blocked(self) -> bool:
        return any(f.level == "block" for f in self.findings)


def review(case: Case, now: dt.datetime | None = None, max_balance_age_h: float = 24.0) -> Review:
    now = now or dt.datetime.now(dt.UTC)
    tr = trace(case)
    out: list[Finding] = []
    roles = {key(a.network, a.address): a for a in case.addresses}

    if not tr.total_origin:
        out.append(
            Finding(
                "FR-ORIGIN",
                "block",
                "no hop carries stolen funds: mark the first hop `origin` or give the victim's address "
                "the role `victim`",
            )
        )
    for th in tr.hops:
        if not th.connected:
            h = th.hop
            out.append(
                Finding(
                    "FR-PATH",
                    "warn",
                    f"{h.tx[:12]}... on {h.network}: {h.sender} holds no traced funds when it sends; this "
                    "hop is not connected to the stolen funds by the hops listed",
                )
            )

    seen_issuers = set()
    for t in case.targets:
        rec, rem = tr.at(t.network, t.address, t.symbol)
        where = f"{t.symbol} {t.address} on {t.network}"
        if rec == 0:
            out.append(Finding("FR-TARGET", "block", f"{where}: no traced funds reached this address"))
        elif t.amount > rem:
            out.append(
                Finding(
                    "FR-TARGET",
                    "warn",
                    f"{where}: asks for {t.amount}, but at most {rem} of the traced funds are still there "
                    f"({rec} arrived)",
                )
            )
        a = roles.get(key(t.network, t.address))
        if a is not None and a.role in SERVICE_ROLES:
            svc = a.service or "the service"
            out.append(
                Finding(
                    "FR-CUSTODIAL",
                    "warn",
                    f"{where} is a {a.role.replace('_', ' ')} address of {svc}. Blocking it would also hit "
                    f"the service's other customers; send this package to {svc} and ask it to hold the "
                    "account",
                )
            )
        if a is not None and a.role == "victim":
            out.append(Finding("FR-TARGET", "block", f"{where} is marked as the victim's address"))
        issuer = for_token(t.symbol)
        if issuer is None:
            out.append(
                Finding(
                    "FR-ISSUER",
                    "warn",
                    f"{t.symbol}: no published freeze policy on file; check the issuer's terms",
                )
            )
        elif issuer.key not in seen_issuers:
            seen_issuers.add(issuer.key)
            out.append(
                Finding("FR-ISSUER", "info", f"{t.symbol} is issued by {issuer.name}", issuer.sources[0])
            )
        bals = [
            b
            for b in case.balances
            if b.network == t.network
            and b.symbol == t.symbol
            and same_address(t.network, b.address, t.address)
        ]
        if not bals:
            out.append(
                Finding(
                    "FR-BALANCE",
                    "warn",
                    f"{where}: no balance check recorded; look it up and add it with the time and source",
                )
            )
        else:
            b = max(bals, key=lambda x: x.as_of)
            age = (now - b.as_of).total_seconds() / 3600
            if age > max_balance_age_h:
                out.append(
                    Finding(
                        "FR-BALANCE", "warn", f"{where}: balance checked {age:.0f} hours ago; check again"
                    )
                )
            if b.amount == 0:
                out.append(
                    Finding(
                        "FR-BALANCE",
                        "warn",
                        f"{where}: held nothing at {b.as_of:%Y-%m-%d %H:%M} UTC; follow the funds to where "
                        "they went",
                    )
                )
            elif b.amount < t.amount:
                out.append(
                    Finding(
                        "FR-BALANCE", "warn", f"{where}: holds {b.amount}, less than the {t.amount} asked for"
                    )
                )

    o = case.order
    if o is None:
        lvl = "warn" if case.purpose == "issuer_review" else "info"
        out.append(
            Finding(
                "FR-ORDER",
                lvl,
                "no lawful order. The issuer can act only under its own published policy, and most "
                "policies name legal orders and law enforcement requests, not private requests",
                f"{GENIUS}, sec. 2(16) and sec. 4(a)(6)(B)",
            )
        )
        if case.purpose == "issuer_review" and not case.reported_to:
            out.append(
                Finding(
                    "FR-REPORTED",
                    "warn",
                    "no report to law enforcement recorded. Issuers' policies turn on law enforcement "
                    "requests and orders; report first (for example to the FBI at ic3.gov) and list it in "
                    "reported_to",
                )
            )
    else:
        if o.authority_kind not in ("court", "federal_agency"):
            out.append(
                Finding(
                    "FR-ORDER",
                    "warn",
                    f"issued by a {o.authority_kind.replace('_', ' ')}. The Act's definition covers orders "
                    "under Federal law from a court of competent jurisdiction or an authorized Federal "
                    "agency; the issuer may still act under its own policy",
                    f"{GENIUS}, sec. 2(16)",
                )
            )
        if not o.final:
            out.append(
                Finding(
                    "FR-ORDER", "warn", "the order is not marked final and valid", f"{GENIUS}, sec. 2(16)"
                )
            )
        if not o.reviewable:
            out.append(
                Finding(
                    "FR-ORDER",
                    "warn",
                    "the order is not marked as subject to judicial or administrative review or appeal",
                    f"{GENIUS}, sec. 2(16)(C)",
                )
            )
        if not o.attached:
            out.append(
                Finding("FR-ORDER", "warn", "attach a copy of the order; the package only describes it")
            )
        named = {key(n, a) for n, a in o.addresses}
        for t in case.targets:
            if key(t.network, t.address) not in named:
                out.append(
                    Finding(
                        "FR-PARTICULARITY",
                        "warn",
                        f"the order does not name {t.address} on {t.network}; an order must specify the "
                        "coins or accounts with reasonable particularity, so the issuer may not act on "
                        "this address",
                        f"{GENIUS}, sec. 2(16)(B)",
                    )
                )
    return Review(tuple(out), tr)
