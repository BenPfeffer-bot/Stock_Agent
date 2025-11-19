# Universe Manager Guide - Survivorship Bias Prevention

## Overview

The `UniverseManager` ensures your backtests don't suffer from **survivorship bias** by tracking when stocks entered and exited your trading universe. This is critical for accurate backtesting and realistic performance evaluation.

## What is Survivorship Bias?

**Survivorship bias** occurs when you backtest only on stocks that "survived" to the present day, ignoring delisted or acquired companies. This leads to unrealistically optimistic results.

### Example of the Problem:

```python
# ❌ BAD: Survivorship Bias
current_sp100 = get_current_sp100_stocks()  # Gets stocks that exist TODAY
backtest(current_sp100, start="2015-01-01", end="2024-01-01")
# Problem: Some stocks in current list didn't exist in 2015!
# You're "time traveling" by using future information
```

### The Correct Way:

```python
# ✅ GOOD: No Survivorship Bias  
universe_2015 = universe_manager.get_tickers(as_of_date=date(2015, 1, 1))
backtest(universe_2015, start="2015-01-01", end="2016-01-01")

universe_2016 = universe_manager.get_tickers(as_of_date=date(2016, 1, 1))
backtest(universe_2016, start="2016-01-01", end="2017-01-01")
# Each backtest uses only stocks that existed at that time
```

---

## Key Features

### 1. **Track Stock Lifecycle**
   - When stocks were added to universe
   - When stocks were removed (delisting, acquisition, etc.)
   - Why they were removed (optional notes)

### 2. **Time-Travel Queries**
   - Query universe "as of" any historical date
   - Get only stocks that existed then
   - Prevents look-ahead bias

### 3. **Flexible Filtering**
   - Filter by market (US, EU, etc.)
   - Filter by sector
   - Filter by market cap
   - Active/inactive stocks

### 4. **Data Coverage Validation**
   - Check if stocks have sufficient data
   - Validate data coverage for backtest period
   - Filter out stocks with insufficient data

---

## Basic Usage

### Initialize

```python
from data.universe import UniverseManager

# Option 1: With database path
um = UniverseManager(db_path="data/stock_data.db")

# Option 2: With existing database manager
from data.database import DatabaseManager
db = DatabaseManager("data/stock_data.db")
um = UniverseManager(db_manager=db)
```

### Add Stocks to Universe

```python
from datetime import date

# Add a single stock
um.add_stock(
    ticker="AAPL",
    name="Apple Inc.",
    sector="Technology",
    industry="Consumer Electronics",
    market="US",
    added_date=date(2018, 1, 1),
    market_cap=2.5e12,
    currency="USD"
)

# Add multiple stocks at once
stocks = [
    {'ticker': 'AAPL', 'name': 'Apple Inc.', 'sector': 'Technology'},
    {'ticker': 'MSFT', 'name': 'Microsoft', 'sector': 'Technology'},
    {'ticker': 'GOOGL', 'name': 'Alphabet', 'sector': 'Technology'},
]

um.bulk_add_stocks(
    stocks,
    market="US",
    added_date=date(2018, 1, 1)
)
```

### Remove Stocks (For Survivorship Tracking)

```python
# Mark stock as removed (not deleted!)
um.remove_stock(
    ticker="TSLA",
    removed_date=date(2023, 6, 1),
    reason="Acquired by private equity"
)

# The stock still exists in database with historical data
# But won't appear in active queries after removal date
```

---

## Preventing Survivorship Bias

### Get Universe at Historical Date

```python
# Get stocks that existed on Jan 1, 2020
universe_2020 = um.get_tickers(as_of_date=date(2020, 1, 1))

# Get stocks that exist today
universe_now = um.get_tickers()  # as_of_date defaults to today

# Check if specific stock was in universe at date
was_in_universe = um.is_in_universe("TSLA", as_of_date=date(2015, 1, 1))
```

### Backtest Without Survivorship Bias

```python
from datetime import date

# Define backtest period
backtest_start = date(2018, 1, 1)
backtest_end = date(2023, 12, 31)

# Get universe safe for backtesting
backtest_tickers = um.get_backtest_universe(
    backtest_start=backtest_start,
    backtest_end=backtest_end,
    market="US",
    require_full_period=True  # Only stocks with full data coverage
)

# This returns only stocks that:
# 1. Existed at backtest_start (no look-ahead)
# 2. Have sufficient data for the period
# 3. Meet your criteria (market, etc.)

# Now backtest safely
results = backtest(backtest_tickers, backtest_start, backtest_end)
```

### Walk-Forward Analysis

