from typing import Optional

from web3.contract.async_contract import AsyncContract

from core.client import Client
from core.constants import LAYERBANK_CONTRACT_ABI, LAYERBANK_CONTRACT_ADDRESS
from core.decorators import gas_delay
from core.token import ETH, LETH, Token
from logger import logger

from .interfaces import Lending


class LayerBank(Lending):
    def __init__(self, client: Client) -> None:
        self.client: Client = client
        self.contract: AsyncContract = self.client.w3.eth.contract(
            address=LAYERBANK_CONTRACT_ADDRESS, abi=LAYERBANK_CONTRACT_ABI
        )

    async def get_supplied_amount(self, token: Token = LETH) -> Optional[int]:
        token_contract = self.client.w3.eth.contract(address=token.contract_address, abi=token.abi)
        try:
            return await token_contract.functions.balanceOf(self.client.address).call()
        except Exception:
            logger.error(f"[Layerbank] Couldn't get supplied amount of {self}")
            return None

    @gas_delay()
    async def supply(self, value: int, token: Token = ETH) -> bool:
        value = token.to_wei(value=value)
        data = self.contract.encodeABI(
            fn_name="supply",
            args=[LETH.contract_address, value],
        )
        logger.info(f"[Layerbank] Supplying {token.from_wei(value=value)} {token.symbol}")
        try:
            tx_hash = await self.client.send_transaction(to=self.contract.address, data=data, value=value)
            return await self.client.verify_tx(tx_hash=tx_hash)
        except Exception as e:
            logger.error(f"[Layerbank] Couldn't supply {token.from_wei(value=value)} {token.symbol}: {e}")
            return False

    @gas_delay()
    async def withdraw(self, token: Token = LETH) -> bool:
        supplied_amout = await self.get_supplied_amount()
        if supplied_amout is None:
            return None
        data = self.contract.encodeABI(fn_name="redeemToken", args=[token.contract_address, supplied_amout])
        logger.info(f"[Layerbank] Withdrawing {token.from_wei(value=supplied_amout)} {token.symbol}")
        try:
            tx_hash = await self.client.send_transaction(to=self.contract.address, data=data)
            return await self.client.verify_tx(tx_hash=tx_hash)
        except Exception as e:
            logger.error(f"[Layerbank] Couldn't withdraw {token.from_wei(value=supplied_amout)} {token.symbol}: {e}")
            return False
