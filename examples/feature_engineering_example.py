#!/usr/bin/env python3
"""
Feature Engineering Example

Demonstrates how to use the technical features module for stock analysis
"""

import pandas as pd
from datetime import datetime, timedelta

from features import TechnicalFeatures, FeatureManager
from data import UniverseManager


def example_1_basic_features():
    """Example 1: Compute basic features for a single stock"""
    print("=" * 80)
    print("Example 1: Basic Feature Computation")
    print("=" * 80)

    fm = FeatureManager()

    # Compute all features
    features = fm.compute_features(
        ticker="AAPL",
        start_date="2023-01-01",
        end_date="2023-12-31",
        feature_set="all",
    )

    print(f"\nComputed {len(features.columns)} features for {len(features)} days")
    print("\nSample features:")
    print(
        features[
            ["close", "sma_20", "rsi_14", "macd", "bb_position", "atr_14"]
        ].tail()
    )


def example_2_momentum_strategy():
    """Example 2: Momentum trading strategy"""
    print("\n" + "=" * 80)
    print("Example 2: Momentum Trading Strategy")
    print("=" * 80)

    fm = FeatureManager()

    # Get momentum features
    features = fm.compute_features(
        ticker="AAPL",
        start_date="2023-01-01",
        end_date="2023-12-31",
        feature_set="momentum",
    )

    # Define signals
    buy_signal = (features["rsi_14"] < 30) & (features["macd_histogram"] > 0)
    sell_signal = (features["rsi_14"] > 70) & (features["macd_histogram"] < 0)

    print(f"\nBuy signals: {buy_signal.sum()}")
    print(f"Sell signals: {sell_signal.sum()}")

    # Show buy opportunities
    buy_dates = features[buy_signal].index
    if len(buy_dates) > 0:
        print("\nBuy opportunities:")
        for date in buy_dates[:5]:  # Show first 5
            row = features.loc[date]
            print(
                f"  {date.strftime('%Y-%m-%d')}: "
                f"RSI={row['rsi_14']:.2f}, "
                f"MACD Hist={row['macd_histogram']:.4f}"
            )


def example_3_volatility_analysis():
    """Example 3: Volatility analysis"""
    print("\n" + "=" * 80)
    print("Example 3: Volatility Analysis")
    print("=" * 80)

    fm = FeatureManager()

    # Get volatility features
    features = fm.compute_features(
        ticker="AAPL",
        start_date="2023-01-01",
        end_date="2023-12-31",
        feature_set="volatility",
    )

    # Bollinger Band position
    features["bb_position"] = (features["close"] - features["bb_lower"]) / (
        features["bb_upper"] - features["bb_lower"]
    )

    # Find breakouts
    upper_breakout = features["bb_position"] > 1.0
    lower_breakout = features["bb_position"] < 0.0

    print(f"\nUpper band breakouts: {upper_breakout.sum()}")
    print(f"Lower band breakouts: {lower_breakout.sum()}")

    # Show recent volatility
    print("\nRecent volatility metrics:")
    recent = features.tail(5)
    print(
        recent[
            ["close", "bb_upper", "bb_lower", "bb_position", "atr_14"]
        ].to_string()
    )


def example_4_multi_ticker_analysis():
    """Example 4: Multi-ticker analysis"""
    print("\n" + "=" * 80)
    print("Example 4: Multi-Ticker Analysis")
    print("=" * 80)

    fm = FeatureManager()

    # Analyze multiple tech stocks
    tickers = ["AAPL", "GOOGL", "MSFT", "AMZN"]

    # Compute panel features
    panel = fm.compute_panel_features(
        tickers=tickers,
        start_date="2023-01-01",
        end_date="2023-12-31",
        feature_list=["close", "returns", "rsi_14", "atr_14", "volume_ratio"],
    )

    print(f"\nPanel dimensions: {panel.shape}")
    print(f"Tickers: {len(panel.index.get_level_values('ticker').unique())}")
    print(f"Dates: {len(panel.index.get_level_values('date').unique())}")

    # Find oversold stocks on latest date
    latest_date = panel.index.get_level_values("date").max()
    latest_data = panel.xs(latest_date, level="date")

    oversold = latest_data[latest_data["rsi_14"] < 30]
    if len(oversold) > 0:
        print(f"\nOversold stocks ({latest_date.strftime('%Y-%m-%d')}):")
        print(oversold[["close", "rsi_14"]].to_string())
    else:
        print(f"\nNo oversold stocks on {latest_date.strftime('%Y-%m-%d')}")


