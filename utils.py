import asyncio
import json
import random
import sys
from typing import List, Optional

import aiohttp
from tqdm import tqdm
from web3 import AsyncWeb3
from web3.types import Wei

from config import CHAIN_TO_CHECK_GAS_PRICE_IN, PROXY_CHANGE_IP_URL
from core.chain import MAINNET, SCROLL, Chain
from logger import logger


async def change_ip() -> None:
    async with aiohttp.ClientSession() as session:
        async with session.get(url=PROXY_CHANGE_IP_URL) as response:
            if response.status == 200:
                logger.debug(f"Successfully changed ip address")
            else:
                logger.warning(f"Couldn't change ip address")


def read_from_txt(file_path: str):
    try:
        with open(file=file_path, mode="r") as file:
            return [line.strip() for line in file]
    except FileNotFoundError:
        logger.error(f"File `{file_path}` not found")
    except Exception as e:
        logger.error(f"Error while reading `{file_path}`: {e}")


def read_from_json(file_path: str):
    try:
        with open(file_path) as json_file:
            return json.load(json_file)
    except FileNotFoundError:
        logger.error(f"File '{file_path}' not found.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Encountered an unexpected error while reading a JSON file '{file_path}': {e}.")
        sys.exit(1)


async def sleep(delay_range: List[int], send_message: bool = True, pr_bar: bool = True) -> None:
    delay = random.randint(*delay_range)

    if send_message:
        logger.info(f"Sleeping for {delay} seconds...")

    if pr_bar:
        with tqdm(total=delay, desc="Waiting", unit="s", dynamic_ncols=True, colour="blue") as pbar:
            for _ in range(delay):
                await asyncio.sleep(delay=1)
                pbar.update(1)
    else:
        await asyncio.sleep(delay=delay)


async def get_chain_gas_price(chain: Optional[Chain] = None) -> Wei:
    if chain is None:
        chain = SCROLL if CHAIN_TO_CHECK_GAS_PRICE_IN == "SCROLL" else MAINNET
    w3 = AsyncWeb3(AsyncWeb3.AsyncHTTPProvider(chain.rpc))
    return await w3.eth.gas_price
