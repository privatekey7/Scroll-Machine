from typing import Optional

from hexbytes import HexBytes
from web3.constants import ADDRESS_ZERO
from web3.contract.async_contract import AsyncContract

from config import SLIPPAGE
from core.client import Client
from core.constants import (
    IZUMI_QUOTER_CONTRACT_ABI,
    IZUMI_QUOTER_CONTRACT_ADDRESS,
    IZUMI_ROUTER_CONTRACT_ABI,
    IZUMI_ROUTER_CONTRACT_ADDRESS,
)
from core.decorators import gas_delay
from core.token import ETH, WETH, Token
from logger import logger

from .interfaces import Dex


class Izumi(Dex):
    def __init__(self, client: Client) -> None:
        self.client: Client = client
        self.router: AsyncContract = self.client.w3.eth.contract(
            address=IZUMI_ROUTER_CONTRACT_ADDRESS, abi=IZUMI_ROUTER_CONTRACT_ABI
        )
        self.quoter: AsyncContract = self.client.w3.eth.contract(
            address=IZUMI_QUOTER_CONTRACT_ADDRESS, abi=IZUMI_QUOTER_CONTRACT_ABI
        )

    def _build_path(self, token_in: Token, token_out: Token, fee: int) -> bytes:
        return (
            HexBytes(token_in.contract_address).rjust(20, b"\0")
            + fee.to_bytes(3, "big")
            + HexBytes(token_out.contract_address).rjust(20, b"\0")
        )

    async def _get_amount_out(
        self,
        path: bytes,
        amount_in: int,
    ) -> Optional[int]:
        try:
            amount_out, _ = await self.quoter.functions.swapAmount(
                amount_in, path
            ).call()
            return int(amount_out * (1 - SLIPPAGE / 100))
        except Exception as e:
            logger.error(f"[Izumi] Error while getting amount out: {e}")
            return None

    async def _get_pool_fee(
        self, token_in: Token, token_out: Token, fee: int = 400
    ) -> Optional[int]:
        try:
            pool_address = await self.quoter.functions.pool(
                token_in.contract_address, token_out.contract_address, fee
            ).call()
            if pool_address != ADDRESS_ZERO:
                return fee
            return await self._get_pool_fee(
                token_in=token_in, token_out=token_out, fee=500
            )
        except Exception as e:
            logger.error(f"[Izumi] Error while getting pool fee: {e}")
            return None

    async def _swap_to_eth(
        self, token_in: Token, value: int, deadline: int, slippage: int
    ) -> Optional[HexBytes]:
        token_out = WETH
        pool_fee = await self._get_pool_fee(token_in=token_in, token_out=token_out)
        if pool_fee is None:
            return None
        path = self._build_path(token_in=token_in, token_out=token_out, fee=pool_fee)
        min_amount_out = await self._get_amount_out(path=path, amount_in=value)
        if min_amount_out is None:
            return None
        if not await self.client.is_amount_out_suitable(
            token_in=token_in,
            token_out=token_out,
            token_in_amount=value,
            min_amount_out=min_amount_out,
            slippage=slippage,
        ):
            return None
        swap_data = self.router.encodeABI(
            fn_name="swapAmount",
            args=[(path, ADDRESS_ZERO, value, min_amount_out, deadline)],
        )
        unwrap_data = self.router.encodeABI(
            fn_name="unwrapWETH9", args=[min_amount_out, self.client.address]
        )
        data = self.router.encodeABI(
            fn_name="multicall", args=[[swap_data, unwrap_data]]
        )
        try:
            return await self.client.send_transaction(to=self.router.address, data=data)
        except Exception as e:
            logger.error(
                f"[Izumi] Couldn't swap {token_in.symbol} to {token_out.symbol}: {e}"
            )
            return None

    async def _swap_from_eth(
        self, token_out: Token, value: int, deadline: int, slippage: int
    ) -> Optional[HexBytes]:
        token_in = WETH
        pool_fee = await self._get_pool_fee(token_in=token_in, token_out=token_out)
        if pool_fee is None:
            return None
        path = self._build_path(token_in=token_in, token_out=token_out, fee=pool_fee)
        min_amount_out = await self._get_amount_out(path=path, amount_in=value)
        if min_amount_out is None:
            return None
        if not await self.client.is_amount_out_suitable(
            token_in=token_in,
            token_out=token_out,
            token_in_amount=value,
            min_amount_out=min_amount_out,
            slippage=slippage,
        ):
            return None
        swap_data = self.router.encodeABI(
            fn_name="swapAmount",
            args=[(path, self.client.address, value, min_amount_out, deadline)],
        )
        refund_data = self.router.encodeABI(fn_name="refundETH")
        data = self.router.encodeABI(
            fn_name="multicall", args=[[swap_data, refund_data]]
        )
        try:
            return await self.client.send_transaction(
                to=self.router.address, data=data, value=value
            )
        except Exception as e:
            logger.error(
                f"[Izumi] Couldn't swap {token_in.symbol} to {token_out.symbol}: {e}"
            )
            return None

    async def _swap_from_token_to_token(
        self,
        token_in: Token,
        token_out: Token,
        value: int,
        deadline: int,
        slippage: int,
    ) -> Optional[HexBytes]:
        pool_fee = await self._get_pool_fee(token_in=token_in, token_out=token_out)
        if pool_fee is None:
            return None
        path = self._build_path(token_in=token_in, token_out=token_out, fee=pool_fee)
        min_amount_out = await self._get_amount_out(path=path, amount_in=value)
        if min_amount_out is None:
            return None
        if not await self.client.is_amount_out_suitable(
            token_in=token_in,
            token_out=token_out,
            token_in_amount=value,
            min_amount_out=min_amount_out,
            slippage=slippage,
        ):
            return None
        data = self.router.encodeABI(
            fn_name="swapAmount",
            args=[[path, self.client.address, value, min_amount_out, deadline]],
        )
        try:
            return await self.client.send_transaction(to=self.router.address, data=data)
        except Exception as e:
            logger.error(
                f"[Izumi] Couldn't swap {token_in.symbol} to {token_out.symbol}: {e}"
            )
            return None

    @gas_delay()
    async def swap(
        self, token_in: Token, token_out: Token, amount: int, slippage: int = SLIPPAGE
    ) -> bool:
        logger.info(
            f"[Izumi] Swapping {amount} {token_in.symbol} to {token_out.symbol}"
        )
        amount = token_in.to_wei(value=amount)
        if not await self.client.approve(
            spender=self.router.address, token=token_in, value=amount
        ):
            return False
        deadline = self.client.get_deadline()
        if token_in == ETH:
            tx_hash = await self._swap_from_eth(
                token_out=token_out, value=amount, deadline=deadline, slippage=slippage
            )
        elif token_out == ETH:
            tx_hash = await self._swap_to_eth(
                token_in=token_in, value=amount, deadline=deadline, slippage=slippage
            )
        else:
            tx_hash = await self._swap_from_token_to_token(
                token_in=token_in,
                token_out=token_out,
                value=amount,
                deadline=deadline,
                slippage=slippage,
            )
        return await self.client.verify_tx(tx_hash=tx_hash)
