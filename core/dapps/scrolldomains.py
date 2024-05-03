from typing import Optional

from web3.contract import AsyncContract

from config import SCROLL_DOMAINS_REFERRAL_ADDRESS
from core.decorators import gas_delay
from logger import logger
from core import Client
from core.constants import (
    SCROLL_DOMAINS_CONTRACT_ADDRESS,
    SCROLL_DOMAINS_CONTRACT_ABI,
    ZERO_ADDRESS,
    SCROLL_DOMAIN_PRICE, RANDOM_USER_FETCH_URL
)


class ScrollDomains:
    def __init__(self, client: Client):
        self.client: Client = client
        self.contract: AsyncContract = self.client.w3.eth.contract(
            address=SCROLL_DOMAINS_CONTRACT_ADDRESS, abi=SCROLL_DOMAINS_CONTRACT_ABI
        )

    @gas_delay()
    async def register(self) -> bool:
        try:
            name = await self._generate_username()

            if not name:
                logger.error("[ScrollDomains] Failed to generate username")
                return False

            if self.client.w3.is_address(SCROLL_DOMAINS_REFERRAL_ADDRESS):
                ref_address = self.client.w3.to_checksum_address(SCROLL_DOMAINS_REFERRAL_ADDRESS)
            else:
                ref_address = ZERO_ADDRESS

            data = self.contract.encodeABI('Register', args=(
                name,
                ref_address
            ))

            logger.info(f"[ScrollDomains] Registering {name}.scroll domain")

            tx_hash = await self.client.send_transaction(
                to=self.contract.address,
                data=data,
                value=SCROLL_DOMAIN_PRICE
            )

            return await self.client.verify_tx(tx_hash=tx_hash)
        except Exception as e:
            logger.error(f"[ScrollDomains] Error while registering domain: {e}")

    async def _generate_username(self) -> Optional[str]:
        res = await self.client.send_get_request(
            url=RANDOM_USER_FETCH_URL
        )

        if not res:
            return None
        return res['username']
