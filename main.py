import asyncio

from logger import logger
from modules.module_manager import menu


async def main():
    await menu()


if __name__ == "__main__":
    try:
        asyncio.run(main=main())
    except KeyboardInterrupt:
        logger.info("User keyboard interrupt. Aborting...")
