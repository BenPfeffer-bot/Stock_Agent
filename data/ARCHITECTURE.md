# Data Manager Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Data Manager System                       │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                          DATA FLOW                               │
└─────────────────────────────────────────────────────────────────┘

    External API          Data Manager          Validation         Output
         │                     │                     │               │
         │                     │                     │               │
    ┌────▼────┐          ┌────▼────┐          ┌────▼────┐     ┌────▼────┐
    │ YFinance│          │  Fetch  │          │Validator│     │Validated│
    │  API    │─────────>│  Data   │─────────>│ Checks  │────>│  Data   │
    └─────────┘          └────┬────┘          └────┬────┘     └────┬────┘
                              │                     │               │
                         ┌────▼────┐          ┌────▼────┐     ┌────▼────┐
                         │  Cache  │          │ Quality │     │ Panel   │
                         │ System  │          │ Reports │     │  Data   │
                         └─────────┘          └─────────┘     └─────────┘
```

## Component Architecture

```
┌───────────────────────────────────────────────────────────────────────┐
│                           DataManager                                  │
├───────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │  Data Fetching   │  │   Validation     │  │     Caching      │   │
│  ├──────────────────┤  ├──────────────────┤  ├──────────────────┤   │
│  │ • fetch_prices   │  │ • validate       │  │ • save_cache     │   │
│  │ • fetch_bulk     │  │ • quality_score  │  │ • load_cache     │   │
│  │ • fetch_fundamen.│  │ • issue_tracking │  │ • clear_cache    │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘   │
│                                                                        │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐   │
│  │  Data Cleaning   │  │   Alignment      │  │     Reports      │   │
│  ├──────────────────┤  ├──────────────────┤  ├──────────────────┤   │
│  │ • fill_missing   │  │ • align_dates    │  │ • validation_sum.│   │
│  │ • remove_dupes   │  │ • inner_join     │  │ • quality_report │   │
│  │ • clip_negatives │  │ • outer_join     │  │ • coverage_anal. │   │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘   │
│                                                                        │
└───────────────────────────────────────────────────────────────────────┘
```

## Validation Pipeline

```
                         VALIDATION PIPELINE
                                
Input DataFrame
     │
     ▼
┌─────────────────────┐
│ 1. Schema Check     │──> Missing columns? ──> FAIL
└──────┬──────────────┘
       │ PASS
       ▼
┌─────────────────────┐
│ 2. Data Completeness│──> Too few rows?   ──> FAIL
└──────┬──────────────┘
       │ PASS
       ▼
┌─────────────────────┐
│ 3. Missing Values   │──> > 5% missing?   ──> FAIL
└──────┬──────────────┘
       │ PASS (or Warning)
       ▼
┌─────────────────────┐
│ 4. OHLC Consistency │──> Violations?     ──> FAIL/Warning
└──────┬──────────────┘
       │ PASS
       ▼
┌─────────────────────┐
│ 5. Price Continuity │──> Large gaps?     ──> Warning
└──────┬──────────────┘
       │ PASS
       ▼
┌─────────────────────┐
│ 6. Volume Check     │──> Zero/neg vol?   ──> FAIL/Warning
└──────┬──────────────┘
       │ PASS
       ▼
┌─────────────────────┐
│ 7. Outlier Detection│──> Outliers?       ──> Warning
└──────┬──────────────┘
       │ PASS
       ▼
┌─────────────────────┐
│ 8. Duplicate Check  │──> Duplicates?     ──> FAIL
└──────┬──────────────┘
       │ PASS
       ▼
┌─────────────────────┐
│ 9. Order Check      │──> Not chrono?     ──> FAIL
└──────┬──────────────┘
       │ PASS
       ▼
┌─────────────────────┐
│ Calculate Quality   │
│ Score (0-1)         │
└──────┬──────────────┘
       │
       ▼
┌─────────────────────┐
│ Score ≥ 0.7?        │──> NO  ──> FAIL
└──────┬──────────────┘
       │ YES
       ▼
   VALIDATED DATA
```

## Quality Scoring System

```
                    QUALITY SCORE CALCULATION
                           (0.0 - 1.0)

┌──────────────────────────────────────────────────────────────┐
│                      Component Scores                         │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  Data Completeness      ████████████████████ 1.00            │
│  Missing Data          ████████████████████ 1.00            │
│  OHLC Consistency      ███████████████████░ 0.95            │
│  Price Continuity      ████████████████░░░░ 0.80            │
│  Volume Quality        ████████████████████ 1.00            │
│  Outlier Check         ██████████████████░░ 0.90            │
│  Uniqueness            ████████████████████ 1.00            │
│  Chronological         ████████████████████ 1.00            │
│                                                               │
│  ─────────────────────────────────────────────────────────  │
│  Overall Quality Score: 0.96 (Excellent)                     │
│                                                               │
└──────────────────────────────────────────────────────────────┘

