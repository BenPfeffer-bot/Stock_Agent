# data/providers/base_provider.py
from abc import ABC, abstractmethod
import pandas as pd
from typing import List, Optional


class BaseDataProvider(ABC):
    """Abstract base class for data providers"""

    @abstractmethod
    def fetch_prices(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch OHLCV data"""
        pass

    @abstractmethod
    def fetch_fundamentals(self, ticker: str) -> dict:
        """Fetch fundamental data"""
        pass

    @abstractmethod
    def get_available_tickers(self, market: str) -> List[str]:
        """Get list of available tickers for a market"""
        pass
