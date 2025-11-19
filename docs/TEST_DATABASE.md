# Database Verification Guide

## Quick Check: Database Exists and Has Data

Based on your terminal output, the database was successfully created with:
- ✅ 98 stocks in universe
- ✅ 96 fundamentals downloaded
- ✅ Average quality score: 0.998 (Excellent!)

However, I notice:
- ⚠️ 0 price records in database

This means fundamentals were downloaded but prices weren't. Let me help you verify and fix this.

## Method 1: Check Database with SQLite Command Line

```bash
# Open database
sqlite3 data/stock_data.db

# Check tables
.tables

# Check universe
SELECT COUNT(*) as universe_size FROM stock_universe;
SELECT ticker, name, sector FROM stock_universe LIMIT 5;

# Check price data
SELECT COUNT(*) as price_records FROM raw_prices;
SELECT ticker, date, close, volume FROM raw_prices LIMIT 5;

# Check fundamentals
SELECT COUNT(*) as fundamental_records FROM fundamentals;
SELECT ticker, metric_name, metric_value FROM fundamentals LIMIT 5;

# Exit
.quit
```

## Method 2: Run Verification Script

```bash
python scripts/verify_database.py
```

This will test:
1. Database initialization
2. Universe retrieval
3. Price data retrieval
4. Fundamentals
5. DataManagerDB integration
6. Feature store operations

## Method 3: Python Quick Check

```python
from data.database import DatabaseManager

# Initialize
db = DatabaseManager("data/stock_data.db")

# Get stats
stats = db.get_data_stats()
print(f"Universe: {stats['universe_size']} stocks")
print(f"Price records: {stats['total_price_records']:,}")
print(f"Date range: {stats['price_date_range']}")

# Check universe
tickers = db.get_universe_tickers(market="US", active_only=True)
print(f"Tickers: {tickers[:10]}")

# Check prices for a ticker
df = db.get_raw_prices("AAPL", "2023-01-01", "2023-12-31")
print(f"AAPL data: {len(df)} rows")
```

## Issue: No Price Data in Database

From your terminal output, I see prices were fetched and validated (10 tickers with excellent quality), but the database shows 0 price records. This suggests the prices were validated but not saved to the database.

### Solution: Re-run with Price Download

The `--skip-prices` flag might have been used, or there was an issue saving to DB. Let's re-run:

```bash
# Download prices for the universe
python scripts/download_sp100.py \
    --start-date 2018-01-01 \
    --end-date 2024-12-31 \
    --batch-size 10
```

This should:
1. Keep existing universe (98 stocks) ✅
2. Keep existing fundamentals (96 stocks) ✅
3. Download and save prices to database ⬅️ This will happen

## Expected Results After Fix

After running the download script with prices, you should see:

```
Universe size: 98
Active stocks: 98
Tickers with prices: 98 (or close to it)
Total price records: ~170,000+ (98 tickers × 7 years × 252 days)
Price date range: (2018-01-01, 2024-12-31)
Quality issues logged: 0 (if data is clean)
```

## Testing Individual Components

### Test 1: Database Tables

```python
from data.database import DatabaseManager

db = DatabaseManager("data/stock_data.db")

# Check tables exist
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    print("Tables:", tables)
```

Expected output:
```
Tables: ['raw_prices', 'stock_universe', 'data_quality_log', 
         'features', 'feature_metadata', 'fundamentals']
```

### Test 2: Universe Management

```python
from data.database import DatabaseManager

db = DatabaseManager("data/stock_data.db")

# Get universe
universe = db.get_universe(market="US", active_only=True)
print(f"Universe size: {len(universe)}")

# Show sample
for stock in universe[:3]:
    print(f"{stock['ticker']}: {stock['name']} ({stock['sector']})")
```

### Test 3: Price Data Operations

