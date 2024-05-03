import random

from config import (
    AMOUNT_TO_LEAVE_ON_SCROLL_RANGE,
    USE_KEEP_AMOUNT,
    AMOUNT_TO_LEAVE_ON_SRC_CHAIN_RANGE,
    AMOUNT_TO_LEAVE_BEFORE_TRANSFER,
    OKX_API_KEY,
    OKX_API_SECRET,
    OKX_API_PASSWORD,
    OKX_WITHDRAW_AMOUNT_RANGE,
    TX_DELAY_RANGE,
)
from core import Chain
from core.chain import SCROLL
from core.constants import POST_BRIDGE_CHECK_WAIT_RANGE
from core.dapps.orbiter import Orbiter
from core.dapps.routernitro import RouterNitro
from core.okx import Okx
from core.token import ETH
from logger import logger
from models.wallet import Wallet
from modules.database import Database
from utils import sleep


async def volume_bridge_and_wait_action(
    wallet: Wallet,
    wallet_index: int,
    database: Database,
    src_chain: Chain,
    dst_chain: Chain,
    bridge_to_use: str,
    state_dict_name: str,
) -> bool:
    if getattr(wallet, state_dict_name)["dst_chain_initial_balance"] is None:
        if not await _bridge_action(
            wallet=wallet,
            wallet_index=wallet_index,
            database=database,
            src_chain=src_chain,
            dst_chain=dst_chain,
            bridge_to_use=bridge_to_use,
            state_dict_name=state_dict_name,
        ):
            return False

    if await _wait_for_bridge_received(wallet=wallet, dst_chain=dst_chain, state_dict_name=state_dict_name):
        getattr(wallet, state_dict_name)["dst_chain_initial_balance"] = None
        if src_chain == SCROLL:
            getattr(wallet, state_dict_name)["bridged_from_scroll"] = True
        else:
            getattr(wallet, state_dict_name)["bridged_to_scroll"] = True

        database.update_state(
            item_index=wallet_index, state_dict_name=state_dict_name, new_state=getattr(wallet, state_dict_name)
        )
        return True


async def volume_okx_withdraw_action(
    wallet: Wallet, wallet_index: int, database: Database, src_chain: Chain, state_dict_name: str
) -> bool:
    target_client = wallet.to_client(chain=src_chain)

    okx = Okx(
        client=target_client,
        api_key=OKX_API_KEY,
        api_secret=OKX_API_SECRET,
        password=OKX_API_PASSWORD,
    )

    amount = round(random.uniform(*OKX_WITHDRAW_AMOUNT_RANGE), 6)
    if await okx.withdraw(amount=amount, chain=src_chain):
        getattr(wallet, state_dict_name)["okx_withdrawn"] = amount
        database.update_state(
            item_index=wallet_index, state_dict_name=state_dict_name, new_state=getattr(wallet, state_dict_name)
        )
        return True
    return False


async def volume_transfer_eth_action(
    database: Database, wallet: Wallet, wallet_index: int, src_chain: Chain, state_dict_name: str
) -> bool:
    client = wallet.to_client(chain=src_chain)

    eth_balance = await client.get_token_balance(ETH, wei=False)
    amount_to_leave = random.uniform(*AMOUNT_TO_LEAVE_BEFORE_TRANSFER)

    if eth_balance < amount_to_leave:
        logger.error("AMOUNT_TO_LEAVE_BEFORE_TRANSFER is more than actual account balance")
        return False

    if amount_to_leave == 0:
        amount_to_transfer = None
    else:
        amount_to_transfer = ETH.to_wei(eth_balance - amount_to_leave)

    if not await client.transfer(to_address=wallet.deposit_address, amount=amount_to_transfer):
        return False

    getattr(wallet, state_dict_name)["deposited_to_okx"] = True
    database.update_state(
        item_index=wallet_index, state_dict_name=state_dict_name, new_state=getattr(wallet, state_dict_name)
    )
    return True


async def _bridge_action(
    wallet: Wallet,
    wallet_index: int,
    database: Database,
    src_chain: Chain,
    dst_chain: Chain,
    bridge_to_use: str,
    state_dict_name: str,
) -> bool:
    src_chain_client = wallet.to_client(chain=src_chain)
    dst_chain_client = wallet.to_client(chain=dst_chain)

    dst_chain_initial_balance = await dst_chain_client.get_token_balance(ETH)

    if src_chain == SCROLL:
        src_chain_eth_balance = await src_chain_client.get_token_balance(ETH, wei=False)
        amount_to_leave = random.uniform(*AMOUNT_TO_LEAVE_ON_SCROLL_RANGE)
        if amount_to_leave == 0:
            amount_to_bridge = None
        else:
            amount_to_bridge = round(src_chain_eth_balance - amount_to_leave, 6)
    else:
        if USE_KEEP_AMOUNT:
            balance = await src_chain_client.get_token_balance(ETH, wei=False)
            keep_amount = round(random.uniform(*AMOUNT_TO_LEAVE_ON_SRC_CHAIN_RANGE), 6)
            if keep_amount == 0:
                amount_to_bridge = None
            else:
                amount_to_bridge = round(balance - keep_amount, 6)
        else:
            amount_to_bridge = getattr(wallet, state_dict_name)["okx_withdrawn"]

    if bridge_to_use == "Nitro":
        bridge_dapp = RouterNitro(src_chain_client=src_chain_client, dst_chain_client=dst_chain_client)
    elif bridge_to_use == "Orbiter":
        bridge_dapp = Orbiter(src_chain_client=src_chain_client, dst_chain_client=dst_chain_client)
    else:
        logger.error(f"Unknown bridge dapp: {bridge_to_use}")
        return False

    if await bridge_dapp.bridge(amount=amount_to_bridge):
        getattr(wallet, state_dict_name)["dst_chain_initial_balance"] = dst_chain_initial_balance
        database.update_state(
            item_index=wallet_index, state_dict_name=state_dict_name, new_state=getattr(wallet, state_dict_name)
        )
        await sleep(delay_range=TX_DELAY_RANGE, pr_bar=True, send_message=False)
        return True
    return False


async def _wait_for_bridge_received(wallet: Wallet, dst_chain: Chain, state_dict_name: str) -> bool:
    dst_chain_client = wallet.to_client(chain=dst_chain)

    while True:
        current_balance = await dst_chain_client.get_token_balance(ETH)
        if current_balance > getattr(wallet, state_dict_name)["dst_chain_initial_balance"]:
            logger.success(f"Bridged ETH has successfully reached {dst_chain.name}")
            return True

        logger.warning("Bridged ETH is still inflight")
        await sleep(delay_range=POST_BRIDGE_CHECK_WAIT_RANGE, pr_bar=False)
