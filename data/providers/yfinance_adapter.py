# data/providers/yfinance_adapter.py
import yfinance as yf
import pandas as pd
from typing import List
import logging

from .base_provider import BaseDataProvider

logger = logging.getLogger(__name__)


class YFinanceAdapter(BaseDataProvider):
    """YFinance data provider implementation"""

    def __init__(self, session=None):
        """
        Initialize YFinance adapter

        Args:
            session: Optional requests session for connection pooling
        """
        self.session = session

    def fetch_prices(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch OHLCV data from YFinance

        Args:
            ticker: Stock ticker symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV data indexed by date
        """
        try:
            logger.debug(f"Fetching {ticker} from {start_date} to {end_date}")

            # Create ticker object
            ticker_obj = yf.Ticker(ticker, session=self.session)

            # Download data
            df = ticker_obj.history(
                start=start_date,
                end=end_date,
                auto_adjust=False,  # Keep unadjusted prices
                actions=True,  # Include dividends and splits
            )

            if df.empty:
                logger.warning(f"No data returned for {ticker}")
                return pd.DataFrame()

            # Standardize column names
            df = df.rename(
                columns={
                    "Open": "Open",
                    "High": "High",
                    "Low": "Low",
                    "Close": "Close",
                    "Volume": "Volume",
                    "Dividends": "Dividends",
                    "Stock Splits": "Splits",
                }
            )

            # Keep only OHLCV columns (and optional corporate actions)
            columns_to_keep = ["Open", "High", "Low", "Close", "Volume"]

            # Add Adj Close if available
            if "Adj Close" in df.columns:
                columns_to_keep.append("Adj Close")

            # Add corporate actions if available
            if "Dividends" in df.columns:
                columns_to_keep.append("Dividends")
            if "Splits" in df.columns:
                columns_to_keep.append("Splits")

            df = df[columns_to_keep]

            # Ensure timezone-naive datetime index
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)

            logger.debug(f"Fetched {len(df)} rows for {ticker}")

            return df

        except Exception as e:
            logger.error(f"Error fetching {ticker}: {str(e)}")
            return pd.DataFrame()

    def fetch_fundamentals(self, ticker: str) -> dict:
        """
        Fetch fundamental data from YFinance

        Args:
            ticker: Stock ticker symbol

        Returns:
            Dictionary with fundamental data
        """
        try:
            ticker_obj = yf.Ticker(ticker, session=self.session)
            info = ticker_obj.info

            if not info:
                logger.warning(f"No fundamental data for {ticker}")
                return {}

            # Extract relevant fundamental data
            fundamentals = {
                # Valuation metrics
                "marketCap": info.get("marketCap"),
                "enterpriseValue": info.get("enterpriseValue"),
                "peRatio": info.get("trailingPE"),
                "forwardPE": info.get("forwardPE"),
                "pbRatio": info.get("priceToBook"),
                "psRatio": info.get("priceToSalesTrailing12Months"),
                "pegRatio": info.get("pegRatio"),
                # Profitability
                "profitMargin": info.get("profitMargins"),
                "operatingMargin": info.get("operatingMargins"),
                "grossMargin": info.get("grossMargins"),
                "roe": info.get("returnOnEquity"),
                "roa": info.get("returnOnAssets"),
                # Financial health
                "debtToEquity": info.get("debtToEquity"),
                "currentRatio": info.get("currentRatio"),
                "quickRatio": info.get("quickRatio"),
                # Income statement
                "revenue": info.get("totalRevenue"),
                "revenueGrowth": info.get("revenueGrowth"),
                "earningsGrowth": info.get("earningsGrowth"),
                "eps": info.get("trailingEps"),
                "forwardEps": info.get("forwardEps"),
                # Dividends
                "dividendYield": info.get("dividendYield"),
                "dividendRate": info.get("dividendRate"),
                "payoutRatio": info.get("payoutRatio"),
                # Other
                "beta": info.get("beta"),
                "sharesOutstanding": info.get("sharesOutstanding"),
                "floatShares": info.get("floatShares"),
                "sector": info.get("sector"),
                "industry": info.get("industry"),
            }

            # Remove None values
            fundamentals = {k: v for k, v in fundamentals.items() if v is not None}

            logger.debug(
                f"Fetched {len(fundamentals)} fundamental metrics for {ticker}"
            )

            return fundamentals

        except Exception as e:
            logger.error(f"Error fetching fundamentals for {ticker}: {str(e)}")
            return {}

    def get_available_tickers(self, market: str) -> List[str]:
        """
        Get list of available tickers for a market

        Note: YFinance doesn't provide a direct way to get all tickers.
        This method returns common index constituents.

        Args:
            market: Market identifier (e.g., 'US', 'EU')

        Returns:
            List of ticker symbols
        """
        # This is a simplified implementation
        # In practice, you'd want to maintain or fetch actual index constituents

        if market == "US":
            # Common S&P 100 stocks (partial list for demonstration)
            return [
                "AAPL",
                "MSFT",
                "GOOGL",
                "AMZN",
                "TSLA",
                "META",
                "NVDA",
                "BRK.B",
                "JPM",
                "JNJ",
                "V",
                "PG",
                "MA",
                "UNH",
                "HD",
                "DIS",
                "PYPL",
                "NFLX",
                "ADBE",
                "CRM",
            ]
        elif market == "EU":
            # Common European stocks
            return [
                "ASML.AS",
                "MC.PA",
                "RMS.PA",
                "OR.PA",
                "SAP.DE",
                "SAN.PA",
                "AIR.PA",
                "SU.PA",
                "TTE.PA",
                "BNP.PA",
            ]
        else:
            logger.warning(f"Unknown market: {market}")
            return []

    def fetch_prices_bulk(
        self,
        tickers: List[str],
        start_date: str,
        end_date: str,
        group_by: str = "ticker",
    ) -> dict:
        """
        Fetch data for multiple tickers efficiently using yfinance download

        Args:
            tickers: List of ticker symbols
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            group_by: How to group results ('ticker' or 'column')

        Returns:
            Dictionary mapping ticker -> DataFrame
        """
        try:
            logger.info(f"Bulk fetching {len(tickers)} tickers")

            # Use yfinance download for efficiency
            data = yf.download(
                tickers=tickers,
                start=start_date,
                end=end_date,
                group_by=group_by,
                auto_adjust=False,
                threads=True,
            )

            if data.empty:
                logger.warning("No data returned from bulk fetch")
                return {}

            # Parse results
            results = {}

            if len(tickers) == 1:
                # Single ticker returns different format
                results[tickers[0]] = data
            else:
                # Multiple tickers
                for ticker in tickers:
                    try:
                        ticker_data = data[ticker]
                        if not ticker_data.empty:
                            results[ticker] = ticker_data
                    except KeyError:
                        logger.warning(f"No data for {ticker} in bulk fetch")

            logger.info(f"Bulk fetch returned data for {len(results)} tickers")

            return results

        except Exception as e:
            logger.error(f"Error in bulk fetch: {str(e)}")
            return {}
