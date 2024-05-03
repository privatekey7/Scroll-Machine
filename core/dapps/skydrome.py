from typing import List, Optional, Tuple, Union

from eth_typing import ChecksumAddress
from hexbytes import HexBytes
from web3.contract.async_contract import AsyncContract

from config import SLIPPAGE
from core.client import Client
from core.constants import (
    SKYDROME_ROUTER_CONTRACT_ABI,
    SKYDROME_ROUTER_CONTRACT_ADDRESS,
)
from core.decorators import gas_delay
from core.token import ETH, WETH, Token
from logger import logger

from .interfaces import Dex


class Skydrome(Dex):
    def __init__(self, client: Client) -> None:
        self.client: Client = client
        self.router: AsyncContract = self.client.w3.eth.contract(
            address=SKYDROME_ROUTER_CONTRACT_ADDRESS, abi=SKYDROME_ROUTER_CONTRACT_ABI
        )

    async def _get_amount_out(self, value: int, token_in: Token, token_out: Token) -> Optional[Tuple[int, bool]]:
        try:
            data = await self.router.functions.getAmountOut(
                value, token_in.contract_address, token_out.contract_address
            ).call()
            amount, _ = data
            if amount == 0:
                return None
            return data
        except Exception as e:
            logger.error(f"[Skydrome] Error while getting amount out: {e}")
            return None

    async def _prepare_swap_data(
        self,
        token_in: Token,
        token_out: Token,
        value: int,
        slippage: Union[int, float] = SLIPPAGE,
    ) -> Optional[Tuple[int, List[List[Optional[Union[str, bool]]]], ChecksumAddress, int]]:
        data = await self._get_amount_out(
            value=value,
            token_in=token_in,
            token_out=token_out,
        )
        if data is None:
            return None
        amount_out, pool_is_stable = data
        if not await self.client.is_amount_out_suitable(
            token_in=token_in,
            token_out=token_out,
            token_in_amount=value,
            min_amount_out=amount_out,
            slippage=slippage,
        ):
            return None
        return (
            int(amount_out * (1 - SLIPPAGE / 100)),
            [[token_in.contract_address, token_out.contract_address, pool_is_stable]],
            self.client.address,
            self.client.get_deadline(),
        )

    async def _swap_exact_eth_for_tokens(self, token_out: Token, value: int) -> Optional[HexBytes]:
        token_in = WETH
        swap_data = await self._prepare_swap_data(token_in=token_in, token_out=token_out, value=value)
        if swap_data is None:
            return None
        data = self.router.encodeABI(fn_name="swapExactETHForTokens", args=swap_data)
        try:
            return await self.client.send_transaction(to=self.router.address, data=data, value=value)
        except Exception as e:
            logger.error(f"[Skydrome] Couldn't swap {token_in.symbol} to {token_out.symbol}: {e}")
            return None

    async def _swap_exact_tokens_for_eth(self, token_in: Token, value: int) -> Optional[HexBytes]:
        token_out = WETH
        swap_data = await self._prepare_swap_data(token_in=token_in, token_out=token_out, value=value)
        if swap_data is None:
            return None
        min_amount_out, path, to, deadline = swap_data
        data = self.router.encodeABI(
            fn_name="swapExactTokensForETH",
            args=[value, min_amount_out, path, to, deadline],
        )
        try:
            return await self.client.send_transaction(to=self.router.address, data=data)
        except Exception as e:
            logger.error(f"[Skydrome] Couldn't swap {token_in.symbol} to {token_out.symbol}: {e}")
            return None

    async def _swap_exact_tokens_for_tokens(self, token_in: Token, token_out: Token, value: int) -> Optional[HexBytes]:
        swap_data = await self._prepare_swap_data(token_in=token_in, token_out=token_out, value=value)
        if swap_data is None:
            return None
        min_amount_out, path, to, deadline = swap_data
        data = self.router.encodeABI(
            fn_name="swapExactTokensForTokens",
            args=[value, min_amount_out, path, to, deadline],
        )
        try:
            return await self.client.send_transaction(to=self.router.address, data=data)
        except Exception as e:
            logger.error(f"[Skydrome] Couldn't swap {token_in.symbol} to {token_out.symbol}: {e}")
            return None

    @gas_delay()
    async def swap(self, token_in: Token, token_out: Token, amount: int) -> bool:
        logger.info(f"[Skydrome] Swapping {amount} {token_in.symbol} to {token_out.symbol}")
        amount = token_in.to_wei(value=amount)
        if not await self.client.approve(spender=self.router.address, token=token_in, value=amount):
            return False
        if token_in == ETH:
            tx_hash = await self._swap_exact_eth_for_tokens(token_out=token_out, value=amount)
        elif token_out == ETH:
            tx_hash = await self._swap_exact_tokens_for_eth(token_in=token_in, value=amount)
        else:
            tx_hash = await self._swap_exact_tokens_for_tokens(token_in=token_in, token_out=token_out, value=amount)
        return await self.client.verify_tx(tx_hash=tx_hash)
