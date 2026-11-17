"""Networks the kit knows: address and hash formats, and an explorer for links.

Explorer links are for the reader's convenience. The kit never fetches them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


@dataclass(frozen=True)
class Network:
    key: str
    family: str  # evm, tron, solana
    name: str
    chain_id: int | None
    tx_url: str
    address_url: str


NETWORKS: dict[str, Network] = {
    n.key: n
    for n in (
        Network(
            "ethereum", "evm", "Ethereum", 1, "https://etherscan.io/tx/{}", "https://etherscan.io/address/{}"
        ),
        Network("base", "evm", "Base", 8453, "https://basescan.org/tx/{}", "https://basescan.org/address/{}"),
        Network(
            "arbitrum",
            "evm",
            "Arbitrum One",
            42161,
            "https://arbiscan.io/tx/{}",
            "https://arbiscan.io/address/{}",
        ),
        Network(
            "polygon",
            "evm",
            "Polygon PoS",
            137,
            "https://polygonscan.com/tx/{}",
            "https://polygonscan.com/address/{}",
        ),
        Network(
            "tron",
            "tron",
            "Tron",
            None,
            "https://tronscan.org/#/transaction/{}",
            "https://tronscan.org/#/address/{}",
        ),
        Network(
            "solana", "solana", "Solana", None, "https://solscan.io/tx/{}", "https://solscan.io/account/{}"
        ),
    )
}

_ADDR = {
    "evm": re.compile(r"^0x[0-9a-fA-F]{40}$"),
    "tron": re.compile(rf"^T[{_B58}]{{33}}$"),
    "solana": re.compile(rf"^[{_B58}]{{32,44}}$"),
}
_TX = {
    "evm": re.compile(r"^0x[0-9a-fA-F]{64}$"),
    "tron": re.compile(r"^[0-9a-fA-F]{64}$"),
    "solana": re.compile(rf"^[{_B58}]{{64,90}}$"),
}


def valid_address(network: str, address: str) -> bool:
    return bool(_ADDR[NETWORKS[network].family].match(address))


def valid_tx(network: str, tx: str) -> bool:
    return bool(_TX[NETWORKS[network].family].match(tx))


def same_address(network: str, a: str, b: str) -> bool:
    """EVM addresses compare without case; base58 addresses are case-sensitive."""
    if NETWORKS[network].family == "evm":
        return a.lower() == b.lower()
    return a == b


def key(network: str, address: str) -> tuple[str, str]:
    return (network, address.lower() if NETWORKS[network].family == "evm" else address)
