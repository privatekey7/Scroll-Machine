import asyncio
import binascii
import random
import re
import sys
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import aiohttp
from aiohttp_proxy import ProxyConnector
from eth_account import Account
from eth_typing import ChecksumAddress
from hexbytes import HexBytes
from web3 import AsyncWeb3
from web3.contract.async_contract import AsyncContract

from config import APPROVE_VALUE_RANGE, POST_APPROVE_DELAY_RANGE, TX_DELAY_RANGE
from core.token import ETH, USDC, USDT, WETH, Token
from logger import logger
from utils import sleep

from . import Chain
from .constants import (
    GAS_LIMIT_MULTIPLIER,
    GAS_PRICE_MULTIPLIER,
    MAX_ALLOWED_TOKEN_PRICE_DIFFERENCE,
    PROXY_PATTERN,
    TOKEN_PRICE_FETCH_URL,
    VERIFY_TX_TIMEOUT, TRANSFER_TX_SIMULATION_VALUE,
)
from .decorators import retry_on_fail
from .exceptions import NoRPCEndpointSpecifiedError


class Client:
    def __init__(self, private_key: str, chain: Optional[Chain] = None, proxy: str = None) -> None:
        self.private_key: str = self._set_private_key(private_key=private_key)
        self.chain: Optional[Chain] = chain
        self.proxy: str = self._set_proxy(proxy=proxy)
        self.w3: Optional[AsyncWeb3] = self._init_w3(chain=chain)
        self.address: ChecksumAddress = AsyncWeb3.to_checksum_address(
            value=Account.from_key(private_key=private_key).address
        )
        self.tokens = [ETH, USDC, USDT]

    def __str__(self):
        return f"{self.address[:6]}...{self.address[-4:]}"

    def _set_proxy(self, proxy: str) -> str:
        if proxy is None:
            return proxy
        pattern = re.compile(pattern=PROXY_PATTERN)
        if pattern.match(proxy):
            return proxy
        logger.error("Invalid proxy format. The correct format is 'username:password@ip_address:port'.")
        sys.exit(1)

    def _get_proxy_connector(self) -> Optional[ProxyConnector]:
        if self.proxy:
            proxy_url = f"http://{self.proxy}"
            return ProxyConnector.from_url(url=proxy_url)
        return None

    def _set_private_key(self, private_key: str) -> str:
        try:
            Account.from_key(private_key=private_key)
            return private_key
        except binascii.Error:
            logger.error(f"Private key `{private_key}` is not a valid hex string.")
            sys.exit(1)
        except ValueError as e:
            logger.error(f"{e} `{private_key}`")
            sys.exit(1)

    def _init_w3(self, chain: Chain) -> AsyncWeb3:
        if self.proxy:
            request_kwargs = {"proxy": f"http://{self.proxy}"}
        else:
            request_kwargs = {}

        if chain is None:
            return None

        try:
            if not chain.rpc:
                raise NoRPCEndpointSpecifiedError(chain=chain)
            return AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(endpoint_uri=chain.rpc, request_kwargs=request_kwargs))
        except Exception as e:
            logger.error(e)
            sys.exit(1)

    @retry_on_fail()
    async def send_get_request(self, url: str, use_proxy: bool = True) -> Optional[Any]:
        if use_proxy:
            connector = self._get_proxy_connector()
        else:
            connector = None

        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(url=url, timeout=100) as response:
                    response.raise_for_status()
                    json_data = await response.json(content_type=None)
                    return json_data
        except aiohttp.ClientResponseError as e:
            logger.error(f"Recieved non-200 response: {e}")
        except aiohttp.ClientConnectionError as e:
            logger.error(f"Connection Error: {e}")
        except aiohttp.InvalidURL as e:
            logger.error(f"Wrong URL format: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
        return None

    async def send_post_request(self, url: str, data: Dict, use_proxy: bool = True) -> Optional[Any]:
        if use_proxy:
            connector = self._get_proxy_connector()
        else:
            connector = None

        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.post(url=url, json=data, timeout=100) as response:
                    response.raise_for_status()
                    return await response.json()
        except aiohttp.ClientResponseError as e:
            logger.error(f"Recieved non-200 response: {e}")
        except aiohttp.ClientConnectionError as e:
            logger.error(f"Connection Error: {e}")
        except aiohttp.InvalidURL as e:
            logger.error(f"Wrong URL format: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred: {e}")
        return None

    async def fetch_token_price(self, token_list: Iterable[Token]) -> Optional[List[int]]:
        token_ids = [token.api_id for token in token_list]
        token_ids_string = ",".join(token_ids)
        url = TOKEN_PRICE_FETCH_URL.format(token_ids_string)
        response = await self.send_get_request(url=url, use_proxy=False)

        if response and isinstance(response, list):
            price_usd = [float(token_data.get("price_usd")) for token_data in response]
            return price_usd
        else:
            logger.error(f"Couldn't fetch price of {[token.symbol for token in token_list]}")
            return None

    def get_deadline(self, seconds: int = 1800) -> int:
        return int(datetime.now(timezone.utc).timestamp()) + seconds

    async def get_gas_estimate(self, tx_params: Dict[str, Union[str, int, None]]) -> Optional[int]:
        try:
            return await self.w3.eth.estimate_gas(tx_params)
        except Exception as e:
            logger.error(f"Transaction estimate failed: {e}")
            return None

    async def get_tx_params(
        self,
        to: str,
        data: Optional[str] = None,
        from_: Optional[str] = None,
        value: Optional[int] = None,
    ) -> Dict[str, Union[str, int]]:
        if not from_:
            from_ = self.address

        tx_params: Dict[str, Union[str, int]] = {
            "chainId": await self.w3.eth.chain_id,
            "nonce": await self.w3.eth.get_transaction_count(self.address),
            "from": self.w3.to_checksum_address(from_),
            "to": self.w3.to_checksum_address(to),
        }

        if data:
            tx_params["data"] = data
        if value is not None:
            tx_params["value"] = value

        gas_price_multiplier = GAS_PRICE_MULTIPLIER if self.chain.chain_id == 534352 else 1
        tx_params["gasPrice"] = int(await self.w3.eth.gas_price * gas_price_multiplier)

        return tx_params

    async def send_transaction(
        self,
        to: str,
        data: str = None,
        from_: str = None,
        value: int = None,
        gas_limit_multiplier: float = GAS_LIMIT_MULTIPLIER,
    ) -> Optional[HexBytes]:
        """
        Sends a transaction on the current client's blockchain.

        Parameters:
        - to (str): The recipient's Ethereum address.
        - data (str, optional): Additional data to include in the transaction.
        - from_ (str, optional): The sender's Ethereum address. If not provided,
          the address associated with the initialized wallet will be used.
        - value (int, optional): The amount of Ether (in wei) to be sent with the transaction.

        Returns:
        - Optional[HexBytes]: The transaction hash if successful, otherwise None.

        Note:
        This method signs and sends an Ethereum transaction using the specified parameters.
        """
        tx_params = await self.get_tx_params(to=to, data=data, from_=from_, value=value)

        gas = await self.get_gas_estimate(tx_params=tx_params)
        if gas is None:
            return None
        tx_params["gas"] = int(gas * gas_limit_multiplier)

        signed_tx = self.w3.eth.account.sign_transaction(tx_params, self.private_key)

        try:
            return await self.w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        except Exception as e:
            logger.error(f"Error while sending transaction: {e}")
            return None

    async def verify_tx(self, tx_hash: Optional[HexBytes], timeout: int = VERIFY_TX_TIMEOUT) -> bool:
        """
        Verifies the status of a transaction on the current client's blockchain.

        Parameters:
        - tx_hash (HexBytes): The hash of the transaction to be verified.
        - timeout (int, optional): The maximum time (in seconds) to wait for the transaction receipt.
          Defaults to the value specified by VERIFY_TX_TIMEOUT.

        Returns:
        - bool: True if the transaction was successful, False otherwise.

        Note:
        This method checks the status of a transaction using its hash. It waits for the transaction
        receipt and logs the success or failure of the transaction with the corresponding log level.
        """
        if tx_hash is None:
            return False

        try:
            response = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)

            if "status" in response and response["status"] == 1:
                logger.success(f"Transaction was successful: {self.chain.explorer}tx/{self.w3.to_hex(tx_hash)}")
                return True
            else:
                logger.error(f"Transaction failed: {self.chain.explorer}tx/{self.w3.to_hex(tx_hash)}")
                return False
        except Exception as e:
            logger.error(f"Unexpected error in verify_tx function: {e}")
            return False

    async def get_allowance(
        self,
        token_contract: AsyncContract,
        spender: ChecksumAddress,
        owner: Optional[ChecksumAddress] = None,
    ) -> Optional[int]:
        if owner is None:
            owner = self.address

        try:
            return await token_contract.functions.allowance(owner, spender).call()
        except Exception as e:
            logger.error(f"Couldn't get allowance for of `{owner}` for `{spender}`: {e}")
            return None

    async def approve(
        self,
        spender: ChecksumAddress,
        token: Token,
        value: int = 0,
        ignore_allowance: bool = False,
        approve_value_range: Optional[List[int]] = APPROVE_VALUE_RANGE,
    ) -> bool:
        if approve_value_range is not None:
            value = token.to_wei(value=random.randint(*APPROVE_VALUE_RANGE))

        if token.is_native:
            return True

        token_contract: AsyncContract = self.w3.eth.contract(address=token.contract_address, abi=token.abi)
        allowance = await self.get_allowance(token_contract=token_contract, spender=spender)
        if ignore_allowance is False:
            if allowance >= value:
                logger.debug(
                    f"Allowance is greater than approve value: {token.from_wei(allowance)} >= {token.from_wei(value)}"
                )
                return True

        logger.info(f"Approving {value / pow(10, token.decimals)} {token.symbol} for spender: {spender}")
        data = token_contract.encodeABI("approve", args=(spender, value))
        tx_hash = await self.send_transaction(to=token_contract.address, data=data)

        if await self.verify_tx(tx_hash=tx_hash):
            await sleep(delay_range=POST_APPROVE_DELAY_RANGE, send_message=False)
            return True
        return False

    async def wrap_eth(self, amount: int) -> bool:
        eth_balance = await self.get_token_balance(ETH)

        if eth_balance < amount:
            logger.error(
                f"Amount to wrap is more than account balance: {ETH.from_wei(eth_balance)} < {ETH.from_wei(amount)}"
            )
            return False

        weth_contract: AsyncContract = self.w3.eth.contract(address=WETH.contract_address, abi=WETH.abi)

        data = weth_contract.encodeABI("deposit", args=())

        logger.info(f"Wrapping {ETH.from_wei(amount)} ETH")

        try:
            tx_hash = await self.send_transaction(to=weth_contract.address, data=data, value=amount)
            if await self.verify_tx(tx_hash=tx_hash):
                await sleep(delay_range=TX_DELAY_RANGE, send_message=False)
                return True
        except Exception as e:
            logger.error(f"Failed to wrap: {e}")
            return False

    async def unwrap_eth(self, amount: int, ignore_sleep: bool=False) -> bool:
        weth_contract: AsyncContract = self.w3.eth.contract(address=WETH.contract_address, abi=WETH.abi)

        data = weth_contract.encodeABI("withdraw", args=([amount]))

        logger.info(f"Unwrapping {ETH.from_wei(amount)} WETH")

        try:
            tx_hash = await self.send_transaction(to=weth_contract.address, data=data)
            if await self.verify_tx(tx_hash=tx_hash):
                if not ignore_sleep:
                    await sleep(delay_range=TX_DELAY_RANGE, send_message=False)
                return True
        except Exception as e:
            logger.error(f"Failed to unwrap: {e}")
            return False

    async def transfer(self, amount: Optional[int], to_address: str) -> bool:
        try:
            balance = await self.get_token_balance(ETH)

            if amount is None:
                amount = await self._calculate_amount_for_all_balance_transfer(balance=balance, to_address=to_address)
            if balance < amount:
                logger.error(
                    f"Amount to transfer is more than account balance: {ETH.from_wei(amount)} < {ETH.from_wei(balance)}"
                )
                return False

            logger.info(f"Transferring {ETH.from_wei(amount)} ETH to {to_address}")
            tx_hash = await self.send_transaction(to=to_address, value=amount)
            return await self.verify_tx(tx_hash=tx_hash)
        except Exception as ex:
            logger.error(f"Error while transferring: {ex}")

    async def _calculate_amount_for_all_balance_transfer(self, balance: int, to_address: str) -> int:
        try:
            tx_params = await self.get_tx_params(to=to_address, value=TRANSFER_TX_SIMULATION_VALUE)
            gas = await self.get_gas_estimate(tx_params=tx_params)
            return balance - int((gas * tx_params['gasPrice']) * 1.55)
        except Exception as e:
            raise Exception(f"Failed to estimate amount for all balance transfer: {e}")

    async def is_amount_out_suitable(
        self,
        token_in: Token,
        token_out: Token,
        token_in_amount: int,
        min_amount_out: int,
        slippage: Union[int, float],
    ) -> bool:
        """
        Checks whether the expected amount of output tokens is suitable based on the input parameters.

        Parameters:
        - token_in (Token): The input token.
        - token_out (Token): The output token.
        - token_in_amount (int): The amount of input tokens to be swapped.
        - min_amount_out (int): The minimum acceptable amount of output tokens.
        - slippage (Union[int, float]): The allowed slippage percentage as an integer or float.

        Returns:
        - bool: True if the expected amount of output tokens is suitable, False otherwise.

        This function calculates the expected output amount based on the provided input parameters,
        considering the current token prices fetched asynchronously. It checks whether the calculated
        minimum amount of output tokens meets the specified minimum requirement, accounting for slippage.

        Note: The function returns False if token price data cannot be fetched.
        """
        price_data = await self.fetch_token_price(token_list=(token_in, token_out))
        if price_data is None:
            return False
        token_in_price, token_out_price = price_data
        token_in_usd_value = token_in.from_wei(value=token_in_amount) * token_in_price
        suitable_min_amount_out = int(
            token_out.to_wei(value=token_in_usd_value / token_out_price * ((100 - slippage) / 100))
            * (1 - MAX_ALLOWED_TOKEN_PRICE_DIFFERENCE / 100)
        )
        if suitable_min_amount_out <= min_amount_out:
            return True
        logger.warning(f"Amount out is lower than minimum suitable value: {min_amount_out} < {suitable_min_amount_out}")
        return False

    @retry_on_fail()
    async def get_token_balance(self, token: Token, wei: bool = True) -> Optional[int]:
        try:
            if token == ETH:
                balance = await self.w3.eth.get_balance(account=self.address)
            else:
                contract = self.w3.eth.contract(address=token.contract_address, abi=token.abi)
                balance = await contract.functions.balanceOf(self.address).call()
            return balance if wei else token.from_wei(value=balance)
        except Exception as e:
            logger.error(f"Couldn't get balance of {token}: {e}")
            return None

    async def get_token_balance_batch(self, token_list: List[Token], wei: bool = True) -> Optional[List[int]]:
        try:
            results = await asyncio.gather(*[self.get_token_balance(token, wei) for token in token_list])

            if any(balance is None for balance in results):
                return None

            return results
        except Exception as e:
            logger.error(f"Couldn't get batch balance: {e}")
            return None

    async def get_token_with_largest_usd_balance(self) -> Optional[Tuple[Token, float]]:
        prices = await self.fetch_token_price(token_list=self.tokens)
        if prices:
            token_price_mapping = {token: price for token, price in zip(self.tokens, prices)}
        else:
            return None

        balances = await self.get_token_balance_batch(token_list=self.tokens, wei=False)
        if balances:
            token_balance_mapping = {token: balance for token, balance in zip(self.tokens, balances)}
        else:
            return None

        usd_balances = {token: balance * token_price_mapping[token] for token, balance in token_balance_mapping.items()}
        token_with_largest_usd_balance = max(usd_balances, key=usd_balances.get)
        return (
            token_with_largest_usd_balance,
            token_balance_mapping[token_with_largest_usd_balance],
        )

    async def wait_for_deposit(
        self,
        initial_balance: int,
        checkup_sleep_time_range: List[int],
        attempts: Optional[int] = None,
    ) -> bool:
        if not attempts:
            attempts = True

        logger.info(f"Waiting for funds on {self.chain.name}")

        while attempts:
            final_balance = await self.get_token_balance(token=ETH)
            if final_balance > initial_balance:
                logger.info(f"Funds on {self.chain.name} received")
                return True
            if attempts is not True:
                attempts -= 1
            await sleep(
                delay_range=checkup_sleep_time_range,
                send_message=False,
                pr_bar=False,
            )
        logger.error(f"Funds not received on {self.chain.name}")
        return False

    async def get_random_token(self, excluded_token: Token) -> Token:
        available_tokens = [token for token in self.tokens if token != excluded_token]
        return random.choice(available_tokens)
