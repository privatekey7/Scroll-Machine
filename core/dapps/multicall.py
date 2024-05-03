from typing import Dict, List, Optional, Tuple

from eth_abi import decode
from eth_typing import HexStr

from core import Client
from core.constants import MULTICALL_V3_CONTRACT_ABI, MULTICALL_V3_CONTRACT_ADDRESS
from core.token import Token
from logger import logger


class MulticallV3:
    def __init__(self, client: Client):
        self.client = client

        self.contract = self.client.w3.eth.contract(
            address=MULTICALL_V3_CONTRACT_ADDRESS, abi=MULTICALL_V3_CONTRACT_ABI
        )

    async def get_token_balances(self, token_list: list[Token]) -> Optional[Dict[Token, float]]:
        try:
            calls = []

            for token in token_list:
                calldata = await self._encode_get_balance_call(token=token)
                calls.append((token.contract_address, calldata))

            results = await self.aggregate(calls=calls)

            if results is None:
                return None

            token_balances = {}

            for token in token_list:
                index = token_list.index(token)
                call_result = results[index]

                balance_wei = decode(["uint256"], call_result)
                token_balances[token] = token.from_wei(balance_wei[0])

            return token_balances
        except Exception as e:
            logger.exception(e)

    async def aggregate(self, calls: List[Tuple[str, HexStr]]):
        try:
            _, results = await self.contract.functions.aggregate(calls).call()

            return results
        except Exception as e:
            logger.error(f"Error while multicall execution: {e}")

    async def _encode_get_balance_call(self, token: Token) -> HexStr:
        token_contract = self.client.w3.eth.contract(address=token.contract_address, abi=token.abi)

        if token.symbol == "COG":
            fn_name = "user_collateral_share"
        else:
            fn_name = "balanceOf"
        data = token_contract.encodeABI(fn_name, args=[self.client.address])

        return data
