"""
НАСТРОЙКА СЕТЕЙ
"""

SCROLL_RPC_ENDPOINT = "https://rpc.ankr.com/scroll"

MAINNET_RPC_ENDPOINT = "https://rpc.ankr.com/eth"

ARBITRUM_RPC_ENDPOINT = "https://rpc.ankr.com/arbitrum"

ZKSYNC_RPC_ENDPOINT = "https://mainnet.era.zksync.io"

LINEA_RPC_ENDPOINT = "https://linea.blockpi.network/v1/rpc/public"

"""
НАСТРОЙКИ ПРОГРЕВА
"""
SLIPPAGE = 5

# Логи в телеграм
LOG_TO_TELEGRAM = True
TELEGRAM_IDS = []
TELEGRAM_BOT_TOKEN = ""

# Перемешивать ли кошельки при создании базы данных (True/False)
SHUFFLE_DATABASE = True

# Сеть, в которой будет проверяться текущий Gwei ("ERC20" или "SCROLL")
CHAIN_TO_CHECK_GAS_PRICE_IN = "ERC20"

# Минимальный Gwei в выбранной сети, при котором не будут отправляться транзакции
GAS_THRESHOLD = 60

# Промежуток времени ожидания между проверками текущего Gwei
GAS_DELAY_RANGE = [10, 15]

# Промежуток времени ожидания между проверками поступления бриджа
WAIT_FOR_DEPOSIT_DELAY_RANGE = [60, 60]

# Диапазон для кол-ва токенов, на которые дается approve.
# Если поставить `None`, то апрув будет даваться только на
# нужное для свапа кол-во токенов. Можно использовать только
# целые числа, например: APPROVE_VALUE_RANGE = [100, 200]
APPROVE_VALUE_RANGE = None

# Диапазон для задержки после аппрува
POST_APPROVE_DELAY_RANGE = [30, 40]

# Диапазон для задержки между транзакциями
TX_DELAY_RANGE = [30, 100]

# Настройка кол-ва свапов для прогрева аккаунтов
IZUMI_SWAPS_COUNT = [0, 0]
SKYDROME_SWAPS_COUNT = [0, 0]
SPACEFI_SWAPS_COUNT = [0, 0]
SYNCSWAP_SWAPS_COUNT = [0, 0]
ZEBRA_SWAPS_COUNT = [0, 0]

# Настройка диапазона процента баланса от токена для свапа
SWAP_PERCENTAGE_RANGE = [55, 65]

# Использование обязательного обратного свапа в ETH,
# в случае, если наибольший баланс кошелька находится не в ETH (True/False)
USE_ETH_BACKSWAP = True

# Настройка кол-ва депозитов/выводов LayerBank для прогрева аккаунтов
LAYERBANK_TX_COUNT = [0, 0]

# Настройка диапазона процента от баланса ETH, который будет одолжен в лендинг
LENDING_PERCENTAGE_RANGE = [20, 30]

# Настройка кол-ва транзакций Dmail
DMAIL_TX_COUNT = [0, 0]

# Настройка кол-ва транзакций Rubyscore (голосование)
RUBYSCORE_TX_COUNT = [1, 1]

# Настройка количества минтов NFT
SCROLL_NFTS_TO_MINT = {
    "0xA17D12bdA7B910281E2D1f52c6FD3002a0DBF8EF": {"mint_fee": 0.0006, "amount": [0, 1]},  # LYRA
    "0x08d544c99c92E4Ad3fCEa33148da223b15BABB51": {"mint_fee": 0.0006, "amount": [0, 1]},  # Secret Scroll
    "0x049FCf09b857DC2CE5AaCBa3543256e1B31399C1": {"mint_fee": 0.0006, "amount": [0, 1]},  # Scroll of History
    "0x09ad16d391b08b529Ebe07e67098745248E00BD8": {"mint_fee": 0.0006, "amount": [0, 1]},  # Mystycal Scroll NFT
    "0xE0455ACFfb322f4eCEA6B8e86C558A398Abc7C6d": {"mint_fee": 0.0006, "amount": [0, 1]},  # Dragon Scroll
    "0xBe08E34B25276B42A802e795759e094C96f9BbFe": {"mint_fee": 0.0006, "amount": [0, 1]},  # Key of Scroll
    "0xa715d214Fe2BA8E9eCaF35B61B42E07fB9AE6d8F": {"mint_fee": 0.0006, "amount": [0, 1]},  # Batman Scroll
    "0xa4E928b809807b73CC63F57b98D972D11913532e": {"mint_fee": 0.0006, "amount": [0, 1]},  # Celestial Scrolls
    "0xbBd3595240C8218328b52890ed9406EC0a941B00": {"mint_fee": 0.0006, "amount": [0, 1]},  # Scroll Early Adopter
}

# Максимальное количество одной NFT, которое может быть на кошельке
MAX_NFT_TOKEN_OWNED = 2

# Регистрировать ли Scroll Domains (True/False)
REGISTER_SCROLL_DOMAINS = False

# Реферальный адрес для Scroll Domains
SCROLL_DOMAINS_REFERRAL_ADDRESS = "0x"

"""
НАСТРОЙКА VOLUME MODE
"""
### Общие настройки (учитываются для модулей 4 и 5)

# Оставлять ли какое-то количество ETH в zkSync (True/False)
# если True, то после вывода с OKX будет выполнен бридж на сумму "баланс - число из AMOUNT_TO_LEAVE_ON_ZKSYNC_RANGE"
USE_KEEP_AMOUNT = True

# Промежуток количества ETH, которое будет оставлено в сети-источнике во время бриджа в Scroll
# учитывается только если USE_KEEP_AMOUNT = True
AMOUNT_TO_LEAVE_ON_SRC_CHAIN_RANGE = [0, 0]

