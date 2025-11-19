# data/providers/__init__.py
from .base_provider import BaseDataProvider
from .yfinance_adapter import YFinanceAdapter
from .news_adapter import NewsAdapter

__all__ = [
    "BaseDataProvider",
    "YFinanceAdapter",
    "NewsAdapter",
]
