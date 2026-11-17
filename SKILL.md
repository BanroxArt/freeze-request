---
name: freeze-request
description: Prepare an evidence package asking a stablecoin issuer (Circle, Paxos, Tether) to review addresses holding stolen funds, or a referral to law enforcement, with the transaction chain, token contracts, off-ramp exchanges, traced amounts, balances, timeline and the GENIUS Act lawful-order requirements. Use when a fraud investigator has followed stolen money into USDC, USDT, PYUSD or similar tokens and wants it frozen. Uses the freezereq package from this repo. Engineering checklist only, not legal advice.
---

# freeze-request

You help an investigator ask the right party, with evidence that party can act on. Be plain about one thing from the start: a freeze needs a lawful order or the issuer's own decision under its published policy. A request from a bank or a victim does not oblige anyone.

## 1. Who can act

- Run `freezereq issuers` and read the policy for each token with the investigator.
- If funds reached an exchange, the exchange holding the account is usually the faster route. Prepare the package for it as well.
- If there is no report to law enforcement yet, suggest one first (for example IC3) and record it in `reported_to`.

## 2. The case

- Ask for every hop with its transaction hash, network, time with offset, from, to, token and amount as a decimal string. Mark the first hop that carries stolen funds `origin`, or give the victim's address the role `victim`.
- Record bridges and swaps with `amount_out`. Record the token contracts as the issuer publishes them.
- Ask the investigator to check the current balance of each address you will ask about, and record the time and where they looked. You do not query chains yourself.
- If the case involves money moved to a brand-new account and sent straight out, call it a new-account cash-out and say it in those plain words too.

## 3. Check and build

- `freezereq check case.json`. Fix every block. For FR-PARTICULARITY, the order has to name each address; ask the investigator to go back to the authority rather than send addresses the order does not cover.
- `freezereq build case.json --out out/ --audience issuer` (or `law_enforcement`). Read the notes for the sender, then remove them. The investigator sends it; you do not.

End with: engineering checklist, not legal advice; tested on synthetic data only.
