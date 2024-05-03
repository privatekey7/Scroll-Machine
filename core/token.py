from dataclasses import dataclass
from typing import Dict, Optional, Union

from .constants import (
    ERC20_CONTRACT_ABI,
    LETH_CONTRACT_ADDRESS,
    USDC_CONTRACT_ADDRESS,
    USDT_CONTRACT_ADDRESS,
    WETH_CONTRACT_ABI,
    WETH_CONTRACT_ADDRESS,
    COG_FINANCE_USDC_WETH_POOL_CONTRACT_ADDRESS,
    COG_FINANCE_USDC_WETH_POOL_CONTRACT_ABI,
)


@dataclass
class Token:
    symbol: str
    decimals: int
    is_stable: bool
    is_native: bool
    api_id: str
    contract_address: Optional[str] = None
    abi: Optional[Dict] = None
    round_to: int = None

    def to_wei(self, value: Union[int, float]) -> int:
        return int(value * pow(10, self.decimals))

    def from_wei(self, value: int) -> float:
        return value / pow(10, self.decimals)

    def __repr__(self) -> str:
        return self.symbol

    def __str__(self) -> str:
        return self.symbol

    def __hash__(self):
        return hash(self.symbol)

    def __eq__(self, other):
        if isinstance(other, Token):
            return self.symbol == other.symbol
        return False


ETH = Token(
    symbol="ETH",
    decimals=18,
    is_stable=False,
    is_native=True,
    api_id="80",
    round_to=6,
)

USDC = Token(
    symbol="USDC",
    decimals=6,
    contract_address=USDC_CONTRACT_ADDRESS,
    abi=ERC20_CONTRACT_ABI,
    is_stable=True,
    is_native=False,
    api_id="33285",
    round_to=3,
)

USDT = Token(
    symbol="USDT",
    decimals=6,
    contract_address=USDT_CONTRACT_ADDRESS,
    abi=ERC20_CONTRACT_ABI,
    is_stable=True,
    is_native=False,
    api_id="518",
    round_to=3,
)

WETH = Token(
    symbol="WETH",
    decimals=18,
    abi=WETH_CONTRACT_ABI,
    contract_address=WETH_CONTRACT_ADDRESS,
    is_stable=False,
    is_native=False,
    api_id="80",
    round_to=6,
)

LETH = Token(
    symbol="lETH",
    decimals=18,
    is_stable=False,
    is_native=False,
    api_id="80",
    contract_address=LETH_CONTRACT_ADDRESS,
    abi=ERC20_CONTRACT_ABI,
)

COG_WETH = Token(
    symbol="COG",
    decimals=18,
    is_stable=False,
    is_native=False,
    api_id="80",
    contract_address=COG_FINANCE_USDC_WETH_POOL_CONTRACT_ADDRESS,
    abi=COG_FINANCE_USDC_WETH_POOL_CONTRACT_ABI,
)

SYMBOLS_TO_TOKENS = {
    "ETH": ETH,
    "USDC": USDC,
    "USDT": USDT,
    "WETH": WETH,
    "lETH": LETH,
    "COG": COG_WETH
}
