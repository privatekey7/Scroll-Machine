import random
from typing import Optional

from web3.contract import AsyncContract

from config import (
    LENDING_PERCENTAGE_RANGE,
    MAX_NFT_TOKEN_OWNED,
    SCROLL_NFTS_TO_MINT,
    SWAP_PERCENTAGE_RANGE,
    TX_DELAY_RANGE,
    USE_ETH_BACKSWAP,
    USE_MOBILE_PROXY,
)
from core.chain import SCROLL
from core.client import Client
from core.constants import SCROLL_NFT_ABI, TOKEN_FULL_BALANCE_USAGE_MULTIPLIER
from core.dapps import (
    Dex,
    Dmail,
    Izumi,
    LayerBank,
    ScrollDomains,
    Skydrome,
    Spacefi,
    Syncswap,
    Zebra,
)
from core.dapps.rubyscore import RubyScore
from core.decorators import gas_delay
from core.token import ETH
from logger import logger
from models.wallet import Wallet
from modules.database import Database
from utils import change_ip, sleep


async def warmup():
    database = Database.read_from_json()

    while database.has_actions_available():
        if USE_MOBILE_PROXY:
            await change_ip()

        wallet_data = database.get_random_item_by_criteria(warmup_finished=False)
        wallet, wallet_index = wallet_data

        dapp = wallet.get_random_dapp()
        action = wallet.get_action_from_dapp(dapp=dapp)

        logger.info(f"Working with wallet {wallet.address}")

        await perform_warmup_action(
            action=action,
            wallet=wallet,
            executor=dapp,
            wallet_index=wallet_index,
            database=database,
        )
        await sleep(delay_range=TX_DELAY_RANGE, send_message=False)
    logger.success("No more wallets left")


async def perform_warmup_action(
    action: str, executor: str, wallet: Wallet, wallet_index: int, database: Database
) -> None:
    client = wallet.to_client(chain=SCROLL)

    if action == "swap":
        has_actions_left = await swap_action(
            dex=executor,
            wallet=wallet,
            wallet_index=wallet_index,
            database=database,
            client=client,
        )
    elif action == "dmail":
        has_actions_left = await dmail_action(
            wallet=wallet,
            wallet_index=wallet_index,
            database=database,
            client=client,
        )
    elif action == "lending":
        has_actions_left = await lending_action(
            lending=executor,
            wallet=wallet,
            wallet_index=wallet_index,
            database=database,
            client=client,
        )
    elif action == "nft":
        nft_address = wallet.get_random_nft()
        has_actions_left = await mint_action(
            nft_address=nft_address, wallet=wallet, wallet_index=wallet_index, database=database, client=client
        )
    elif action == "domain":
        has_actions_left = await register_domain_action(
            wallet=wallet, wallet_index=wallet_index, database=database, client=client
        )
    elif action == "rubyscore":
        has_actions_left = await rubyscore_action(
            wallet=wallet, wallet_index=wallet_index, database=database, client=client
        )
    else:
        has_actions_left = wallet.has_actions_available()

    if not has_actions_left:
        database.update_item(item_index=wallet_index, warmup_finished=True)


async def swap_action(dex: str, wallet: Wallet, wallet_index: int, database: Database, client: Client) -> bool:
    token_in_data = await client.get_token_with_largest_usd_balance()
    if not token_in_data:
        return False
    token_in, balance = token_in_data

    if not token_in.is_native and USE_ETH_BACKSWAP:
        amount = balance * TOKEN_FULL_BALANCE_USAGE_MULTIPLIER
        token_out = ETH
        is_backswapped = True
    else:
        amount = round(
            float(balance) * (random.randint(*SWAP_PERCENTAGE_RANGE) / 100),
            token_in.round_to,
        )
        token_out = await client.get_random_token(excluded_token=token_in)
        is_backswapped = False

    dex_instance = get_dex_instance_by_name(client=client, dex=dex)
    if dex_instance is None:
        return False

    if await dex_instance.swap(token_in=token_in, token_out=token_out, amount=amount) and not is_backswapped:
        database.decrease_swap_count(item_index=wallet_index, wallet=wallet, dex=dex)
        return wallet.has_actions_available()
    return True


