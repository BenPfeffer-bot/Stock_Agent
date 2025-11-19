# Quick Start: Data Management

## Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

## Step 2: Download S&P 100 Historical Data

### Option A: Full S&P 100 (Recommended)

```bash
python scripts/download_sp100.py \
    --start-date 2018-01-01 \
    --end-date 2024-12-31 \
    --batch-size 10
```

This will:
1. Create SQLite database at `data/stock_data.db`
2. Download ~100 tickers from S&P 100
3. Validate data quality
4. Store in data lake
5. Populate stock universe
6. Fetch fundamental data

**Estimated time:** 15-30 minutes (depending on network speed)

### Option B: Quick Test (5 tickers)

```bash
python scripts/download_sp100.py \
    --start-date 2023-01-01 \
    --end-date 2024-12-31 \
    --tickers AAPL MSFT GOOGL AMZN TSLA
```

**Estimated time:** 1-2 minutes

### Option C: Prices Only (Skip Fundamentals)

```bash
python scripts/download_sp100.py \
    --start-date 2018-01-01 \
    --end-date 2024-12-31 \
    --skip-fundamentals
```

## Step 3: Verify Data

```python
from data.data_manager_db import DataManagerDB
from data.providers.yfinance_adapter import YFinanceAdapter

# Initialize
provider = YFinanceAdapter()
dm = DataManagerDB(provider=provider, db_path="data/stock_data.db")

# Check stats
stats = dm.get_database_stats()
print(f"Tickers with data: {stats['tickers_with_prices']}")
print(f"Total records: {stats['total_price_records']:,}")
print(f"Date range: {stats['price_date_range']}")

# Load universe
tickers = dm.load_universe(market="US", active_only=True)
print(f"Universe size: {len(tickers)}")

# Test loading data
df = dm.fetch_prices("AAPL", "2023-01-01", "2023-12-31")
print(f"AAPL data: {len(df)} rows")
print(df.head())
```

## Step 4: Usage Examples

### Load Data for Training

```python
# Load data for multiple tickers
tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
data_dict = dm.fetch_prices_bulk(
    tickers=tickers,
    start_date="2020-01-01",
    end_date="2024-12-31",
    validate=True,
)

# Create panel data for RL environment
panel = dm.create_panel_data(data_dict, align_method="inner")
print(f"Panel shape: {panel.shape}")
```

### Compute and Store Features

```python
from features.technical import TechnicalFeatures

# Compute technical features
tech = TechnicalFeatures()
features_df = tech.compute(data_dict["AAPL"])

# Save to feature store
dm.save_features(
    ticker="AAPL",
    features_df=features_df,
)

# Load features later
features = dm.load_features(
    ticker="AAPL",
    start_date="2023-01-01",
    end_date="2023-12-31",
)
```

### Check Data Quality

```python
# Get validation summary
summary = dm.get_validation_summary()
print(summary)

# Get quality report
report = dm.get_quality_report()
print(f"Average quality score: {report['avg_quality_score']:.2f}")

# Check for issues
issues = dm.get_quality_issues(min_severity=2)
if not issues.empty:
    print("Quality issues found:")
    print(issues)
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'yfinance'"

```bash
pip install yfinance
```

### Issue: "Database is locked"

SQLite issue with concurrent access. Wait and retry, or:

```python
# Close any open connections
dm.db.get_connection().close()
```

### Issue: "No data returned for ticker"

Some reasons:
- Ticker delisted/invalid
- Network issues
- yfinance API rate limiting

Check logs for specific error. Failed tickers are tracked:

```python
print(f"Failed tickers: {dm.failed_tickers}")
```

### Issue: Download is slow

Options to speed up:
1. Increase batch size: `--batch-size 20`
2. Use smaller date range
3. Check network connection
4. yfinance may rate limit - add delays if needed

### Issue: Want to re-download specific ticker

```python
# Force refresh from provider
df = dm.fetch_prices(
    ticker="AAPL",
    start_date="2023-01-01",
    end_date="2024-12-31",
    force_refresh=True,  # Ignore cache and database
    save_to_db=True,      # Update database
)
```

## Next Steps

1. **Compute Features**: See `features/` directory
2. **Setup Environment**: See `environment/trading_env.py`
3. **Train Agent**: See `training/trainer.py`
4. **Backtest**: See `evaluation/backtester.py`

## Database Location

Default: `data/stock_data.db`

To use a different location:

```python
dm = DataManagerDB(
    provider=provider,
    db_path="/path/to/your/database.db",
)
```

## Data Structure

```
data/
├── stock_data.db          # Main SQLite database
│   ├── raw_prices         # Layer 1: Data Lake
│   ├── fundamentals       # Layer 1: Data Lake
│   ├── stock_universe     # Universe tracking
│   ├── data_quality_log   # Quality issues
│   └── features           # Layer 2: Feature Store
└── data_cache/            # File-based cache (optional)
```

## Command Reference

```bash
# Download full S&P 100
python scripts/download_sp100.py

# Specify date range
python scripts/download_sp100.py --start-date 2020-01-01 --end-date 2024-12-31

# Specific tickers only
python scripts/download_sp100.py --tickers AAPL MSFT GOOGL

# Skip fundamentals (faster)
python scripts/download_sp100.py --skip-fundamentals

# Skip prices (only fundamentals)
python scripts/download_sp100.py --skip-prices

# Custom database location
python scripts/download_sp100.py --db-path /path/to/db.db

# Larger batch size (faster but more memory)
python scripts/download_sp100.py --batch-size 20

# Help
python scripts/download_sp100.py --help
```

## Storage Requirements

| Scenario | Storage Needed |
|----------|----------------|
| 5 tickers, 1 year | ~1 MB |
| 10 tickers, 5 years | ~5 MB |
| S&P 100, 5 years | ~50 MB |
| S&P 100 + features | ~250 MB |
| S&P 500, 10 years | ~500 MB |

SQLite performs well up to several GB.

## Performance Tips

1. **Use database layer** - Much faster than re-fetching
2. **Enable caching** - Reduces redundant database queries  
3. **Compute features once** - Store in feature store
4. **Batch operations** - Use `fetch_prices_bulk` for multiple tickers
5. **Index optimization** - Database has pre-built indices

## Data Quality Guarantees

All data passing validation has:
- ✅ < 5% missing values
- ✅ < 2% zero volume days
- ✅ Consistent OHLC relationships
- ✅ No duplicate timestamps
- ✅ Chronological order
- ✅ Quality score ≥ 0.7

Failed tickers are tracked and can be retried or excluded.

## Getting Help

See full documentation:
- `DATA_ARCHITECTURE.md` - Two-layer design details
- `README_DATA_MANAGER.md` - Data manager usage (if exists)
- `IMPLEMENTATION_SUMMARY.md` - Complete feature list

Or check the code:
- `data/data_manager_db.py` - Main data manager
- `data/database.py` - Database operations
- `data/validators.py` - Quality validation