# Промежуток количества ETH, которое будет оставлено в Scroll при бридже всего баланса в стартовую сеть (указана в VOLUME_MODE_CHAIN_TO_USE)
AMOUNT_TO_LEAVE_ON_SCROLL_RANGE = [0, 0]

# Промежуток количества ETH, которое будет оставлено в сети при отправке всего баланса на OKX
AMOUNT_TO_LEAVE_BEFORE_TRANSFER = [0, 0]

# Используемая сеть для вывода с OKX ("ZKSYNC", "LINEA", "ARBITRUM")
# в случае использования ZKSYNC, после прогона объемов депозит на OKX будет идти через Arbitrum
VOLUME_MODE_CHAIN_TO_USE = "LINEA"

# Используемый мост для бриджа в Scroll (после вывода с OKX) ("Orbiter", "Nitro")
VOLUME_BRIDGE_TO_SCROLL_NAME = "Orbiter"

# Используемый мост для бриджа из Scroll (после достижения объёма) ("Orbiter", "Nitro")
VOLUME_BRIDGE_FROM_SCROLL_NAME = "Orbiter"

# Промежуток задержки между кошельками
WALLET_DELAY_RANGE = [1, 5]


### Настройки только для модуля 4

# Промежуток необходимого объема для кошелька (в ETH)
COG_VOLUME_ETH_GOAL_RANGE = [0, 0]

# Промежуток процента баланса ETH для врапа
WRAP_ETH_BALANCE_PERCENTAGE_RANGE = [80, 90]

# Промежуток процента от баланса WETH, который будет использоваться для супплая (при каждом супплае выбирается рандомно)
WRAPPED_ETH_USAGE_PERCENTAGE_RANGE = [80, 90]


### Настройки только для модуля 5

# Промежуток необходимого объема для кошелька (в USD)
VOLUME_MODE_USD_GOAL_RANGE = [0, 0]

# Список протоколов для взаимодействия в режиме объёмов
# Значение по умолчанию:
# VOLUME_DAPPS_TO_USE = {
#     "swap": ["izumi", "skydrome", "spacefi", "syncswap", "zebra"],
#     "lending": ["layerbank", "cog"],
# }
VOLUME_DAPPS_TO_USE = {
    "swap": ["izumi", "skydrome", "spacefi", "syncswap", "zebra"],
    "lending": ["layerbank", "cog"],
}

"""
НАСТРОЙКА БРИДЖЕЙ
"""
# Используемый мост в модуле 3 ("Orbiter" / "Nitro" / "Official")
BRIDGE_TO_USE = "Orbiter"

# Сеть-источник бриджа в случае использования Orbiter/Nitro ("LINEA", "ARBITRUM", "ZKSYNC", "SCROLL")
SRC_CHAIN_TO_USE = "LINEA"

# Сеть-получатель бриджа в случае использования Orbiter/Nitro ("LINEA", "ARBITRUM", "ZKSYNC", "SCROLL")
DST_CHAIN_TO_USE = "SCROLL"

# Максимальная комиссия моста Nitro
NITRO_BRIDGE_FEE_THRESHOLD = 0.00001

# Промежуток времени ожидания между проверками текущей комиссии Nitro
NITRO_BRIDGE_FEE_DELAY_RANGE = [60, 60]

# Использовать вывод с OKX перед началом всех действий в модуле 3 (True/False)
# При BRIDGE_TO_USE = "Orbiter" будет сделан вывод в Arbitrum; при "Official" - в ERC20; при "Nitro" - в zkSync Era
USE_OKX_WITHDRAW = False

# Промежуток количества ETH для вывода с OKX
OKX_WITHDRAW_AMOUNT_RANGE = [0.003, 0.004]

# Настройка диапазона количества ETH для бриджа
# При USE_OKX_WITHDRAW = True или BRIDGE_FULL_BALANCE = True данный параметр игнорируется
BRIDGE_AMOUNT_RANGE = [0.1, 0.2]

# Бридж всего баланса (True/False)
BRIDGE_FULL_BALANCE = True

# Оставлять ли какое-то количество ETH в сети-источнике (True/False)
# если True, то будет выполнен бридж на сумму "баланс - число из BRIDGER_KEEP_AMOUNT_RANGE"
BRIDGER_USE_KEEP_AMOUNT = False

# Промежуток количества ETH, которое будет оставлено в сети-источнике бриджа при бридже всего баланса
BRIDGER_KEEP_AMOUNT_RANGE = [0, 0]

# Диапазон для задержки после бриджа
POST_BRIDGE_DELAY_RANGE = [20, 30]

"""
НАСТРОЙКА СБОРЩИКА ТОКЕНОВ
"""
# Минимальный баланс токена в USD эквиваленте, чтобы сборщик свапнул его в ETH
MINIMUM_USD_COLLECTED_VALUE = 0.05

# Токены, которые будут проверяться сборщиком ('WETH', 'lETH', 'COG', 'USDC', 'USDT')
TOKENS_TO_COLLECT = ["WETH", "lETH", "COG", "USDC", "USDT"]

"""
НАСТРОЙКА OKX
"""
# API ключ от OKX.
OKX_API_KEY = ""

# Секрет от API ключа от OKX
OKX_API_SECRET = ""

# Пароль от API ключа от OKX
OKX_API_PASSWORD = ""

"""
НАСТРОЙКА ПРОКСИ
----------------
Если вы используете мобильные прокси, то в файле data/proxies.txt нужно указать прокси только ОДИН раз на первой строке.
"""
USE_MOBILE_PROXY = False

# Ссылка на смену IP
PROXY_CHANGE_IP_URL = ""
