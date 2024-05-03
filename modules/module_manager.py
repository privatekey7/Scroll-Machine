from logger import logger
from modules.bridger import bridge_batch
from modules.collector import collect
from modules.database import Database
from modules.cog_volume import cog_volume
from modules.volume import volume
from modules.warmup import warmup


async def menu() -> None:
    await greeting()
    module_num = input("Enter a module number: ")
    if module_num == "1":
        Database.create_database()
    if module_num == "2":
        await warmup()
    if module_num == "3":
        await bridge_batch()
    if module_num == "4":
        await cog_volume()
    if module_num == "5":
        await volume()
    if module_num == "6":
        await collect()


async def greeting() -> None:
    logger.debug(
        r"""
   _____                 ____   __  ___           __    _          
  / ___/______________  / / /  /  |/  /___ ______/ /_  (_)___  ___ 
  \__ \/ ___/ ___/ __ \/ / /  / /|_/ / __ `/ ___/ __ \/ / __ \/ _ \
 ___/ / /__/ /  / /_/ / / /  / /  / / /_/ / /__/ / / / / / / /  __/
/____/\___/_/   \____/_/_/  /_/  /_/\__,_/\___/_/ /_/_/_/ /_/\___/ 
                                                                                     
1. [DATABASE] Создать базу данных | Create database
2. [WARMUP] Прогрев кошельков | Wallets warmup
3. [BRIDGER] Бридж в/из Scroll | Batch bridge to/from Scroll
4. [COG VOLUME] Набив объемов через Cog | Cog volume Mode
5. [VOLUME] Набив объемов через все протоколы | Volume mode
6. [COLLECTOR] Сборщик токенов | Collector
"""
    )
