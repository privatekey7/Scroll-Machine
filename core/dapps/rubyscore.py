from core.client import Client
from core.constants import RUBYSCORE_CONTRACT_ADDRESS
from logger import logger


class RubyScore:
    def __init__(self, client: Client) -> None:
        self.client = client
        self.contract = client.w3.eth.contract(address=RUBYSCORE_CONTRACT_ADDRESS)

    async def vote(self) -> bool:
        logger.info("[Rubyscore] Voting")
        tx_hash = await self.client.send_transaction(to=self.contract.address, data="0x632a9a52")
        return await self.client.verify_tx(tx_hash=tx_hash)
