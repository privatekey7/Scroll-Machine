from typing import Optional

from web3 import Web3, AsyncWeb3
from web3.contract import AsyncContract

from core.chain import SCROLL
from core.decorators import gas_delay
from core.token import ETH
from logger import logger
from core import Client
from core.constants import (
    SCROLL_BRIDGE_CONTRACT_ADDRESS,
    SCROLL_BRIDGE_CONTRACT_ABI,
    SCROLL_BRIDGE_TX_SIMULATION_VALUE,
    SCROLL_BRIDGE_RECEIVE_GAS_LIMIT,
    SCROLL_GAS_PRICE_MULTIPLIER,
    SCROLL_MESSAGE,
    SCROLL_BRIDGE_FULL_BRIDGE_GAS_MULTIPLIER,
)
from utils import get_chain_gas_price


class ScrollBridge:
    def __init__(self, client: Client):
        self.client: Client = client
        self.messenger: AsyncContract = self.client.w3.eth.contract(
            address=SCROLL_BRIDGE_CONTRACT_ADDRESS, abi=SCROLL_BRIDGE_CONTRACT_ABI
        )

    async def _get_scroll_gas_fee(self):
        try:
            gas_price = await get_chain_gas_price(chain=SCROLL)
            return int(gas_price * SCROLL_GAS_PRICE_MULTIPLIER * SCROLL_BRIDGE_RECEIVE_GAS_LIMIT)
        except Exception as e:
            raise Exception(f"Error while estimating Scroll gas fee: {e}")

    async def _calculate_amount_for_full_bridge(self) -> float:
        try:
            tx_params = await self.client.get_tx_params(
                to=self.messenger.address,
                data=self.messenger.encodeABI(
                    "sendMessage",
                    args=(
                        self.client.address,
                        SCROLL_BRIDGE_TX_SIMULATION_VALUE - await self._get_scroll_gas_fee(),
                        SCROLL_MESSAGE,
                        SCROLL_BRIDGE_RECEIVE_GAS_LIMIT,
                    ),
                ),
                value=SCROLL_BRIDGE_TX_SIMULATION_VALUE,
            )

            gas = await self.client.get_gas_estimate(tx_params=tx_params)
            gas_fee = int((gas * tx_params["gasPrice"] * SCROLL_BRIDGE_FULL_BRIDGE_GAS_MULTIPLIER))
            balance = await self.client.get_token_balance(ETH)
            return int((balance - gas_fee) * 0.98)
        except Exception as e:
            raise Exception(f"Error while estimating full bridge amount: {e}")

    @gas_delay()
    async def bridge(self, amount: Optional[float]) -> bool:
        try:
            if amount is None:
                amount = await self._calculate_amount_for_full_bridge()
            else:
                amount = ETH.to_wei(amount)

            data = self.messenger.encodeABI(
                "sendMessage",
                args=(
                    self.client.address,
                    amount - await self._get_scroll_gas_fee(),
                    SCROLL_MESSAGE,
                    SCROLL_BRIDGE_RECEIVE_GAS_LIMIT,
                ),
            )

            logger.info(f"[ScrollBridge] Bridging {self.client.w3.from_wei(amount, 'ether')} ETH to Scroll")
            tx_hash = await self.client.send_transaction(to=self.messenger.address, data=data, value=amount)
            return await self.client.verify_tx(tx_hash=tx_hash)
        except Exception as e:
            logger.error(f"[ScrollBridge] Error: {e}")
