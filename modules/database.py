import binascii
import itertools
import json
import random
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from config import (
    COG_VOLUME_ETH_GOAL_RANGE,
    DMAIL_TX_COUNT,
    IZUMI_SWAPS_COUNT,
    LAYERBANK_TX_COUNT,
    RUBYSCORE_TX_COUNT,
    SCROLL_NFTS_TO_MINT,
    SHUFFLE_DATABASE,
    SKYDROME_SWAPS_COUNT,
    SPACEFI_SWAPS_COUNT,
    SYNCSWAP_SWAPS_COUNT,
    TOKENS_TO_COLLECT,
    USE_MOBILE_PROXY,
    VOLUME_MODE_USD_GOAL_RANGE,
    ZEBRA_SWAPS_COUNT,
)
from core import Client
from core.constants import (
    DATABASE_FILE_PATH,
    DEPOSIT_ADDRESSES_PATH,
    PRIVATE_KEYS_FILE_PATH,
    PROXIES_FILE_PATH,
)
from logger import logger
from models.wallet import Wallet
from utils import read_from_txt


@dataclass
class Database:
    data: List[Wallet]

    def _to_dict(self) -> List[Dict[str, Any]]:
        return [vars(wallet) for wallet in self.data]

    @staticmethod
    def _create_database() -> "Database":
        try:
            data = []

            private_keys = read_from_txt(file_path=PRIVATE_KEYS_FILE_PATH)
            proxies = read_from_txt(file_path=PROXIES_FILE_PATH)
            deposit_addresses = read_from_txt(file_path=DEPOSIT_ADDRESSES_PATH)

            if USE_MOBILE_PROXY:
                proxies = proxies * len(private_keys)

            if len(private_keys) < len(proxies):
                raise DataAmountMismatchError

            for private_key, proxy, deposit_address in itertools.zip_longest(
                private_keys, proxies, deposit_addresses, fillvalue=None
            ):
                try:
                    layerbank_tx_count = random.randint(*LAYERBANK_TX_COUNT)
                    wallet = Wallet(
                        client=Client(private_key=private_key, proxy=proxy),
                        deposit_address=deposit_address,
                        izumi_swaps_count=random.randint(*IZUMI_SWAPS_COUNT),
                        skydrome_swaps_count=random.randint(*SKYDROME_SWAPS_COUNT),
                        spacefi_swaps_count=random.randint(*SPACEFI_SWAPS_COUNT),
                        syncswap_swaps_count=random.randint(*SYNCSWAP_SWAPS_COUNT),
                        zebra_swaps_count=random.randint(*ZEBRA_SWAPS_COUNT),
                        layerbank_deposits=layerbank_tx_count,
                        layerbank_withdrawals=layerbank_tx_count,
                        dmail_tx_count=random.randint(*DMAIL_TX_COUNT),
                        rubyscore_tx_count=random.randint(*RUBYSCORE_TX_COUNT),
                        nfts_to_mint={
                            addr: random.randint(*config["amount"]) for addr, config in SCROLL_NFTS_TO_MINT.items()
                        },
                        cog_volume_state={
                            "volume_goal": round(random.uniform(*COG_VOLUME_ETH_GOAL_RANGE), 5),
                            "volume_reached": 0.0,
                            "okx_withdrawn": None,
                            "dst_chain_initial_balance": None,
                            "bridged_to_scroll": False,
                            "eth_wrapped": False,
                            "last_action": None,
                            "eth_unwrapped": False,
                            "bridged_from_scroll": False,
                            "deposited_to_okx": False,
                        },
                        volume_mode_state={
                            "okx_withdrawn": None,
                            "bridged_to_scroll": False,
                            "dst_chain_initial_balance": None,
                            "volume_goal": round(random.uniform(*VOLUME_MODE_USD_GOAL_RANGE), 5),
                            "volume_reached": 0.0,
                            "last_lending": None,
                            "eth_wrapped": False,
                            "bridged_from_scroll": False,
                            "deposited_to_okx": False,
                        },
                    )
                except binascii.Error:
                    logger.error(f"Provided private key is not valid: {private_key}")
                    sys.exit(1)
                data.append(wallet)

            if SHUFFLE_DATABASE:
                random.shuffle(data)
            logger.success("Database created successfully")
            return Database(data=data)
        except Exception as e:
            logger.exception(f"Error while creating database: {e}")
            sys.exit(1)

    def save_database(self, file_path: str = DATABASE_FILE_PATH) -> None:
        data_dict = self._to_dict()
        with open(file=file_path, mode="w") as json_file:
            json.dump(data_dict, json_file, indent=4)

    @staticmethod
    def create_database():
        db = Database._create_database()
        db.save_database()

    @classmethod
    def read_from_json(cls, file_path: str = DATABASE_FILE_PATH) -> "Database":
        try:
            with open(file=file_path, mode="r") as json_file:
                data_dict = json.load(fp=json_file)
        except Exception as e:
            logger.error(f"Failed to read database: {e}")
            sys.exit(1)

        data = []
        for item in data_dict:
            wallet_data = {
                "private_key": item.pop("private_key"),
                "proxy": item.pop("proxy"),
            }
            item.pop("address")
            client = Client(**wallet_data)
            wallet = Wallet(client=client, **item)
            data.append(wallet)
        return cls(data=data)

    def update_item(self, item_index: int, **kwargs):
        if 0 <= item_index < len(self.data):
            item = self.data[item_index]

            for key, value in kwargs.items():
                setattr(item, key, value)

            self.save_database()
        else:
            logger.error(f"Invalid item index: {item_index}")

    def update_state(self, item_index: int, state_dict_name: str, new_state: str):
        if 0 <= item_index < len(self.data):
            item = self.data[item_index]
            setattr(item, state_dict_name, new_state)
            self.save_database()
        else:
            logger.error(f"Invalid item index: {item_index}")

    def decrease_swap_count(self, item_index: int, wallet: Wallet, dex: str):
        if dex == "izumi":
            self.update_item(item_index=item_index, izumi_swaps_count=wallet.izumi_swaps_count - 1)
        elif dex == "skydrome":
            self.update_item(
                item_index=item_index,
                skydrome_swaps_count=wallet.skydrome_swaps_count - 1,
            )
        elif dex == "spacefi":
            self.update_item(
                item_index=item_index,
                spacefi_swaps_count=wallet.spacefi_swaps_count - 1,
            )
        elif dex == "syncswap":
            self.update_item(
                item_index=item_index,
                syncswap_swaps_count=wallet.syncswap_swaps_count - 1,
            )
        elif dex == "zebra":
            self.update_item(item_index=item_index, zebra_swaps_count=wallet.zebra_swaps_count - 1)

    def decrease_nft_count(self, item_index: int, wallet: Wallet, address: str, amount=1):
        if wallet.nfts_to_mint[address] < amount:
            return

        wallet.nfts_to_mint[address] -= amount
        self.update_item(item_index=item_index, nfts_to_mint=wallet.nfts_to_mint)

    def decrease_lending_count(self, item_index: int, wallet: Wallet, lending: str, action: str):
        if lending == "layerbank":
            if action == "supply":
                self.update_item(item_index=item_index, layerbank_deposits=wallet.layerbank_deposits - 1)
            elif action == "withdraw":
                self.update_item(item_index=item_index, layerbank_withdrawals=wallet.layerbank_withdrawals - 1)

    def get_random_item_by_criteria(self, **kwargs) -> Optional[Tuple[Wallet, int]]:
        """
        Returns a random wallet and its index that matches the given kwargs.
        If no wallet matches, returns None.
        """
        # Filter wallets based on kwargs
        filtered_wallets = [
            wallet for wallet in self.data if all(getattr(wallet, k, None) == v for k, v in kwargs.items())
        ]

        # Check if there are any wallets after filtering
        if not filtered_wallets:
            return None

        # Select a random wallet
        selected_wallet = random.choice(filtered_wallets)
        index = self.data.index(selected_wallet)

        return selected_wallet, index

    def get_first_volume_wallet(self, state_dict_name: str) -> Optional[Tuple[Wallet, int]]:
        for item in self.data:
            if getattr(item, state_dict_name)["deposited_to_okx"]:
                continue
            return item, self.data.index(item)
        return None

    def has_actions_available(self) -> bool:
        """
        Check if any item in the database has "warmup_finished" set to False.
        Return True if the first instance is found, else return False.
        """
        for wallet in self.data:
            if not getattr(wallet, "warmup_finished", True):
                return True
        return False

    def has_volume_actions_available(self) -> bool:
        for wallet in self.data:
            if not wallet.cog_volume_state["deposited_to_okx"]:
                return True
        return False

    def ensure_ready_for_volume_mode(self) -> bool:
        for wallet in self.data:
            if not wallet.deposit_address:
                return False
        return True

    def get_random_active_collector_item(self) -> Optional[Wallet]:
        active_wallets = []

        for wallet in self.data:
            if set(wallet.tokens_collected) != set(TOKENS_TO_COLLECT):
                active_wallets.append(wallet)

        if len(active_wallets) == 0:
            return None
        return random.choice(active_wallets)


class DataAmountMismatchError(Exception):
    def __init__(self):
        super().__init__(f"Amount of private keys and proxies do not match")
