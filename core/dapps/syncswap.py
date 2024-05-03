from typing import Optional, Union

from eth_abi.abi import encode
from hexbytes import HexBytes
from web3.constants import ADDRESS_ZERO
from web3.contract.async_contract import AsyncContract

from config import SLIPPAGE
from core import Client
from core.constants import (
    SYNCSWAP_CLASSIC_POOL_FACTORY_ABI,
    SYNCSWAP_CLASSIC_POOL_FACTORY_ADDRESS,
    SYNCSWAP_POOL_ABI,
    SYNCSWAP_ROUTER_CONTRACT_ABI,
    SYNCSWAP_ROUTER_CONTRACT_ADDRESS,
    SYNCSWAP_STABLE_POOL_FACTORY_ABI,
    SYNCSWAP_STABLE_POOL_FACTORY_ADDRESS,
)
from core.decorators import gas_delay
from core.token import ETH, WETH, Token
from logger import logger

from . import Dex


class Syncswap(Dex):
    def __init__(self, client: Client) -> None:
        self.client: Client = client
        self.router: AsyncContract = self.client.w3.eth.contract(
            address=SYNCSWAP_ROUTER_CONTRACT_ADDRESS,
            abi=SYNCSWAP_ROUTER_CONTRACT_ABI,
        )
        self.classic_pool_factory: AsyncContract = self.client.w3.eth.contract(
            address=SYNCSWAP_CLASSIC_POOL_FACTORY_ADDRESS,
            abi=SYNCSWAP_CLASSIC_POOL_FACTORY_ABI,
        )
        self.stable_pool_factory: AsyncContract = self.client.w3.eth.contract(
            address=SYNCSWAP_STABLE_POOL_FACTORY_ADDRESS,
            abi=SYNCSWAP_STABLE_POOL_FACTORY_ABI,
        )

    async def _get_pool_address(self, token_in: Token, token_out: Token) -> Optional[HexBytes]:
        if token_in.is_stable and token_out.is_stable:
            pool_factory = self.stable_pool_factory
        else:
            pool_factory = self.classic_pool_factory

        try:
            pool_address = await pool_factory.functions.getPool(
                token_in.contract_address, token_out.contract_address
            ).call()
            if pool_address == ADDRESS_ZERO:
                return None
            return pool_address
        except Exception as e:
            logger.error(f"[Syncswap] Couldn't get pool address: {e}")
            return None

    async def _get_amount_out(
        self,
        pool_contract_address: HexBytes,
        token_in: Token,
        amount_in: int,
    ) -> Optional[int]:
        pool_contract: AsyncContract = self.client.w3.eth.contract(address=pool_contract_address, abi=SYNCSWAP_POOL_ABI)
        try:
            amount_out = await pool_contract.functions.getAmountOut(
                token_in.contract_address, amount_in, self.client.address
            ).call()
            return int(amount_out * (1 - SLIPPAGE / 100))
        except Exception as e:
            logger.error(f"[Zebra] Error while getting amount out: {e}")
            return None

    async def _prepare_swap_data(
        self,
        token_in: Token,
        token_out: Token,
        amount_in: Union[int, float],
        slippage: int = SLIPPAGE,
        withdraw_mode: int = 1,
    ) -> Optional[int]:
        if token_in == ETH:
            token_in = WETH
        elif token_out == ETH:
            token_out = WETH

        pool_contract_address = await self._get_pool_address(token_in=token_in, token_out=token_out)
        if pool_contract_address is None:
            return None
        min_amount_out = await self._get_amount_out(
            pool_contract_address=pool_contract_address,
            token_in=token_in,
            amount_in=amount_in,
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

        steps = [
            {
                "pool": pool_contract_address,
                "data": encode(
                    ["address", "address", "uint8"],
                    [
                        token_in.contract_address,
                        self.client.address,
                        withdraw_mode,
                    ],
                ),
                "callback": ADDRESS_ZERO,  # no callback
                "callbackData": "0x",
            }
        ]
        paths = [
            {
                "steps": steps,
                "tokenIn": ADDRESS_ZERO if token_in == WETH else token_in.contract_address,
                "amountIn": amount_in,
            }
        ]

        return paths, min_amount_out, self.client.get_deadline()

    @gas_delay()
    async def swap(self, token_in: Token, token_out: Token, amount: int) -> bool:
        logger.info(f"[Syncswap] Swapping {amount} {token_in.symbol} to {token_out.symbol}")
        amount = token_in.to_wei(value=amount)
        # if swapping from ETH set tx `value` to `amount`
        if token_in == ETH:
            value = amount
        else:
            value = 0
        if not await self.client.approve(spender=self.router.address, token=token_in, value=amount):
            return False

        swap_data = await self._prepare_swap_data(token_in=token_in, token_out=token_out, amount_in=amount)
        if swap_data is None:
            return False
        paths, amount_out, deadline = swap_data
        data = self.router.encodeABI(fn_name="swap", args=(paths, amount_out, deadline))
        try:
            tx_hash = await self.client.send_transaction(to=self.router.address, data=data, value=value)
            return await self.client.verify_tx(tx_hash=tx_hash)
        except Exception as e:
            logger.error(f"[Syncswap] Couldn't swap {token_in.symbol} to {token_out.symbol}: {e}")
            return False
