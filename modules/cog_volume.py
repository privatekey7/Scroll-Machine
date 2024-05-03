import random


from core.chain import ARBITRUM, SCROLL, ZKSYNC, NAMES_TO_CHAINS
from core.constants import COG_VOLUME_STATE_NAME
from core.dapps import CogFinance
from core.token import ETH, WETH
from logger import logger
from config import (
    USE_MOBILE_PROXY,
    WALLET_DELAY_RANGE,
    WRAP_ETH_BALANCE_PERCENTAGE_RANGE,
    TX_DELAY_RANGE,
    WRAPPED_ETH_USAGE_PERCENTAGE_RANGE,
    VOLUME_MODE_CHAIN_TO_USE,
    VOLUME_BRIDGE_TO_SCROLL_NAME,
    VOLUME_BRIDGE_FROM_SCROLL_NAME,
)
from models.wallet import Wallet
from modules.base.volume_base import (
    volume_okx_withdraw_action,
    volume_bridge_and_wait_action,
    volume_transfer_eth_action,
)
from modules.database import Database
from utils import change_ip, sleep


async def cog_volume():
    database = Database.read_from_json()

    if not database.ensure_ready_for_volume_mode():
        logger.error("Deposit addresses must be provided for each wallet")
        return

    while database.has_volume_actions_available():
        try:
            if USE_MOBILE_PROXY:
                await change_ip()

            wallet_data = database.get_first_volume_wallet(state_dict_name="cog_volume_state")

            if wallet_data is None:
                break

            wallet, wallet_index = wallet_data

            logger.info(f"Working with wallet {wallet.address}")

            await perform_volume_mode_cycle(database=database, wallet=wallet, wallet_index=wallet_index)
            await sleep(delay_range=WALLET_DELAY_RANGE, send_message=False)
        except Exception as e:
            logger.exception(f"Error occurred: {e}")
    logger.success("No more wallets left")


async def perform_volume_mode_cycle(database: Database, wallet: Wallet, wallet_index: int) -> bool:
    chain_to_use = NAMES_TO_CHAINS[VOLUME_MODE_CHAIN_TO_USE]
    if wallet.cog_volume_state["okx_withdrawn"] is None:
        if not await volume_okx_withdraw_action(
            wallet=wallet,
            wallet_index=wallet_index,
            database=database,
            src_chain=chain_to_use,
            state_dict_name=COG_VOLUME_STATE_NAME,
        ):
            return False

    if not wallet.cog_volume_state["bridged_to_scroll"]:
        if not await volume_bridge_and_wait_action(
            database=database,
            wallet=wallet,
            wallet_index=wallet_index,
            src_chain=chain_to_use,
            dst_chain=SCROLL,
            bridge_to_use=VOLUME_BRIDGE_TO_SCROLL_NAME,
            state_dict_name=COG_VOLUME_STATE_NAME,
        ):
            return False

    client = wallet.to_client(chain=SCROLL)

    if not wallet.cog_volume_state["eth_wrapped"]:
        eth_balance = await client.get_token_balance(token=ETH)
        amount_to_wrap = int(eth_balance * (random.randint(*WRAP_ETH_BALANCE_PERCENTAGE_RANGE) / 100))

        if not await client.wrap_eth(amount=amount_to_wrap):
            return False

        wallet.cog_volume_state["eth_wrapped"] = True
        database.update_item(item_index=wallet_index, cog_volume_state=wallet.cog_volume_state)

    cog = CogFinance(client=client)

    while (
        wallet.cog_volume_state["volume_reached"] < wallet.cog_volume_state["volume_goal"]
        or wallet.cog_volume_state["last_action"] == "supply"
    ):
        if USE_MOBILE_PROXY:
            await change_ip()

        if wallet.cog_volume_state["last_action"] == "withdraw" or wallet.cog_volume_state["last_action"] is None:
            tx_amount = int(
                (await client.get_token_balance(token=WETH))
                * (random.randint(*WRAPPED_ETH_USAGE_PERCENTAGE_RANGE) / 100)
            )
            if not await cog.supply(value=tx_amount):
                continue

            action = "supply"
        else:
            tx_amount = 0
            if not await cog.withdraw():
                continue

            action = "withdraw"

        wallet.cog_volume_state["volume_reached"] += round(WETH.from_wei(tx_amount), 6)
        wallet.cog_volume_state["last_action"] = action
        database.update_item(item_index=wallet_index, cog_volume_state=wallet.cog_volume_state)

        await sleep(delay_range=TX_DELAY_RANGE, send_message=False)

    if not wallet.cog_volume_state["eth_unwrapped"]:
        weth_balance = await client.get_token_balance(token=WETH)

        if not await client.unwrap_eth(amount=weth_balance):
            return False

        wallet.cog_volume_state["eth_unwrapped"] = True
        database.update_item(item_index=wallet_index, cog_volume_state=wallet.cog_volume_state)

    chain_to_withdraw = ARBITRUM if chain_to_use == ZKSYNC else chain_to_use
    if not wallet.cog_volume_state["bridged_from_scroll"]:
        if not await volume_bridge_and_wait_action(
            database=database,
            wallet=wallet,
            wallet_index=wallet_index,
            src_chain=SCROLL,
            dst_chain=chain_to_withdraw,
            bridge_to_use=VOLUME_BRIDGE_FROM_SCROLL_NAME,
            state_dict_name=COG_VOLUME_STATE_NAME,
        ):
            return False

    if not wallet.cog_volume_state["deposited_to_okx"]:
        if not await volume_transfer_eth_action(
            database=database,
            wallet=wallet,
            wallet_index=wallet_index,
            src_chain=chain_to_withdraw,
            state_dict_name=COG_VOLUME_STATE_NAME,
        ):
            return False
    return True
