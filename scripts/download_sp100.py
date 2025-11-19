#!/usr/bin/env python3
"""
Download historical data for S&P 100 stocks

This script:
1. Loads S&P 100 constituents
2. Fetches historical price data
3. Validates data quality
4. Stores in database (data lake)
5. Populates stock universe
"""

import sys
from pathlib import Path
import logging
from datetime import date
import argparse

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.data_manager_db import DataManagerDB
from data.providers.yfinance_adapter import YFinanceAdapter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# S&P 100 constituents (as of 2024)
# Source: https://en.wikipedia.org/wiki/S%26P_100
SP100_TICKERS = [
    # Technology
    "AAPL", "MSFT", "GOOGL", "META", "NVDA", "AVGO", "ORCL", "CSCO", "ADBE", "CRM",
    "INTC", "AMD", "TXN", "QCOM", "INTU", "IBM", "NOW",
    # Healthcare
    "UNH", "JNJ", "LLY", "ABBV", "MRK", "TMO", "ABT", "DHR", "AMGN", "PFE",
    "BMY", "GILD", "VRTX", "CVS", "CI", "HUM", "ISRG",
    # Financials
    "BRK.B", "JPM", "V", "MA", "BAC", "WFC", "MS", "GS", "SPGI", "BLK",
    "C", "AXP", "SCHW", "USB", "PNC", "COF",
    # Consumer Discretionary
    "AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "LOW", "TGT", "TJX",
    # Consumer Staples
    "PG", "KO", "PEP", "COST", "WMT", "PM", "MO", "CL", "MDLZ",
    # Energy
    "XOM", "CVX", "COP", "SLB", "EOG", "PXD",
    # Industrials
    "BA", "HON", "UPS", "RTX", "LMT", "CAT", "GE", "MMM", "DE", "UNP",
    # Communication Services
    "NFLX", "DIS", "CMCSA", "T", "VZ", "TMUS",
    # Utilities
    "NEE", "DUK", "SO",
    # Real Estate
    "AMT", "PLD",
    # Materials
    "LIN", "APD", "SHW",
]


# Company names and sectors (subset for metadata)
COMPANY_METADATA = {
    "AAPL": {"name": "Apple Inc.", "sector": "Technology", "industry": "Consumer Electronics"},
    "MSFT": {"name": "Microsoft Corporation", "sector": "Technology", "industry": "Software"},
    "GOOGL": {"name": "Alphabet Inc.", "sector": "Technology", "industry": "Internet Content"},
    "AMZN": {"name": "Amazon.com Inc.", "sector": "Consumer Discretionary", "industry": "E-commerce"},
    "TSLA": {"name": "Tesla Inc.", "sector": "Consumer Discretionary", "industry": "Automotive"},
    "META": {"name": "Meta Platforms Inc.", "sector": "Technology", "industry": "Social Media"},
    "NVDA": {"name": "NVIDIA Corporation", "sector": "Technology", "industry": "Semiconductors"},
    "BRK.B": {"name": "Berkshire Hathaway", "sector": "Financials", "industry": "Conglomerate"},
    "JPM": {"name": "JPMorgan Chase & Co.", "sector": "Financials", "industry": "Banking"},
    "JNJ": {"name": "Johnson & Johnson", "sector": "Healthcare", "industry": "Pharmaceuticals"},
    "V": {"name": "Visa Inc.", "sector": "Financials", "industry": "Payments"},
    "PG": {"name": "Procter & Gamble", "sector": "Consumer Staples", "industry": "Household Products"},
    "MA": {"name": "Mastercard Inc.", "sector": "Financials", "industry": "Payments"},
    "UNH": {"name": "UnitedHealth Group", "sector": "Healthcare", "industry": "Health Insurance"},
    "HD": {"name": "Home Depot", "sector": "Consumer Discretionary", "industry": "Home Improvement"},
    # Add more as needed...
}


def populate_universe(dm: DataManagerDB, tickers: list, market: str = "US"):
    """
    Populate stock universe in database
    
    Args:
        dm: DataManagerDB instance
        tickers: List of tickers to add
        market: Market identifier
    """
    logger.info(f"Populating universe with {len(tickers)} stocks")
    
    for ticker in tickers:
        metadata = COMPANY_METADATA.get(ticker, {})
        
        dm.add_to_universe(
            ticker=ticker,
            name=metadata.get("name", ticker),
            sector=metadata.get("sector"),
            industry=metadata.get("industry"),
            market=market,
            added_date=date(2018, 1, 1),  # Assuming all in universe since 2018
            is_active=True,
        )
    
    logger.info("Universe populated")


