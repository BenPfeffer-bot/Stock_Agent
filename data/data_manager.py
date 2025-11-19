# data/data_manager.py
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional
import logging
from datetime import datetime, timedelta
import pickle
import yaml

from .validators import DataValidator, ValidationResult, DataQualityReport
from .providers.base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class DataManager:
    """
    Central data management system with caching, validation, and quality control

    Responsibilities:
    - Fetch data from providers
    - Validate data quality
    - Cache data locally for performance
    - Handle missing data and errors gracefully
    - Provide clean, validated data to downstream systems
    """

    def __init__(
        self,
        provider: BaseDataProvider,
        cache_dir: str = "data_cache",
        config_path: Optional[str] = None,
        enable_cache: bool = True,
        cache_expiry_days: int = 1,
    ):
        """
        Initialize DataManager

        Args:
            provider: Data provider instance (e.g., YFinanceAdapter)
            cache_dir: Directory for caching data
            config_path: Path to data configuration YAML
            enable_cache: Whether to use caching
            cache_expiry_days: Days before cache expires
        """
        self.provider = provider
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.enable_cache = enable_cache
        self.cache_expiry_days = cache_expiry_days

        # Load configuration
        if config_path:
            with open(config_path, "r") as f:
                self.config = yaml.safe_load(f)["data"]
        else:
            self.config = self._default_config()

        # Initialize validator
        quality_thresholds = self.config.get("quality_thresholds", {})
        self.validator = DataValidator(
            min_quality_score=quality_thresholds.get("min_quality_score", 0.7),
            max_missing_pct=quality_thresholds.get("max_missing_pct", 0.05),
            max_zero_volume_pct=quality_thresholds.get("max_zero_volume_pct", 0.02),
            outlier_std_threshold=quality_thresholds.get("outlier_std_threshold", 10.0),
        )

        # Tracking
        self.validation_results: Dict[str, ValidationResult] = {}
        self.failed_tickers: List[str] = []
        self.cached_tickers: List[str] = []

    def _default_config(self) -> Dict:
        """Default configuration"""
        return {
            "quality_thresholds": {
                "min_quality_score": 0.7,
                "max_missing_pct": 0.05,
                "max_zero_volume_pct": 0.02,
                "outlier_std_threshold": 10.0,
            },
            "date_range": {
                "train_start": "2018-01-01",
                "train_end": "2023-12-31",
            },
        }

    def fetch_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        validate: bool = True,
        force_refresh: bool = False,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch and validate price data for a ticker

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            validate: Whether to validate data quality
            force_refresh: Force refresh from provider (ignore cache)

        Returns:
            DataFrame with validated OHLCV data, or None if validation fails
        """
        # Check cache first
        if self.enable_cache and not force_refresh:
            cached_data = self._load_from_cache(ticker, "prices", start_date, end_date)
            if cached_data is not None:
                logger.info(f"Loaded {ticker} from cache")
                self.cached_tickers.append(ticker)
                return cached_data

        # Fetch from provider
        try:
            logger.info(f"Fetching {ticker} from provider")
            df = self.provider.fetch_prices(ticker, start_date, end_date)

            if df is None or df.empty:
                logger.warning(f"No data returned for {ticker}")
                self.failed_tickers.append(ticker)
                return None

            # Validate data quality
            if validate:
                validation_result = self.validator.validate_price_data(df, ticker)
                self.validation_results[ticker] = validation_result

                if not validation_result.is_valid:
                    logger.error(
                        f"Validation failed for {ticker}: "
                        f"Score={validation_result.quality_score:.2f}, "
                        f"Issues={validation_result.issues}"
                    )
                    self.failed_tickers.append(ticker)
                    return None

                if validation_result.warnings:
                    logger.warning(
                        f"Validation warnings for {ticker}: {validation_result.warnings}"
                    )

                logger.info(
                    f"Validated {ticker}: Quality score = {validation_result.quality_score:.2f}"
                )

            # Clean data
            df = self._clean_price_data(df)

            # Cache the validated data
            if self.enable_cache:
                self._save_to_cache(df, ticker, "prices", start_date, end_date)

            return df

        except Exception as e:
            logger.error(f"Error fetching {ticker}: {str(e)}", exc_info=True)
            self.failed_tickers.append(ticker)
            return None

    def fetch_prices_bulk(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        validate: bool = True,
        force_refresh: bool = False,
        fail_on_error: bool = False,
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch price data for multiple tickers

        Args:
            tickers: List of ticker symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            validate: Whether to validate data quality
            force_refresh: Force refresh from provider
            fail_on_error: Raise exception if any ticker fails

        Returns:
            Dictionary mapping ticker -> DataFrame
        """
        results = {}
        failed = []

        logger.info(f"Fetching data for {len(tickers)} tickers")

        for i, ticker in enumerate(tickers):
            logger.info(f"Progress: {i + 1}/{len(tickers)} - {ticker}")

            df = self.fetch_prices(
                ticker,
                start_date,
                end_date,
                validate=validate,
                force_refresh=force_refresh,
            )

            if df is not None:
                results[ticker] = df
            else:
                failed.append(ticker)

        # Log summary
        logger.info(
            f"Bulk fetch complete: {len(results)} successful, {len(failed)} failed"
        )

        if failed:
            logger.warning(f"Failed tickers: {failed}")

        if fail_on_error and failed:
            raise ValueError(f"Failed to fetch data for: {failed}")

        return results

    def fetch_fundamentals(
        self,
        ticker: str,
        validate: bool = True,
        force_refresh: bool = False,
    ) -> Optional[Dict]:
        """
        Fetch and validate fundamental data

        Args:
            ticker: Stock ticker symbol
            validate: Whether to validate data quality
            force_refresh: Force refresh from provider

        Returns:
            Dictionary with fundamental data, or None if validation fails
        """
        # Check cache
        if self.enable_cache and not force_refresh:
            cached_data = self._load_from_cache(ticker, "fundamentals")
            if cached_data is not None:
                return cached_data

        # Fetch from provider
        try:
            data = self.provider.fetch_fundamentals(ticker)

            if not data:
                logger.warning(f"No fundamental data for {ticker}")
                return None

            # Validate
            if validate:
                validation_result = self.validator.validate_fundamental_data(
                    data, ticker
                )

                if not validation_result.is_valid:
                    logger.warning(
                        f"Fundamental validation failed for {ticker}: "
                        f"{validation_result.issues}"
                    )
                    return None

            # Cache
            if self.enable_cache:
                self._save_to_cache(data, ticker, "fundamentals")

            return data

        except Exception as e:
            logger.error(f"Error fetching fundamentals for {ticker}: {str(e)}")
            return None

    def _clean_price_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and preprocess price data

        - Forward fill missing values (up to 5 days)
        - Remove rows with remaining NaNs
        - Ensure chronological order
        - Remove duplicates
        """
        df = df.copy()

        # Sort by date
        df = df.sort_index()

        # Remove duplicates
        df = df[~df.index.duplicated(keep="first")]

        # Forward fill missing values (limited to 5 days)
        df = df.ffill(limit=5)

        # Drop rows with remaining NaNs
        df = df.dropna()

        # Ensure positive prices and volumes
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            if col == "Volume":
                df[col] = df[col].clip(lower=0)
            else:  # Price columns
                df[col] = df[col].clip(lower=0.01)  # Minimum $0.01

        return df

    def _get_cache_path(
        self,
        ticker: str,
        data_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Path:
        """Generate cache file path"""
        if start_date and end_date:
            filename = f"{ticker}_{data_type}_{start_date}_{end_date}.pkl"
        else:
            filename = f"{ticker}_{data_type}.pkl"

        return self.cache_dir / filename

    def _save_to_cache(
        self,
        data,
        ticker: str,
        data_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        """Save data to cache"""
        cache_path = self._get_cache_path(ticker, data_type, start_date, end_date)

        cache_data = {
            "data": data,
            "timestamp": datetime.now(),
            "ticker": ticker,
            "data_type": data_type,
        }

        try:
            with open(cache_path, "wb") as f:
                pickle.dump(cache_data, f)
            logger.debug(f"Cached {ticker} to {cache_path}")
        except Exception as e:
            logger.warning(f"Failed to cache {ticker}: {str(e)}")

    def _load_from_cache(
        self,
        ticker: str,
        data_type: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ):
        """Load data from cache if available and not expired"""
        cache_path = self._get_cache_path(ticker, data_type, start_date, end_date)

        if not cache_path.exists():
            return None

        # Check expiry
        cache_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
        if cache_age > timedelta(days=self.cache_expiry_days):
            logger.debug(f"Cache expired for {ticker}")
            return None

        try:
            with open(cache_path, "rb") as f:
                cache_data = pickle.load(f)
            return cache_data["data"]
        except Exception as e:
            logger.warning(f"Failed to load cache for {ticker}: {str(e)}")
            return None

    def clear_cache(self, ticker: Optional[str] = None):
        """Clear cache for specific ticker or all tickers"""
        if ticker:
            for cache_file in self.cache_dir.glob(f"{ticker}_*.pkl"):
                cache_file.unlink()
                logger.info(f"Cleared cache: {cache_file}")
        else:
            for cache_file in self.cache_dir.glob("*.pkl"):
                cache_file.unlink()
            logger.info("Cleared all cache")

    def get_validation_summary(self) -> pd.DataFrame:
        """Get summary of validation results"""
        if not self.validation_results:
            logger.warning("No validation results available")
            return pd.DataFrame()

        return DataQualityReport.generate_summary(self.validation_results)

    def get_quality_report(self) -> Dict:
        """Generate comprehensive quality report"""
        if not self.validation_results:
            return {
                "total_tickers": 0,
                "validated_tickers": 0,
                "failed_tickers": 0,
            }

        summary_df = self.get_validation_summary()
        distribution = DataQualityReport.get_quality_distribution(
            self.validation_results
        )

        return {
            "total_tickers": len(self.validation_results),
            "valid_tickers": summary_df["is_valid"].sum(),
            "failed_tickers": len(self.failed_tickers),
            "avg_quality_score": summary_df["quality_score"].mean(),
            "quality_distribution": distribution,
            "cached_tickers": len(set(self.cached_tickers)),
            "summary": summary_df,
        }

    def align_data(
        self,
        data_dict: Dict[str, pd.DataFrame],
        method: str = "inner",
    ) -> Dict[str, pd.DataFrame]:
        """
        Align multiple ticker DataFrames to common date index

        Args:
            data_dict: Dictionary mapping ticker -> DataFrame
            method: 'inner' (intersection) or 'outer' (union) of dates

        Returns:
            Dictionary with aligned DataFrames
        """
        if not data_dict:
            return {}

        # Get common date index
        if method == "inner":
            # Intersection of all date indices
            common_idx = None
            for df in data_dict.values():
                if common_idx is None:
                    common_idx = df.index
                else:
                    common_idx = common_idx.intersection(df.index)
        else:  # outer
            # Union of all date indices
            common_idx = None
            for df in data_dict.values():
                if common_idx is None:
                    common_idx = df.index
                else:
                    common_idx = common_idx.union(df.index)

        # Reindex all DataFrames
        aligned = {}
        for ticker, df in data_dict.items():
            aligned_df = df.reindex(common_idx)

            if method == "outer":
                # Forward fill for outer join
                aligned_df = aligned_df.fillna(method="ffill", limit=5)

            aligned[ticker] = aligned_df

        logger.info(
            f"Aligned {len(data_dict)} tickers to {len(common_idx)} common dates "
            f"using {method} method"
        )

        return aligned

    def create_panel_data(
        self,
        data_dict: Dict[str, pd.DataFrame],
        align_method: str = "inner",
    ) -> pd.DataFrame:
        """
        Create panel data structure (multi-index: date x ticker)

        Args:
            data_dict: Dictionary mapping ticker -> DataFrame
            align_method: How to align dates across tickers

        Returns:
            Panel DataFrame with MultiIndex
        """
        # Align data first
        aligned_data = self.align_data(data_dict, method=align_method)

        # Create panel
        panels = []
        for ticker, df in aligned_data.items():
            df_copy = df.copy()
            df_copy["ticker"] = ticker
            df_copy = df_copy.reset_index()
            df_copy.rename(columns={df_copy.columns[0]: "date"}, inplace=True)
            panels.append(df_copy)

        panel_df = pd.concat(panels, ignore_index=True)
        panel_df = panel_df.set_index(["date", "ticker"])
        panel_df = panel_df.sort_index()

        logger.info(
            f"Created panel data: {len(panel_df)} rows, "
            f"{panel_df.index.get_level_values('ticker').nunique()} tickers"
        )

        return panel_df

    def export_validation_report(self, output_path: str):
        """Export validation results to CSV"""
        summary_df = self.get_validation_summary()
        summary_df.to_csv(output_path, index=False)
        logger.info(f"Exported validation report to {output_path}")

    def get_data_coverage(
        self,
        data_dict: Dict[str, pd.DataFrame],
    ) -> pd.DataFrame:
        """
        Analyze data coverage across tickers

        Returns:
            DataFrame with coverage statistics
        """
        coverage_data = []

        for ticker, df in data_dict.items():
            coverage_data.append(
                {
                    "ticker": ticker,
                    "start_date": df.index.min(),
                    "end_date": df.index.max(),
                    "total_days": len(df),
                    "missing_values": df.isnull().sum().sum(),
                    "completeness": 1.0 - (df.isnull().sum().sum() / df.size),
                }
            )

        return pd.DataFrame(coverage_data)
