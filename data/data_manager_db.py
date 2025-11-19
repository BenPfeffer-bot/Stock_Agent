# data/data_manager_db.py
"""
Database-backed Data Manager with two-layer architecture:
1. Data Lake: Raw, immutable provider data
2. Feature Store: Processed features for RL consumption
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
import logging
from datetime import datetime, date

from .data_manager import DataManager
from .database import DatabaseManager
from .validators import ValidationResult
from .providers.base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class DataManagerDB(DataManager):
    """
    Database-backed data manager with data lake and feature store
    
    Extends base DataManager with persistent storage:
    - Raw prices stored in data lake
    - Computed features stored in feature store
    - Stock universe with survivorship bias handling
    - Data quality logging
    """
    
    def __init__(
        self,
        provider: BaseDataProvider,
        db_path: str = "data/stock_data.db",
        cache_dir: str = "data_cache",
        config_path: Optional[str] = None,
        enable_cache: bool = True,
        cache_expiry_days: int = 1,
        use_database: bool = True,
    ):
        """
        Initialize database-backed data manager
        
        Args:
            provider: Data provider instance
            db_path: Path to SQLite database
            cache_dir: Directory for caching
            config_path: Path to data configuration YAML
            enable_cache: Whether to use file-based caching
            cache_expiry_days: Days before cache expires
            use_database: Whether to use database layer
        """
        super().__init__(
            provider=provider,
            cache_dir=cache_dir,
            config_path=config_path,
            enable_cache=enable_cache,
            cache_expiry_days=cache_expiry_days,
        )
        
        self.use_database = use_database
        if use_database:
            self.db = DatabaseManager(db_path)
            logger.info(f"Database-backed data manager initialized: {db_path}")
        else:
            self.db = None
    
    def fetch_prices(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        validate: bool = True,
        force_refresh: bool = False,
        save_to_db: bool = True,
    ) -> Optional[pd.DataFrame]:
        """
        Fetch and validate price data with database persistence
        
        Order of operations:
        1. Check database first
        2. If not in DB or force_refresh, fetch from provider
        3. Validate data
        4. Save to database
        5. Return validated data
        
        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            validate: Whether to validate data quality
            force_refresh: Force refresh from provider
            save_to_db: Whether to save to database
            
        Returns:
            DataFrame with validated OHLCV data, or None if validation fails
        """
        # Try database first (if enabled and not forcing refresh)
        if self.use_database and not force_refresh:
            df = self.db.get_raw_prices(ticker, start_date, end_date)
            if not df.empty:
                logger.info(f"Loaded {ticker} from database ({len(df)} rows)")
                return df
        
        # Fetch from provider using parent class method
        df = super().fetch_prices(ticker, start_date, end_date, validate, force_refresh)
        
        if df is None or df.empty:
            return None
        
        # Save to database if validation passed
        if self.use_database and save_to_db:
            quality_score = None
            if ticker in self.validation_results:
                quality_score = self.validation_results[ticker].quality_score
            
            self.db.insert_raw_prices(
                ticker=ticker,
                df=df,
                provider="yfinance",
                quality_score=quality_score,
            )
            
            # Log quality issues to database
            if ticker in self.validation_results:
                self._log_quality_issues(ticker, self.validation_results[ticker])
        
        return df
    
    def fetch_prices_bulk(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        validate: bool = True,
        force_refresh: bool = False,
        fail_on_error: bool = False,
        save_to_db: bool = True,
    ) -> Dict[str, pd.DataFrame]:
        """
        Fetch price data for multiple tickers with database persistence
        
        Args:
            tickers: List of ticker symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            validate: Whether to validate data quality
            force_refresh: Force refresh from provider
            fail_on_error: Raise exception if any ticker fails
            save_to_db: Whether to save to database
            
        Returns:
            Dictionary mapping ticker -> DataFrame
        """
        results = {}
        
        # Try to load from database first
        if self.use_database and not force_refresh:
            db_results = self.db.get_raw_prices_bulk(tickers, start_date, end_date)
            results.update(db_results)
            
            # Remove tickers already loaded from DB
            remaining_tickers = [t for t in tickers if t not in results]
            logger.info(
                f"Loaded {len(results)} tickers from database, "
                f"{len(remaining_tickers)} to fetch from provider"
            )
        else:
            remaining_tickers = tickers
        
        # Fetch remaining tickers from provider
        if remaining_tickers:
            new_results = super().fetch_prices_bulk(
                tickers=remaining_tickers,
                start_date=start_date,
                end_date=end_date,
                validate=validate,
                force_refresh=force_refresh,
                fail_on_error=fail_on_error,
            )
            
            # Save to database
            if self.use_database and save_to_db:
                for ticker, df in new_results.items():
                    quality_score = None
                    if ticker in self.validation_results:
                        quality_score = self.validation_results[ticker].quality_score
                    
                    self.db.insert_raw_prices(
                        ticker=ticker,
                        df=df,
                        quality_score=quality_score,
                    )
                    
                    # Log quality issues
                    if ticker in self.validation_results:
                        self._log_quality_issues(ticker, self.validation_results[ticker])
            
            results.update(new_results)
        
        return results
    
    def _log_quality_issues(self, ticker: str, result: ValidationResult):
        """Log validation issues to database"""
        if not self.use_database:
            return
        
        date_range = result.metadata.get("date_range", (None, None))
        if not date_range[0]:
            return
        
        issue_date = date_range[1]  # Use end date for logging
        
        # Log issues (severity 3 = high)
        for issue in result.issues:
            self.db.log_quality_issue(
                ticker=ticker,
                issue_date=issue_date,
                issue_type="validation_failure",
                severity=3,
                details={"message": issue, "score": result.quality_score},
            )
        
        # Log warnings (severity 1 = low)
        for warning in result.warnings:
            self.db.log_quality_issue(
                ticker=ticker,
                issue_date=issue_date,
                issue_type="validation_warning",
                severity=1,
                details={"message": warning, "score": result.quality_score},
            )
    
    # ==================== UNIVERSE MANAGEMENT ====================
    
    def load_universe(
        self,
        market: Optional[str] = None,
        active_only: bool = True,
        as_of_date: Optional[date] = None,
    ) -> List[str]:
        """
        Load stock universe from database
        
        Args:
            market: Filter by market (US, EU, etc.)
            active_only: Only return currently active stocks
            as_of_date: Get universe as of specific date (for survivorship bias)
            
        Returns:
            List of ticker symbols
        """
        if not self.use_database:
            logger.warning("Database not enabled, cannot load universe")
            return []
        
        return self.db.get_universe_tickers(market, active_only, as_of_date)
    
    def add_to_universe(
        self,
        ticker: str,
        name: str,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        market: str = "US",
        **kwargs,
    ):
        """Add stock to universe"""
        if not self.use_database:
            logger.warning("Database not enabled, cannot add to universe")
            return
        
        self.db.add_to_universe(
            ticker=ticker,
            name=name,
            sector=sector,
            industry=industry,
            market=market,
            **kwargs,
        )
    
    def remove_from_universe(self, ticker: str, removed_date: Optional[date] = None):
        """Remove stock from universe (for survivorship bias tracking)"""
        if not self.use_database:
            logger.warning("Database not enabled, cannot remove from universe")
            return
        
        self.db.remove_from_universe(ticker, removed_date)
    
    # ==================== FEATURE STORE OPERATIONS ====================
    
    def save_features(
        self,
        ticker: str,
        features_df: pd.DataFrame,
        feature_columns: Optional[List[str]] = None,
    ) -> int:
        """
        Save computed features to feature store
        
        Args:
            ticker: Stock ticker
            features_df: DataFrame with features (index=date)
            feature_columns: List of feature columns to save
            
        Returns:
            Number of feature values saved
        """
        if not self.use_database:
            logger.warning("Database not enabled, cannot save features")
            return 0
        
        return self.db.insert_features(ticker, features_df, feature_columns)
    
    def load_features(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        feature_names: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Load features from feature store
        
        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            feature_names: List of specific features to load
            
        Returns:
            DataFrame with features (index=date, columns=feature names)
        """
        if not self.use_database:
            logger.warning("Database not enabled, cannot load features")
            return pd.DataFrame()
        
        return self.db.get_features(ticker, start_date, end_date, feature_names)
    
    def load_features_bulk(
        self,
        tickers: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        feature_names: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Load features for multiple tickers as panel data
        
        Args:
            tickers: List of stock tickers
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            feature_names: List of specific features to load
            
        Returns:
            DataFrame with MultiIndex (date, ticker)
        """
        if not self.use_database:
            logger.warning("Database not enabled, cannot load features")
            return pd.DataFrame()
        
        return self.db.get_features_bulk(tickers, start_date, end_date, feature_names)
    
    def register_feature(
        self,
        feature_name: str,
        description: str,
        feature_type: str = "technical",
    ):
        """Register feature in metadata"""
        if not self.use_database:
            logger.warning("Database not enabled, cannot register feature")
            return
        
        self.db.register_feature(feature_name, description, feature_type)
    
    # ==================== FUNDAMENTALS ====================
    
    def save_fundamentals(
        self,
        ticker: str,
        fundamentals: Dict,
        metric_date: Optional[date] = None,
    ) -> int:
        """
        Save fundamental data to database
        
        Args:
            ticker: Stock ticker
            fundamentals: Dictionary of fundamental metrics
            metric_date: Date of metrics (defaults to today)
            
        Returns:
            Number of metrics saved
        """
        if not self.use_database:
            logger.warning("Database not enabled, cannot save fundamentals")
            return 0
        
        if metric_date is None:
            metric_date = date.today()
        
        return self.db.insert_fundamentals(ticker, fundamentals, metric_date)
    
    def load_fundamentals(
        self,
        ticker: str,
        metric_date: Optional[date] = None,
    ) -> Dict:
        """
        Load fundamental data from database
        
        Args:
            ticker: Stock ticker
            metric_date: Specific date (if None, gets most recent)
            
        Returns:
            Dictionary of fundamental metrics
        """
        if not self.use_database:
            logger.warning("Database not enabled, cannot load fundamentals")
            return {}
        
        return self.db.get_fundamentals(ticker, metric_date)
    
    # ==================== QUALITY AND STATS ====================
    
    def get_quality_issues(
        self,
        ticker: Optional[str] = None,
        min_severity: int = 1,
    ) -> pd.DataFrame:
        """Get data quality issues from log"""
        if not self.use_database:
            logger.warning("Database not enabled, cannot get quality issues")
            return pd.DataFrame()
        
        return self.db.get_quality_issues(ticker=ticker, min_severity=min_severity)
    
    def get_database_stats(self) -> Dict:
        """Get database statistics"""
        if not self.use_database:
            return {"database_enabled": False}
        
        stats = self.db.get_data_stats()
        stats["database_enabled"] = True
        return stats
    
    def export_to_csv(
        self,
        ticker: str,
        start_date: str,
        end_date: str,
        output_path: str,
        include_features: bool = False,
    ):
        """
        Export data to CSV
        
        Args:
            ticker: Stock ticker
            start_date: Start date
            end_date: End date
            output_path: Output CSV path
            include_features: Whether to include features
        """
        # Get price data
        df = self.fetch_prices(ticker, start_date, end_date)
        
        if df is None or df.empty:
            logger.warning(f"No data to export for {ticker}")
            return
        
        # Optionally merge with features
        if include_features and self.use_database:
            features = self.load_features(ticker, start_date, end_date)
            if not features.empty:
                df = df.join(features, how='left')
        
        df.to_csv(output_path)
        logger.info(f"Exported {ticker} data to {output_path}")

