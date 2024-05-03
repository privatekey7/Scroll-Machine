from dataclasses import dataclass
from typing import Optional

from config import (
    ARBITRUM_RPC_ENDPOINT,
    MAINNET_RPC_ENDPOINT,
    SCROLL_RPC_ENDPOINT,
    ZKSYNC_RPC_ENDPOINT, LINEA_RPC_ENDPOINT,
)


@dataclass
class Chain:
    name: str
    chain_id: int
    coin_symbol: str
    explorer: str
    rpc: str
    orbiter_chain_id: int
    okx_chain_name: Optional[str] = None
    okx_withdrawal_fee: Optional[str] = None


SCROLL = Chain(
    name="SCROLL",
    chain_id=534352,
    coin_symbol="ETH",
    explorer="https://scrollscan.com/",
    rpc=SCROLL_RPC_ENDPOINT,
    orbiter_chain_id=19,
)

ZKSYNC = Chain(
    name="ZKSYNC",
    chain_id=324,
    coin_symbol="ETH",
    explorer="https://explorer.zksync.io/",
    rpc=ZKSYNC_RPC_ENDPOINT,
    orbiter_chain_id=14,
    okx_chain_name="zkSync Era",
    okx_withdrawal_fee="0.000041",
)

ARBITRUM = Chain(
    name="ARBITRUM",
    chain_id=42161,
    coin_symbol="ETH",
    explorer="https://arbiscan.io/",
    rpc=ARBITRUM_RPC_ENDPOINT,
    orbiter_chain_id=2,
    okx_chain_name="Arbitrum One",
    okx_withdrawal_fee="0.0001",
)

LINEA = Chain(
    name="LINEA",
    chain_id=59144,
    coin_symbol="ETH",
    explorer="https://lineascan.build/",
    rpc=LINEA_RPC_ENDPOINT,
    orbiter_chain_id=23,
    okx_chain_name="Linea",
    okx_withdrawal_fee="0.0002"
)

MAINNET = Chain(
    name="MAINNET",
    chain_id=1,
    coin_symbol="ETH",
    explorer="https://etherscan.io/",
    rpc=MAINNET_RPC_ENDPOINT,
    orbiter_chain_id=1,
    okx_chain_name="ERC20",
    okx_withdrawal_fee="0.0036",
)

NAMES_TO_CHAINS = {
    MAINNET.name: MAINNET,
    SCROLL.name: SCROLL,
    ZKSYNC.name: ZKSYNC,
    ARBITRUM.name: ARBITRUM,
    LINEA.name: LINEA
}
