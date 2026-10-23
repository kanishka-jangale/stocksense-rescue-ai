"""
StockSense Rescue AI - Trending & Emerging Product Demand Analytics
Compares recent demand windows against multi-week baseline demand to distinguish
emerging breakouts from established high-volume staples and demand decay.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional
import numpy as np
import pandas as pd

from src.models import TrendAnalysis, Product


class TrendEngine:
    def __init__(self, recent_window_days: int = 14, baseline_window_days: int = 46):
        self.recent_window_days = recent_window_days
        self.baseline_window_days = baseline_window_days

    def analyze_sales_history(
        self, sales_df: Optional[pd.DataFrame], products: List[Product]
    ) -> List[TrendAnalysis]:
        """Calculates demand momentum, classifies trend, and outputs actionable stocking guidance."""
        if sales_df is None or not isinstance(sales_df, pd.DataFrame) or sales_df.empty or "date" not in sales_df.columns:
            # Fallback if no historical sales data provided
            return [
                TrendAnalysis(
                    product_id=p.product_id,
                    product_name=p.product_name,
                    category=p.category,
                    baseline_daily_sales=p.avg_daily_sales,
                    recent_daily_sales=p.avg_daily_sales,
                    demand_change_pct=0.0,
                    trend_classification="Uncalibrated (No History)",
                    action_recommendation="Use Static Inventory Reorder",
                    action_explanation="No daily sales history available to establish trend slope. Using static velocity.",
                    confidence_score=0.3,
                )
                for p in products
            ]

        # Convert date to datetime
        df = sales_df.copy()
        df["date"] = pd.to_datetime(df["date"])
        max_date = df["date"].max()
        cutoff_recent = max_date - timedelta(days=self.recent_window_days)
        cutoff_baseline = cutoff_recent - timedelta(days=self.baseline_window_days)

        results = []
        product_dict = {p.product_id: p for p in products}

        for pid, prod in product_dict.items():
            p_sales = df[df["product_id"] == pid]
            if p_sales.empty:
                results.append(
                    TrendAnalysis(
                        product_id=pid,
                        product_name=prod.product_name,
                        category=prod.category,
                        baseline_daily_sales=0.0,
                        recent_daily_sales=0.0,
                        demand_change_pct=0.0,
                        trend_classification="No Activity Recorded",
                        action_recommendation="Investigate or Liquidate",
                        action_explanation="No sales transactions found in historical log.",
                        confidence_score=0.2,
                    )
                )
                continue

            recent_df = p_sales[p_sales["date"] > cutoff_recent]
            baseline_df = p_sales[(p_sales["date"] <= cutoff_recent) & (p_sales["date"] >= cutoff_baseline)]

            recent_total = recent_df["units_sold"].sum()
            recent_daily = recent_total / max(1, self.recent_window_days)

            baseline_total = baseline_df["units_sold"].sum()
            baseline_daily = baseline_total / max(1, self.baseline_window_days)

            # Avoid division by zero
            if baseline_daily > 0:
                change_pct = round(((recent_daily - baseline_daily) / baseline_daily) * 100.0, 1)
            else:
                change_pct = 100.0 if recent_daily > 0 else 0.0

            # Confidence score based on data density & regularity
            days_with_records = len(p_sales["date"].unique())
            record_completeness = min(1.0, days_with_records / (self.recent_window_days + self.baseline_window_days))
            # Standard deviation check for unusual spikes
            sales_std = float(p_sales["units_sold"].std()) if len(p_sales) > 1 else 0.0
            spike_penalty = 0.15 if sales_std > (baseline_daily * 2.5 + 1.0) else 0.0
            confidence_score = round(max(0.2, min(0.98, record_completeness - spike_penalty)), 2)

            # Classification logic
            if baseline_daily == 0 and recent_daily == 0:
                trend_class = "Dead Mover"
                action_rec = "Clearance / Do Not Restock"
                action_exp = f"0 sales over entire {days_with_records}-day tracking window. Capital is trapped in stagnant inventory."
            elif baseline_daily < 4.0 and change_pct >= 30.0:
                trend_class = "Emerging Demand Surge"
                action_rec = "Test Small Quantity (Pilot Order)"
                action_exp = (
                    f"Sales surged +{change_pct}% recently (from {baseline_daily:.1f}/day to {recent_daily:.1f}/day). "
                    "Recommend a measured pilot order to test sustained customer interest without overcommitting capital."
                )
            elif baseline_daily >= 4.0 and change_pct >= 10.0:
                trend_class = "Established High-Velocity Growth"
                action_rec = "Replenish Established (Bulk Savings)"
                action_exp = (
                    f"Strong established core seller maintaining high volume ({recent_daily:.1f}/day, +{change_pct}%). "
                    "Replenish with regional/wholesale suppliers to lock in volume discounts and prevent costly stockouts."
                )
            elif abs(change_pct) < 15.0 and recent_daily > 0:
                trend_class = "Stable Core Staple"
                action_rec = "Maintain Standard Cadence"
                action_exp = f"Predictable demand velocity ({recent_daily:.1f}/day). Maintain normal reorder cycle with supplier."
            elif change_pct <= -25.0:
                trend_class = "Softening / Demand Decay"
                action_rec = "Caution: Order Minimums Only"
                action_exp = f"Demand slowed by {change_pct}%. Avoid high MOQs to prevent overstocking."
            else:
                trend_class = "Moderate Movement"
                action_rec = "Normal Review"
                action_exp = f"Demand velocity at {recent_daily:.1f}/day with {change_pct}% change."

            results.append(
                TrendAnalysis(
                    product_id=pid,
                    product_name=prod.product_name,
                    category=prod.category,
                    baseline_daily_sales=round(baseline_daily, 2),
                    recent_daily_sales=round(recent_daily, 2),
                    demand_change_pct=change_pct,
                    trend_classification=trend_class,
                    action_recommendation=action_rec,
                    action_explanation=action_exp,
                    confidence_score=confidence_score,
                    data_period_days=days_with_records,
                )
            )

        return results
