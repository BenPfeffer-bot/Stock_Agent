# Data Architecture: Two-Layer Design

## Overview

The Stock Agent uses a **two-layer data architecture** that separates raw data storage from processed features. This design provides:

- **Flexibility**: Switch data providers without affecting downstream systems
- **Reproducibility**: Immutable raw data ensures reproducible experiments
- **Performance**: Feature store eliminates redundant computation
- **Survivorship Bias Handling**: Track universe changes over time
- **Quality Assurance**: Comprehensive logging and validation

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    TWO-LAYER ARCHITECTURE                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: DATA LAKE (Raw, Immutable, Versioned)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │              │  │              │  │              │         │
│  │  raw_prices  │  │ fundamentals │  │  universe    │         │
│  │              │  │              │  │              │         │
│  │ • OHLCV data │  │ • P/E ratios │  │ • Tickers    │         │
│  │ • Provider   │  │ • Margins    │  │ • Sectors    │         │
│  │ • Timestamp  │  │ • Metrics    │  │ • Active?    │         │
│  │ • Quality ✓  │  │ • Provider   │  │ • Dates      │         │
│  │              │  │              │  │              │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│                                                                  │
│  ┌──────────────────────────────────────────────────┐          │
│  │         data_quality_log                         │          │
│  │  • Issue tracking                                │          │
│  │  • Severity levels                               │          │
│  │  • Audit trail                                   │          │
│  └──────────────────────────────────────────────────┘          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ▼
                   Data Validation & Cleaning
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 2: FEATURE STORE (Processed, Optimized for RL)           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    features                              │   │
│  │  • Technical indicators (RSI, MACD, Bollinger, ...)     │   │
│  │  • Fundamental ratios (PE, PB, ROE, ...)                │   │
│  │  │  • Sentiment scores                                   │   │
│  │  • Macro indicators                                      │   │
│  │  • Cross-sectional features (rankings, z-scores)        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │               feature_metadata                           │   │
│  │  • Feature descriptions                                  │   │
│  │  • Data types                                            │   │
│  │  • Feature categories                                    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ▼
                   RL Training Environment
