# data/database.py
"""
Database layer for raw data lake and feature store
Designed for easy migration from SQLite to PostgreSQL
"""

import sqlite3
import pandas as pd
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime, date
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    Manages database operations for data lake and feature store

    Two-layer architecture:
    1. Data Lake: Raw, immutable provider data with quality scores
    2. Feature Store: Processed features for RL consumption
    """

    def __init__(self, db_path: str = "data/stock_data.db"):
        """
        Initialize database manager

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database schema
        self._init_schema()

        logger.info(f"Database initialized at {self.db_path}")

    @contextmanager
    def get_connection(self):
        """Context manager for database connections"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # Raw prices table (data lake)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS raw_prices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    date DATE NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    adj_close REAL,
                    volume REAL,
                    dividends REAL DEFAULT 0.0,
                    splits REAL DEFAULT 0.0,
                    provider TEXT DEFAULT 'yfinance',
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    data_quality_score REAL,
                    UNIQUE(ticker, date, provider)
                )
            """)

            # Create indices for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_raw_prices_ticker_date 
                ON raw_prices(ticker, date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_raw_prices_date 
                ON raw_prices(date)
            """)

            # Stock universe table (survivorship bias handling)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS stock_universe (
                    ticker TEXT PRIMARY KEY,
                    name TEXT,
                    sector TEXT,
                    industry TEXT,
                    market TEXT,
                    currency TEXT DEFAULT 'USD',
                    is_active BOOLEAN DEFAULT 1,
                    added_date DATE NOT NULL,
                    removed_date DATE,
                    market_cap REAL,
                    notes TEXT
                )
            """)

            # Data quality log
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_quality_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    date DATE NOT NULL,
                    issue_type TEXT NOT NULL,
                    severity INTEGER,
                    details TEXT,
                    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_quality_log_ticker 
                ON data_quality_log(ticker)
            """)

            # Features table (feature store)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS features (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    date DATE NOT NULL,
                    feature_name TEXT NOT NULL,
                    feature_value REAL,
                    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ticker, date, feature_name)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_features_ticker_date 
                ON features(ticker, date)
            """)

            # Feature metadata table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS feature_metadata (
                    feature_name TEXT PRIMARY KEY,
                    description TEXT,
                    feature_type TEXT,
                    data_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Fundamentals table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS fundamentals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ticker TEXT NOT NULL,
                    date DATE NOT NULL,
                    metric_name TEXT NOT NULL,
                    metric_value REAL,
                    provider TEXT DEFAULT 'yfinance',
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ticker, date, metric_name, provider)
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fundamentals_ticker_date 
                ON fundamentals(ticker, date)
            """)

            logger.info("Database schema initialized")

    # ==================== DATA LAKE OPERATIONS ====================

    def insert_raw_prices(
        self,
        ticker: str,
        df: pd.DataFrame,
        provider: str = "yfinance",
        quality_score: Optional[float] = None,
    ) -> int:
        """
        Insert raw price data into data lake

        Args:
            ticker: Stock ticker
            df: DataFrame with OHLCV data (index=date)
            provider: Data provider name
            quality_score: Overall quality score (0-1)

        Returns:
            Number of rows inserted
        """
        if df.empty:
            return 0

        df_copy = df.copy()
        df_copy["ticker"] = ticker
        df_copy["provider"] = provider
        df_copy["data_quality_score"] = quality_score
        df_copy["ingested_at"] = datetime.now()

        # Ensure date is in columns (not index)
        if "date" not in df_copy.columns:
            df_copy = df_copy.reset_index()
            # Rename the index column to 'date' if it has a different name
            if df_copy.columns[0] != "date" and df_copy.index.name != "date":
                df_copy.rename(columns={df_copy.columns[0]: "date"}, inplace=True)
            elif "index" in df_copy.columns:
                df_copy.rename(columns={"index": "date"}, inplace=True)

        # Rename columns to match schema (lowercase)
        column_mapping = {
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Adj Close": "adj_close",
            "Volume": "volume",
            "Dividends": "dividends",
            "Splits": "splits",
        }
        df_copy = df_copy.rename(columns=column_mapping)

        # Select only relevant columns
        columns = [
            "ticker",
            "date",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
            "dividends",
            "splits",
            "provider",
            "ingested_at",
            "data_quality_score",
        ]
        available_columns = [col for col in columns if col in df_copy.columns]
        df_insert = df_copy[available_columns]

        with self.get_connection() as conn:
            # Use INSERT OR REPLACE to handle duplicates
            df_insert.to_sql(
                "raw_prices",
                conn,
                if_exists="append",
                index=False,
                method="multi",
            )
            rows_inserted = len(df_insert)

        logger.info(f"Inserted {rows_inserted} rows for {ticker} from {provider}")
        return rows_inserted

    def get_raw_prices(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        provider: str = "yfinance",
    ) -> pd.DataFrame:
        """
        Retrieve raw price data from data lake

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            provider: Data provider name

        Returns:
            DataFrame with OHLCV data
        """
        query = """
            SELECT date, open, high, low, close, adj_close, volume,
                   dividends, splits, data_quality_score, ingested_at
            FROM raw_prices
            WHERE ticker = ? AND provider = ?
        """
        params = [ticker, provider]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date"

        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params, parse_dates=["date"])

        if not df.empty:
            df.set_index("date", inplace=True)

        return df

    def get_raw_prices_bulk(
        self,
        tickers: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        provider: str = "yfinance",
    ) -> Dict[str, pd.DataFrame]:
        """
        Retrieve raw price data for multiple tickers

        Args:
            tickers: List of stock tickers
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            provider: Data provider name

        Returns:
            Dictionary mapping ticker -> DataFrame
        """
        results = {}
        for ticker in tickers:
            df = self.get_raw_prices(ticker, start_date, end_date, provider)
            if not df.empty:
                results[ticker] = df

        return results

    # ==================== UNIVERSE MANAGEMENT ====================

    def add_to_universe(
        self,
        ticker: str,
        name: str,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        market: str = "US",
        added_date: Optional[date] = None,
        **kwargs,
    ):
        """
        Add stock to universe

        Args:
            ticker: Stock ticker
            name: Company name
            sector: Sector
            industry: Industry
            market: Market (US, EU, etc.)
            added_date: Date added to universe
            **kwargs: Additional fields (market_cap, currency, etc.)
        """
        if added_date is None:
            added_date = date.today()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO stock_universe
                (ticker, name, sector, industry, market, added_date, 
                 is_active, currency, market_cap, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    ticker,
                    name,
                    sector,
                    industry,
                    market,
                    added_date,
                    kwargs.get("is_active", True),
                    kwargs.get("currency", "USD"),
                    kwargs.get("market_cap"),
                    kwargs.get("notes"),
                ),
            )

        logger.info(f"Added {ticker} to universe")

    def remove_from_universe(self, ticker: str, removed_date: Optional[date] = None):
        """
        Mark stock as removed from universe (for survivorship bias handling)

        Args:
            ticker: Stock ticker
            removed_date: Date removed from universe
        """
        if removed_date is None:
            removed_date = date.today()

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE stock_universe
                SET is_active = 0, removed_date = ?
                WHERE ticker = ?
            """,
                (removed_date, ticker),
            )

        logger.info(f"Marked {ticker} as removed from universe")

    def get_universe(
        self,
        market: Optional[str] = None,
        active_only: bool = True,
        as_of_date: Optional[date] = None,
    ) -> List[Dict]:
        """
        Get stock universe with survivorship bias handling

        Args:
            market: Filter by market (US, EU, etc.)
            active_only: Only return currently active stocks
            as_of_date: Get universe as of specific date

        Returns:
            List of stock dictionaries
        """
        query = "SELECT * FROM stock_universe WHERE 1=1"
        params = []

        if market:
            query += " AND market = ?"
            params.append(market)

        if active_only:
            query += " AND is_active = 1"

        if as_of_date:
            query += " AND added_date <= ?"
            params.append(as_of_date)
            query += " AND (removed_date IS NULL OR removed_date > ?)"
            params.append(as_of_date)

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    def get_universe_tickers(
        self,
        market: Optional[str] = None,
        active_only: bool = True,
        as_of_date: Optional[date] = None,
    ) -> List[str]:
        """Get list of tickers in universe"""
        universe = self.get_universe(market, active_only, as_of_date)
        return [stock["ticker"] for stock in universe]

    # ==================== DATA QUALITY LOGGING ====================

    def log_quality_issue(
        self,
        ticker: str,
        issue_date: date,
        issue_type: str,
        severity: int,
        details: Optional[Dict] = None,
    ):
        """
        Log data quality issue

        Args:
            ticker: Stock ticker
            issue_date: Date of issue
            issue_type: Type of issue (missing, zero_volume, price_spike, etc.)
            severity: Severity level (1=low, 2=medium, 3=high)
            details: Additional details as dictionary
        """
        details_json = json.dumps(details) if details else None

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO data_quality_log
                (ticker, date, issue_type, severity, details)
                VALUES (?, ?, ?, ?, ?)
            """,
                (ticker, issue_date, issue_type, severity, details_json),
            )

    def get_quality_issues(
        self,
        ticker: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        min_severity: int = 1,
    ) -> pd.DataFrame:
        """
        Retrieve data quality issues

        Args:
            ticker: Filter by ticker
            start_date: Start date
            end_date: End date
            min_severity: Minimum severity level

        Returns:
            DataFrame with quality issues
        """
        query = "SELECT * FROM data_quality_log WHERE severity >= ?"
        params = [min_severity]

        if ticker:
            query += " AND ticker = ?"
            params.append(ticker)

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        query += " ORDER BY date DESC, severity DESC"

        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params)

        return df

    # ==================== FEATURE STORE OPERATIONS ====================

    def insert_features(
        self,
        ticker: str,
        df: pd.DataFrame,
        feature_columns: Optional[List[str]] = None,
    ) -> int:
        """
        Insert computed features into feature store

        Args:
            ticker: Stock ticker
            df: DataFrame with features (index=date, columns=feature names)
            feature_columns: List of feature column names to insert

        Returns:
            Number of rows inserted
        """
        if df.empty:
            return 0

        df_copy = df.copy()

        # Ensure date is in columns
        if "date" not in df_copy.columns:
            df_copy = df_copy.reset_index()

        # Determine which features to insert
        if feature_columns is None:
            feature_columns = [
                col for col in df_copy.columns if col not in ["date", "ticker"]
            ]

        # Melt to long format
        df_long = df_copy.melt(
            id_vars=["date"],
            value_vars=feature_columns,
            var_name="feature_name",
            value_name="feature_value",
        )
        df_long["ticker"] = ticker
        df_long["computed_at"] = datetime.now()

        # Remove NaN values
        df_long = df_long.dropna(subset=["feature_value"])

        with self.get_connection() as conn:
            df_long.to_sql(
                "features",
                conn,
                if_exists="append",
                index=False,
                method="multi",
            )
            rows_inserted = len(df_long)

        logger.info(f"Inserted {rows_inserted} feature values for {ticker}")
        return rows_inserted

    def get_features(
        self,
        ticker: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        feature_names: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Retrieve features from feature store

        Args:
            ticker: Stock ticker
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            feature_names: List of feature names to retrieve

        Returns:
            DataFrame with features (index=date, columns=feature names)
        """
        query = """
            SELECT date, feature_name, feature_value
            FROM features
            WHERE ticker = ?
        """
        params = [ticker]

        if start_date:
            query += " AND date >= ?"
            params.append(start_date)

        if end_date:
            query += " AND date <= ?"
            params.append(end_date)

        if feature_names:
            placeholders = ",".join("?" * len(feature_names))
            query += f" AND feature_name IN ({placeholders})"
            params.extend(feature_names)

        query += " ORDER BY date"

        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=params, parse_dates=["date"])

        if df.empty:
            return pd.DataFrame()

        # Pivot to wide format
        df_wide = df.pivot(index="date", columns="feature_name", values="feature_value")

        return df_wide

    def get_features_bulk(
        self,
        tickers: List[str],
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        feature_names: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Retrieve features for multiple tickers as panel data

        Args:
            tickers: List of stock tickers
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            feature_names: List of feature names to retrieve

        Returns:
            DataFrame with MultiIndex (date, ticker)
        """
        dfs = []
        for ticker in tickers:
            df = self.get_features(ticker, start_date, end_date, feature_names)
            if not df.empty:
                df["ticker"] = ticker
                df = df.reset_index()
                dfs.append(df)

        if not dfs:
            return pd.DataFrame()

        panel_df = pd.concat(dfs, ignore_index=True)
        panel_df = panel_df.set_index(["date", "ticker"])
        panel_df = panel_df.sort_index()

        return panel_df

    def register_feature(
        self,
        feature_name: str,
        description: str,
        feature_type: str = "technical",
        data_type: str = "float",
    ):
        """
        Register feature metadata

        Args:
            feature_name: Feature name
            description: Feature description
            feature_type: Type (technical, fundamental, sentiment, macro)
            data_type: Data type (float, int, bool)
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO feature_metadata
                (feature_name, description, feature_type, data_type)
                VALUES (?, ?, ?, ?)
            """,
                (feature_name, description, feature_type, data_type),
            )

        logger.debug(f"Registered feature: {feature_name}")

    def get_feature_metadata(self) -> pd.DataFrame:
        """Get all feature metadata"""
        with self.get_connection() as conn:
            df = pd.read_sql_query("SELECT * FROM feature_metadata", conn)
        return df

    # ==================== FUNDAMENTALS ====================

    def insert_fundamentals(
        self,
        ticker: str,
        fundamentals: Dict[str, Any],
        metric_date: date,
        provider: str = "yfinance",
    ) -> int:
        """
        Insert fundamental data

        Args:
            ticker: Stock ticker
            fundamentals: Dictionary of fundamental metrics
            metric_date: Date of metrics
            provider: Data provider

        Returns:
            Number of metrics inserted
        """
        if not fundamentals:
            return 0

        with self.get_connection() as conn:
            cursor = conn.cursor()
            count = 0
            for metric_name, metric_value in fundamentals.items():
                if metric_value is not None:
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO fundamentals
                        (ticker, date, metric_name, metric_value, provider)
                        VALUES (?, ?, ?, ?, ?)
                    """,
                        (ticker, metric_date, metric_name, metric_value, provider),
                    )
                    count += 1

        logger.info(f"Inserted {count} fundamental metrics for {ticker}")
        return count

    def get_fundamentals(
        self,
        ticker: str,
        metric_date: Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Get fundamental data for ticker

        Args:
            ticker: Stock ticker
            metric_date: Specific date (if None, gets most recent)

        Returns:
            Dictionary of fundamental metrics
        """
        if metric_date:
            query = """
                SELECT metric_name, metric_value
                FROM fundamentals
                WHERE ticker = ? AND date = ?
            """
            params = [ticker, metric_date]
        else:
            query = """
                SELECT metric_name, metric_value
                FROM fundamentals
                WHERE ticker = ?
                ORDER BY date DESC
                LIMIT 100
            """
            params = [ticker]

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()

        return {row["metric_name"]: row["metric_value"] for row in rows}

    # ==================== UTILITY METHODS ====================

    def get_data_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # Raw prices stats
            cursor.execute("SELECT COUNT(*) FROM raw_prices")
            stats["total_price_records"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT ticker) FROM raw_prices")
            stats["tickers_with_prices"] = cursor.fetchone()[0]

            cursor.execute("SELECT MIN(date), MAX(date) FROM raw_prices")
            row = cursor.fetchone()
            stats["price_date_range"] = (row[0], row[1])

            # Universe stats
            cursor.execute("SELECT COUNT(*) FROM stock_universe")
            stats["universe_size"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM stock_universe WHERE is_active = 1")
            stats["active_stocks"] = cursor.fetchone()[0]

            # Features stats
            cursor.execute("SELECT COUNT(*) FROM features")
            stats["total_feature_values"] = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(DISTINCT feature_name) FROM features")
            stats["unique_features"] = cursor.fetchone()[0]

            # Quality issues
            cursor.execute("SELECT COUNT(*) FROM data_quality_log")
            stats["quality_issues_logged"] = cursor.fetchone()[0]

        return stats

    def vacuum(self):
        """Optimize database (reclaim space, rebuild indices)"""
        with self.get_connection() as conn:
            conn.execute("VACUUM")
        logger.info("Database vacuumed")