```python
# Backtest year by year with correct universe each year
results = []

for year in range(2018, 2024):
    year_start = date(year, 1, 1)
    year_end = date(year, 12, 31)
    
    # Get universe as it was at the start of that year
    universe = um.get_tickers(as_of_date=year_start, market="US")
    
    # Backtest with that year's universe
    result = backtest(universe, year_start, year_end)
    results.append(result)

# Combine results for overall performance
```

---

## Filtering and Queries

### Filter by Market

```python
# Get US stocks only
us_stocks = um.get_tickers(market="US")

# Get European stocks
eu_stocks = um.get_tickers(market="EU")
```

### Filter by Sector

```python
# Get all tech stocks
tech_stocks = um.get_universe(sector="Technology")

# Get tech stocks as of 2020
tech_2020 = um.get_universe(
    sector="Technology",
    as_of_date=date(2020, 1, 1)
)
```

### Get Stock Information

```python
# Get detailed info about a stock
stock_info = um.get_stock_info("AAPL")

print(f"Ticker: {stock_info.ticker}")
print(f"Name: {stock_info.name}")
print(f"Sector: {stock_info.sector}")
print(f"Added: {stock_info.added_date}")
print(f"Removed: {stock_info.removed_date}")  # None if still active
print(f"Active: {stock_info.is_active}")
```

### Track Universe Changes

```python
# Get stocks added/removed in 2022
changes = um.get_universe_changes(
    start_date=date(2022, 1, 1),
    end_date=date(2022, 12, 31),
    market="US"
)

print(f"Added: {changes['added']}")
print(f"Removed: {changes['removed']}")
```

---

## Data Coverage Validation

### Validate Data Availability

```python
# Check which stocks have sufficient data for backtest
coverage = um.validate_universe_data_coverage(
    start_date=date(2020, 1, 1),
    end_date=date(2023, 12, 31),
    min_data_points=800  # ~3 years of trading days
)

# Show stocks with insufficient data
insufficient = coverage[~coverage['has_sufficient_data']]
print(f"Stocks with insufficient data: {len(insufficient)}")
print(insufficient[['ticker', 'data_points', 'coverage_pct']])

# Get only stocks with full coverage
good_tickers = coverage[coverage['has_sufficient_data']]['ticker'].tolist()
```

---

## Statistics and Analysis

### Get Universe Statistics

```python
stats = um.get_universe_stats(as_of_date=date(2022, 1, 1))

print(f"Total stocks: {stats['total_stocks']}")
print(f"Active stocks: {stats['active_stocks']}")
print(f"Inactive stocks: {stats['inactive_stocks']}")

print("\nBy Market:")
for market, count in stats['by_market'].items():
    print(f"  {market}: {count}")

print("\nBy Sector:")
for sector, count in stats['by_sector'].items():
    print(f"  {sector}: {count}")
```

### Get Available Sectors

```python
# Get list of all sectors
sectors = um.get_sectors(market="US")
print(f"Sectors: {sectors}")
```

---

## Real-World Example

### Complete Backtest Setup

```python
from data.universe import UniverseManager
from data.data_manager_db import DataManagerDB
from data.providers.yfinance_adapter import YFinanceAdapter
from datetime import date

# 1. Initialize managers
provider = YFinanceAdapter()
dm = DataManagerDB(provider=provider, db_path="data/stock_data.db")
um = UniverseManager(db_path="data/stock_data.db")

# 2. Define backtest period
backtest_start = date(2020, 1, 1)
backtest_end = date(2023, 12, 31)

# 3. Get backtest-safe universe (no survivorship bias!)
universe = um.get_backtest_universe(
    backtest_start=backtest_start,
    backtest_end=backtest_end,
    market="US",
    require_full_period=True
)

print(f"Backtesting with {len(universe)} stocks")

# 4. Validate data coverage
coverage = um.validate_universe_data_coverage(
    backtest_start,
    backtest_end,
    min_data_points=800
)

sufficient_tickers = coverage[coverage['has_sufficient_data']]['ticker'].tolist()
print(f"{len(sufficient_tickers)} stocks have sufficient data")

# 5. Load data for backtest
data_dict = dm.fetch_prices_bulk(
    tickers=sufficient_tickers,
    start_date=str(backtest_start),
    end_date=str(backtest_end)
)

# 6. Create panel data for RL environment
panel = dm.create_panel_data(data_dict)

# 7. Run backtest/training
from environment.trading_env import TradingEnv
env = TradingEnv(data=panel)
# ... train agent ...
```

---

## Export and Reporting

### Export Universe to CSV

```python
# Export current universe
um.export_universe(
    output_path="outputs/universe_current.csv"
)

# Export historical universe
um.export_universe(
    output_path="outputs/universe_2020.csv",
    as_of_date=date(2020, 1, 1),
    market="US"
)
```

---

## Best Practices

