import random
from typing import Dict, List

from config import (
    MINIMUM_USD_COLLECTED_VALUE,
    TOKENS_TO_COLLECT,
    TX_DELAY_RANGE,
    USE_MOBILE_PROXY,
)
from core import Client
from core.chain import SCROLL
from core.constants import TOKEN_FULL_BALANCE_USAGE_MULTIPLIER
from core.dapps import CogFinance, LayerBank
from core.dapps.multicall import MulticallV3
from core.token import COG_WETH, ETH, LETH, SYMBOLS_TO_TOKENS, USDC, USDT, WETH, Token
from logger import logger
from models.wallet import Wallet
from modules.database import Database
from modules.warmup import get_dex_instance_by_name
from utils import change_ip, sleep


async def collect():
    database = Database.read_from_json()

    if len(database.data) == 0:
        logger.error("Database is empty")
        return None

    token_ids_to_prices = await get_token_ids_to_prices(wallet=database.data[0])

    while True:
        if USE_MOBILE_PROXY:
            await change_ip()

        wallet = database.get_random_active_collector_item()

        if wallet is None:
            break

        logger.info(f"Working with wallet {wallet.address}")

        tokens_to_collect = list(set(TOKENS_TO_COLLECT) - set(wallet.tokens_collected))

        await perform_collector_action(
            database=database,
            wallet=wallet,
            token_symbols_to_collect=tokens_to_collect,
            token_prices=token_ids_to_prices,
        )
    logger.success("No more wallets left")


async def perform_collector_action(
    database: Database, wallet: Wallet, token_symbols_to_collect: List[str], token_prices: Dict[str, float]
):
    tokens_to_collect = [SYMBOLS_TO_TOKENS[token_symbol] for token_symbol in token_symbols_to_collect]

    client = wallet.to_client(SCROLL)

    tokens_usd_balances = await get_token_usd_balances(
        client=client, token_list=tokens_to_collect, token_prices=token_prices
    )

    for token, usd_balance in tokens_usd_balances.items():
        if usd_balance < MINIMUM_USD_COLLECTED_VALUE:
            tokens_to_collect.remove(token)
            wallet.tokens_collected.append(token.symbol)
            database.save_database()

    if len(tokens_to_collect) == 0:
        return None

    logger.debug(f"Tokens to collect: {tokens_to_collect}")

    token_in = random.choice(tokens_to_collect)

    if token_in == LETH:
        layerbank = LayerBank(client=client)
        collect_result = await layerbank.withdraw()
    elif token_in == COG_WETH:
        cog_finance = CogFinance(client=client)
        collect_result = await cog_finance.withdraw()
    elif token_in == WETH:
        weth_balance = int(await client.get_token_balance(token=WETH) * TOKEN_FULL_BALANCE_USAGE_MULTIPLIER)
        collect_result = await client.unwrap_eth(amount=weth_balance)
    else:
        token_balance = await client.get_token_balance(token=token_in, wei=False) * TOKEN_FULL_BALANCE_USAGE_MULTIPLIER
        collect_result = await perform_swap_action(client=client, token_in=token_in, amount=token_balance)

    if collect_result:
        wallet.tokens_collected.append(token_in.symbol)

        if token_in == COG_WETH and "WETH" in wallet.tokens_collected:
            wallet.tokens_collected.remove("WETH")

        database.save_database()
        await sleep(delay_range=TX_DELAY_RANGE)


async def get_token_ids_to_prices(wallet: Wallet) -> Dict[str, float]:
    temp_client = wallet.to_client(chain=SCROLL)
    tokens_to_fetch = [ETH, USDT, USDC]

    prices = await temp_client.fetch_token_price(tokens_to_fetch)
    token_ids_to_prices = {token.api_id: price for token, price in zip(tokens_to_fetch, prices)}

    return token_ids_to_prices


async def get_token_usd_balances(
    client: Client, token_list: List[Token], token_prices: Dict[str, float]
) -> Dict[Token, float]:
    multicall = MulticallV3(client=client)
    token_balances = await multicall.get_token_balances(token_list=token_list)

    usd_balances = {token: balance * token_prices[token.api_id] for token, balance in token_balances.items()}

    return usd_balances


async def perform_swap_action(client: Client, token_in: Token, amount: float):
    dex = random.choice(["izumi", "skydrome", "spacefi", "syncswap", "zebra"])

    dex_instance = get_dex_instance_by_name(client=client, dex=dex)

    return await dex_instance.swap(token_in=token_in, token_out=ETH, amount=amount)