```

## Database Schema

### Layer 1: Data Lake

#### `raw_prices` Table
Stores immutable raw OHLCV data from providers.

```sql
CREATE TABLE raw_prices (
    id INTEGER PRIMARY KEY,
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
);
```

**Key Features:**
- Immutable: Once written, never modified
- Versioned: Provider field allows multiple data sources
- Quality tracked: Each record has a quality score
- Timestamped: Track when data was ingested

#### `stock_universe` Table
Tracks stock universe with survivorship bias handling.

```sql
CREATE TABLE stock_universe (
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
);
```

**Survivorship Bias Handling:**
- Track when stocks entered/exited universe
- Query universe "as of" any historical date
- Prevent look-ahead bias in backtesting

#### `data_quality_log` Table
Comprehensive quality issue tracking.

```sql
CREATE TABLE data_quality_log (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    issue_type TEXT NOT NULL,
    severity INTEGER,  -- 1=low, 2=medium, 3=high
    details TEXT,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Issue Types:**
- `missing`: Missing data points
- `zero_volume`: Zero trading volume
- `price_spike`: Unrealistic price movement
- `validation_failure`: Failed quality checks
- `validation_warning`: Quality warnings

#### `fundamentals` Table
Flexible storage for fundamental metrics.

```sql
CREATE TABLE fundamentals (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    metric_name TEXT NOT NULL,
    metric_value REAL,
    provider TEXT DEFAULT 'yfinance',
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date, metric_name, provider)
);
```

### Layer 2: Feature Store

#### `features` Table
Stores computed features in normalized form.

```sql
CREATE TABLE features (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    date DATE NOT NULL,
    feature_name TEXT NOT NULL,
    feature_value REAL,
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ticker, date, feature_name)
);
```

**Storage Format:**
- **Normalized (long format)**: Each feature value is a row
- **Efficient updates**: Update single features without rewriting all
- **Fast queries**: Indexed by (ticker, date, feature_name)

#### `feature_metadata` Table
Documents available features.

```sql
CREATE TABLE feature_metadata (
    feature_name TEXT PRIMARY KEY,
    description TEXT,
    feature_type TEXT,  -- technical, fundamental, sentiment, macro
    data_type TEXT,     -- float, int, bool
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Usage Examples

### 1. Downloading Historical Data

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

# Fetch and store S&P 100 data
tickers = ["AAPL", "MSFT", "GOOGL", ...]
data_dict = dm.fetch_prices_bulk(
    tickers=tickers,
    start_date="2018-01-01",
    end_date="2024-12-31",
    validate=True,
    save_to_db=True,  # Automatically saved to database
)
```

**Or use the provided script:**

```bash
python scripts/download_sp100.py \
    --start-date 2018-01-01 \
    --end-date 2024-12-31 \
    --batch-size 10
```

### 2. Loading Data from Database

```python
# Load raw prices from data lake
df = dm.fetch_prices(
    ticker="AAPL",
    start_date="2023-01-01",
    end_date="2023-12-31",
)

# This checks database first, falls back to provider if needed
```

### 3. Universe Management

```python
# Add stock to universe
dm.add_to_universe(
    ticker="AAPL",
    name="Apple Inc.",
    sector="Technology",
    industry="Consumer Electronics",
    market="US",
    added_date=date(2018, 1, 1),
)

# Get current universe
active_tickers = dm.load_universe(market="US", active_only=True)

# Get historical universe (for backtesting without survivorship bias)
universe_2020 = dm.load_universe(
    market="US",
    as_of_date=date(2020, 1, 1),
)
```

### 4. Feature Store Operations

```python
# Compute and save features
from features.technical import TechnicalFeatures

tech_features = TechnicalFeatures()
features_df = tech_features.compute(df)

# Save to feature store
dm.save_features(
    ticker="AAPL",
    features_df=features_df,
    feature_columns=["rsi_14", "macd", "bb_upper", "bb_lower"],
)

# Register feature metadata
dm.register_feature(
    feature_name="rsi_14",
    description="14-day Relative Strength Index",
    feature_type="technical",
)

# Load features for model training
features = dm.load_features(
    ticker="AAPL",
    start_date="2023-01-01",
    end_date="2023-12-31",
    feature_names=["rsi_14", "macd", "returns_1d"],
)

# Load features for multiple tickers (panel data)
panel = dm.load_features_bulk(
    tickers=["AAPL", "MSFT", "GOOGL"],
    start_date="2023-01-01",
    end_date="2023-12-31",
)
```

### 5. Quality Monitoring

```python
# Check data quality issues
issues = dm.get_quality_issues(ticker="AAPL", min_severity=2)
print(issues)

# Get database statistics
stats = dm.get_database_stats()
print(f"Total records: {stats['total_price_records']:,}")
print(f"Date range: {stats['price_date_range']}")
print(f"Quality issues: {stats['quality_issues_logged']}")
```

## Benefits of Two-Layer Architecture

### 1. **Provider Independence**

Switch from yfinance to Bloomberg without changing downstream code:

```python
# Old provider
provider_old = YFinanceAdapter()

# New provider
provider_new = BloombergAdapter()

# Data manager works with both - just swap provider
dm = DataManagerDB(provider=provider_new, ...)

# RL environment consumes features - doesn't know about provider change!
```

### 2. **Reproducibility**

```python
# Raw data is immutable in data lake
# Can always recompute features with new logic
# But original data never changes

# V1 features
features_v1 = compute_features_v1(raw_data)

# V2 features (improved algorithm)
features_v2 = compute_features_v2(raw_data)

# Compare performance
backtest(features_v1)
backtest(features_v2)
```

### 3. **Performance**

```python
# First run: Compute features (slow)
compute_all_features(tickers, start_date, end_date)  # ~10 min

# Subsequent runs: Load from feature store (fast)
features = dm.load_features_bulk(tickers, start_date, end_date)  # ~1 sec

# RL training gets instant access to pre-computed features
```

### 4. **Survivorship Bias Prevention**

```python
# Backtest as if you were trading in 2020
# Only use stocks that existed then
universe_2020 = dm.load_universe(as_of_date=date(2020, 1, 1))

# Some stocks in universe_2020 might be delisted now
# But we still have their data for accurate backtesting
```

## Migration Path: SQLite → PostgreSQL

The schema is designed for easy migration:

```python
# Development: SQLite
dm = DataManagerDB(db_path="data/stock_data.db", ...)

# Production: PostgreSQL (when ready)
dm = DataManagerDB(
    db_path="postgresql://user:pass@localhost:5432/stocks",
    ...
)
```

**Migration steps:**
1. Export SQLite to SQL dump
2. Import to PostgreSQL
3. Update connection string
4. No code changes needed!

## Best Practices

### 1. Always Use Database Layer

```python
# ✓ Good: Database-backed
from data.data_manager_db import DataManagerDB
dm = DataManagerDB(use_database=True)

# ✗ Avoid: File-only caching (loses benefits)
from data.data_manager import DataManager
dm = DataManager()  # Only file cache, no database
```

### 2. Validate Before Storing

```python
# Validation ensures only quality data enters data lake
data_dict = dm.fetch_prices_bulk(
    tickers=tickers,
    validate=True,  # ← Always validate
    save_to_db=True,
)
```

### 3. Use Feature Store for Training

```python
# ✓ Good: Load pre-computed features
features = dm.load_features_bulk(tickers, start_date, end_date)

# ✗ Avoid: Recomputing features every time
for epoch in range(100):
    features = compute_features(raw_data)  # Wasteful!
```

### 4. Track Universe Changes

```python
# When a stock is delisted
dm.remove_from_universe(
    ticker="DEFUNCT",
    removed_date=date(2023, 6, 1),
)

# Prevents look-ahead bias in backtests
```

## Database Maintenance

### Vacuum Database

```python
# Reclaim space and rebuild indices
dm.db.vacuum()
```

### Export Data

```python
# Export to CSV for analysis
dm.export_to_csv(
    ticker="AAPL",
    start_date="2023-01-01",
    end_date="2023-12-31",
    output_path="exports/aapl_2023.csv",
    include_features=True,
)
```

### Backup Database

```bash
# Simple backup
cp data/stock_data.db data/stock_data_backup.db

# With compression
tar -czf stock_data_$(date +%Y%m%d).tar.gz data/stock_data.db
```

## Storage Requirements

Estimated database sizes for S&P 100:

| Data Type | Time Period | Approx Size |
|-----------|-------------|-------------|
| Raw Prices | 5 years | ~50 MB |
| Fundamentals | Current | ~5 MB |
| Features (50 features) | 5 years | ~200 MB |
| **Total** | **5 years** | **~255 MB** |

SQLite can easily handle databases up to several GB, making it perfect for development and small-scale production.

## Summary

The two-layer architecture provides:

✅ **Separation of Concerns**: Raw data vs. processed features  
✅ **Flexibility**: Easy provider switching  
✅ **Performance**: Pre-computed features  
✅ **Reproducibility**: Immutable raw data  
✅ **Quality**: Comprehensive validation and logging  
✅ **Scalability**: Easy migration to PostgreSQL  
✅ **Research-Friendly**: Track experiments, compare feature versions  

This design follows industry best practices from quantitative finance and makes your RL trading agent production-ready.

