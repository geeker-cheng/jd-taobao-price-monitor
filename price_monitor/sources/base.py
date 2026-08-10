from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import Quote


class PriceSource(ABC):
    @abstractmethod
    def fetch(self, product: dict) -> Quote:
        raise NotImplementedError
