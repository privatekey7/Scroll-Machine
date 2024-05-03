![image](https://github.com/privatekey7/Scroll-Machine/assets/36263200/4903dc18-96a5-43f1-a9a8-e7580a6113d2)

# Scroll Machine

Универсальный софт для прокрутки Scroll

Поддержка протоколов:

Dmail

Izumi

Nitro Bridge

Orbiter Bridge

Scroll Domains

SpaceFi

SyncSwap

Nfts2me

LayerBank

Cog finance

RubyScore

Skydrome

и др.

- Прогрев кошелька
- Бридж в/из Scroll
- Набив объёмов
- Сборщик токенов

Возможность логирования в Telegram

#### Установка зависимостей для Windows:

1. `cd путь\к\проекту`.
2. `python -m venv venv`.
3. `.\venv\Scripts\activate`.
4. `pip install -r requirements.txt`.

#### Установка зависимостей для MacOS / Linux:

Выполняем данные команды в терминале:

1. `cd путь/к/проекту`.
2. `python3 -m venv venv`.
3. MacOS/Linux `source venv/bin/activate`.
4. `pip install -r requirements.txt`.

#### Настройка:

Все настройки софта находятся в файле `config.py` и подписаны.


#### Запуск:

1. В `data/private_keys.txt` записываете приватные ключи EVM
2. В `data/proxies.txt` записываете прокси в формате `user:pass@ip:port`

Пишем в консоли `python main.py` на Windows или `python3 main.py` на MacOS / Linux
