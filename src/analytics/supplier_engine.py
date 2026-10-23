"""
StockSense Rescue AI - Small-to-Large Supplier Intelligence Engine
Evaluates supplier quotes across Local, Regional, and Wholesaler tiers.
Calculates landed costs, minimum cash commitments, delivery lead time impacts,
and composite multi-factor fit scores with transparent trade-off explanations.
"""

from typing import Dict, List, Optional, Any
import pandas as pd

from src.models import SupplierQuote, Product


class SupplierEngine:
    def __init__(self, cost_weight: float = 0.40, speed_weight: float = 0.25, moq_weight: float = 0.15, reliability_weight: float = 0.20):
        self.cost_weight = cost_weight
        self.speed_weight = speed_weight
        self.moq_weight = moq_weight
        self.reliability_weight = reliability_weight

    def compare_suppliers_for_product(
        self, product_id: str, supplier_quotes: List[SupplierQuote], desired_qty: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """Compares all supplier quotes for a given product and generates multi-criteria scores."""
        matched = [q for q in supplier_quotes if q.product_id == product_id]
        if not matched:
            return []

        results = []
        for q in matched:
            eval_qty = desired_qty if (desired_qty and desired_qty >= q.min_order_qty) else q.min_order_qty
            landed = q.calculate_landed_cost(eval_qty)

            results.append({
                "supplier_id": q.supplier_id,
                "business_name": q.business_name,
                "supplier_scale": q.supplier_scale,
                "service_area": q.service_area,
                "product_id": q.product_id,
                "base_unit_price": q.unit_purchase_price,
                "discount_pct": q.discount_pct,
                "delivery_charge": q.delivery_charge,
                "order_qty": landed["order_qty"],
                "min_order_qty": q.min_order_qty,
                "total_landed_cost": landed["total_landed_cost"],
                "effective_unit_cost": landed["effective_unit_cost"],
                "delivery_lead_time_days": q.delivery_lead_time_days,
                "available_qty": q.available_qty,
                "reliability_score": q.reliability_score,
                "return_policy": q.return_policy,
                "last_price_update": q.last_price_update,
            })

        # Normalize metrics to compute composite Fit Score (0 to 100)
        min_cost = min(r["effective_unit_cost"] for r in results)
        max_cost = max(r["effective_unit_cost"] for r in results)
        min_lead = min(r["delivery_lead_time_days"] for r in results)
        max_lead = max(r["delivery_lead_time_days"] for r in results)
        min_moq = min(r["min_order_qty"] for r in results)
        max_moq = max(r["min_order_qty"] for r in results)

        for r in results:
            # Cost score: 1.0 if lowest cost, lower if expensive
            cost_norm = 1.0 if max_cost == min_cost else 1.0 - ((r["effective_unit_cost"] - min_cost) / (max_cost - min_cost))
            # Speed score: 1.0 if fastest lead time
            speed_norm = 1.0 if max_lead == min_lead else 1.0 - ((r["delivery_lead_time_days"] - min_lead) / (max_lead - min_lead))
            # MOQ score: 1.0 if lowest MOQ (best for small retailer liquidity)
            moq_norm = 1.0 if max_moq == min_moq else 1.0 - ((r["min_order_qty"] - min_moq) / (max_moq - min_moq))
            # Reliability score is directly 0.0 to 1.0
            rel_norm = r["reliability_score"]

            composite_score = (
                (cost_norm * self.cost_weight)
                + (speed_norm * self.speed_weight)
                + (moq_norm * self.moq_weight)
                + (rel_norm * self.reliability_weight)
            ) * 100.0

            r["fit_score"] = round(composite_score, 1)

            # Build transparent trade-off explanation
            tradeoffs = []
            if r["effective_unit_cost"] == min_cost:
                tradeoffs.append("Lowest unit landed cost")
            if r["delivery_lead_time_days"] == min_lead:
                tradeoffs.append("Fastest delivery")
            if r["min_order_qty"] == min_moq:
                tradeoffs.append("Lowest initial cash lockup (MOQ)")
            if r["reliability_score"] >= 0.95:
                tradeoffs.append("High fulfilment reliability")

            warnings = []
            if r["delivery_lead_time_days"] > 4:
                warnings.append(f"Long lead time ({r['delivery_lead_time_days']} days)")
            if r["min_order_qty"] > 25:
                warnings.append(f"High MOQ ({r['min_order_qty']} units)")
            if r["reliability_score"] < 0.90:
                warnings.append(f"Moderate fulfilment reliability ({int(r['reliability_score']*100)}%)")

            r["key_advantages"] = ", ".join(tradeoffs) if tradeoffs else "Standard terms"
            r["trade_off_caveat"] = ", ".join(warnings) if warnings else "Well-balanced option"

        return sorted(results, key=lambda x: x["fit_score"], reverse=True)

    def find_best_supplier(
        self,
        product_id: str,
        supplier_quotes: List[SupplierQuote],
        criterion: str = "best_fit",  # "lowest_cost", "fastest", "lowest_moq", "best_fit"
        needed_qty: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Returns the optimal supplier according to selected operational criterion."""
        compared = self.compare_suppliers_for_product(product_id, supplier_quotes, needed_qty)
        if not compared:
            return None

        if criterion == "lowest_cost":
            return min(compared, key=lambda x: x["effective_unit_cost"])
        elif criterion == "fastest":
            return min(compared, key=lambda x: (x["delivery_lead_time_days"], x["effective_unit_cost"]))
        elif criterion == "lowest_moq":
            return min(compared, key=lambda x: (x["min_order_qty"], x["effective_unit_cost"]))
        else:
            return compared[0]  # sorted by highest fit_score