async def dmail_action(wallet: Wallet, wallet_index: int, database: Database, client: Client) -> bool:
    dmail = Dmail(client=client)
    if await dmail.send_mail():
        database.update_item(item_index=wallet_index, dmail_tx_count=wallet.dmail_tx_count - 1)
        return wallet.has_actions_available()
    return True


async def rubyscore_action(wallet: Wallet, wallet_index: int, database: Database, client: Client) -> bool:
    rubyscore = RubyScore(client=client)
    if await rubyscore.vote():
        database.update_item(item_index=wallet_index, rubyscore_tx_count=wallet.rubyscore_tx_count - 1)
        return wallet.has_actions_available()
    return True


async def lending_action(lending: str, wallet: Wallet, wallet_index: int, database: Database, client: Client) -> bool:
    balance = await client.get_token_balance(token=ETH, wei=False)
    amount = round(
        float(balance) * (random.randint(*LENDING_PERCENTAGE_RANGE) / 100),
        ETH.round_to,
    )

    if lending == "layerbank":
        lending_instance = LayerBank(client=client)

    supplied_amount = await lending_instance.get_supplied_amount()

    if supplied_amount > 0:
        action_result = await lending_instance.withdraw()
        action = "withdraw"
    else:
        action_result = await lending_instance.supply(value=amount)
        action = "supply"

    if action_result:
        database.decrease_lending_count(item_index=wallet_index, wallet=wallet, lending=lending, action=action)
        return wallet.has_actions_available()
    return True


async def register_domain_action(wallet: Wallet, wallet_index: int, database: Database, client: Client) -> bool:
    domains = ScrollDomains(client=client)
    if await domains.register():
        database.update_item(item_index=wallet_index, domain_registered=True)
        return wallet.has_actions_available()
    return True


@gas_delay()
async def mint_action(wallet: Wallet, wallet_index: int, database: Database, client: Client, nft_address: str) -> bool:
    nft_contract: AsyncContract = client.w3.eth.contract(
        address=client.w3.to_checksum_address(nft_address), abi=SCROLL_NFT_ABI
    )

    try:
        nft_name = await nft_contract.functions.name().call()
        amount_owned = await nft_contract.functions.balanceOf(client.address).call()

        if amount_owned >= MAX_NFT_TOKEN_OWNED:
            logger.warning(f"Max amount of {nft_name} is already minted")
            database.decrease_nft_count(
                item_index=wallet_index, wallet=wallet, address=nft_address, amount=wallet.nfts_to_mint[nft_address]
            )
            return wallet.has_actions_available()

        logger.info(f"[NFT2Me] Minting {nft_name}")

        data = nft_contract.encodeABI("mint", args=())
        tx_hash = await client.send_transaction(
            to=nft_address, data=data, value=ETH.to_wei(SCROLL_NFTS_TO_MINT[nft_address]["mint_fee"])
        )
        if await client.verify_tx(tx_hash=tx_hash):
            database.decrease_nft_count(item_index=wallet_index, wallet=wallet, address=nft_address)
            return wallet.has_actions_available()
    except Exception as e:
        logger.error(f"[NFT2Me] Failed to mint {nft_address}: {e}")
    return True


def get_dex_instance_by_name(client: Client, dex: str) -> Optional[Dex]:
    if dex == "izumi":
        return Izumi(client=client)
    elif dex == "skydrome":
        return Skydrome(client=client)
    elif dex == "spacefi":
        return Spacefi(client=client)
    elif dex == "syncswap":
        return Syncswap(client=client)
    elif dex == "zebra":
        return Zebra(client=client)
    return None