Quality Bands:
  0.90 - 1.00 : Excellent ★★★★★
  0.80 - 0.90 : Good     ★★★★☆
  0.70 - 0.80 : Fair     ★★★☆☆
  <0.70       : Poor     ★★☆☆☆ (Rejected)
```

## Cache System

```
                        CACHE SYSTEM

┌────────────────────────────────────────────────────────┐
│                    Cache Flow                           │
└────────────────────────────────────────────────────────┘

Request Data
     │
     ▼
┌──────────────┐      YES      ┌──────────────┐
│ Cache Exists?│─────────────>│ Cache Expired?│
└──────┬───────┘               └──────┬───────┘
       │ NO                           │ YES
       │                              │
       ▼                              ▼
┌──────────────────────────────────────────┐
│           Fetch from Provider             │
└──────────────┬───────────────────────────┘
               │                    ▲
               ▼                    │ NO (valid cache)
       ┌──────────────┐             │
       │   Validate   │             │
       └──────┬───────┘             │
              │                     │
              ▼                     │
       ┌──────────────┐             │
       │  Save Cache  │             │
       └──────┬───────┘             │
              │                     │
              └─────────────────────┘
                      │
                      ▼
              ┌──────────────┐
              │ Return Data  │
              └──────────────┘

Cache Structure:
  data_cache/
    ├── AAPL_prices_2023-01-01_2024-01-01.pkl
    ├── MSFT_prices_2023-01-01_2024-01-01.pkl
    ├── GOOGL_prices_2023-01-01_2024-01-01.pkl
    ├── AAPL_fundamentals.pkl
    └── ...

Each cache file contains:
  {
    'data': DataFrame or Dict,
    'timestamp': datetime,
    'ticker': str,
    'data_type': str
  }
```

## Data Providers

```
┌────────────────────────────────────────────────────────────┐
│                 BaseDataProvider (Abstract)                 │
├────────────────────────────────────────────────────────────┤
│  • fetch_prices(ticker, start, end) -> DataFrame           │
│  • fetch_fundamentals(ticker) -> dict                      │
│  • get_available_tickers(market) -> List[str]              │
└────────────────────────────────────────────────────────────┘
                              ▲
                              │
                ┌─────────────┴─────────────┐
                │                           │
┌───────────────▼──────────┐  ┌─────────────▼──────────────┐
│   YFinanceAdapter        │  │   NewsAdapter (Placeholder) │
├──────────────────────────┤  ├────────────────────────────┤
│ • Real-time OHLCV data   │  │ • News articles            │
│ • 40+ fundamental metrics│  │ • Sentiment scores         │
│ • Corporate actions      │  │ • Market news              │
│ • Bulk download          │  │ • (To be implemented)      │
└──────────────────────────┘  └────────────────────────────┘
```

## Panel Data Structure

```
                   PANEL DATA CREATION
                   
Individual Ticker DataFrames:

AAPL:                    MSFT:                    GOOGL:
Date       | Close       Date       | Close       Date       | Close
2023-01-01 | 150.0      2023-01-01 | 250.0      2023-01-01 | 90.0
2023-01-02 | 152.0      2023-01-02 | 252.0      2023-01-02 | 91.0
2023-01-03 | 151.0      2023-01-03 | 251.0      2023-01-03 | 92.0
    ...                     ...                     ...

                         ↓ ALIGN & STACK ↓

Panel DataFrame (MultiIndex):

Date        Ticker | Open   High   Low    Close  Volume
2023-01-01  AAPL   | 149.0  151.0  148.0  150.0  1000000
2023-01-01  GOOGL  | 89.0   91.0   88.0   90.0   2000000
2023-01-01  MSFT   | 249.0  251.0  248.0  250.0  1500000
2023-01-02  AAPL   | 150.0  153.0  149.0  152.0  1100000
2023-01-02  GOOGL  | 90.0   92.0   89.0   91.0   2100000
2023-01-02  MSFT   | 250.0  253.0  249.0  252.0  1600000
...

Benefits:
• Efficient multi-ticker operations
• Easy feature engineering across tickers
• Compatible with ML frameworks
• Simplified backtesting
```

## Integration with Training Pipeline

```
┌────────────────────────────────────────────────────────────────┐
│                    TRAINING PIPELINE INTEGRATION                │
└────────────────────────────────────────────────────────────────┘

┌──────────────┐
│    Config    │
│ data_config  │
│   .yaml      │
└──────┬───────┘
       │
       ▼
