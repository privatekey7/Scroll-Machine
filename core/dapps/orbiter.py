from decimal import Decimal
from typing import Optional, Tuple

from core.decorators import gas_delay
from core.token import ETH, Token
from logger import logger
from core import Client, Chain
from core.constants import (
    ORBITER_TX_SIMULATION_VALUE,
    ORBITER_TRADING_FEES_DATA,
    ORBITER_CHAIN_CODE_BASE,
    ORBITER_CONTRACT_ADDRESSES,
    GAS_ESTIMATE_MULTIPLIER,
    ESTIMATE_FULL_BRIDGE_ROUND,
    SCROLL_GAS_ESTIMATE_MULTIPLIER,
)


class Orbiter:
    def __init__(self, src_chain_client: Client, dst_chain_client: Client):
        self.src_chain_client = src_chain_client
        self.dst_chain_client = dst_chain_client

    async def _calculate_amount_for_all_balance_bridge(self, trading_fee: float) -> Optional[float]:
        try:
            tx_params = await self.src_chain_client.get_tx_params(
                to=ORBITER_CONTRACT_ADDRESSES[self.src_chain_client.chain.name],
                value=ORBITER_TX_SIMULATION_VALUE,
            )

            multiplier = (
                SCROLL_GAS_ESTIMATE_MULTIPLIER
                if self.src_chain_client.chain.chain_id == 534352
                else GAS_ESTIMATE_MULTIPLIER
            )
            gas = await self.src_chain_client.get_gas_estimate(tx_params=tx_params)
            gas_fee = int((gas * tx_params["gasPrice"] * multiplier))
            balance = await self.src_chain_client.get_token_balance(ETH)
            return round(ETH.from_wei(balance - gas_fee), ESTIMATE_FULL_BRIDGE_ROUND) - trading_fee
        except Exception as e:
            logger.error(f"[Orbiter] Failed to estimate amount for full bridge: {e}")
            return None

    def _adjust_amount(self, amount: float, dst_chain: Chain, trading_fee: float) -> Decimal:
        return Decimal("{:.14f}{}".format(amount + trading_fee, (ORBITER_CHAIN_CODE_BASE + dst_chain.orbiter_chain_id)))

    @staticmethod
    def _get_path_fees_info(src_chain: Chain, dest_chain: Chain) -> Tuple:
        selected_path = f"{src_chain.orbiter_chain_id}-{dest_chain.orbiter_chain_id}"

        for path in ORBITER_TRADING_FEES_DATA:
            if path == selected_path:
                min_amount = ORBITER_TRADING_FEES_DATA.get(path).get("ETH-ETH").get("minPrice")
                max_amount = ORBITER_TRADING_FEES_DATA.get(path).get("ETH-ETH").get("maxPrice")
                trading_fee = ORBITER_TRADING_FEES_DATA.get(path).get("ETH-ETH").get("tradingFee")

                return min_amount, max_amount, trading_fee

    @gas_delay()
    async def bridge(
        self,
        amount: Optional[float],
        token: Optional[Token] = ETH,
    ) -> bool:
        min_amount, max_amount, trading_fee = Orbiter._get_path_fees_info(
            src_chain=self.src_chain_client.chain, dest_chain=self.dst_chain_client.chain
        )

        if not amount:
            amount = await self._calculate_amount_for_all_balance_bridge(trading_fee=trading_fee)
            if amount is None:
                return False

        value = self._adjust_amount(amount=amount, dst_chain=self.dst_chain_client.chain, trading_fee=trading_fee)
        if amount < min_amount:
            logger.error(f"[Orbiter] Specified value `{amount}` is lower than minimum sent value `{min_amount}`")
            return False
        logger.info(
            f"[Orbiter] Bridging {round(value, 5)} {token.symbol} from {self.src_chain_client.chain.name}"
            f" to {self.dst_chain_client.chain.name}"
        )

        try:
            tx_hash = await self.src_chain_client.send_transaction(
                value=ETH.to_wei(value), to=ORBITER_CONTRACT_ADDRESSES[self.src_chain_client.chain.name]
            )
            return await self.src_chain_client.verify_tx(tx_hash=tx_hash)
        except Exception as e:
            logger.error(f"[Orbiter] Couldn't execute bridge transaction: {e}")
            return False
