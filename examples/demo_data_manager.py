#!/usr/bin/env python3
"""
Demonstration script for DataManager with quality checks

This script shows how to:
1. Initialize the DataManager with a data provider
2. Fetch and validate data for multiple tickers
3. Generate quality reports
4. Handle failed validations
5. Work with cached data
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.data_manager import DataManager
from data.providers.yfinance_adapter import YFinanceAdapter
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Demonstrate DataManager capabilities"""

    print("=" * 80)
    print("DataManager with Quality Checks - Demonstration")
    print("=" * 80)

    # Initialize provider and data manager
    print("\n1. Initializing DataManager...")
    provider = YFinanceAdapter()
    data_manager = DataManager(
        provider=provider,
        cache_dir="data_cache",
        config_path="config/data_config.yaml",
        enable_cache=True,
        cache_expiry_days=1,
    )

    # Define test tickers
    tickers = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]
    start_date = "2023-01-01"
    end_date = "2024-01-01"

    # Fetch data with validation
    print(f"\n2. Fetching and validating data for {len(tickers)} tickers...")
    print(f"   Date range: {start_date} to {end_date}")

    data_dict = data_manager.fetch_prices_bulk(
        tickers=tickers,
        start_date=start_date,
        end_date=end_date,
        validate=True,
        force_refresh=False,
    )

    # Display results
    print(f"\n3. Fetch Results:")
    print(f"   Successfully fetched: {len(data_dict)} tickers")
    print(f"   Failed: {len(data_manager.failed_tickers)} tickers")

    if data_manager.failed_tickers:
        print(f"   Failed tickers: {data_manager.failed_tickers}")

    # Display validation summary
    print("\n4. Validation Summary:")
    summary_df = data_manager.get_validation_summary()
    if not summary_df.empty:
        print("\n" + summary_df.to_string(index=False))

    # Generate quality report
    print("\n5. Quality Report:")
    quality_report = data_manager.get_quality_report()
    print(f"   Total tickers validated: {quality_report['total_tickers']}")
    print(f"   Valid tickers: {quality_report['valid_tickers']}")
    print(f"   Failed tickers: {quality_report['failed_tickers']}")
    print(f"   Average quality score: {quality_report['avg_quality_score']:.3f}")
    print(f"   Cached tickers: {quality_report['cached_tickers']}")

    print("\n   Quality Distribution:")
    for level, count in quality_report["quality_distribution"].items():
        print(f"     {level.capitalize()}: {count}")

    # Show data coverage
    if data_dict:
        print("\n6. Data Coverage Analysis:")
        coverage_df = data_manager.get_data_coverage(data_dict)
        print("\n" + coverage_df.to_string(index=False))

    # Demonstrate data alignment
    if len(data_dict) > 1:
        print("\n7. Data Alignment:")
        aligned_data = data_manager.align_data(data_dict, method="inner")
        print(f"   Aligned {len(aligned_data)} tickers")

        # Show common date range
        if aligned_data:
            sample_ticker = list(aligned_data.keys())[0]
            sample_df = aligned_data[sample_ticker]
            print(
                f"   Common date range: {sample_df.index.min()} to {sample_df.index.max()}"
            )
            print(f"   Common trading days: {len(sample_df)}")

    # Create panel data
    if len(data_dict) > 1:
        print("\n8. Creating Panel Data:")
        panel_df = data_manager.create_panel_data(data_dict, align_method="inner")
        print(f"   Panel shape: {panel_df.shape}")
        print(f"   Panel index levels: {panel_df.index.names}")
        print(f"\n   Sample (first 5 rows):")
        print(panel_df.head().to_string())

    # Export validation report
    print("\n9. Exporting validation report...")
    output_path = "outputs/results/validation_report.csv"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    data_manager.export_validation_report(output_path)
    print(f"   Report saved to: {output_path}")

    # Show individual validation details
    print("\n10. Detailed Validation Results:")
    for ticker, result in data_manager.validation_results.items():
        print(f"\n   {ticker}:")
        print(f"     Valid: {result.is_valid}")
        print(f"     Quality Score: {result.quality_score:.3f}")
        print(f"     Row Count: {result.metadata.get('row_count', 0)}")
        print(f"     Missing %: {result.metadata.get('missing_pct', 0):.2%}")

        if result.issues:
            print(f"     Issues: {result.issues}")

        if result.warnings:
            print(f"     Warnings: {result.warnings}")

        # Show component scores
        component_scores = result.metadata.get("component_scores", {})
        if component_scores:
            print(f"     Component Scores:")
            for component, score in component_scores.items():
                print(f"       {component}: {score:.3f}")

    print("\n" + "=" * 80)
    print("Demonstration complete!")
    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error(f"Error in demonstration: {str(e)}", exc_info=True)
        sys.exit(1)
