# data/validators.py
import pandas as pd
import numpy as np
from typing import Dict, List
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of data validation"""

    is_valid: bool
    quality_score: float
    issues: List[str]
    warnings: List[str]
    metadata: Dict


class DataValidator:
    """Comprehensive data quality validator for financial time series"""

    def __init__(
        self,
        min_quality_score: float = 0.7,
        max_missing_pct: float = 0.05,
        max_zero_volume_pct: float = 0.02,
        outlier_std_threshold: float = 10.0,
    ):
        """
        Initialize validator with quality thresholds

        Args:
            min_quality_score: Minimum acceptable quality score (0-1)
            max_missing_pct: Maximum percentage of missing data allowed
            max_zero_volume_pct: Maximum percentage of zero volume days allowed
            outlier_std_threshold: Standard deviations for outlier detection
        """
        self.min_quality_score = min_quality_score
        self.max_missing_pct = max_missing_pct
        self.max_zero_volume_pct = max_zero_volume_pct
        self.outlier_std_threshold = outlier_std_threshold

    def validate_price_data(
        self, df: pd.DataFrame, ticker: str, required_columns: List[str] = None
    ) -> ValidationResult:
        """
        Comprehensive validation of OHLCV price data

        Args:
            df: DataFrame with OHLCV data
            ticker: Stock ticker for logging
            required_columns: List of required columns

        Returns:
            ValidationResult with detailed quality assessment
        """
        if required_columns is None:
            required_columns = ["Open", "High", "Low", "Close", "Volume"]

        issues = []
        warnings = []
        scores = {}

        # Check 1: Required columns present
        missing_cols = set(required_columns) - set(df.columns)
        if missing_cols:
            issues.append(f"Missing required columns: {missing_cols}")
            return ValidationResult(
                is_valid=False,
                quality_score=0.0,
                issues=issues,
                warnings=warnings,
                metadata={},
            )

        # Check 2: Sufficient data points
        min_rows = 30  # At least one month of trading days
        if len(df) < min_rows:
            issues.append(f"Insufficient data: {len(df)} rows (minimum {min_rows})")
            scores["data_completeness"] = 0.0
        else:
            scores["data_completeness"] = min(1.0, len(df) / 252)  # Normalize to year

        # Check 3: Missing values
        missing_pct = df[required_columns].isnull().sum().sum() / (
            len(df) * len(required_columns)
        )
        scores["missing_data"] = 1.0 - min(1.0, missing_pct / self.max_missing_pct)

        if missing_pct > self.max_missing_pct:
            issues.append(f"Too many missing values: {missing_pct:.2%}")
        elif missing_pct > 0:
            warnings.append(f"Some missing values: {missing_pct:.2%}")

        # Check 4: OHLC consistency
        if all(col in df.columns for col in ["Open", "High", "Low", "Close"]):
            ohlc_valid = self._validate_ohlc_consistency(df)
            scores["ohlc_consistency"] = ohlc_valid["score"]

            if ohlc_valid["violations"] > 0:
                violation_pct = ohlc_valid["violations"] / len(df)
                if violation_pct > 0.01:  # More than 1% violations
                    issues.append(
                        f"OHLC consistency violations: {ohlc_valid['violations']} "
                        f"({violation_pct:.2%})"
                    )
                else:
                    warnings.append(
                        f"Minor OHLC inconsistencies: {ohlc_valid['violations']} rows"
                    )

        # Check 5: Price continuity (no unrealistic gaps)
        if "Close" in df.columns:
            continuity = self._check_price_continuity(df["Close"], ticker)
            scores["price_continuity"] = continuity["score"]

            if continuity["large_gaps"] > 0:
                warnings.append(
                    f"Large price gaps detected: {continuity['large_gaps']} instances"
                )

        # Check 6: Volume validation
        if "Volume" in df.columns:
            volume_check = self._validate_volume(df["Volume"])
            scores["volume_quality"] = volume_check["score"]

            if volume_check["zero_pct"] > self.max_zero_volume_pct:
                issues.append(
                    f"Too many zero volume days: {volume_check['zero_pct']:.2%}"
                )
            elif volume_check["zero_pct"] > 0:
                warnings.append(
                    f"Some zero volume days: {volume_check['zero_pct']:.2%}"
                )

        # Check 7: Outlier detection
        if "Close" in df.columns:
            outliers = self._detect_outliers(df["Close"])
            scores["outlier_check"] = outliers["score"]

            if outliers["count"] > 0:
                outlier_pct = outliers["count"] / len(df)
                if outlier_pct > 0.05:  # More than 5% outliers
                    issues.append(
                        f"Excessive outliers: {outliers['count']} ({outlier_pct:.2%})"
                    )
                else:
                    warnings.append(f"Outliers detected: {outliers['count']}")

        # Check 8: Duplicate timestamps
        if df.index.duplicated().any():
            dup_count = df.index.duplicated().sum()
            issues.append(f"Duplicate timestamps: {dup_count}")
            scores["uniqueness"] = 1.0 - (dup_count / len(df))
        else:
            scores["uniqueness"] = 1.0

        # Check 9: Chronological order
        if not df.index.is_monotonic_increasing:
            issues.append("Data not in chronological order")
            scores["chronological"] = 0.0
        else:
            scores["chronological"] = 1.0

        # Calculate overall quality score
        quality_score = np.mean(list(scores.values())) if scores else 0.0
        is_valid = len(issues) == 0 and quality_score >= self.min_quality_score

        metadata = {
            "ticker": ticker,
            "row_count": len(df),
            "date_range": (df.index.min(), df.index.max())
            if len(df) > 0
            else (None, None),
            "missing_pct": missing_pct,
            "component_scores": scores,
        }

        return ValidationResult(
            is_valid=is_valid,
            quality_score=quality_score,
            issues=issues,
            warnings=warnings,
            metadata=metadata,
        )

    def _validate_ohlc_consistency(self, df: pd.DataFrame) -> Dict:
        """Check that High >= Low, High >= Open/Close, Low <= Open/Close"""
        violations = 0

        # High should be highest
        violations += (df["High"] < df["Low"]).sum()
        violations += (df["High"] < df["Open"]).sum()
        violations += (df["High"] < df["Close"]).sum()

        # Low should be lowest
        violations += (df["Low"] > df["Open"]).sum()
        violations += (df["Low"] > df["Close"]).sum()

        score = 1.0 - min(1.0, violations / len(df))

        return {"violations": violations, "score": score}

    def _check_price_continuity(self, prices: pd.Series, ticker: str) -> Dict:
        """Check for unrealistic price gaps (e.g., stock splits, errors)"""
        returns = prices.pct_change().dropna()

        # Consider gaps > 50% in single day as potentially problematic
        large_gaps = (returns.abs() > 0.5).sum()

        # But some gaps might be legitimate (stock splits, etc.)
        # Score based on frequency
        gap_pct = large_gaps / len(returns) if len(returns) > 0 else 0
        score = 1.0 - min(1.0, gap_pct * 10)  # Penalize heavily

        return {"large_gaps": large_gaps, "score": score}

    def _validate_volume(self, volume: pd.Series) -> Dict:
        """Validate volume data"""
        # Check for negative volumes
        negative_count = (volume < 0).sum()

        # Check for zero volumes
        zero_count = (volume == 0).sum()
        zero_pct = zero_count / len(volume)

        # Check for unrealistic spikes (> 100x median)
        median_vol = volume.median()
        if median_vol > 0:
            spike_count = (volume > median_vol * 100).sum()
        else:
            spike_count = 0

        # Calculate score
        penalties = 0
        if negative_count > 0:
            penalties += 0.5
        penalties += min(0.3, zero_pct * 10)
        penalties += min(0.2, spike_count / len(volume))

        score = max(0.0, 1.0 - penalties)

        return {
            "zero_count": zero_count,
            "zero_pct": zero_pct,
            "negative_count": negative_count,
            "spike_count": spike_count,
            "score": score,
        }

    def _detect_outliers(self, prices: pd.Series) -> Dict:
        """Detect outliers using returns-based approach"""
        returns = prices.pct_change().dropna()

        if len(returns) < 10:
            return {"count": 0, "score": 1.0}

        # Use robust statistics (median, MAD)
        median_return = returns.median()
        mad = np.median(np.abs(returns - median_return))

        # Modified z-score
        if mad > 0:
            modified_z = 0.6745 * (returns - median_return) / mad
            outliers = (modified_z.abs() > self.outlier_std_threshold).sum()
        else:
            outliers = 0

        outlier_pct = outliers / len(returns)
        score = 1.0 - min(1.0, outlier_pct * 20)  # Heavy penalty for outliers

        return {"count": outliers, "score": score}

    def validate_fundamental_data(self, data: Dict, ticker: str) -> ValidationResult:
        """Validate fundamental data"""
        issues = []
        warnings = []

        if not data:
            issues.append("No fundamental data provided")
            return ValidationResult(
                is_valid=False,
                quality_score=0.0,
                issues=issues,
                warnings=warnings,
                metadata={"ticker": ticker},
            )

        # Check for key fundamental fields
        important_fields = [
            "marketCap",
            "peRatio",
            "pbRatio",
            "dividendYield",
            "eps",
            "revenue",
            "profitMargin",
        ]

        missing_fields = [
            f for f in important_fields if f not in data or data[f] is None
        ]

        if missing_fields:
            warnings.append(f"Missing fundamental fields: {missing_fields}")

        # Check for reasonable values
        score = 1.0 - (len(missing_fields) / len(important_fields))

        return ValidationResult(
            is_valid=score >= self.min_quality_score,
            quality_score=score,
            issues=issues,
            warnings=warnings,
            metadata={
                "ticker": ticker,
                "fields_present": len(important_fields) - len(missing_fields),
                "fields_total": len(important_fields),
            },
        )


class DataQualityReport:
    """Generate comprehensive data quality reports"""

    @staticmethod
    def generate_summary(
        validation_results: Dict[str, ValidationResult],
    ) -> pd.DataFrame:
        """
        Generate summary DataFrame from validation results

        Args:
            validation_results: Dict mapping ticker -> ValidationResult

        Returns:
            DataFrame with quality metrics per ticker
        """
        summary_data = []

        for ticker, result in validation_results.items():
            summary_data.append(
                {
                    "ticker": ticker,
                    "is_valid": result.is_valid,
                    "quality_score": result.quality_score,
                    "num_issues": len(result.issues),
                    "num_warnings": len(result.warnings),
                    "row_count": result.metadata.get("row_count", 0),
                    "missing_pct": result.metadata.get("missing_pct", 0),
                }
            )

        return pd.DataFrame(summary_data)

    @staticmethod
    def get_failed_tickers(
        validation_results: Dict[str, ValidationResult],
    ) -> List[str]:
        """Get list of tickers that failed validation"""
        return [
            ticker
            for ticker, result in validation_results.items()
            if not result.is_valid
        ]

    @staticmethod
    def get_quality_distribution(
        validation_results: Dict[str, ValidationResult],
    ) -> Dict[str, int]:
        """Get distribution of quality scores"""
        bins = {"excellent": 0, "good": 0, "fair": 0, "poor": 0}

        for result in validation_results.values():
            score = result.quality_score
            if score >= 0.9:
                bins["excellent"] += 1
            elif score >= 0.8:
                bins["good"] += 1
            elif score >= 0.7:
                bins["fair"] += 1
            else:
                bins["poor"] += 1

        return bins
