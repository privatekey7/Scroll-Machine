import random

from core.constants import POST_BRIDGE_CHECK_WAIT_RANGE
from core.dapps import ScrollBridge
from core.dapps.orbiter import Orbiter
from core.dapps.routernitro import RouterNitro
from core.token import ETH
from logger import logger
from config import (
    OKX_API_KEY,
    OKX_API_SECRET,
    OKX_API_PASSWORD,
    OKX_WITHDRAW_AMOUNT_RANGE,
    USE_OKX_WITHDRAW,
    BRIDGE_TO_USE,
    BRIDGE_FULL_BALANCE,
    BRIDGE_AMOUNT_RANGE,
    POST_BRIDGE_DELAY_RANGE,
    USE_MOBILE_PROXY,
    BRIDGER_USE_KEEP_AMOUNT,
    BRIDGER_KEEP_AMOUNT_RANGE,
    SRC_CHAIN_TO_USE,
    DST_CHAIN_TO_USE,
)
from core import Client
from core.chain import SCROLL, MAINNET, NAMES_TO_CHAINS
from core.okx import Okx
from models.wallet import Wallet
from modules.database import Database
from utils import sleep, change_ip


async def bridge_batch():
    database = Database.read_from_json()

    while True:
        if USE_MOBILE_PROXY:
            await change_ip()

        wallet_data = database.get_random_item_by_criteria(bridge_finished=False)

        if wallet_data is None:
            break

        wallet, wallet_index = wallet_data
        logger.info(f"Working with wallet {wallet.address}")

        if USE_OKX_WITHDRAW:
            if not await perform_okx_withdraw(wallet=wallet, wallet_index=wallet_index, database=database):
                continue

        if not await perform_bridge(wallet=wallet, wallet_index=wallet_index, database=database):
            continue

        await sleep(delay_range=POST_BRIDGE_DELAY_RANGE, send_message=False)
    logger.success("No more wallets left")


async def perform_okx_withdraw(wallet: Wallet, wallet_index: int, database: Database) -> bool:
    if wallet.okx_withdrawn is not None or SRC_CHAIN_TO_USE == SCROLL.name:
        return True

    if BRIDGE_TO_USE == "Orbiter" or BRIDGE_TO_USE == "Nitro":
        chain = NAMES_TO_CHAINS[SRC_CHAIN_TO_USE]
        client = wallet.to_client(chain=chain)
    elif BRIDGE_TO_USE == "Official":
        client = wallet.to_client(chain=MAINNET)
    else:
        logger.error(f'BRIDGE_TO_USE can only have "Orbiter", "Nitro" or "Official" value')
        exit()

    okx = Okx(
        client=client,
        api_key=OKX_API_KEY,
        api_secret=OKX_API_SECRET,
        password=OKX_API_PASSWORD,
    )

    amount = round(random.uniform(*OKX_WITHDRAW_AMOUNT_RANGE), 6)

    if await okx.withdraw(amount=amount, chain=client.chain):
        database.update_item(item_index=wallet_index, okx_withdrawn=amount)
        return True
    return False


async def perform_bridge(wallet: Wallet, wallet_index: int, database: Database) -> bool:
    dst_chain_client = wallet.to_client(chain=NAMES_TO_CHAINS[DST_CHAIN_TO_USE])

    if wallet.initial_balance is not None:
        if await check_if_bridge_finished(wallet=wallet, client=dst_chain_client):
            logger.success(f"Bridged ETH has successfully reached Scroll")
            database.update_item(item_index=wallet_index, bridge_finished=True)
            return True
        else:
            logger.warning(f"Bridged ETH is still inflight")
            await sleep(delay_range=POST_BRIDGE_CHECK_WAIT_RANGE, pr_bar=False)
            return False

    if BRIDGE_TO_USE == "Orbiter":
        client = wallet.to_client(chain=NAMES_TO_CHAINS[SRC_CHAIN_TO_USE])
        bridge_dapp = Orbiter(src_chain_client=client, dst_chain_client=dst_chain_client)
    elif BRIDGE_TO_USE == "Nitro":
        client = wallet.to_client(chain=NAMES_TO_CHAINS[SRC_CHAIN_TO_USE])
        bridge_dapp = RouterNitro(src_chain_client=client, dst_chain_client=dst_chain_client)
    elif BRIDGE_TO_USE == "Official":
        client = wallet.to_client(chain=MAINNET)
        bridge_dapp = ScrollBridge(client=client)
    else:
        logger.error(f'BRIDGE_TO_USE can only have "Orbiter", "Nitro" or "Official" value')
        exit()

    initial_balance = await dst_chain_client.get_token_balance(ETH)

    if BRIDGER_USE_KEEP_AMOUNT:
        balance = await client.get_token_balance(ETH, wei=False)
        keep_amount = round(random.uniform(*BRIDGER_KEEP_AMOUNT_RANGE), 6)
        amount = balance - keep_amount
    elif wallet.okx_withdrawn is not None and client.chain != SCROLL:
        amount = wallet.okx_withdrawn
    elif BRIDGE_FULL_BALANCE:
        amount = None
    else:
        amount = round(random.uniform(*BRIDGE_AMOUNT_RANGE), 6)

    if await bridge_dapp.bridge(amount=amount):
        database.update_item(item_index=wallet_index, initial_balance=initial_balance)
        return True
    return False


async def check_if_bridge_finished(wallet: Wallet, client: Client) -> bool:
    current_balance = await client.get_token_balance(ETH)
    return current_balance > wallet.initial_balance