### 1. Always Use as_of_date for Backtesting

```python
# ✅ GOOD
for year in range(2018, 2024):
    universe = um.get_tickers(as_of_date=date(year, 1, 1))
    backtest(universe, ...)

# ❌ BAD - Uses current universe for all years!
universe = um.get_tickers()  # Gets today's universe
for year in range(2018, 2024):
    backtest(universe, ...)  # Survivorship bias!
```

### 2. Track Removals with Reasons

```python
# Good: Document why stocks were removed
um.remove_stock("XYZ", removed_date=date(2022, 6, 1), reason="Delisted due to bankruptcy")
um.remove_stock("ABC", removed_date=date(2023, 3, 15), reason="Acquired by DEF")
```

### 3. Validate Data Coverage

```python
# Always check data availability before backtesting
coverage = um.validate_universe_data_coverage(start, end)
good_tickers = coverage[coverage['has_sufficient_data']]['ticker'].tolist()

# Use only stocks with good coverage
backtest(good_tickers, ...)
```

### 4. Use get_backtest_universe()

```python
# This does it all: as_of_date + data validation
backtest_tickers = um.get_backtest_universe(
    backtest_start=date(2020, 1, 1),
    backtest_end=date(2023, 12, 31),
    require_full_period=True
)
```

---

## Common Patterns

### Pattern 1: Rolling Backtest

```python
# Backtest with rebalancing every quarter
from dateutil.relativedelta import relativedelta

start = date(2020, 1, 1)
end = date(2023, 12, 31)
current = start

while current < end:
    quarter_end = min(current + relativedelta(months=3), end)
    
    # Get universe at start of quarter
    universe = um.get_tickers(as_of_date=current, market="US")
    
    # Backtest this quarter
    result = backtest(universe, current, quarter_end)
    
    current = quarter_end
```

### Pattern 2: Sector Rotation

```python
# Test different sectors at different times
sectors = um.get_sectors(market="US")

for sector in sectors:
    # Get sector stocks as they were in 2020
    sector_universe = um.get_universe(
        sector=sector,
        as_of_date=date(2020, 1, 1),
        market="US"
    )
    
    sector_tickers = [s.ticker for s in sector_universe]
    backtest(sector_tickers, ...)
```

### Pattern 3: Universe Drift Analysis

```python
# Analyze how universe changed over time
years = range(2018, 2024)
universe_sizes = {}

for year in years:
    universe = um.get_tickers(as_of_date=date(year, 1, 1))
    universe_sizes[year] = len(universe)

print("Universe size over time:")
for year, size in universe_sizes.items():
    print(f"{year}: {size} stocks")
```

---

## Integration with DataManagerDB

The UniverseManager works seamlessly with DataManagerDB:

```python
from data.universe import UniverseManager
from data.data_manager_db import DataManagerDB
from data.providers.yfinance_adapter import YFinanceAdapter

# Initialize
provider = YFinanceAdapter()
dm = DataManagerDB(provider=provider, db_path="data/stock_data.db")

# Universe manager shares same database
um = UniverseManager(db_path="data/stock_data.db")

# Load universe
tickers = um.get_tickers(as_of_date=date(2022, 1, 1))

# Load data for those tickers
data_dict = dm.fetch_prices_bulk(tickers, "2022-01-01", "2022-12-31")

# DataManagerDB can also load universe directly
dm_tickers = dm.load_universe(as_of_date=date(2022, 1, 1))
```

---

## Troubleshooting

### Issue: All stocks show removed_date

**Cause:** You called `remove_stock()` without specifying a date

**Fix:** Only call `remove_stock()` for actually removed stocks

### Issue: Backtest universe is empty

**Possible causes:**
1. `as_of_date` is before any stocks were added
2. All stocks were removed before that date
3. Filters are too restrictive

**Debug:**
```python
# Check what's in universe without filters
all_stocks = um.get_universe(active_only=False)
print(f"Total stocks in database: {len(all_stocks)}")

# Check specific date
stocks_at_date = um.get_universe(as_of_date=your_date, active_only=False)
print(f"Stocks at {your_date}: {len(stocks_at_date)}")
```

### Issue: Stock not found in historical query

**Cause:** Stock was added to universe after your query date

**Fix:** Check when stock was added:
```python
stock = um.get_stock_info("TICKER")
print(f"Added date: {stock.added_date}")
```

---

## Summary

The UniverseManager is your key tool for preventing survivorship bias. Always:

✅ Use `as_of_date` for historical queries  
✅ Track stock additions and removals  
✅ Validate data coverage before backtesting  
✅ Use `get_backtest_universe()` for safe backtesting  
✅ Export universe snapshots for reproducibility  

This ensures your backtests are realistic and your results are trustworthy! 🎯

