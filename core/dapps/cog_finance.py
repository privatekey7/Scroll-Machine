from typing import Optional

from web3.contract import AsyncContract
from logger import logger

from core import Client
from core.constants import COG_FINANCE_USDC_WETH_POOL_CONTRACT_ADDRESS, COG_FINANCE_USDC_WETH_POOL_CONTRACT_ABI
from core.dapps.interfaces import Lending
from core.token import Token, WETH


class CogFinance(Lending):
    def __init__(self, client: Client) -> None:
        self.client: Client = client
        self.contract: AsyncContract = self.client.w3.eth.contract(
            address=COG_FINANCE_USDC_WETH_POOL_CONTRACT_ADDRESS, abi=COG_FINANCE_USDC_WETH_POOL_CONTRACT_ABI
        )

    async def supply(self, value: int, token: Token = WETH) -> bool:
        data = self.contract.encodeABI(
            fn_name="add_collateral",
            args=[self.client.address, value],
        )

        if not await self.client.approve(token=token, value=value, spender=self.contract.address):
            return False

        logger.info(
            f"[Cog Finance] Supplying {token.from_wei(value=value)} {token.symbol}"
        )

        try:
            tx_hash = await self.client.send_transaction(
                to=self.contract.address, data=data
            )
            return await self.client.verify_tx(tx_hash=tx_hash)
        except Exception as e:
            logger.error(
                f"[Cog Finance] Couldn't supply {token.from_wei(value=value)} {token.symbol}: {e}"
            )
            return False

    async def withdraw(self, token: Token = WETH) -> bool:
        supplied_amount = await self.get_supplied_amount()

        if supplied_amount is None:
            return False

        data = self.contract.encodeABI(
            fn_name="remove_collateral", args=[self.client.address, supplied_amount]
        )

        logger.info(
            f"[Cog Finance] Withdrawing {token.from_wei(value=supplied_amount)} {token.symbol}"
        )

        try:
            tx_hash = await self.client.send_transaction(
                to=self.contract.address, data=data
            )
            return await self.client.verify_tx(tx_hash=tx_hash)
        except Exception as e:
            logger.error(
                f"[Cog Finance] Couldn't withdraw {token.from_wei(value=supplied_amount)} {token.symbol}: {e}"
            )
            return False

    async def get_supplied_amount(self, token: Optional[Token] = None) -> Optional[int]:
        try:
            return await self.contract.functions.user_collateral_share(self.client.address).call()
        except Exception as e:
            logger.error(f"[Cog Finance] Couldn't get supplied amount of {self}")
            return None

