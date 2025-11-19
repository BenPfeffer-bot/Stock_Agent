# data/universe.py
"""
Universe Manager with Survivorship Bias Handling

Key Features:
- Track stock additions/removals over time
- Query universe as of any historical date
- Prevent look-ahead bias in backtesting
- Support multiple markets and filters
- Integration with database layer
"""

from typing import List, Dict, Optional, Set
from datetime import date, datetime, timedelta
import logging
from dataclasses import dataclass
import pandas as pd

from .database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class UniverseStock:
    """Represents a stock in the universe"""

    ticker: str
    name: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    market: str = "US"
    currency: str = "USD"
    is_active: bool = True
    added_date: Optional[date] = None
    removed_date: Optional[date] = None
    market_cap: Optional[float] = None
    notes: Optional[str] = None


class UniverseManager:
    """
    Manages the stock universe with survivorship bias handling

    This class ensures backtesting doesn't suffer from survivorship bias by
    tracking when stocks entered and exited the universe.
    """

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        db_path: str = "data/stock_data.db",
    ):
        """
        Initialize Universe Manager

        Args:
            db_manager: DatabaseManager instance (optional)
            db_path: Path to database if db_manager not provided
        """
        if db_manager is None:
            self.db = DatabaseManager(db_path)
        else:
            self.db = db_manager

        logger.info("Universe Manager initialized")

    def add_stock(
        self,
        ticker: str,
        name: str,
        sector: Optional[str] = None,
        industry: Optional[str] = None,
        market: str = "US",
        added_date: Optional[date] = None,
        **kwargs,
    ) -> bool:
        """
        Add a stock to the universe

        Args:
            ticker: Stock ticker symbol
            name: Company name
            sector: Sector classification
            industry: Industry classification
            market: Market identifier (US, EU, etc.)
            added_date: Date added to universe (defaults to today)
            **kwargs: Additional fields (market_cap, currency, notes)

        Returns:
            True if successfully added
        """
        try:
            self.db.add_to_universe(
                ticker=ticker,
                name=name,
                sector=sector,
                industry=industry,
                market=market,
                added_date=added_date,
                **kwargs,
            )
            logger.info(f"Added {ticker} to universe")
            return True
        except Exception as e:
            logger.error(f"Failed to add {ticker} to universe: {e}")
            return False

    def remove_stock(
        self,
        ticker: str,
        removed_date: Optional[date] = None,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Remove a stock from the universe (mark as inactive)

        This doesn't delete the stock, it marks it as removed for
        survivorship bias tracking.

        Args:
            ticker: Stock ticker symbol
            removed_date: Date removed from universe (defaults to today)
            reason: Reason for removal (delisting, acquisition, etc.)

        Returns:
            True if successfully removed
        """
        try:
            self.db.remove_from_universe(ticker, removed_date)

            # Optionally log the reason in notes
            if reason:
                # Update notes with removal reason
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE stock_universe 
                        SET notes = COALESCE(notes || ' | ', '') || ?
                        WHERE ticker = ?
                        """,
                        (f"Removed: {reason}", ticker),
                    )

            logger.info(f"Removed {ticker} from universe (reason: {reason})")
            return True
        except Exception as e:
            logger.error(f"Failed to remove {ticker} from universe: {e}")
            return False

    def get_universe(
        self,
        as_of_date: Optional[date] = None,
        market: Optional[str] = None,
        sector: Optional[str] = None,
        active_only: bool = True,
        min_market_cap: Optional[float] = None,
    ) -> List[UniverseStock]:
        """
        Get universe with filters

        Args:
            as_of_date: Get universe as of this date (prevents look-ahead bias)
            market: Filter by market (US, EU, etc.)
            sector: Filter by sector
            active_only: Only return currently active stocks
            min_market_cap: Minimum market cap filter

        Returns:
            List of UniverseStock objects
        """
        universe_dicts = self.db.get_universe(
            market=market, active_only=active_only, as_of_date=as_of_date
        )

        # Convert to UniverseStock objects
        stocks = []
        for stock_dict in universe_dicts:
            stock = UniverseStock(
                ticker=stock_dict["ticker"],
                name=stock_dict["name"],
                sector=stock_dict.get("sector"),
                industry=stock_dict.get("industry"),
                market=stock_dict.get("market", "US"),
                currency=stock_dict.get("currency", "USD"),
                is_active=bool(stock_dict.get("is_active", True)),
                added_date=stock_dict.get("added_date"),
                removed_date=stock_dict.get("removed_date"),
                market_cap=stock_dict.get("market_cap"),
                notes=stock_dict.get("notes"),
            )

            # Apply additional filters
            if sector and stock.sector != sector:
                continue

            if min_market_cap and (
                stock.market_cap is None or stock.market_cap < min_market_cap
            ):
                continue

            stocks.append(stock)

        logger.info(
            f"Retrieved {len(stocks)} stocks from universe "
            f"(as_of={as_of_date}, market={market}, sector={sector})"
        )

        return stocks

    def get_tickers(
        self,
        as_of_date: Optional[date] = None,
        market: Optional[str] = None,
        sector: Optional[str] = None,
        active_only: bool = True,
    ) -> List[str]:
        """
        Get list of ticker symbols with filters

        Args:
            as_of_date: Get universe as of this date
            market: Filter by market
            sector: Filter by sector
            active_only: Only return active stocks

        Returns:
            List of ticker symbols
        """
        stocks = self.get_universe(
            as_of_date=as_of_date, market=market, sector=sector, active_only=active_only
        )
        return [stock.ticker for stock in stocks]

    def get_stock_info(self, ticker: str) -> Optional[UniverseStock]:
        """
        Get detailed information about a specific stock

        Args:
            ticker: Stock ticker symbol

        Returns:
            UniverseStock object or None if not found
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM stock_universe WHERE ticker = ?", (ticker,))
            row = cursor.fetchone()

        if row is None:
            return None

        return UniverseStock(
            ticker=row["ticker"],
            name=row["name"],
            sector=row["sector"],
            industry=row["industry"],
            market=row["market"],
            currency=row["currency"],
            is_active=bool(row["is_active"]),
            added_date=row["added_date"],
            removed_date=row["removed_date"],
            market_cap=row["market_cap"],
            notes=row["notes"],
        )

    def is_in_universe(self, ticker: str, as_of_date: Optional[date] = None) -> bool:
        """
        Check if a stock was in the universe at a specific date

        Args:
            ticker: Stock ticker symbol
            as_of_date: Date to check (defaults to today)

        Returns:
            True if stock was in universe at that date
        """
        if as_of_date is None:
            as_of_date = date.today()

        stock = self.get_stock_info(ticker)
        if stock is None:
            return False

        # Check if stock existed at that date
        if stock.added_date and stock.added_date > as_of_date:
            return False

        if stock.removed_date and stock.removed_date <= as_of_date:
            return False

        return True

    def get_sectors(self, market: Optional[str] = None) -> List[str]:
        """
        Get list of unique sectors in universe

        Args:
            market: Filter by market

        Returns:
            List of sector names
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            query = """
                SELECT DISTINCT sector 
                FROM stock_universe 
                WHERE sector IS NOT NULL
            """
            params = []

            if market:
                query += " AND market = ?"
                params.append(market)

            query += " ORDER BY sector"

            cursor.execute(query, params)
            return [row[0] for row in cursor.fetchall()]

    def get_universe_changes(
        self, start_date: date, end_date: date, market: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """
        Get stocks that were added or removed during a period

        Args:
            start_date: Start of period
            end_date: End of period
            market: Filter by market

        Returns:
            Dictionary with 'added' and 'removed' lists
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()

            # Get additions
            query_added = """
                SELECT ticker 
                FROM stock_universe 
                WHERE added_date BETWEEN ? AND ?
            """
            params_added = [start_date, end_date]

            if market:
                query_added += " AND market = ?"
                params_added.append(market)

            cursor.execute(query_added, params_added)
            added = [row[0] for row in cursor.fetchall()]

            # Get removals
            query_removed = """
                SELECT ticker 
                FROM stock_universe 
                WHERE removed_date BETWEEN ? AND ?
            """
            params_removed = [start_date, end_date]

            if market:
                query_removed += " AND market = ?"
                params_removed.append(market)

            cursor.execute(query_removed, params_removed)
            removed = [row[0] for row in cursor.fetchall()]

        logger.info(
            f"Universe changes {start_date} to {end_date}: "
            f"{len(added)} added, {len(removed)} removed"
        )

        return {"added": added, "removed": removed}

    def get_universe_stats(self, as_of_date: Optional[date] = None) -> Dict:
        """
        Get statistics about the universe

        Args:
            as_of_date: Date for statistics (defaults to today)

        Returns:
            Dictionary with universe statistics
        """
        stocks = self.get_universe(as_of_date=as_of_date, active_only=False)

        active_stocks = [s for s in stocks if s.is_active]
        inactive_stocks = [s for s in stocks if not s.is_active]

        # Group by market
        by_market = {}
        for stock in stocks:
            market = stock.market or "Unknown"
            by_market[market] = by_market.get(market, 0) + 1

        # Group by sector
        by_sector = {}
        for stock in stocks:
            sector = stock.sector or "Unknown"
            by_sector[sector] = by_sector.get(sector, 0) + 1

        return {
            "total_stocks": len(stocks),
            "active_stocks": len(active_stocks),
            "inactive_stocks": len(inactive_stocks),
            "by_market": by_market,
            "by_sector": by_sector,
            "as_of_date": as_of_date or date.today(),
        }

    def bulk_add_stocks(
        self, stocks: List[Dict], market: str = "US", added_date: Optional[date] = None
    ) -> int:
        """
        Add multiple stocks to universe at once

        Args:
            stocks: List of stock dictionaries with at least 'ticker' and 'name'
            market: Market for all stocks
            added_date: Date added for all stocks

        Returns:
            Number of stocks successfully added
        """
        success_count = 0

        for stock_data in stocks:
            try:
                self.add_stock(
                    ticker=stock_data["ticker"],
                    name=stock_data.get("name", stock_data["ticker"]),
                    sector=stock_data.get("sector"),
                    industry=stock_data.get("industry"),
                    market=market,
                    added_date=added_date,
                    market_cap=stock_data.get("market_cap"),
                    currency=stock_data.get("currency", "USD"),
                    notes=stock_data.get("notes"),
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Failed to add {stock_data.get('ticker')}: {e}")

        logger.info(f"Bulk add: {success_count}/{len(stocks)} stocks added")
        return success_count

    def validate_universe_data_coverage(
        self, start_date: date, end_date: date, min_data_points: int = 252
    ) -> pd.DataFrame:
        """
        Validate that universe stocks have sufficient data coverage

        Args:
            start_date: Start of required period
            end_date: End of required period
            min_data_points: Minimum number of data points required

        Returns:
            DataFrame with coverage statistics per ticker
        """
        tickers = self.get_tickers(as_of_date=start_date, active_only=True)

        coverage_data = []
        for ticker in tickers:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT COUNT(*) as count, MIN(date) as min_date, MAX(date) as max_date
                    FROM raw_prices
                    WHERE ticker = ? AND date BETWEEN ? AND ?
                    """,
                    (ticker, start_date, end_date),
                )
                row = cursor.fetchone()

            count = row[0] if row else 0
            has_sufficient = count >= min_data_points

            coverage_data.append(
                {
                    "ticker": ticker,
                    "data_points": count,
                    "min_date": row[1] if row else None,
                    "max_date": row[2] if row else None,
                    "has_sufficient_data": has_sufficient,
                    "coverage_pct": (count / min_data_points * 100) if count > 0 else 0,
                }
            )

        df = pd.DataFrame(coverage_data)

        logger.info(
            f"Data coverage: {df['has_sufficient_data'].sum()}/{len(df)} stocks "
            f"have sufficient data ({min_data_points}+ points)"
        )

        return df

    def get_backtest_universe(
        self,
        backtest_start: date,
        backtest_end: date,
        market: Optional[str] = None,
        require_full_period: bool = True,
    ) -> List[str]:
        """
        Get universe suitable for backtesting without survivorship bias

        Args:
            backtest_start: Start date of backtest
            backtest_end: End date of backtest
            market: Filter by market
            require_full_period: Only include stocks with full data coverage

        Returns:
            List of ticker symbols safe for backtesting
        """
        # Get stocks that existed at backtest start
        tickers = self.get_tickers(
            as_of_date=backtest_start,
            market=market,
            active_only=False,  # Include stocks that may have been removed later
        )

        if require_full_period:
            # Validate data coverage
            coverage = self.validate_universe_data_coverage(
                backtest_start,
                backtest_end,
                min_data_points=int(
                    (backtest_end - backtest_start).days * 0.7
                ),  # 70% coverage
            )

            # Filter to stocks with sufficient data
            sufficient_tickers = coverage[coverage["has_sufficient_data"]][
                "ticker"
            ].tolist()
            tickers = [t for t in tickers if t in sufficient_tickers]

        logger.info(
            f"Backtest universe ({backtest_start} to {backtest_end}): "
            f"{len(tickers)} stocks"
        )

        return tickers

    def export_universe(
        self,
        output_path: str,
        as_of_date: Optional[date] = None,
        market: Optional[str] = None,
    ):
        """
        Export universe to CSV

        Args:
            output_path: Path to output CSV file
            as_of_date: Date for universe snapshot
            market: Filter by market
        """
        stocks = self.get_universe(
            as_of_date=as_of_date, market=market, active_only=False
        )

        data = []
        for stock in stocks:
            data.append(
                {
                    "ticker": stock.ticker,
                    "name": stock.name,
                    "sector": stock.sector,
                    "industry": stock.industry,
                    "market": stock.market,
                    "currency": stock.currency,
                    "is_active": stock.is_active,
                    "added_date": stock.added_date,
                    "removed_date": stock.removed_date,
                    "market_cap": stock.market_cap,
                    "notes": stock.notes,
                }
            )

        df = pd.DataFrame(data)
        df.to_csv(output_path, index=False)

        logger.info(f"Exported {len(df)} stocks to {output_path}")
