import random
from typing import List, Optional, Tuple, Union

from config import REGISTER_SCROLL_DOMAINS, VOLUME_DAPPS_TO_USE
from core import Client
from core.chain import Chain
from core.constants import ACTION_TO_DAPP
from logger import logger


class Wallet:
    def __init__(
        self,
        client: Client,
        deposit_address: str,
        izumi_swaps_count: int,
        skydrome_swaps_count: int,
        spacefi_swaps_count: int,
        syncswap_swaps_count: int,
        zebra_swaps_count: int,
        layerbank_deposits: int,
        layerbank_withdrawals: int,
        dmail_tx_count: int,
        rubyscore_tx_count: int,
        nfts_to_mint: dict[str, int],
        cog_volume_state: dict[str, Union[bool, str, float, None]],
        volume_mode_state: dict[str, Union[bool, str, float, None]],
        domain_registered: bool = False,
        warmup_finished: bool = False,
        okx_withdrawn: Optional[float] = None,
        initial_balance: Optional[float] = None,
        bridge_finished: bool = False,
        tokens_collected: list[str] = [],
    ) -> None:
        self.private_key = client.private_key
        self.address = client.address
        self.proxy = client.proxy
        self.deposit_address = deposit_address
        self.warmup_finished = warmup_finished
        self.izumi_swaps_count = izumi_swaps_count
        self.skydrome_swaps_count = skydrome_swaps_count
        self.spacefi_swaps_count = spacefi_swaps_count
        self.syncswap_swaps_count = syncswap_swaps_count
        self.zebra_swaps_count = zebra_swaps_count
        self.dmail_tx_count = dmail_tx_count
        self.rubyscore_tx_count = rubyscore_tx_count
        self.layerbank_deposits = layerbank_deposits
        self.layerbank_withdrawals = layerbank_withdrawals
        self.nfts_to_mint = nfts_to_mint
        self.domain_registered = domain_registered
        self.okx_withdrawn = okx_withdrawn
        self.initial_balance = initial_balance
        self.bridge_finished = bridge_finished
        self.cog_volume_state = cog_volume_state
        self.volume_mode_state = volume_mode_state
        self.tokens_collected = tokens_collected

    def __str__(self):
        return f"{self.address[:6]}...{self.address[-4:]}"

    def to_client(self, chain: Chain) -> Client:
        return Client(private_key=self.private_key, chain=chain, proxy=self.proxy)

    def get_available_withdraw(self) -> Optional[str]:
        for lending in ACTION_TO_DAPP["lending"]:
            if getattr(self, f"{lending}_deposits") < getattr(self, f"{lending}_withdrawals"):
                return lending
        return None

    def get_random_dapp(self) -> Optional[str]:
        lending_to_withdraw = self.get_available_withdraw()
        if lending_to_withdraw is not None:
            return lending_to_withdraw

        available_dapps = set()
        if self.izumi_swaps_count > 0:
            available_dapps.add("izumi")
        if self.skydrome_swaps_count > 0:
            available_dapps.add("skydrome")
        if self.spacefi_swaps_count > 0:
            available_dapps.add("spacefi")
        if self.syncswap_swaps_count > 0:
            available_dapps.add("syncswap")
        if self.zebra_swaps_count > 0:
            available_dapps.add("zebra")
        if self.layerbank_deposits > 0 or self.layerbank_withdrawals > 0:
            available_dapps.add("layerbank")
        if self.dmail_tx_count > 0:
            available_dapps.add("dmail")
        if self.rubyscore_tx_count > 0:
            available_dapps.add("rubyscore")
        if len(self.get_active_nfts()) > 0:
            available_dapps.add("nft")
        if REGISTER_SCROLL_DOMAINS and not self.domain_registered:
            available_dapps.add("domain")
        available_dapps = list(available_dapps)
        if available_dapps:
            return random.choice(available_dapps)
        return None

    def get_random_volume_action_pair(self) -> Optional[Tuple[str, str]]:
        try:
            if self.volume_mode_state["last_lending"] is not None:
                return "lending", self.volume_mode_state["last_lending"]

            if self.volume_mode_state["eth_wrapped"]:
                return "unwrap", "weth"

            dapp_type = random.choice(list(VOLUME_DAPPS_TO_USE.keys()))
            dapp = random.choice(VOLUME_DAPPS_TO_USE[dapp_type])
            return dapp_type, dapp
        except Exception as e:
            logger.error(f"Failed to pick random action: {e}")
            return None

    def get_random_nft(self) -> Optional[str]:
        active_nfts = self.get_active_nfts()

        if len(active_nfts) == 0:
            return None
        return random.choice(active_nfts)

    def get_active_nfts(self) -> List[str]:
        return [nft_address for nft_address, count in self.nfts_to_mint.items() if count > 0]

    def get_action_from_dapp(self, dapp: str) -> str:
        dapp_to_action = {d: action for action, dapps in ACTION_TO_DAPP.items() for d in dapps}
        return dapp_to_action.get(dapp, "Unknown action")

    def has_actions_available(self) -> bool:
        if (
            self.izumi_swaps_count > 0
            or self.skydrome_swaps_count > 0
            or self.spacefi_swaps_count > 0
            or self.syncswap_swaps_count > 0
            or self.zebra_swaps_count > 0
            or self.layerbank_deposits > 0
            or self.layerbank_withdrawals > 0
            or self.dmail_tx_count > 0
            or self.rubyscore_tx_count > 0
            or len(self.get_active_nfts()) > 0
            or (REGISTER_SCROLL_DOMAINS and not self.domain_registered)
        ):
            return True
        return False
