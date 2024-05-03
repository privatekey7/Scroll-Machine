import random
from hashlib import sha256

from core.client import Client
from core.constants import DMAIL_CONTRACT_ABI, DMAIL_CONTRACT_ADDRESS
from logger import logger


class Dmail:
    def __init__(self, client: Client) -> None:
        self.client = client
        self.contract = client.w3.eth.contract(address=DMAIL_CONTRACT_ADDRESS, abi=DMAIL_CONTRACT_ABI)

    async def send_mail(self) -> bool:
        logger.info("[Dmail] Sending mail")
        to = sha256(str(1e11 * random.random()).encode()).hexdigest()
        subject = sha256(str(1e11 * random.random()).encode()).hexdigest()
        data = self.contract.encodeABI("send_mail", args=(to, subject))

        tx_hash = await self.client.send_transaction(to=self.contract.address, data=data)
        return await self.client.verify_tx(tx_hash=tx_hash)
