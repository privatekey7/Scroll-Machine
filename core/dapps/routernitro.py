from typing import Dict, Optional

from web3 import Web3
from web3.contract import AsyncContract

from config import NITRO_BRIDGE_FEE_DELAY_RANGE, NITRO_BRIDGE_FEE_THRESHOLD
from core import Client
from core.constants import (
    CHAIN_TO_NITRO_ASSET_FORWARDER_CONTRACT_ADDRESS,
    NATIVE_TOKEN_ADDRESS,
    NITRO_ASSET_FORWARDER_CONTRACT_ABI,
    ROUTER_PATHFINDER_QUOTE_FETCH_URL,
    ROUTER_PATHFINDER_TX_FETCH_URL,
    ROUTER_TX_SIMULATION_VALUE,
)
from core.decorators import gas_delay
from core.token import ETH
from logger import logger
from utils import sleep


class RouterNitro:
    def __init__(self, src_chain_client: Client, dst_chain_client: Client):
        self.src_chain_client = src_chain_client
        self.dst_chain_client = dst_chain_client

        self.router: AsyncContract = self.src_chain_client.w3.eth.contract(
            address=CHAIN_TO_NITRO_ASSET_FORWARDER_CONTRACT_ADDRESS[src_chain_client.chain.name],
            abi=NITRO_ASSET_FORWARDER_CONTRACT_ABI,
        )

    async def _calculate_amount_for_all_balance_bridge(self) -> Optional[float]:
        data = await self._get_tx_data(amount=ROUTER_TX_SIMULATION_VALUE)

        if not data:
            return None

        tx_params = await self.src_chain_client.get_tx_params(
            to=self.router.address, data=data["txn"]["data"], value=ROUTER_TX_SIMULATION_VALUE
        )

        gas = await self.src_chain_client.get_gas_estimate(tx_params=tx_params)
        gas_fee = int((gas * tx_params["gasPrice"] * 1.1))
        balance = await self.src_chain_client.get_token_balance(ETH)

        return round(Web3.from_wei(balance - gas_fee, "ether"), 5)

    async def _get_tx_data(self, amount: int) -> Optional[Dict]:
        quote = await self.src_chain_client.send_get_request(
            url=ROUTER_PATHFINDER_QUOTE_FETCH_URL.format(
                from_token=NATIVE_TOKEN_ADDRESS,
                to_token=NATIVE_TOKEN_ADDRESS,
                amount=amount,
                from_chain_id=self.src_chain_client.chain.chain_id,
                to_chain_id=self.dst_chain_client.chain.chain_id,
            )
        )

        if not quote:
            return None

        quote["receiverAddress"] = self.src_chain_client.address
        quote["senderAddress"] = self.src_chain_client.address

        transaction = await self.src_chain_client.send_post_request(url=ROUTER_PATHFINDER_TX_FETCH_URL, data=quote)
        return transaction

    async def _wait_for_suitable_quote(self, amount: int) -> Dict:
        while True:
            quote = await self._get_tx_data(amount=amount)

            if quote is None:
                logger.error("[RouterNitro] Failed to fetch current fee")
                await sleep(delay_range=NITRO_BRIDGE_FEE_DELAY_RANGE, pr_bar=False)
                continue

            bridge_fee = ETH.from_wei(int(quote["bridgeFee"]["amount"]))
            if bridge_fee > NITRO_BRIDGE_FEE_THRESHOLD:
                logger.warning(
                    f"[RouterNitro] Current bridge fee is {bridge_fee} ETH > {NITRO_BRIDGE_FEE_THRESHOLD} ETH"
                )
                await sleep(delay_range=NITRO_BRIDGE_FEE_DELAY_RANGE, pr_bar=False)
                continue
            return quote

    @gas_delay()
    async def bridge(self, amount: Optional[float]) -> bool:
        try:
            if not amount:
                amount = await self._calculate_amount_for_all_balance_bridge()
                if not amount:
                    logger.error("[RouterNitro] Failed to calculate amount for full bridge")
                    return False

            value = ETH.to_wei(amount)
            data = await self._wait_for_suitable_quote(amount=value)

            logger.info(
                f"[RouterNitro] Bridging {amount} ETH from {self.src_chain_client.chain.name} "
                f"to {self.dst_chain_client.chain.name}"
            )

            tx_hash = await self.src_chain_client.send_transaction(
                to=self.router.address, data=data["txn"]["data"], value=value
            )
            return await self.src_chain_client.verify_tx(tx_hash=tx_hash)
        except Exception as e:
            logger.error(f"[RouterNitro] Error while bridging: {e}")
