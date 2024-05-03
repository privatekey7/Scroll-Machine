import random
from typing import Optional, Tuple, Dict

from core import Client
from core.chain import ARBITRUM, SCROLL, ZKSYNC, NAMES_TO_CHAINS
from core.constants import TOKEN_FULL_BALANCE_USAGE_MULTIPLIER, VOLUME_MODE_STATE_NAME
from core.dapps import CogFinance, LayerBank
from core.token import ETH, WETH
from logger import logger
from config import (
    USE_MOBILE_PROXY,
    WALLET_DELAY_RANGE,
    VOLUME_MODE_CHAIN_TO_USE,
    USE_ETH_BACKSWAP,
    SWAP_PERCENTAGE_RANGE,
    LENDING_PERCENTAGE_RANGE,
    VOLUME_BRIDGE_TO_SCROLL_NAME,
    VOLUME_BRIDGE_FROM_SCROLL_NAME,
    TOKENS_TO_COLLECT,
    TX_DELAY_RANGE,
)
from models.wallet import Wallet
from modules.base.volume_base import (
    volume_okx_withdraw_action,
    volume_bridge_and_wait_action,
    volume_transfer_eth_action,
)
from modules.collector import get_token_ids_to_prices, perform_collector_action
from modules.database import Database
from modules.warmup import get_dex_instance_by_name
from utils import change_ip, sleep


async def volume():
    database = Database.read_from_json()

    if not database.ensure_ready_for_volume_mode():
        logger.error("Deposit addresses must be provided for each wallet")
        return

    token_ids_to_prices = await get_token_ids_to_prices(wallet=database.data[0])

    while database.has_volume_actions_available():
        try:
            if USE_MOBILE_PROXY:
                await change_ip()

            wallet_data = database.get_first_volume_wallet(state_dict_name="volume_mode_state")

            if wallet_data is None:
                break

            wallet, wallet_index = wallet_data
            logger.info(f"Working with wallet {wallet.address}")

            await perform_volume_mode_cycle(
                database=database, wallet=wallet, wallet_index=wallet_index, token_prices=token_ids_to_prices
            )
            await sleep(delay_range=WALLET_DELAY_RANGE, send_message=False)
        except Exception as e:
            logger.exception(f"Error occurred: {e}")
    logger.success("No more wallets left")


async def perform_volume_mode_cycle(
    database: Database, wallet: Wallet, wallet_index: int, token_prices: Dict[str, float]
) -> Optional[bool]:
    chain_to_use = NAMES_TO_CHAINS[VOLUME_MODE_CHAIN_TO_USE]
    if wallet.volume_mode_state["okx_withdrawn"] is None:
        if not await volume_okx_withdraw_action(
            wallet=wallet,
            wallet_index=wallet_index,
            database=database,
            src_chain=chain_to_use,
            state_dict_name=VOLUME_MODE_STATE_NAME,
        ):
            return False

    if not wallet.volume_mode_state["bridged_to_scroll"]:
        if not await volume_bridge_and_wait_action(
            database=database,
            wallet=wallet,
            wallet_index=wallet_index,
            src_chain=chain_to_use,
            dst_chain=SCROLL,
            bridge_to_use=VOLUME_BRIDGE_TO_SCROLL_NAME,
            state_dict_name=VOLUME_MODE_STATE_NAME,
        ):
            return False

    while wallet.volume_mode_state["volume_reached"] < wallet.volume_mode_state["volume_goal"]:
        action_data = wallet.get_random_volume_action_pair()
        if action_data is None:
            return None
        action, dapp = action_data

        amount_used = await perform_volume_action(
            action=action,
            executor=dapp,
            wallet=wallet,
            wallet_index=wallet_index,
            database=database,
            token_prices=token_prices,
        )

        if amount_used is not None:
            wallet.volume_mode_state["volume_reached"] += amount_used
            database.update_item(item_index=wallet_index, volume_mode_state=wallet.volume_mode_state)

        await sleep(delay_range=TX_DELAY_RANGE, send_message=False)

    await volume_collector_action(database=database, wallet=wallet, token_prices=token_prices)

    chain_to_withdraw = ARBITRUM if chain_to_use == ZKSYNC else chain_to_use
    if not wallet.volume_mode_state["bridged_from_scroll"]:
        if not await volume_bridge_and_wait_action(
            database=database,
            wallet=wallet,
            wallet_index=wallet_index,
            src_chain=SCROLL,
            dst_chain=chain_to_withdraw,
            bridge_to_use=VOLUME_BRIDGE_FROM_SCROLL_NAME,
            state_dict_name=VOLUME_MODE_STATE_NAME,
        ):
            return False

    if not wallet.volume_mode_state["deposited_to_okx"]:
        if not await volume_transfer_eth_action(
            database=database,
            wallet=wallet,
            wallet_index=wallet_index,
            src_chain=chain_to_withdraw,
            state_dict_name=VOLUME_MODE_STATE_NAME,
        ):
            return False
    return True