def example_5_custom_indicators():
    """Example 5: Using individual indicators"""
    print("\n" + "=" * 80)
    print("Example 5: Custom Indicator Combinations")
    print("=" * 80)

    tech = TechnicalFeatures()
    fm = FeatureManager()

    # Get raw price data
    from data import DataManagerDB

    dm = DataManagerDB()
    prices = dm.get_prices("AAPL", "2023-01-01", "2023-12-31")

    if prices.empty:
        print("No price data available")
        return

    # Compute custom indicators
    print("\nComputing custom indicators...")

    # Multiple timeframe analysis
    sma_10 = tech.sma(prices["close"], 10)
    sma_20 = tech.sma(prices["close"], 20)
    sma_50 = tech.sma(prices["close"], 50)

    ema_12 = tech.ema(prices["close"], 12)
    ema_26 = tech.ema(prices["close"], 26)

    rsi_14 = tech.rsi(prices["close"], 14)

    # Golden cross (SMA 50 crosses above SMA 200)
    sma_200 = tech.sma(prices["close"], 200)
    golden_cross = (sma_50 > sma_200) & (sma_50.shift(1) <= sma_200.shift(1))

    print(f"Golden cross signals: {golden_cross.sum()}")

    # Triple moving average strategy
    triple_bullish = (sma_10 > sma_20) & (sma_20 > sma_50)
    triple_bearish = (sma_10 < sma_20) & (sma_20 < sma_50)

    print(f"Triple bullish periods: {triple_bullish.sum()}")
    print(f"Triple bearish periods: {triple_bearish.sum()}")


def example_6_feature_stats():
    """Example 6: Feature statistics and metadata"""
    print("\n" + "=" * 80)
    print("Example 6: Feature Statistics")
    print("=" * 80)

    fm = FeatureManager()

    # Get available features
    all_features = fm.get_feature_list("all")
    momentum_features = fm.get_feature_list("momentum")
    volatility_features = fm.get_feature_list("volatility")

    print(f"\nTotal features available: {len(all_features)}")
    print(f"Momentum features: {len(momentum_features)}")
    print(f"Volatility features: {len(volatility_features)}")

    print("\nMomentum features:")
    for feat in momentum_features[:10]:
        print(f"  - {feat}")

    # Get database stats
    try:
        stats = fm.get_feature_stats()
        print("\nFeature store statistics:")
        print(f"  Total feature rows: {stats['total_feature_rows']}")
        print(f"  Unique tickers: {stats['unique_tickers']}")
        print(f"  Unique features: {stats['unique_feature_names']}")
        if stats["date_range"]["start"]:
            print(
                f"  Date range: {stats['date_range']['start']} to {stats['date_range']['end']}"
            )
    except Exception as e:
        print(f"\nNo features in database yet: {e}")


def example_7_rl_features():
    """Example 7: Feature engineering for RL"""
    print("\n" + "=" * 80)
    print("Example 7: RL Feature Engineering")
    print("=" * 80)

    fm = FeatureManager()

    # Create normalized features for RL
    features = fm.compute_features(
        ticker="AAPL",
        start_date="2022-01-01",
        end_date="2023-12-31",
        feature_set="all",
    )

    # Select key features
    rl_features = features[
        [
            "returns",
            "price_to_sma20",
            "price_to_sma50",
            "rsi_14",
            "macd_histogram",
            "bb_position",
            "atr_14",
            "volume_ratio",
        ]
    ].copy()

    # Normalize features (rolling z-score)
    print("\nNormalizing features...")
    for col in rl_features.columns:
        mean = rl_features[col].rolling(252, min_periods=20).mean()
        std = rl_features[col].rolling(252, min_periods=20).std()
        rl_features[f"{col}_norm"] = (rl_features[col] - mean) / std

    # Remove NaN rows
    rl_features = rl_features.dropna()

    print(f"\nRL features shape: {rl_features.shape}")
    print("\nSample normalized features:")
    print(rl_features[[c for c in rl_features.columns if "_norm" in c]].tail())

    # Check for inf/nan
    has_inf = rl_features.isin([float("inf"), float("-inf")]).any().any()
    has_nan = rl_features.isna().any().any()

    print(f"\nHas infinite values: {has_inf}")
    print(f"Has NaN values: {has_nan}")

    if not has_inf and not has_nan:
        print("✓ Features ready for RL training!")


def main():
    """Run all examples"""
    print("\n")
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "TECHNICAL FEATURES EXAMPLES" + " " * 31 + "║")
    print("╚" + "=" * 78 + "╝")

    examples = [
        ("Basic Features", example_1_basic_features),
        ("Momentum Strategy", example_2_momentum_strategy),
        ("Volatility Analysis", example_3_volatility_analysis),
        ("Multi-Ticker", example_4_multi_ticker_analysis),
        ("Custom Indicators", example_5_custom_indicators),
        ("Feature Stats", example_6_feature_stats),
        ("RL Features", example_7_rl_features),
    ]

    for name, func in examples:
        try:
            func()
        except Exception as e:
            print(f"\n✗ Error in {name}: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 80)
    print("Examples completed!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()

