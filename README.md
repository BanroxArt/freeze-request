# freeze-request

Builds the evidence package a fraud investigator sends to a stablecoin issuer's freeze team, or hands to law enforcement with a referral: the transaction chain with hashes and explorer links, the token contracts, the off-ramp points, the addresses still holding traced funds and how much, a timeline, and the legal basis spelled out. It checks the case before anything goes out, and it says plainly what the package is not: an order.

Built and maintained by Art Akopian, CEO of [Banrox](https://banrox.com).

> **Engineering checklist, not legal advice.** A stablecoin issuer freezes or blocks an address only under a lawful order or under its own published policy. This package is neither; it is the evidence that helps an issuer, an agent or a prosecutor act quickly. Tested on synthetic data only: every address, transaction hash, token contract, case number and amount in this repo is made up.

## Why

Once stolen money is turned into a stablecoin, the bank's recall tools stop working. A wire carries a UETR and can be recalled; a token transfer to a self-hosted wallet cannot. What remains is the issuer, which can block an address, and the exchanges where the funds land, which can hold an account.

The GENIUS Act (Pub. L. 119-27) requires permitted issuers to have "technical capabilities, policies, and procedures to block, freeze, and reject specific or impermissible transactions that violate Federal or State laws, rules, or regulations" (sec. 4(a)(5)(A)(iv)), and to be able to comply, and to comply, with any lawful order (sec. 4(a)(6)(B)). A lawful order must come from a court of competent jurisdiction or an authorized Federal agency, be final and valid, be open to review or appeal, and specify "the payment stablecoins or accounts subject to blocking with reasonable particularity" (sec. 2(16)). The Act takes effect on January 18, 2027.

The issuers' own policies say the same thing in their own words:

- Circle's access denial policy: Circle "will not deny access to individual addresses" except to protect the network, to comply with a law, regulation or legal order from a recognized U.S. or French authority, or in response to certain urgent law enforcement requests pending a court order, certain sanctions or national security requests, and certain orders pending the Mutual Legal Assistance Treaty process. It blocks whole addresses; "It is not possible to deny access to individual Circle Stablecoin tokens."
- Paxos's stablecoin terms: Paxos freezes if required by law on "a formal legal directive", on a formal notification from a Paxos partner under agreed terms, or "as deemed necessary or appropriate by Paxos in its sole discretion". Its PYUSD contract README says freezing "is something that Paxos will not do on its own accord".
- Tether's terms (last updated February 26, 2026): Tether may freeze tokens "as required by applicable Law or where Tether, in its sole discretion, determines it is prudent to do so".

So a bank or victim cannot get a freeze by asking. What it can do is make the request easy to act on for the people who can: law enforcement, a court, the issuer under its own policy, and the exchange that holds the account at the end of the chain. That means exact addresses, exact amounts, the token contract on the right network, how the funds got there, and whether they are still there. This tool builds that and checks it.

## What it checks

| rule | level | what it checks |
|---|---|---|
| FR-ORIGIN | block | at least one hop carries the stolen funds (marked `origin`, or sent from an address with role `victim`) |
| FR-PATH | warn | each hop is connected to the stolen funds by the hops listed |
| FR-TARGET | block / warn | each address you ask about received traced funds and is not the victim's; the amount asked for is not more than the traced funds still there |
| FR-CUSTODIAL | warn | an address you ask about belongs to an exchange, OTC desk or bridge; blocking it would hit that service's other customers, so ask the service to hold the account |
| FR-BALANCE | warn | a balance check is recorded for each address, is recent (24 hours by default), and covers the amount |
| FR-ORDER | warn / info | with no order, says what that means; with an order, checks the sec. 2(16) elements: court or Federal agency, final, open to review, copy attached |
| FR-PARTICULARITY | warn | the order names every address you ask about (sec. 2(16)(B)) |
| FR-REPORTED | warn | a request to an issuer records a report to law enforcement first |
| FR-ISSUER | info / warn | the issuer and its published policy for each token, or a warning when none is on file |

## Tracing rule

The tool follows the funds through the hops you list with one stated rule, stolen-first: when an address sends, the stolen funds it holds are counted as leaving before anything else. It counts only the hops in the case and knows nothing else about an address's balance. Swaps and bridges carry the traced share through at the rate of the hop (amount out over amount in), rounded down to the token's decimals.

That gives the most that can be traced to each address, which is the right ceiling for a request: never ask for more than that. It is not proof of where any particular coin went. Courts use several tracing rules, and an investigator or a court may apply a different one.

## Use

```sh
pip install .
freezereq check examples/case.json --now 2026-11-14T18:00:00Z
freezereq build examples/case.json --out out/                              # issuer copy
freezereq build examples/case.json --out out/ --audience law_enforcement   # full copy
freezereq issuers                                                          # policies on file
```

`build` writes `<case_id>-<audience>.json` and `.md`, with a SHA-256 over the canonical JSON. It refuses to build when a check blocks. Warnings appear in the Markdown under "Notes for the sender (remove before sending)" and are left out of the JSON. Exit codes: 0 built or clean, 2 blocked, 1 bad input. For a PDF, convert the Markdown with any tool you trust, for example `pandoc out/ECB-FRZ-2026-0007-issuer.md -o package.pdf`.

The issuer copy leaves out the victim's details and the bank payments that funded the purchase. The law enforcement copy has everything.

`examples/case.json` is a synthetic business email compromise: a $250,000 wire to a brand-new exchange account (a new-account cash-out: money moved to a brand-new account and sent straight out), bought as USDC, withdrawn, split, bridged to Base and swapped to USDT, with part sent to two exchanges. `examples/case-with-order.json` adds a court order that names only one of the two addresses, which FR-PARTICULARITY catches.

## The case file

```json
{
  "case_id": "ECB-FRZ-2026-0007",
  "purpose": "issuer_review",
  "prepared_by": {"org": "...", "contact": "..."},
  "prepared_on": "2026-11-14",
  "summary": "what happened, in plain words",
  "tokens": [{"symbol": "USDC", "network": "base", "contract": "0x...", "decimals": 6}],
  "addresses": [{"network": "base", "address": "0x...", "role": "suspect", "service": "", "evidence": ""}],
  "hops": [{"tx": "0x...", "network": "ethereum", "time": "2026-11-12T19:42:11Z", "from": "0x...", "to": "0x...",
            "symbol": "USDC", "amount": "249000", "origin": true}],
  "targets": [{"network": "base", "address": "0x...", "symbol": "USDC", "amount": "129985.5", "reason": "..."}],
  "balances": [{"network": "base", "address": "0x...", "symbol": "USDC", "amount": "129985.5",
                "as_of": "2026-11-14T16:00:00Z", "source": "where you looked"}],
  "funding": [], "events": [], "order": null, "victim": {}, "reported_to": []
}
```

Amounts are decimal strings in token units, never floats. Times need an offset and are shown in UTC. Hops of kind `bridge` take `to_network` and `amount_out`; hops of kind `swap` take `to_symbol` and `amount_out`. Networks: Ethereum, Base, Arbitrum One, Polygon PoS, Tron and Solana, with address and hash formats checked for each.

## What is real and what is not

- Real: the quoted text of the GENIUS Act, and the issuers' published policies as of the dates in [docs/sources.md](docs/sources.md). Issuers change these documents; `freezereq issuers` prints what is on file and when it was checked.
- Not real: everything in `examples/`. The token contracts there are made up too; use the contract addresses the issuer publishes.
- The tool never queries a blockchain or an explorer. Balances are what you record, with the time and where you looked. Explorer links are there for the reader.
- The tool does not send anything to anyone.
- Several issuers have more channels than their public terms describe. The tool lists only what the public documents say.
- The GENIUS Act's lawful-order provisions apply to permitted issuers once the Act is in force. Before January 18, 2027, issuers act under their own terms and the law that already applies to them.

## Development

```sh
pip install -e ".[dev]"
ruff check . && ruff format --check . && python scripts/check.py && mypy && pytest -q
python bench/run.py
```

## License

MIT. Copyright (c) 2026 Banrox Inc.
