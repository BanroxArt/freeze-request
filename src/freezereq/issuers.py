"""What each issuer says in public about freezing or blocking, with the source.

Every entry quotes or closely paraphrases the issuer's own published terms or
policy, checked on the date in `checked`. Issuers change these documents;
check again before relying on an entry. The on-chain check is the view
function an analyst can call to see whether an address is already blocked.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Issuer:
    key: str
    name: str
    tokens: tuple[str, ...]
    acts_on: tuple[str, ...]
    own_discretion: str
    granularity: str
    onchain_check: str | None
    contact: str
    sources: tuple[str, ...]
    checked: str


ISSUERS: dict[str, Issuer] = {
    i.key: i
    for i in (
        Issuer(
            key="circle",
            name="Circle Internet Financial",
            tokens=("USDC", "EURC"),
            acts_on=(
                "a law, regulation, or legal order from a duly recognized U.S. or French authority, court "
                "of competent jurisdiction, or other governmental authority with jurisdiction over Circle",
                "certain urgent law enforcement requests pending a valid court order",
                "certain government requests based on sanctions-related activity or imminent national "
                "security threats",
                "certain court orders pending completion of the Mutual Legal Assistance Treaty process",
                "a threat to the security, integrity, or reliability of the network, such as compromised "
                "privileged keys",
            ),
            own_discretion=(
                "The access denial policy says Circle will not deny access to individual addresses except "
                "in the listed circumstances. A request from a bank or a victim alone is not one of them."
            ),
            granularity=(
                "Whole addresses only: 'It is not possible to deny access to individual Circle Stablecoin "
                "tokens.' A blocked address can neither send nor receive."
            ),
            onchain_check="isBlacklisted(address) on the token contract (stablecoin-evm Blacklistable.sol)",
            contact="Through law enforcement or the authority issuing the order; Circle's policy names no "
            "channel for private requests.",
            sources=(
                "https://6778953.fs1.hubspotusercontent-na1.net/hubfs/6778953/Blog%20Posts/Circle%20Stablecoin%20Access%20Denial%20Policy_pdf.pdf",
                "https://www.circle.com/legal/usdc-terms",
                "https://github.com/circlefin/stablecoin-evm/blob/master/contracts/v1/Blacklistable.sol",
            ),
            checked="2026-11-16",
        ),
        Issuer(
            key="paxos",
            name="Paxos",
            tokens=("PYUSD", "USDP", "USDG"),
            acts_on=(
                "a formal legal directive from a regulator, judicial body, law enforcement agency, or "
                "other legal entity having jurisdiction over Paxos (court-ordered subpoenas, national "
                "security letters, formal written directives from a regulator)",
                "a formal notification by a Paxos partner under previously agreed contractual terms",
            ),
            own_discretion=(
                "The stablecoin terms also allow a freeze 'as deemed necessary or appropriate by Paxos in "
                "its sole discretion'. The PYUSD contract README says freezing 'is something that Paxos "
                "will not do on its own accord'. Seizure needs a binding legal directive."
            ),
            granularity="Per address: the asset protection role can freeze an address and, once frozen, wipe "
            "it.",
            onchain_check="isFrozen(address) on the token contract (pyusd-contract README)",
            contact="Sec. 3.5 of the terms gives one address for reporting improper conduct and another "
            "for law enforcement information requests.",
            sources=(
                "https://www.paxos.com/terms-and-conditions/stablecoin-terms-conditions",
                "https://github.com/paxosglobal/pyusd-contract",
            ),
            checked="2026-11-16",
        ),
        Issuer(
            key="tether",
            name="Tether",
            tokens=("USDT",),
            acts_on=(
                "applicable law",
                "Tether's own determination that it is prudent, or that the holder breached the terms",
            ),
            own_discretion=(
                "The terms let Tether freeze tokens 'as required by applicable Law or where Tether, in "
                "its sole discretion, determines it is prudent to do so', and list blacklisting addresses "
                "as a possible sanction for prohibited use."
            ),
            granularity="Addresses ('blacklisting any Digital Tokens Address which holds Tether Tokens').",
            onchain_check=None,
            contact="Not stated in the terms page we checked.",
            sources=("https://tether.to/en/legal/",),
            checked="2026-11-16",
        ),
    )
}


def for_token(symbol: str) -> Issuer | None:
    for i in ISSUERS.values():
        if symbol.upper() in i.tokens:
            return i
    return None