┌──────────────────────┐
│   Data Manager       │
│  • Load config       │
│  • Init provider     │
│  • Set thresholds    │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Fetch & Validate    │
│  • Get universe      │
│  • Bulk fetch        │
│  • Quality checks    │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│  Quality Report      │
│  • Check failures    │
│  • Log warnings      │
│  • Filter bad data   │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│   Data Alignment     │
│  • Common dates      │
│  • Handle gaps       │
│  • Create panel      │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│ Feature Engineering  │
│  • Technical feats.  │
│  • Fundamentals      │
│  • Sentiment         │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│   Trading Env        │
│  • Initialize        │
│  • Reset state       │
│  • Step through      │
└──────┬───────────────┘
       │
       ▼
┌──────────────────────┐
│    RL Agent          │
│  • Train PPO/SAC     │
│  • Track metrics     │
│  • Save checkpoints  │
└──────────────────────┘
```

## Error Handling Flow

```
                    ERROR HANDLING

┌──────────────────────────────────────────────────────────┐
│                   Error Categories                        │
└──────────────────────────────────────────────────────────┘

Provider Errors           Validation Errors        Cache Errors
     │                          │                       │
     │                          │                       │
┌────▼─────┐            ┌──────▼────┐           ┌─────▼──────┐
│ Network  │            │ Data      │           │ Corrupted  │
│ Timeout  │            │ Quality   │           │ Cache      │
└────┬─────┘            └──────┬────┘           └─────┬──────┘
     │                         │                       │
     └─────────┬───────────────┴───────────────────────┘
               │
               ▼
     ┌─────────────────┐
     │  Log Error      │
     │  Add to Failed  │
     │  Continue       │
     └────────┬────────┘
              │
              ▼
     ┌─────────────────┐
     │  Return None    │
     │  or Empty       │
     └────────┬────────┘
              │
              ▼
     ┌─────────────────┐
     │  Caller Checks  │
     │  Handle Failed  │
     │  Retry/Skip     │
     └─────────────────┘

No exceptions propagate unless fail_on_error=True
```

## Class Hierarchy

```
DataManager
  ├── __init__(provider, cache_dir, config_path, ...)
  │
  ├── Data Fetching
  │   ├── fetch_prices(ticker, start_date, end_date)
  │   ├── fetch_prices_bulk(tickers, start_date, end_date)
  │   └── fetch_fundamentals(ticker)
  │
  ├── Validation
  │   └── validator: DataValidator instance
  │
  ├── Caching
  │   ├── _save_to_cache(data, ticker, type, ...)
  │   ├── _load_from_cache(ticker, type, ...)
  │   └── clear_cache(ticker)
  │
  ├── Data Processing
  │   ├── _clean_price_data(df)
  │   ├── align_data(data_dict, method)
  │   └── create_panel_data(data_dict)
  │
  └── Reporting
      ├── get_validation_summary()
      ├── get_quality_report()
      ├── get_data_coverage(data_dict)
      └── export_validation_report(path)

DataValidator
  ├── __init__(min_quality_score, max_missing_pct, ...)
  │
  ├── validate_price_data(df, ticker) -> ValidationResult
  │   ├── _validate_ohlc_consistency(df)
  │   ├── _check_price_continuity(prices, ticker)
  │   ├── _validate_volume(volume)
  │   └── _detect_outliers(prices)
  │
  └── validate_fundamental_data(data, ticker) -> ValidationResult

ValidationResult (dataclass)
  ├── is_valid: bool
  ├── quality_score: float
  ├── issues: List[str]
  ├── warnings: List[str]
  └── metadata: Dict

DataQualityReport (static methods)
  ├── generate_summary(validation_results) -> DataFrame
  ├── get_failed_tickers(validation_results) -> List[str]
  └── get_quality_distribution(validation_results) -> Dict
```

## Performance Considerations

```
┌────────────────────────────────────────────────────────────┐
│              PERFORMANCE OPTIMIZATIONS                      │
└────────────────────────────────────────────────────────────┘

1. Caching
   • Reduces API calls by ~90%
   • Fast pickle serialization
   • Configurable expiry

2. Bulk Operations
   • YFinance bulk download API
   • Single API call for multiple tickers
   • ~10x faster than sequential

3. Vectorized Operations
   • Pandas operations (no loops)
   • NumPy for numerical checks
   • Efficient memory usage

4. Lazy Loading
   • Validation on demand
   • Cache loaded only when needed
   • Minimal memory footprint

5. Early Exit
   • Fail fast on critical issues
   • Skip expensive checks if basic fails
   • Reduce validation time

Typical Performance:
  • Single ticker fetch: ~1-2s (first), ~0.01s (cached)
  • Bulk 10 tickers: ~5-10s (first), ~0.1s (cached)
  • Validation: ~0.1-0.5s per ticker
  • Panel creation: ~0.5-2s for 10 tickers
```

## Summary

This architecture provides:
- ✅ Modular, extensible design
- ✅ Clear separation of concerns
- ✅ Robust error handling
- ✅ Performance optimization
- ✅ Easy integration
- ✅ Comprehensive validation
- ✅ Quality guarantees

