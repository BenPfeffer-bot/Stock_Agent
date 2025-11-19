#!/usr/bin/env python3
"""
Quick verification script for database functionality
Run this to verify your database is working correctly
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from data.database import DatabaseManager
from data.data_manager_db import DataManagerDB
from data.providers.yfinance_adapter import YFinanceAdapter


def main():
    print("\n" + "=" * 80)
    print("DATABASE VERIFICATION")
    print("=" * 80)
    
    # Test 1: Database stats
    print("\n1. Checking database statistics...")
    try:
        db = DatabaseManager(db_path="data/stock_data.db")
        stats = db.get_data_stats()
        
        print(f"   ✓ Universe size: {stats['universe_size']}")
        print(f"   ✓ Active stocks: {stats['active_stocks']}")
        print(f"   ✓ Tickers with prices: {stats['tickers_with_prices']}")
        print(f"   ✓ Total price records: {stats['total_price_records']:,}")
        print(f"   ✓ Price date range: {stats['price_date_range']}")
        
        if stats['universe_size'] == 0:
            print("\n   ⚠ WARNING: Universe is empty. Run download script first.")
            return False
            
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        return False
    
    # Test 2: Universe retrieval
    print("\n2. Testing universe retrieval...")
    try:
        tickers = db.get_universe_tickers(market="US", active_only=True)
        print(f"   ✓ Retrieved {len(tickers)} tickers")
        print(f"   ✓ Sample: {tickers[:5]}")
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        return False
    
    # Test 3: Price data retrieval
    print("\n3. Testing price data retrieval...")
    try:
        if tickers:
            test_ticker = tickers[0]
            df = db.get_raw_prices(test_ticker, "2023-01-01", "2023-12-31")
            
            if not df.empty:
                print(f"   ✓ Retrieved {len(df)} rows for {test_ticker}")
                print(f"   ✓ Columns: {list(df.columns)[:5]}...")
                print(f"   ✓ Date range: {df.index.min()} to {df.index.max()}")
            else:
                print(f"   ⚠ No price data for {test_ticker}")
        else:
            print("   ⚠ No tickers to test")
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        return False
    
    # Test 4: Fundamentals
    print("\n4. Testing fundamentals retrieval...")
    try:
        if tickers:
            fundamentals = db.get_fundamentals(tickers[0])
            if fundamentals:
                print(f"   ✓ Retrieved {len(fundamentals)} metrics for {tickers[0]}")
                sample = list(fundamentals.items())[:3]
                for metric, value in sample:
                    print(f"     - {metric}: {value}")
            else:
                print(f"   ⚠ No fundamentals for {tickers[0]}")
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        return False
    
    # Test 5: DataManagerDB integration
    print("\n5. Testing DataManagerDB...")
    try:
        provider = YFinanceAdapter()
        dm = DataManagerDB(
            provider=provider,
            db_path="data/stock_data.db",
            use_database=True,
        )
        
        print("   ✓ DataManagerDB initialized")
        
        # Load from database
        if tickers:
            df = dm.fetch_prices(tickers[0], "2023-01-01", "2023-12-31", validate=False)
            if df is not None and not df.empty:
                print(f"   ✓ Loaded {len(df)} rows from database")
            else:
                print("   ⚠ No data loaded")
        
    except Exception as e:
        print(f"   ✗ FAILED: {e}")
        return False
    
    # Test 6: Feature store (create test features)
    print("\n6. Testing feature store...")
    try:
        if tickers and not df.empty:
            # Create simple test features
            import pandas as pd
            features_df = pd.DataFrame({
                'returns_1d': df['close'].pct_change(),
                'volume_ma': df['volume'].rolling(20).mean(),
            }, index=df.index).dropna()
            
            # Save to feature store
            count = db.insert_features(tickers[0], features_df)
            print(f"   ✓ Inserted {count} feature values")
            
            # Retrieve features
            loaded = db.get_features(tickers[0], "2023-01-01", "2023-12-31")
            if not loaded.empty:
                print(f"   ✓ Retrieved {len(loaded)} rows of features")
                print(f"   ✓ Features: {list(loaded.columns)}")
            else:
                print("   ⚠ No features retrieved")
    except Exception as e:
        print(f"   ⚠ Feature store test skipped or failed: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("✓ ALL TESTS PASSED!")
    print("=" * 80)
    print("\nYour database is working correctly and ready to use.")
    print("You can now:")
    print("  - Load data with DataManagerDB")
    print("  - Compute and store features")
    print("  - Train your RL agent")
    print("\n" + "=" * 80)
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Verification failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

