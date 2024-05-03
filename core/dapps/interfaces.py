from abc import ABC, abstractmethod
from typing import Optional

from core.token import Token


class Dex(ABC):
    @abstractmethod
    async def swap(self, token_in: Token, token_out: Token, amount: float) -> bool:
        pass


class Lending(ABC):
    @abstractmethod
    async def supply(self, token: Token):
        pass

    @abstractmethod
    async def withdraw(self, token: Token):
        pass

    @abstractmethod
    async def get_supplied_amount(self, token: Optional[Token]):
        pass
