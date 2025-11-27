"""
Feature Manager for computing and storing technical features

Integrates with DatabaseManager to cache computed features
"""

import pandas as pd
import numpy as np
from typing import List, Optional, Dict
import logging

from data.database import DatabaseManager
from data.data_manager_db import DataManagerDB
from .technical import TechnicalFeatures

logger = logging.getLogger(__name__)


class FeatureManager:
    """
    Manages feature computation and storage

    Features are computed from raw price data and stored in the feature store.
    Supports caching to avoid recomputing expensive features.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        data_manager: Optional[DataManagerDB] = None,
        db_path: str = "data/stock_data.db",
    ):
        """
        Initialize Feature Manager

        Args:
            db_manager: DatabaseManager instance
            data_manager: DataManagerDB instance
            db_path: Path to database file
        """
        if db_manager is None:
            self.db = DatabaseManager(db_path)
        else:
            self.db = db_manager

        if data_manager is None:
            self.data_manager = DataManagerDB(db_manager=self.db)
        else:
            self.data_manager = data_manager

        self.technical = TechnicalFeatures()

        logger.info("Feature Manager initialized")

    def compute_features(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        feature_set: str = "all",
        use_cache: bool = True,
    ) -> pd.DataFrame:
        """
        Compute features for a ticker

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            feature_set: Feature set to compute ('all', 'momentum', 'volatility', 'volume', 'trend')
            use_cache: Whether to use cached features

        Returns:
            DataFrame with features
        """
        logger.info(
            f"Computing {feature_set} features for {ticker} "
            f"from {start_date} to {end_date}"
        )

        # Check cache first
        if use_cache:
            cached = self._get_cached_features(
                ticker, start_date, end_date, feature_set
            )
            if cached is not None and not cached.empty:
                logger.info(f"Using cached features for {ticker}")
                return cached

        # Get price data
        price_data = self.data_manager.get_prices(ticker, start_date, end_date)

        if price_data.empty:
            logger.warning(f"No price data for {ticker}")
            return pd.DataFrame()

        # Compute features based on feature set
        if feature_set == "all":
            features = self.technical.compute_all_features(price_data, prefix="")
        elif feature_set == "momentum":
            features = self._compute_momentum_features(price_data)
        elif feature_set == "volatility":
            features = self._compute_volatility_features(price_data)
        elif feature_set == "volume":
            features = self._compute_volume_features(price_data)
        elif feature_set == "trend":
            features = self._compute_trend_features(price_data)
        else:
            raise ValueError(f"Unknown feature set: {feature_set}")

        # Store in database
        self._store_features(ticker, features, feature_set)

        return features

    def compute_features_bulk(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        feature_set: str = "all",
        use_cache: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """
        Compute features for multiple tickers

        Args:
            tickers: List of stock tickers
            start_date: Start date
            end_date: End date
            feature_set: Feature set to compute
            use_cache: Whether to use cached features

        Returns:
            Dictionary mapping ticker to features DataFrame
        """
        logger.info(
            f"Computing features for {len(tickers)} tickers ({feature_set} set)"
        )

        results = {}
        for ticker in tickers:
            try:
                features = self.compute_features(
                    ticker, start_date, end_date, feature_set, use_cache
                )
                if not features.empty:
                    results[ticker] = features
            except Exception as e:
                logger.error(f"Failed to compute features for {ticker}: {e}")

        logger.info(
            f"Successfully computed features for {len(results)}/{len(tickers)} tickers"
        )

        return results

    def compute_panel_features(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        feature_list: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Compute features for multiple tickers in panel format

        Args:
            tickers: List of stock tickers
            start_date: Start date
            end_date: End date
            feature_list: Optional list of specific features to compute

        Returns:
            Panel DataFrame with MultiIndex (date, ticker)
        """
        logger.info(
            f"Computing panel features for {len(tickers)} tickers "
            f"from {start_date} to {end_date}"
        )

        all_features = []

        for ticker in tickers:
            try:
                # Get price data
                price_data = self.data_manager.get_prices(ticker, start_date, end_date)

                if price_data.empty:
                    continue

                # Compute features
                if feature_list:
                    features = self.technical.compute_feature_subset(
                        price_data, feature_list
                    )
                else:
                    features = self.technical.compute_all_features(price_data)

                # Add ticker column
                features["ticker"] = ticker

                all_features.append(features)

            except Exception as e:
                logger.error(f"Failed to compute features for {ticker}: {e}")

        if not all_features:
            logger.warning("No features computed for any ticker")
            return pd.DataFrame()

        # Concatenate all features
        panel = pd.concat(all_features, axis=0)

        # Create MultiIndex
        panel = panel.reset_index()
        panel = panel.set_index(["date", "ticker"])
        panel = panel.sort_index()

        logger.info(
            f"Panel features: {len(panel.index.get_level_values('ticker').unique())} tickers, "
            f"{len(panel.index.get_level_values('date').unique())} dates, "
            f"{len(panel.columns)} features"
        )

        return panel

    def _compute_momentum_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute momentum-related features"""
        features = pd.DataFrame(index=df.index)

        # Returns
        features["returns"] = df["close"].pct_change()
        features["log_returns"] = np.log(df["close"] / df["close"].shift(1))

        # RSI
        features["rsi_14"] = self.technical.rsi(df["close"], 14)

        # MACD
        macd = self.technical.macd(df["close"])
        features["macd"] = macd["macd"]
        features["macd_signal"] = macd["signal"]
        features["macd_histogram"] = macd["histogram"]

        # Stochastic
        stoch = self.technical.stochastic(df["high"], df["low"], df["close"])
        features["stoch_k"] = stoch["k"]
        features["stoch_d"] = stoch["d"]

        # ROC and Momentum
        features["roc_12"] = self.technical.roc(df["close"], 12)
        features["momentum_10"] = self.technical.momentum(df["close"], 10)

        return features

    def _compute_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute volatility-related features"""
        features = pd.DataFrame(index=df.index)

        # Bollinger Bands
        bb = self.technical.bollinger_bands(df["close"], 20, 2.0)
        features["bb_upper"] = bb["upper"]
        features["bb_middle"] = bb["middle"]
        features["bb_lower"] = bb["lower"]
        features["bb_bandwidth"] = bb["bandwidth"]
        features["bb_position"] = (df["close"] - bb["lower"]) / (
            bb["upper"] - bb["lower"]
        )

        # ATR
        features["atr_14"] = self.technical.atr(df["high"], df["low"], df["close"], 14)

        # Historical Volatility
        features["historical_vol_20"] = self.technical.historical_volatility(
            df["close"], 20
        )

        return features

    def _compute_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute volume-related features"""
        features = pd.DataFrame(index=df.index)

        if "volume" not in df.columns:
            logger.warning("No volume data available")
            return features

        # Volume SMA and ratio
        features["volume"] = df["volume"]
        features["volume_sma_20"] = self.technical.volume_sma(df["volume"], 20)
        features["volume_ratio"] = df["volume"] / features["volume_sma_20"]

        # OBV
        features["obv"] = self.technical.obv(df["close"], df["volume"])

        # VWAP
        features["vwap"] = self.technical.vwap(
            df["high"], df["low"], df["close"], df["volume"]
        )

        # MFI
        features["mfi_14"] = self.technical.mfi(
            df["high"], df["low"], df["close"], df["volume"], 14
        )

        return features

    def _compute_trend_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute trend-related features"""
        features = pd.DataFrame(index=df.index)

        # Moving Averages
        for period in [5, 10, 20, 50, 200]:
            features[f"sma_{period}"] = self.technical.sma(df["close"], period)
            features[f"ema_{period}"] = self.technical.ema(df["close"], period)

        # Price relative to MAs
        features["price_to_sma20"] = df["close"] / features["sma_20"]
        features["price_to_sma50"] = df["close"] / features["sma_50"]

        # ADX
        features["adx_14"] = self.technical.adx(df["high"], df["low"], df["close"], 14)

        # Aroon
        aroon = self.technical.aroon(df["high"], df["low"], 25)
        features["aroon_up"] = aroon["up"]
        features["aroon_down"] = aroon["down"]
        features["aroon_osc"] = aroon["oscillator"]

        return features

    def _get_cached_features(
        self, ticker: str, start_date: str, end_date: str, feature_set: str
    ) -> Optional[pd.DataFrame]:
        """Get cached features from database"""
        try:
            # Try to get from database
            # Note: This is a simplified version - you'd want to query by feature_set
            features = self.db.get_features(ticker, start_date, end_date)
            return features
        except Exception as e:
            logger.debug(f"No cached features for {ticker}: {e}")
            return None

    def _store_features(self, ticker: str, features: pd.DataFrame, feature_set: str):
        """Store computed features in database"""
        try:
            if features.empty:
                return

            # Register feature metadata
            for col in features.columns:
                if col not in ["date", "ticker"]:
                    self.db.register_feature(
                        feature_name=col,
                        feature_type="technical",
                        feature_group=feature_set,
                        description=f"Technical indicator: {col}",
                    )

            # Store features
            self.db.insert_features(ticker, features)

            logger.info(
                f"Stored {len(features)} rows x {len(features.columns)} features "
                f"for {ticker}"
            )

        except Exception as e:
            logger.error(f"Failed to store features for {ticker}: {e}")

    def get_feature_list(self, feature_set: str = "all") -> List[str]:
        """
        Get list of available features for a feature set

        Args:
            feature_set: Feature set name

        Returns:
            List of feature names
        """
        # Create dummy data to get feature names
        dummy_data = pd.DataFrame(
            {
                "open": [100] * 300,
                "high": [105] * 300,
                "low": [95] * 300,
                "close": [100] * 300,
                "volume": [1000000] * 300,
            },
            index=pd.date_range(start="2020-01-01", periods=300, freq="B"),
        )

        if feature_set == "all":
            features = self.technical.compute_all_features(dummy_data)
        elif feature_set == "momentum":
            features = self._compute_momentum_features(dummy_data)
        elif feature_set == "volatility":
            features = self._compute_volatility_features(dummy_data)
        elif feature_set == "volume":
            features = self._compute_volume_features(dummy_data)
        elif feature_set == "trend":
            features = self._compute_trend_features(dummy_data)
        else:
            return []

        return list(features.columns)

    def get_feature_stats(self) -> Dict:
        """
        Get statistics about stored features

        Returns:
            Dictionary with feature statistics
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Count features
            cursor.execute("SELECT COUNT(*) FROM features")
            total_features = cursor.fetchone()[0]

            # Count unique tickers
            cursor.execute("SELECT COUNT(DISTINCT ticker) FROM features")
            unique_tickers = cursor.fetchone()[0]

            # Count feature types
            cursor.execute("SELECT COUNT(DISTINCT feature_name) FROM feature_metadata")
            unique_feature_names = cursor.fetchone()[0]

            # Get date range
            cursor.execute("SELECT MIN(date), MAX(date) FROM features")
            date_range = cursor.fetchone()

        return {
            "total_feature_rows": total_features,
            "unique_tickers": unique_tickers,
            "unique_feature_names": unique_feature_names,
            "date_range": {
                "start": date_range[0],
                "end": date_range[1],
            },
        }
