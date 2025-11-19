from typing import List
import pandas as pd
from features.technical import TechnicalFeatures
from features.sentiment import SentimentFeatures
from features.macro import MacroFeatures


class FeaturePipeline:
    """Orchestrates feature computation"""

    def __init__(self, config):
        self.config = config
        self.technical_features = TechnicalFeatures()
        self.sentiment_features = SentimentFeatures()
        self.macro_features = MacroFeatures()

    def compute_features(
        self, ticker: str, date: str, lookback_days: int = 252
    ) -> dict:
        """
        Compute all features for a ticker at a given date
        Only uses data available before this date (no look-ahead)
        """
        pass

    def compute_cross_sectional_features(
        self, universe: List[str], date: str
    ) -> pd.DataFrame:
        """
        Compute features that require cross-sectional information
        (sector momentum, relative strength, etc.)
        """
        pass
