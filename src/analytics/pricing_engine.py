"""
StockSense Rescue AI - Smart Price Segmentation Engine
Implements category-specific thresholds and category-relative quantile segmentation.
Identifies lower-cost, similar, and premium alternatives, and evaluates customer mix balance.
"""

from typing import Dict, List, Optional, Tuple
import pandas as pd
import numpy as np

from src.models import Product, PriceSegmentClassification


# Default category-specific price thresholds (currency units)
DEFAULT_CATEGORY_THRESHOLDS: Dict[str, Dict[str, float]] = {
    "Dairy": {"budget_max": 55.0, "value_max": 120.0, "standard_max": 220.0},
    "Staples": {"budget_max": 100.0, "value_max": 250.0, "standard_max": 450.0},
    "Beverages": {"budget_max": 60.0, "value_max": 170.0, "standard_max": 300.0},
    "Snacks": {"budget_max": 30.0, "value_max": 80.0, "standard_max": 140.0},
    "Personal Care": {"budget_max": 50.0, "value_max": 120.0, "standard_max": 300.0},
}


class PricingEngine:
    def __init__(
        self,
        category_thresholds: Optional[Dict[str, Dict[str, float]]] = None,
        use_relative_quantiles: bool = False,
    ):
        self.category_thresholds = category_thresholds or DEFAULT_CATEGORY_THRESHOLDS
        self.use_relative_quantiles = use_relative_quantiles

    def classify_products(self, products: List[Product]) -> List[PriceSegmentClassification]:
        """Classifies each product into Budget, Value, Standard, or Premium segment."""
        if not products:
            return []

        df = pd.DataFrame([
            {
                "product_id": p.product_id,
                "product_name": p.product_name,
                "category": p.category,
                "selling_price": p.selling_price,
                "cost_price": p.cost_price,
                "gross_margin_pct": p.gross_margin_pct,
            }
            for p in products
        ])

        classifications = []

        if self.use_relative_quantiles:
            # Category-relative quartile method (25th, 50th, 75th percentiles per category)
            for cat, group in df.groupby("category"):
                prices = group["selling_price"]
                if len(prices) >= 4:
                    q25 = float(prices.quantile(0.25))
                    q50 = float(prices.quantile(0.50))
                    q75 = float(prices.quantile(0.75))
                else:
                    # Fallback to category thresholds if fewer than 4 items
                    th = self.category_thresholds.get(cat, {"budget_max": 50, "value_max": 150, "standard_max": 300})
                    q25, q50, q75 = th["budget_max"], th["value_max"], th["standard_max"]

                for _, r in group.iterrows():
                    p = r["selling_price"]
                    if p <= q25:
                        seg = "Budget/Economy"
                        exp = f"Relative {cat} Quartile (<= {q25:.1f}): Entry-level price point for cost-conscious shoppers."
                    elif p <= q50:
                        seg = "Value/Affordable Quality"
                        exp = f"Relative {cat} Quartile ({q25:.1f} - {q50:.1f}): High value per unit, attractive mass-market appeal."
                    elif p <= q75:
                        seg = "Standard/Mid-Range"
                        exp = f"Relative {cat} Quartile ({q50:.1f} - {q75:.1f}): Established branded quality tier."
                    else:
                        seg = "Premium"
                        exp = f"Relative {cat} Quartile (> {q75:.1f}): High-margin specialty product targeting quality/luxury demand."

                    classifications.append(
                        PriceSegmentClassification(
                            product_id=r["product_id"],
                            product_name=r["product_name"],
                            category=cat,
                            selling_price=r["selling_price"],
                            cost_price=r["cost_price"],
                            gross_margin_pct=r["gross_margin_pct"],
                            price_segment=seg,
                            method_used="Category-Relative Quantiles (25/50/75th Percentiles)",
                            explanation=exp,
                        )
                    )
        else:
            # Category-specific explicit boundary thresholds
            for _, r in df.iterrows():
                cat = r["category"]
                p = r["selling_price"]
                th = self.category_thresholds.get(
                    cat, {"budget_max": 50.0, "value_max": 150.0, "standard_max": 300.0}
                )

                if p <= th["budget_max"]:
                    seg = "Budget/Economy"
                    exp = f"Category '{cat}' threshold <= {th['budget_max']:.1f}. Accessible for basic daily utility."
                elif p <= th["value_max"]:
                    seg = "Value/Affordable Quality"
                    exp = f"Category '{cat}' threshold {th['budget_max']:.1f} - {th['value_max']:.1f}. Balanced price-to-performance."
                elif p <= th["standard_max"]:
                    seg = "Standard/Mid-Range"
                    exp = f"Category '{cat}' threshold {th['value_max']:.1f} - {th['standard_max']:.1f}. Mainstream benchmark tier."
                else:
                    seg = "Premium"
                    exp = f"Category '{cat}' threshold > {th['standard_max']:.1f}. High-tier specialty formulation or packaging."

                classifications.append(
                    PriceSegmentClassification(
                        product_id=r["product_id"],
                        product_name=r["product_name"],
                        category=cat,
                        selling_price=r["selling_price"],
                        cost_price=r["cost_price"],
                        gross_margin_pct=r["gross_margin_pct"],
                        price_segment=seg,
                        method_used=f"Category-Specific Absolute Thresholds ({cat})",
                        explanation=exp,
                    )
                )

        return classifications

    def find_alternatives(
        self, target_product_id: str, products: List[Product], classifications: List[PriceSegmentClassification]
    ) -> Dict[str, List[Dict]]:
        """Finds lower-cost, similar-tier, and premium alternatives in the same category."""
        target_prod = next((p for p in products if p.product_id == target_product_id), None)
        if not target_prod:
            return {"cheaper": [], "similar": [], "premium": []}

        same_category = [p for p in products if p.category == target_prod.category and p.product_id != target_product_id]
        class_map = {c.product_id: c.price_segment for c in classifications}

        cheaper = []
        similar = []
        premium = []

        for p in same_category:
            diff_pct = ((p.selling_price - target_prod.selling_price) / target_prod.selling_price) * 100.0
            item_info = {
                "product_id": p.product_id,
                "product_name": p.product_name,
                "selling_price": p.selling_price,
                "price_segment": class_map.get(p.product_id, "Unknown"),
                "margin_pct": p.gross_margin_pct,
                "price_diff_pct": round(diff_pct, 1),
            }
            if diff_pct < -15.0:
                cheaper.append(item_info)
            elif abs(diff_pct) <= 15.0:
                similar.append(item_info)
            else:
                premium.append(item_info)

        return {
            "cheaper": sorted(cheaper, key=lambda x: x["selling_price"]),
            "similar": sorted(similar, key=lambda x: abs(x["price_diff_pct"])),
            "premium": sorted(premium, key=lambda x: x["selling_price"]),
        }

    def evaluate_assortment_balance(
        self, classifications: List[PriceSegmentClassification], target_mix: Dict[str, float]
    ) -> Dict[str, Any]:
        """Compares current inventory segment distribution against target customer mix."""
        total = len(classifications)
        if total == 0:
            return {}

        counts = {
            "Budget/Economy": 0,
            "Value/Affordable Quality": 0,
            "Standard/Mid-Range": 0,
            "Premium": 0,
        }
        for c in classifications:
            counts[c.price_segment] = counts.get(c.price_segment, 0) + 1

        actual_mix = {k: round((v / total) * 100.0, 1) for k, v in counts.items()}
        variance = {k: round(actual_mix.get(k, 0.0) - target_mix.get(k, 25.0), 1) for k in counts}

        recommendations = []
        for seg, gap in variance.items():
            if gap < -10.0:
                recommendations.append(f"Under-indexed in {seg} ({actual_mix[seg]}% vs target {target_mix.get(seg)}%). Prioritize stocking items in this segment.")
            elif gap > 15.0:
                recommendations.append(f"Over-indexed in {seg} ({actual_mix[seg]}% vs target {target_mix.get(seg)}%). Consider moderating reorders in this segment.")

        return {
            "counts": counts,
            "actual_mix": actual_mix,
            "target_mix": target_mix,
            "variance": variance,
            "recommendations": recommendations,
        }