def download_historical_data(
    dm: DataManagerDB,
    tickers: list,
    start_date: str,
    end_date: str,
    batch_size: int = 10,
):
    """
    Download historical data for tickers
    
    Args:
        dm: DataManagerDB instance
        tickers: List of tickers
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        batch_size: Number of tickers to fetch at once
    """
    logger.info(
        f"Downloading historical data for {len(tickers)} tickers "
        f"from {start_date} to {end_date}"
    )
    
    total_fetched = 0
    total_failed = 0
    
    # Process in batches
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = (len(tickers) + batch_size - 1) // batch_size
        
        logger.info(f"Processing batch {batch_num}/{total_batches}: {batch}")
        
        try:
            data_dict = dm.fetch_prices_bulk(
                tickers=batch,
                start_date=start_date,
                end_date=end_date,
                validate=True,
                force_refresh=False,  # Use cached/DB data if available
                fail_on_error=False,
                save_to_db=True,
            )
            
            total_fetched += len(data_dict)
            failed_in_batch = len(batch) - len(data_dict)
            total_failed += failed_in_batch
            
            logger.info(
                f"Batch {batch_num}: {len(data_dict)} successful, "
                f"{failed_in_batch} failed"
            )
            
        except Exception as e:
            logger.error(f"Error processing batch {batch_num}: {e}")
            total_failed += len(batch)
    
    logger.info(
        f"Download complete: {total_fetched} successful, {total_failed} failed"
    )
    
    return total_fetched, total_failed


def fetch_fundamentals(dm: DataManagerDB, tickers: list):
    """
    Fetch and store fundamental data for tickers
    
    Args:
        dm: DataManagerDB instance
        tickers: List of tickers
    """
    logger.info(f"Fetching fundamentals for {len(tickers)} tickers")
    
    successful = 0
    failed = 0
    
    for ticker in tickers:
        try:
            # Fetch from provider
            fundamentals = dm.fetch_fundamentals(ticker, validate=False)
            
            if fundamentals:
                # Save to database
                count = dm.save_fundamentals(
                    ticker=ticker,
                    fundamentals=fundamentals,
                    metric_date=date.today(),
                )
                successful += 1
                logger.info(f"Saved {count} fundamental metrics for {ticker}")
            else:
                failed += 1
                logger.warning(f"No fundamentals for {ticker}")
        
        except Exception as e:
            failed += 1
            logger.error(f"Error fetching fundamentals for {ticker}: {e}")
    
    logger.info(
        f"Fundamentals fetch complete: {successful} successful, {failed} failed"
    )


def print_summary(dm: DataManagerDB):
    """Print summary of data in database"""
    logger.info("=" * 80)
    logger.info("DATABASE SUMMARY")
    logger.info("=" * 80)
    
    stats = dm.get_database_stats()
    
    logger.info(f"Universe size: {stats.get('universe_size', 0)}")
    logger.info(f"Active stocks: {stats.get('active_stocks', 0)}")
    logger.info(f"Tickers with price data: {stats.get('tickers_with_prices', 0)}")
    logger.info(f"Total price records: {stats.get('total_price_records', 0):,}")
    logger.info(f"Price date range: {stats.get('price_date_range')}")
    logger.info(f"Quality issues logged: {stats.get('quality_issues_logged', 0)}")
    
    # Validation summary
    if dm.validation_results:
        logger.info("\nVALIDATION SUMMARY:")
        summary = dm.get_validation_summary()
        logger.info(f"\n{summary.to_string(index=False)}")
        
        # Quality report
        quality_report = dm.get_quality_report()
        logger.info(f"\nAverage Quality Score: {quality_report['avg_quality_score']:.3f}")
        logger.info("Quality Distribution:")
        for level, count in quality_report["quality_distribution"].items():
            logger.info(f"  {level.capitalize()}: {count}")
    
    logger.info("=" * 80)


def main():
    """Main execution"""
    parser = argparse.ArgumentParser(
        description="Download S&P 100 historical data"
    )
    parser.add_argument(
        "--start-date",
        default="2018-01-01",
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end-date",
        default="2024-12-31",
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--db-path",
        default="data/stock_data.db",
        help="Database path",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Batch size for downloading",
    )
    parser.add_argument(
        "--skip-prices",
        action="store_true",
        help="Skip downloading prices",
    )
    parser.add_argument(
        "--skip-fundamentals",
        action="store_true",
        help="Skip downloading fundamentals",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        help="Specific tickers to download (overrides S&P 100)",
    )
    
    args = parser.parse_args()
    
    # Initialize data manager
    logger.info("Initializing data manager...")
    provider = YFinanceAdapter()
    dm = DataManagerDB(
        provider=provider,
        db_path=args.db_path,
        enable_cache=True,
        use_database=True,
    )
    
    # Determine tickers
    tickers = args.tickers if args.tickers else SP100_TICKERS
    logger.info(f"Processing {len(tickers)} tickers")
    
    # Populate universe
    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: Populating Universe")
    logger.info("=" * 80)
    populate_universe(dm, tickers)
    
    # Download prices
    if not args.skip_prices:
        logger.info("\n" + "=" * 80)
        logger.info("STEP 2: Downloading Historical Prices")
        logger.info("=" * 80)
        download_historical_data(
            dm=dm,
            tickers=tickers,
            start_date=args.start_date,
            end_date=args.end_date,
            batch_size=args.batch_size,
        )
    
    # Download fundamentals
    if not args.skip_fundamentals:
        logger.info("\n" + "=" * 80)
        logger.info("STEP 3: Fetching Fundamentals")
        logger.info("=" * 80)
        fetch_fundamentals(dm, tickers)
    
    # Print summary
    logger.info("\n")
    print_summary(dm)
    
    logger.info("\n✓ Data download complete!")
    logger.info(f"Database location: {args.db_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

