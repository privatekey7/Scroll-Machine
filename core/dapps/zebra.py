from typing import List, Optional, Tuple, Union

from hexbytes import HexBytes
from web3.contract.async_contract import AsyncContract

from config import SLIPPAGE
from core import Client
from core.constants import ZEBRA_ROUTER_CONTRACT_ABI, ZEBRA_ROUTER_CONTRACT_ADDRESS
from core.token import ETH, WETH, Token
from logger import logger

from ..decorators import gas_delay
from . import Dex


class Zebra(Dex):
    def __init__(self, client: Client) -> None:
        self.client: Client = client
        self.router: AsyncContract = self.client.w3.eth.contract(
            address=ZEBRA_ROUTER_CONTRACT_ADDRESS, abi=ZEBRA_ROUTER_CONTRACT_ABI
        )

    async def _get_amount_out(
        self,
        amount_in: int,
        token_in: Token,
        token_out: Token,
    ) -> Optional[int]:
        """
        Calculate the amount out based on the provided parameters.

        Args:
            amount_in (int): The input amount.
            token_in (Token): The input token.
            token_out (Token): The output token.
            slippage (Union[int, float]): The slippage percentage.

        Returns:
            Optional[int]: The calculated amount out, or None if an error occurs.
        """
        try:
            path = [token_in.contract_address, token_out.contract_address]
            data = await self.router.functions.getAmountsOut(amount_in, path).call()
            if not data:
                return None
            _, amount_out = data
            return int(amount_out * (1 - SLIPPAGE / 100))
        except Exception as e:
            logger.error(f"[Zebra] Error while getting amount out: {e}")
            return None

    async def _swap_exact_tokens_for_tokens(
        self, token_in: Token, token_out: Token, value: int, slippage: Union[int, float]
    ) -> Optional[HexBytes]:
        swap_data = await self._prepare_swap_data(
            token_in=token_in, token_out=token_out, amount_in=value, slippage=slippage
        )
        if swap_data is None:
            return None
        min_amount_out, deadline = swap_data
        path = [token_in.contract_address, token_out.contract_address]
        data = self.router.encodeABI(
            fn_name="swapExactTokensForTokens",
            args=(value, min_amount_out, path, self.client.address, deadline),
        )
        try:
            return await self.client.send_transaction(to=self.router.address, data=data)
        except Exception as e:
            logger.error(f"[Zebra] Couldn't swap {token_in.symbol} to {token_out.symbol}: {e}")
            return None

    async def _swap_exact_tokens_for_eth(
        self, token_in: Token, value: int, slippage: Union[int, float]
    ) -> Optional[HexBytes]:
        token_out = WETH
        swap_data = await self._prepare_swap_data(
            token_in=token_in, token_out=token_out, amount_in=value, slippage=slippage
        )
        if swap_data is None:
            return None
        min_amount_out, deadline = swap_data
        path = [token_in.contract_address, token_out.contract_address]
        data = self.router.encodeABI(
            fn_name="swapExactTokensForETH",
            args=(value, min_amount_out, path, self.client.address, deadline),
        )
        try:
            return await self.client.send_transaction(to=self.router.address, data=data)
        except Exception as e:
            logger.error(f"[Zebra] Couldn't swap {token_in.symbol} to {token_out.symbol}: {e}")
            return None

    async def _swap_exact_eth_for_tokens(
        self, token_out: Token, value: int, slippage: Union[int, float]
    ) -> Optional[HexBytes]:
        """
        Swap a specific amount of Ethereum for tokens with a specified slippage using the Uniswap V2 Router.

        Args:
            token_out (Token): The output token to receive from the swap.
            value (int): The amount of Ethereum to be swapped.
            slippage (Union[int, float]): The allowed slippage percentage for the swap.

        Returns:
            Optional[HexBytes]: The transaction hash if the swap is successful, None otherwise.
        """
        token_in = WETH
        swap_data = await self._prepare_swap_data(
            token_in=token_in, token_out=token_out, amount_in=value, slippage=slippage
        )
        if swap_data is None:
            return None
        min_amount_out, deadline = swap_data
        path = [token_in.contract_address, token_out.contract_address]
        data = self.router.encodeABI(
            fn_name="swapExactETHForTokens",
            args=(min_amount_out, path, self.client.address, deadline),
        )
        try:
            return await self.client.send_transaction(to=self.router.address, data=data, value=value)
        except Exception as e:
            logger.error(f"[Zebra] Couldn't swap {token_in.symbol} to {token_out.symbol}: {e}")
            return None

    async def _prepare_swap_data(
        self,
        token_in: Token,
        token_out: Token,
        amount_in: int,
        slippage: Union[int, float],
    ) -> Optional[Tuple[int, int]]:
        """
        Prepare data for a token swap, including the minimum amount of output tokens
        and the deadline for the transaction.

        Args:
            token_in (Token): The input token to be swapped.
            token_out (Token): The output token to receive from the swap.
            amount_in (int): The amount of input tokens to be swapped.
            slippage (Union[int, float]): The allowed slippage percentage for the swap.

        Returns:
            Optional[Tuple[int, int]]: A tuple containing the minimum amount of output tokens
            and the deadline for the transaction in seconds since the Unix epoch. Returns
            None if there's an error in calculating the minimum amount.
        """
        min_amount_out = await self._get_amount_out(
            amount_in=amount_in,
            token_in=token_in,
            token_out=token_out,
        )
        if min_amount_out is None:
            return None
        if not await self.client.is_amount_out_suitable(
            token_in=token_in,
            token_out=token_out,
            token_in_amount=amount_in,
            min_amount_out=min_amount_out,
            slippage=slippage,
        ):
            return None
        return min_amount_out, self.client.get_deadline()

    @gas_delay()
    async def swap(self, token_in: Token, token_out: Token, amount: int, slippage: int = SLIPPAGE) -> bool:
        logger.info(f"[Zebra] Swapping {amount} {token_in.symbol} to {token_out.symbol}")

        amount = token_in.to_wei(value=amount)
        if not await self.client.approve(spender=self.router.address, token=token_in, value=amount):
            return False

        if token_in == ETH:
            tx_hash = await self._swap_exact_eth_for_tokens(token_out=token_out, value=amount, slippage=slippage)
        elif token_out == ETH:
            tx_hash = await self._swap_exact_tokens_for_eth(token_in=token_in, value=amount, slippage=slippage)
        else:
            tx_hash = await self._swap_exact_tokens_for_tokens(
                token_in=token_in, token_out=token_out, value=amount, slippage=slippage
            )
        return await self.client.verify_tx(tx_hash=tx_hash)