async def perform_volume_action(
    action: str, executor: str, wallet: Wallet, wallet_index: int, database: Database, token_prices: Dict[str, float]
) -> Optional[float]:
    client = wallet.to_client(chain=SCROLL)

    if action == "swap":
        swap_result = await volume_swap_action(dex=executor, client=client)
        if swap_result is None:
            return None

        amount, token_id = swap_result
        return round(amount * token_prices[token_id], 3)
    elif action == "lending":
        amount_used = await volume_lending_action(
            lending=executor,
            wallet=wallet,
            wallet_index=wallet_index,
            database=database,
            client=client,
        )
        if amount_used is None:
            return None
        return round(amount_used * token_prices[ETH.api_id], 3)
    elif action == "unwrap":
        weth_balance = await client.get_token_balance(WETH)
        if await client.unwrap_eth(amount=weth_balance, ignore_sleep=True):
            wallet.volume_mode_state["eth_wrapped"] = False
            database.update_item(item_index=wallet_index, volume_mode_state=wallet.volume_mode_state)
        return None


async def volume_swap_action(dex: str, client: Client) -> Optional[Tuple[float, str]]:
    token_in_data = await client.get_token_with_largest_usd_balance()
    if not token_in_data:
        return None
    token_in, balance = token_in_data

    if not token_in.is_native and USE_ETH_BACKSWAP:
        amount = balance * TOKEN_FULL_BALANCE_USAGE_MULTIPLIER
        token_out = ETH
    else:
        amount = round(
            float(balance) * (random.randint(*SWAP_PERCENTAGE_RANGE) / 100),
            token_in.round_to,
        )
        token_out = await client.get_random_token(excluded_token=token_in)

    dex_instance = get_dex_instance_by_name(client=client, dex=dex)
    if dex_instance is None:
        return None

    if await dex_instance.swap(token_in=token_in, token_out=token_out, amount=amount):
        return amount, token_in.api_id
    return None


async def volume_lending_action(
    lending: str, wallet: Wallet, wallet_index: int, database: Database, client: Client
) -> Optional[float]:
    eth_used = 0.0

    if lending == "cog":
        lending_instance = CogFinance(client=client)
    if lending == "layerbank":
        lending_instance = LayerBank(client=client)

    supplied_amount = await lending_instance.get_supplied_amount()

    if supplied_amount > 0:
        if not await lending_instance.withdraw():
            return eth_used

        wallet.volume_mode_state["last_lending"] = None
        database.update_item(item_index=wallet_index, volume_mode_state=wallet.volume_mode_state)
        await sleep(delay_range=TX_DELAY_RANGE, send_message=False)

        if lending == "cog":
            weth_balance = await client.get_token_balance(token=WETH)
            if await client.unwrap_eth(amount=weth_balance):
                wallet.volume_mode_state["eth_wrapped"] = False
                database.update_item(item_index=wallet_index, volume_mode_state=wallet.volume_mode_state)
        return eth_used

    balance = await client.get_token_balance(token=ETH, wei=False)
    amount = round(
        float(balance) * (random.randint(*LENDING_PERCENTAGE_RANGE) / 100),
        ETH.round_to,
    )

    if lending == "cog":
        if wallet.volume_mode_state["eth_wrapped"]:
            amount = await client.get_token_balance(token=WETH, wei=False)
        else:
            if not await client.wrap_eth(amount=WETH.to_wei(amount)):
                return None
            eth_used += amount
            wallet.volume_mode_state["eth_wrapped"] = True
            database.update_item(item_index=wallet_index, volume_mode_state=wallet.volume_mode_state)

    value = amount if lending == "layerbank" else WETH.to_wei(amount)
    if not await lending_instance.supply(value=value):
        return eth_used

    eth_used += amount
    wallet.volume_mode_state["last_lending"] = lending
    database.update_item(item_index=wallet_index, volume_mode_state=wallet.volume_mode_state)
    return eth_used


async def volume_collector_action(database: Database, wallet: Wallet, token_prices: Dict[str, float]):
    while len(wallet.tokens_collected) != len(TOKENS_TO_COLLECT):
        tokens_to_collect = list(set(TOKENS_TO_COLLECT) - set(wallet.tokens_collected))

        await perform_collector_action(
            database=database,
            wallet=wallet,
            token_symbols_to_collect=tokens_to_collect,
            token_prices=token_prices,
        )
