"""Build the evidence package: JSON for systems, Markdown for people."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from decimal import Decimal
from typing import Any

from .case import Case
from .checks import GENIUS, Review
from .issuers import for_token
from .networks import NETWORKS, key
from .trace import RULE

FORMAT = "freeze-request/1"
AUDIENCES = ("issuer", "law_enforcement")
GENIUS_URL = "https://www.congress.gov/119/plaws/publ27/PLAW-119publ27.htm"

STATEMENT = (
    "This package is evidence, not an order. A stablecoin issuer freezes or blocks an address only under "
    "a lawful order or its own published policy. Nothing here obliges the issuer to act, and the sender "
    "does not claim that it does."
)

_S4 = (
    "Permitted issuers must have 'technical capabilities, policies, and procedures to block, freeze, and "
    "reject specific or impermissible transactions that violate Federal or State laws, rules, or "
    "regulations'."
)
_S46 = (
    "A permitted issuer may issue payment stablecoins only if it 'has the technological capability to "
    "comply, and will comply, with the terms of any lawful order'."
)
_S216 = (
    "A lawful order is a final and valid order under Federal law from a court of competent jurisdiction "
    "or an authorized Federal agency that requires the issuer to seize, freeze, burn, or prevent the "
    "transfer of its stablecoins, 'specifies the payment stablecoins or accounts subject to blocking with "
    "reasonable particularity', and is subject to judicial or administrative review or appeal."
)
_FORCE = (
    "The Act takes effect on January 18, 2027 (18 months after enactment; 120 days after the OCC's "
    "October 23, 2026 final rule falls later). Before then, issuers act under their own terms and the law "
    "that already applies to them."
)
LEGAL = {
    "statement": STATEMENT,
    "genius_act": {
        "citation": GENIUS,
        "url": GENIUS_URL,
        "sec_4_a_5_A_iv": _S4,
        "sec_4_a_6_B": _S46,
        "sec_2_16": _S216,
        "in_force": _FORCE,
    },
}


def _dec(x: Decimal) -> str:
    return format(x.normalize(), "f")


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _iso(t: dt.datetime) -> str:
    return t.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def timeline(case: Case, audience: str) -> list[dict[str, str]]:
    rows: list[tuple[str, str]] = []
    if audience == "law_enforcement":
        for f in case.funding:
            rows.append(
                (
                    f.date.isoformat(),
                    f"{f.rail} {f.amount_cents / 100:,.2f} {f.currency} from {f.sender_institution} to "
                    f"{f.receiver_institution}",
                )
            )
    for h in case.hops:
        rows.append((_iso(h.time), f"{h.kind} {_dec(h.amount)} {h.symbol} on {h.network} to {h.recipient}"))
    for e in case.events:
        rows.append((_iso(e.time), e.what))
    for b in case.balances:
        rows.append(
            (_iso(b.as_of), f"balance check: {b.address} held {_dec(b.amount)} {b.symbol} ({b.source})")
        )
    if case.order is not None:
        rows.append(
            (case.order.date.isoformat(), f"order {case.order.reference} issued by {case.order.authority}")
        )
    rows.sort(key=lambda r: r[0])
    return [{"time": t, "what": w} for t, w in rows]


def document(case: Case, rv: Review, audience: str) -> dict[str, Any]:
    if audience not in AUDIENCES:
        raise ValueError(f"audience must be one of {AUDIENCES}")
    tr = rv.trace
    roles = {key(a.network, a.address): a for a in case.addresses}

    def addr_info(net: str, a: str) -> dict[str, str]:
        r = roles.get(key(net, a))
        d = {"network": net, "address": a, "explorer": NETWORKS[net].address_url.format(a)}
        if r is not None:
            d.update(role=r.role, label=r.label, service=r.service, evidence=r.evidence)
        return {k: v for k, v in d.items() if v}

    hops = []
    for th in tr.hops:
        h = th.hop
        d: dict[str, Any] = {
            "tx": h.tx,
            "explorer": NETWORKS[h.network].tx_url.format(h.tx),
            "network": h.network,
            "time": _iso(h.time),
            "kind": h.kind,
            "from": h.sender,
            "to": h.recipient,
            "symbol": h.symbol,
            "amount": _dec(h.amount),
            "traced": _dec(th.traced_in),
        }
        if h.kind != "transfer":
            d.update(to_network=h.out_network, to_symbol=h.out_symbol, amount_out=_dec(h.received))
        if h.note:
            d["note"] = h.note
        hops.append(d)

    offramps = []
    for (net, ak, sym), amt in sorted(tr.received.items()):
        r = roles.get((net, ak))
        if r is not None and r.role in ("exchange_deposit", "otc", "bridge"):
            offramps.append({**addr_info(net, r.address), "symbol": sym, "traced_in": _dec(amt)})

    targets = []
    for t in case.targets:
        rec, rem = tr.at(t.network, t.address, t.symbol)
        tok = case.token(t.network, t.symbol)
        assert tok is not None
        issuer = for_token(t.symbol)
        bals = [b for b in case.balances if key(b.network, b.address) == key(t.network, t.address)]
        last = max(bals, key=lambda b: b.as_of) if bals else None
        targets.append(
            {
                **addr_info(t.network, t.address),
                "symbol": t.symbol,
                "contract": tok.contract,
                "chain_id": NETWORKS[t.network].chain_id,
                "requested": _dec(t.amount),
                "traced_in": _dec(rec),
                "traced_remaining": _dec(rem),
                "last_balance": None
                if last is None
                else {"amount": _dec(last.amount), "as_of": _iso(last.as_of), "source": last.source},
                "issuer": issuer.name if issuer else None,
                "reason": t.reason,
            }
        )

    issuers: list[dict[str, Any]] = []
    for sym in sorted({t.symbol for t in case.targets}):
        i = for_token(sym)
        if i is not None and all(x["name"] != i.name for x in issuers):
            issuers.append(
                {
                    "name": i.name,
                    "tokens": list(i.tokens),
                    "acts_on": list(i.acts_on),
                    "own_discretion": i.own_discretion,
                    "granularity": i.granularity,
                    "onchain_check": i.onchain_check,
                    "contact": i.contact,
                    "sources": list(i.sources),
                    "checked": i.checked,
                }
            )

    order = None
    if case.order is not None:
        o = case.order
        order = {
            "authority_kind": o.authority_kind,
            "authority": o.authority,
            "reference": o.reference,
            "date": o.date.isoformat(),
            "final": o.final,
            "reviewable": o.reviewable,
            "attached": o.attached,
            "addresses": [{"network": n, "address": a} for n, a in o.addresses],
        }

    body: dict[str, Any] = {
        "format": FORMAT,
        "audience": audience,
        "case_id": case.case_id,
        "prepared_by": case.prepared_by,
        "prepared_on": case.prepared_on.isoformat(),
        "summary": case.summary,
        "legal_basis": LEGAL,
        "order": order,
        "reported_to": list(case.reported_to),
        "tokens": [
            {
                "symbol": t.symbol,
                "network": t.network,
                "chain_id": NETWORKS[t.network].chain_id,
                "contract": t.contract,
                "decimals": t.decimals,
                "issuer": (i.name if (i := for_token(t.symbol)) else None),
            }
            for t in case.tokens
        ],
        "tracing_rule": RULE,
        "stolen_at_origin": [
            {"network": n, "symbol": s, "amount": _dec(a)} for (n, s), a in sorted(tr.total_origin.items())
        ],
        "hops": hops,
        "offramps": offramps,
        "targets": targets,
        "issuer_policies": issuers,
        "timeline": timeline(case, audience),
        "findings": [
            {"rule": f.rule, "level": f.level, "message": f.message, "source": f.source}
            for f in rv.findings
            if f.level != "warn"
        ],
    }
    if audience == "law_enforcement":
        body["victim"] = case.victim
        body["funding"] = [
            {
                "rail": f.rail,
                "date": f.date.isoformat(),
                "amount_cents": f.amount_cents,
                "currency": f.currency,
                "sender_institution": f.sender_institution,
                "receiver_institution": f.receiver_institution,
                "refs": f.refs,
                "note": f.note,
            }
            for f in case.funding
        ]
    body["sha256"] = hashlib.sha256(canonical(body)).hexdigest()
    return body


def _table(head: list[str], rows: list[list[str]]) -> list[str]:
    def cell(x: str) -> str:
        return x.replace("|", "\\|").replace("\n", " ")

    return [
        "| " + " | ".join(head) + " |",
        "|" + "---|" * len(head),
        *("| " + " | ".join(cell(c) for c in r) + " |" for r in rows),
    ]


def _balance(b: dict[str, str] | None) -> str:
    return "not checked" if b is None else f"{b['amount']} at {b['as_of']} ({b['source']})"


def markdown(doc: dict[str, Any], rv: Review) -> str:
    who = "stablecoin issuer review" if doc["audience"] == "issuer" else "law enforcement referral"
    L = [
        f"# Freeze evidence package {doc['case_id']} ({who})",
        "",
        f"Prepared by {doc['prepared_by']['org']} ({doc['prepared_by']['contact']}) on {doc['prepared_on']}.",
        f"SHA-256 of the JSON copy: `{doc['sha256']}`",
        "",
        f"> {STATEMENT}",
        "",
        "## Summary",
        "",
        doc["summary"],
        "",
    ]
    warns = [f for f in rv.findings if f.level == "warn"]
    if warns:
        L += ["## Notes for the sender (remove before sending)", ""]
        L += [f"- {f.rule}: {f.message}" + (f" ({f.source})" if f.source else "") for f in warns]
        L.append("")
    L += ["## What we ask", ""]
    L += _table(
        [
            "network",
            "token and contract",
            "address",
            "requested",
            "traced in",
            "traced still there",
            "last balance",
        ],
        [
            [
                t["network"],
                f"{t['symbol']} `{t['contract']}`",
                f"`{t['address']}`" + (f" ({t['role'].replace('_', ' ')})" if t.get("role") else ""),
                t["requested"],
                t["traced_in"],
                t["traced_remaining"],
                _balance(t["last_balance"]),
            ]
            for t in doc["targets"]
        ],
    )
    L.append("")
    for t in doc["targets"]:
        L.append(f"- `{t['address']}`: {t['reason']}")
    L += ["", "## Legal basis", ""]
    g = doc["legal_basis"]["genius_act"]
    L += [
        f"- {g['citation']} sec. 4(a)(5)(A)(iv): {g['sec_4_a_5_A_iv']}",
        f"- Sec. 4(a)(6)(B): {g['sec_4_a_6_B']}",
        f"- Sec. 2(16): {g['sec_2_16']}",
        f"- In force: {g['in_force']}",
        f"- Text: {g['url']}",
        "",
    ]
    o = doc["order"]
    if o is None:
        L += ["No lawful order accompanies this package.", ""]
    else:
        L += [
            f"Order {o['reference']}, {o['authority']} ({o['authority_kind'].replace('_', ' ')}), "
            f"{o['date']}. Final: {'yes' if o['final'] else 'no'}. Subject to review or appeal: "
            f"{'yes' if o['reviewable'] else 'no'}. Copy attached: {'yes' if o['attached'] else 'no'}.",
            "Addresses the order names: "
            + ", ".join(f"`{a['address']}` ({a['network']})" for a in o["addresses"]),
            "",
        ]
    if doc["reported_to"]:
        L += ["Reported to: " + "; ".join(doc["reported_to"]), ""]
    for i in doc["issuer_policies"]:
        L += [f"### {i['name']} ({', '.join(i['tokens'])}): published policy, checked {i['checked']}", ""]
        L += ["Acts on:"] + [f"- {x}" for x in i["acts_on"]]
        L += ["", i["own_discretion"], "", f"Granularity: {i['granularity']}"]
        if i["onchain_check"]:
            L.append(f"On-chain check: {i['onchain_check']}")
        L += [f"Contact: {i['contact']}", "Sources: " + " ; ".join(i["sources"]), ""]
    L += ["## Tokens", ""]
    L += _table(
        ["token", "network", "chain id", "contract", "issuer"],
        [
            [
                t["symbol"],
                t["network"],
                str(t["chain_id"] or ""),
                f"`{t['contract']}`",
                t["issuer"] or "unknown",
            ]
            for t in doc["tokens"]
        ],
    )
    L += ["", "## Transaction chain", "", f"Tracing rule: {doc['tracing_rule']}.", ""]
    L += [
        "Stolen funds at the start: "
        + ", ".join(f"{x['amount']} {x['symbol']} on {x['network']}" for x in doc["stolen_at_origin"]),
        "",
    ]
    L += _table(
        ["time (UTC)", "network", "kind", "from", "to", "amount", "traced", "tx"],
        [
            [
                h["time"].replace("T", " ").rstrip("Z"),
                h["network"]
                + (f" to {h['to_network']}" if h.get("to_network", h["network"]) != h["network"] else ""),
                h["kind"],
                f"`{h['from']}`",
                f"`{h['to']}`",
                f"{h['amount']} {h['symbol']}"
                + (f" ({h['amount_out']} {h['to_symbol']} out)" if h["kind"] != "transfer" else ""),
                h["traced"],
                f"[`{h['tx'][:14]}...`]({h['explorer']})",
            ]
            for h in doc["hops"]
        ],
    )
    L += ["", "## Off-ramp points", ""]
    if doc["offramps"]:
        L += _table(
            ["address", "kind", "service", "traced in", "evidence"],
            [
                [
                    f"`{x['address']}` ({x['network']})",
                    x.get("role", "").replace("_", " "),
                    x.get("service", ""),
                    f"{x['traced_in']} {x['symbol']}",
                    x.get("evidence", ""),
                ]
                for x in doc["offramps"]
            ],
        )
    else:
        L.append("None identified in the hops listed.")
    if doc["audience"] == "law_enforcement":
        L += ["", "## Victim and fiat leg", ""]
        L += [f"- {k}: {v}" for k, v in doc["victim"].items()] or ["- not given"]
        for f in doc["funding"]:
            refs = ", ".join(f"{k} {v}" for k, v in f["refs"].items())
            L.append(
                f"- {f['date']}: {f['rail']} {f['amount_cents'] / 100:,.2f} {f['currency']}, "
                f"{f['sender_institution']} to {f['receiver_institution']}"
                + (f" ({refs})" if refs else "")
                + (f". {f['note']}" if f["note"] else "")
            )
    else:
        L += ["", "Victim details and the bank payments that funded the purchase are left out of this copy."]
    L += ["", "## Timeline (UTC)", ""]
    L += [f"- {r['time'].replace('T', ' ').rstrip('Z')}: {r['what']}" for r in doc["timeline"]]
    info = [f for f in doc["findings"] if f["level"] == "info"]
    if info:
        L += ["", "## Checks", ""]
        L += [f"- {f['rule']}: {f['message']}" + (f" ({f['source']})" if f["source"] else "") for f in info]
    L += ["", "Prepared with freeze-request, an engineering checklist, not legal advice.", ""]
    return "\n".join(L)