```python
from data.database import DatabaseManager

db = DatabaseManager("data/stock_data.db")

# Check if we have price data
with db.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM raw_prices")
    count = cursor.fetchone()[0]
    print(f"Total price records: {count:,}")
    
    if count > 0:
        # Get sample
        cursor.execute("""
            SELECT ticker, date, close, volume 
            FROM raw_prices 
            ORDER BY date DESC 
            LIMIT 5
        """)
        for row in cursor.fetchall():
            print(f"{row[0]}: {row[1]} close={row[2]:.2f} vol={row[3]:,.0f}")
```

### Test 4: Feature Store

```python
from data.database import DatabaseManager
import pandas as pd

db = DatabaseManager("data/stock_data.db")

# Register a feature
db.register_feature(
    "test_feature",
    "Test feature description",
    "technical"
)

# Create dummy feature data
test_data = pd.DataFrame({
    'date': pd.date_range('2023-01-01', periods=10),
    'test_feature': range(10)
}).set_index('date')

# Insert
count = db.insert_features("TEST", test_data)
print(f"Inserted {count} feature values")

# Retrieve
features = db.get_features("TEST", "2023-01-01", "2023-01-10")
print(features)
```

### Test 5: DataManagerDB

```python
from data.data_manager_db import DataManagerDB
from data.providers.yfinance_adapter import YFinanceAdapter

# Initialize
provider = YFinanceAdapter()
dm = DataManagerDB(
    provider=provider,
    db_path="data/stock_data.db",
    use_database=True,
)

# Load universe
tickers = dm.load_universe(market="US", active_only=True)
print(f"Loaded {len(tickers)} tickers from universe")

# Fetch data (will load from DB if available)
df = dm.fetch_prices("AAPL", "2023-01-01", "2023-12-31")
if df is not None:
    print(f"Loaded AAPL: {len(df)} rows")
    print(df.head())
else:
    print("No data - need to download prices")

# Get database stats
stats = dm.get_database_stats()
for key, value in stats.items():
    print(f"{key}: {value}")
```

## Troubleshooting

### Problem: "No such table: raw_prices"

**Solution:** Database schema not initialized

```python
from data.database import DatabaseManager
db = DatabaseManager("data/stock_data.db")  # This will create tables
```

### Problem: "Database is locked"

**Solution:** Close other connections

```python
# Make sure to close connections
with db.get_connection() as conn:
    # do work
    pass  # Connection closes automatically
```

### Problem: "No price data in database"

**Solution:** Run download script without `--skip-prices`

```bash
python scripts/download_sp100.py
```

### Problem: "ModuleNotFoundError"

**Solution:** Install dependencies

```bash
pip install -r requirements.txt
```

## Success Indicators

Your database is working correctly when:

✅ All 6 tables exist
✅ Universe has 90+ stocks
✅ Price records > 100,000 (for S&P 100 over 5 years)
✅ Can retrieve data for any ticker in universe
✅ Feature store accepts and returns features
✅ DataManagerDB loads data from database

## Next Steps After Verification

Once database is verified:

1. **Compute Features**: Use feature engineering modules
2. **Train Agent**: Load features for RL training
3. **Backtest**: Use historical universe to avoid survivorship bias
4. **Monitor Quality**: Check quality logs regularly

## Files to Check

- `data/stock_data.db` - Main database (should be ~50MB+ with data)
- `data_cache/` - File-based cache (optional)
- `outputs/results/validation_report.csv` - Quality validation results

## Quick Diagnosis Commands

```bash
# Check database file size
ls -lh data/stock_data.db

# Count records in each table
sqlite3 data/stock_data.db "SELECT 'raw_prices', COUNT(*) FROM raw_prices; \
SELECT 'stock_universe', COUNT(*) FROM stock_universe; \
SELECT 'fundamentals', COUNT(*) FROM fundamentals; \
SELECT 'features', COUNT(*) FROM features;"

# Show most recent price data
sqlite3 data/stock_data.db "SELECT ticker, date, close FROM raw_prices ORDER BY date DESC LIMIT 5;"
```

## Help

If issues persist:
1. Check `data/database.py` - Database implementation
2. Check `data/data_manager_db.py` - Manager integration
3. Check `scripts/download_sp100.py` - Download script
4. Review terminal output for specific errors

