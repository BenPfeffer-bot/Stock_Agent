# features/technical.py
"""
Technical indicators for stock trading

Implements common technical analysis indicators:
- Trend: SMA, EMA, MACD, ADX
- Momentum: RSI, Stochastic, CCI, ROC
- Volatility: Bollinger Bands, ATR, Keltner Channels
- Volume: OBV, Volume MA, VWAP
- Price patterns: Support/Resistance levels
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class TechnicalFeatures:
    """Compute technical indicators from price data"""

    def __init__(self):
        """Initialize technical features calculator"""
        self.indicators = {}

    # ==================== Moving Averages ====================

    @staticmethod
    def sma(series: pd.Series, period: int) -> pd.Series:
        """
        Simple Moving Average

        Args:
            series: Price series
            period: Number of periods

        Returns:
            SMA series
        """
        return series.rolling(window=period, min_periods=period).mean()

    @staticmethod
    def ema(series: pd.Series, period: int) -> pd.Series:
        """
        Exponential Moving Average

        Args:
            series: Price series
            period: Number of periods

        Returns:
            EMA series
        """
        return series.ewm(span=period, adjust=False).mean()

    @staticmethod
    def wma(series: pd.Series, period: int) -> pd.Series:
        """
        Weighted Moving Average

        Args:
            series: Price series
            period: Number of periods

        Returns:
            WMA series
        """
        weights = np.arange(1, period + 1)
        return series.rolling(window=period).apply(
            lambda x: np.dot(x, weights) / weights.sum(), raw=True
        )

    # ==================== Momentum Indicators ====================

    @staticmethod
    def rsi(series: pd.Series, period: int = 14) -> pd.Series:
        """
        Relative Strength Index

        Args:
            series: Price series
            period: RSI period (default 14)

        Returns:
            RSI series (0-100)
        """
        delta = series.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def macd(
        self,
        series: pd.Series,
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> Dict[str, pd.Series]:
        """
        Moving Average Convergence Divergence

        Args:
            series: Price series
            fast_period: Fast EMA period
            slow_period: Slow EMA period
            signal_period: Signal line period

        Returns:
            Dictionary with 'macd', 'signal', 'histogram'
        """
        fast_ema = self.ema(series, fast_period)
        slow_ema = self.ema(series, slow_period)

        macd_line = fast_ema - slow_ema
        signal_line = self.ema(macd_line, signal_period)
        histogram = macd_line - signal_line

        return {
            "macd": macd_line,
            "signal": signal_line,
            "histogram": histogram,
        }

    @staticmethod
    def stochastic(
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        k_period: int = 14,
        d_period: int = 3,
    ) -> Dict[str, pd.Series]:
        """
        Stochastic Oscillator

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            k_period: %K period
            d_period: %D period

        Returns:
            Dictionary with 'k' and 'd' series
        """
        lowest_low = low.rolling(window=k_period).min()
        highest_high = high.rolling(window=k_period).max()

        k = 100 * (close - lowest_low) / (highest_high - lowest_low)
        d = k.rolling(window=d_period).mean()

        return {"k": k, "d": d}

    @staticmethod
    def cci(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20
    ) -> pd.Series:
        """
        Commodity Channel Index

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: CCI period

        Returns:
            CCI series
        """
        typical_price = (high + low + close) / 3
        sma_tp = typical_price.rolling(window=period).mean()
        mad = typical_price.rolling(window=period).apply(
            lambda x: np.abs(x - x.mean()).mean()
        )

        cci = (typical_price - sma_tp) / (0.015 * mad)
        return cci

    @staticmethod
    def roc(series: pd.Series, period: int = 12) -> pd.Series:
        """
        Rate of Change

        Args:
            series: Price series
            period: ROC period

        Returns:
            ROC series (percentage)
        """
        return ((series - series.shift(period)) / series.shift(period)) * 100

    @staticmethod
    def momentum(series: pd.Series, period: int = 10) -> pd.Series:
        """
        Momentum indicator

        Args:
            series: Price series
            period: Momentum period

        Returns:
            Momentum series
        """
        return series - series.shift(period)

    # ==================== Volatility Indicators ====================

    def bollinger_bands(
        self, series: pd.Series, period: int = 20, std_dev: float = 2.0
    ) -> Dict[str, pd.Series]:
        """
        Bollinger Bands

        Args:
            series: Price series
            period: Moving average period
            std_dev: Number of standard deviations

        Returns:
            Dictionary with 'upper', 'middle', 'lower', 'bandwidth'
        """
        middle = self.sma(series, period)
        std = series.rolling(window=period).std()

        upper = middle + (std * std_dev)
        lower = middle - (std * std_dev)
        bandwidth = (upper - lower) / middle

        return {
            "upper": upper,
            "middle": middle,
            "lower": lower,
            "bandwidth": bandwidth,
        }

    @staticmethod
    def atr(
        high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """
        Average True Range

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ATR period

        Returns:
            ATR series
        """
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())

        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        return atr

    def keltner_channels(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20, atr_multiplier: float = 2.0
    ) -> Dict[str, pd.Series]:
        """
        Keltner Channels

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: EMA period
            atr_multiplier: ATR multiplier

        Returns:
            Dictionary with 'upper', 'middle', 'lower'
        """
        middle = self.ema(close, period)
        atr_value = self.atr(high, low, close, period)

        upper = middle + (atr_multiplier * atr_value)
        lower = middle - (atr_multiplier * atr_value)

        return {"upper": upper, "middle": middle, "lower": lower}

    @staticmethod
    def historical_volatility(series: pd.Series, period: int = 20) -> pd.Series:
        """
        Historical Volatility (annualized)

        Args:
            series: Price series
            period: Calculation period

        Returns:
            Volatility series (annualized)
        """
        log_returns = np.log(series / series.shift(1))
        volatility = log_returns.rolling(window=period).std() * np.sqrt(252)
        return volatility

    # ==================== Volume Indicators ====================

    @staticmethod
    def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        On-Balance Volume

        Args:
            close: Close prices
            volume: Volume

        Returns:
            OBV series
        """
        obv = (np.sign(close.diff()) * volume).fillna(0).cumsum()
        return obv

    @staticmethod
    def vwap(high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series) -> pd.Series:
        """
        Volume Weighted Average Price

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            volume: Volume

        Returns:
            VWAP series
        """
        typical_price = (high + low + close) / 3
        return (typical_price * volume).cumsum() / volume.cumsum()

    def volume_sma(self, volume: pd.Series, period: int = 20) -> pd.Series:
        """
        Volume Simple Moving Average

        Args:
            volume: Volume series
            period: Period

        Returns:
            Volume SMA
        """
        return self.sma(volume, period)

    @staticmethod
    def mfi(
        high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int = 14
    ) -> pd.Series:
        """
        Money Flow Index

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            volume: Volume
            period: MFI period

        Returns:
            MFI series (0-100)
        """
        typical_price = (high + low + close) / 3
        money_flow = typical_price * volume

        positive_flow = money_flow.where(typical_price > typical_price.shift(1), 0)
        negative_flow = money_flow.where(typical_price < typical_price.shift(1), 0)

        positive_mf = positive_flow.rolling(window=period).sum()
        negative_mf = negative_flow.rolling(window=period).sum()

        mfi = 100 - (100 / (1 + positive_mf / negative_mf))
        return mfi

    # ==================== Trend Indicators ====================

    @staticmethod
    def adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """
        Average Directional Index

        Args:
            high: High prices
            low: Low prices
            close: Close prices
            period: ADX period

        Returns:
            ADX series
        """
        # Calculate +DM and -DM
        high_diff = high.diff()
        low_diff = -low.diff()

        plus_dm = high_diff.where((high_diff > low_diff) & (high_diff > 0), 0)
        minus_dm = low_diff.where((low_diff > high_diff) & (low_diff > 0), 0)

        # Calculate ATR
        high_low = high - low
        high_close = np.abs(high - close.shift())
        low_close = np.abs(low - close.shift())
        true_range = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        atr = true_range.rolling(window=period).mean()

        # Calculate +DI and -DI
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

        # Calculate DX and ADX
        dx = 100 * np.abs(plus_di - minus_di) / (plus_di + minus_di)
        adx = dx.rolling(window=period).mean()

        return adx

    @staticmethod
    def aroon(high: pd.Series, low: pd.Series, period: int = 25) -> Dict[str, pd.Series]:
        """
        Aroon Indicator

        Args:
            high: High prices
            low: Low prices
            period: Aroon period

        Returns:
            Dictionary with 'up', 'down', 'oscillator'
        """
        aroon_up = (
            high.rolling(window=period + 1).apply(lambda x: x.argmax(), raw=True) / period * 100
        )
        aroon_down = (
            low.rolling(window=period + 1).apply(lambda x: x.argmin(), raw=True) / period * 100
        )
        aroon_oscillator = aroon_up - aroon_down

        return {"up": aroon_up, "down": aroon_down, "oscillator": aroon_oscillator}

    # ==================== Feature Computation ====================

    def compute_all_features(
        self, df: pd.DataFrame, prefix: str = ""
    ) -> pd.DataFrame:
        """
        Compute all technical features for a dataframe

        Args:
            df: DataFrame with OHLCV data
            prefix: Optional prefix for feature names

        Returns:
            DataFrame with all technical features
        """
        if df.empty:
            return pd.DataFrame()

        logger.info(f"Computing technical features for {len(df)} rows")

        # Ensure column names are lowercase
        df = df.copy()
        df.columns = [col.lower() for col in df.columns]

        features = pd.DataFrame(index=df.index)

        try:
            # Price features
            features[f"{prefix}close"] = df["close"]
            features[f"{prefix}returns"] = df["close"].pct_change()
            features[f"{prefix}log_returns"] = np.log(df["close"] / df["close"].shift(1))

            # Moving Averages
            for period in [5, 10, 20, 50, 200]:
                features[f"{prefix}sma_{period}"] = self.sma(df["close"], period)
                features[f"{prefix}ema_{period}"] = self.ema(df["close"], period)

            # Price relative to moving averages
            features[f"{prefix}price_to_sma20"] = df["close"] / features[f"{prefix}sma_20"]
            features[f"{prefix}price_to_sma50"] = df["close"] / features[f"{prefix}sma_50"]

            # Momentum
            features[f"{prefix}rsi_14"] = self.rsi(df["close"], 14)

            macd_result = self.macd(df["close"])
            features[f"{prefix}macd"] = macd_result["macd"]
            features[f"{prefix}macd_signal"] = macd_result["signal"]
            features[f"{prefix}macd_histogram"] = macd_result["histogram"]

            stoch_result = self.stochastic(df["high"], df["low"], df["close"])
            features[f"{prefix}stoch_k"] = stoch_result["k"]
            features[f"{prefix}stoch_d"] = stoch_result["d"]

            features[f"{prefix}cci_20"] = self.cci(df["high"], df["low"], df["close"], 20)
            features[f"{prefix}roc_12"] = self.roc(df["close"], 12)
            features[f"{prefix}momentum_10"] = self.momentum(df["close"], 10)

            # Volatility
            bb_result = self.bollinger_bands(df["close"], 20, 2.0)
            features[f"{prefix}bb_upper"] = bb_result["upper"]
            features[f"{prefix}bb_middle"] = bb_result["middle"]
            features[f"{prefix}bb_lower"] = bb_result["lower"]
            features[f"{prefix}bb_bandwidth"] = bb_result["bandwidth"]
            features[f"{prefix}bb_position"] = (df["close"] - bb_result["lower"]) / (
                bb_result["upper"] - bb_result["lower"]
            )

            features[f"{prefix}atr_14"] = self.atr(df["high"], df["low"], df["close"], 14)
            features[f"{prefix}historical_vol_20"] = self.historical_volatility(df["close"], 20)

            # Trend
            features[f"{prefix}adx_14"] = self.adx(df["high"], df["low"], df["close"], 14)

            aroon_result = self.aroon(df["high"], df["low"], 25)
            features[f"{prefix}aroon_up"] = aroon_result["up"]
            features[f"{prefix}aroon_down"] = aroon_result["down"]
            features[f"{prefix}aroon_osc"] = aroon_result["oscillator"]

            # Volume
            if "volume" in df.columns:
                features[f"{prefix}volume"] = df["volume"]
                features[f"{prefix}volume_sma_20"] = self.volume_sma(df["volume"], 20)
                features[f"{prefix}volume_ratio"] = (
                    df["volume"] / features[f"{prefix}volume_sma_20"]
                )
                features[f"{prefix}obv"] = self.obv(df["close"], df["volume"])
                features[f"{prefix}vwap"] = self.vwap(
                    df["high"], df["low"], df["close"], df["volume"]
                )
                features[f"{prefix}mfi_14"] = self.mfi(
                    df["high"], df["low"], df["close"], df["volume"], 14
                )

            # Price patterns
            features[f"{prefix}high_low_range"] = (df["high"] - df["low"]) / df["close"]
            features[f"{prefix}close_to_high"] = (df["high"] - df["close"]) / (
                df["high"] - df["low"]
            )
            features[f"{prefix}close_to_low"] = (df["close"] - df["low"]) / (
                df["high"] - df["low"]
            )

            logger.info(f"Computed {len(features.columns)} technical features")

        except Exception as e:
            logger.error(f"Error computing features: {e}")
            raise

        return features

    def compute_feature_subset(
        self,
        df: pd.DataFrame,
        feature_list: List[str],
        prefix: str = "",
    ) -> pd.DataFrame:
        """
        Compute only specified features

        Args:
            df: DataFrame with OHLCV data
            feature_list: List of feature names to compute
            prefix: Optional prefix for feature names

        Returns:
            DataFrame with requested features
        """
        all_features = self.compute_all_features(df, prefix)
        available_features = [f for f in feature_list if f in all_features.columns]

        if len(available_features) < len(feature_list):
            missing = set(feature_list) - set(available_features)
            logger.warning(f"Missing features: {missing}")

        return all_features[available_features]
