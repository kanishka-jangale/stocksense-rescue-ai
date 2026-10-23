"""
StockSense Rescue AI - Budget-Aware Purchasing Optimizer
Implements deterministic, explainable multi-attribute priority scoring and
budget-constrained purchase allocation satisfying MOQs, landed costs, and lead times.
"""

from typing import Dict, List, Optional, Set
import uuid

from src.models import (
    Product,
    SupplierQuote,
    PurchasePlan,
    PurchaseRecommendationItem,
    InventoryRiskAnalysis,
    TrendAnalysis,
    PriceSegmentClassification,
)
from src.analytics.inventory_engine import InventoryEngine
from src.analytics.supplier_engine import SupplierEngine


class PurchaseOptimizer:
    def __init__(self, supplier_engine: Optional[SupplierEngine] = None):
        self.supplier_engine = supplier_engine or SupplierEngine()

    def generate_plan(
        self,
        products: List[Product],
        supplier_quotes: List[SupplierQuote],
        inventory_risks: List[InventoryRiskAnalysis],
        trend_analyses: Optional[List[TrendAnalysis]] = None,
        segment_classifications: Optional[List[PriceSegmentClassification]] = None,
        total_budget: float = 10000.0,
        target_categories: Optional[List[str]] = None,
        target_segments: Optional[List[str]] = None,
        max_delivery_days: Optional[int] = None,
        priority_product_ids: Optional[List[str]] = None,
        inventory_capacity_units: Optional[float] = None,
    ) -> PurchasePlan:
        """Constructs an optimal, budget-compliant purchase plan using deterministic priority heuristics."""
        plan_id = f"PLAN-{uuid.uuid4().hex[:8].upper()}"

        if total_budget <= 0:
            return PurchasePlan(
                plan_id=plan_id,
                total_budget=total_budget,
                total_allocated=0.0,
                remaining_budget=0.0,
                items=[],
                unsatisfied_constraints=["Provided purchasing budget is zero or negative. No purchases can be planned."],
                summary="Budget is zero; no purchase actions possible.",
            )

        # Index helper structures
        risk_map = {r.product_id: r for r in inventory_risks}
        trend_map = {t.product_id: t for t in (trend_analyses or [])}
        seg_map = {s.product_id: s for s in (segment_classifications or [])}
        prod_map = {p.product_id: p for p in products}

        candidates = []

        for p in products:
            pid = p.product_id

            # Apply Category filter
            if target_categories and p.category not in target_categories:
                continue

            # Apply Segment filter
            seg_info = seg_map.get(pid)
            if target_segments and seg_info and seg_info.price_segment not in target_segments:
                continue

            risk = risk_map.get(pid)
            trend = trend_map.get(pid)

            # Do not reorder dead movers with zero sales unless user explicitly prioritized them
            is_priority = bool(priority_product_ids and pid in priority_product_ids)
            if p.avg_daily_sales <= 0 and not is_priority:
                continue

            # Check if reorder is needed
            needed_qty = risk.suggested_reorder_qty if risk else 0.0
            if needed_qty <= 0 and not is_priority:
                continue

            # If priority item but suggested reorder was 0, set minimum 1 day of sales or safety stock
            if needed_qty <= 0 and is_priority:
                needed_qty = max(p.safety_stock, p.avg_daily_sales * 5) or 5.0

            # Find suitable suppliers
            quotes = [q for q in supplier_quotes if q.product_id == pid]
            if max_delivery_days is not None:
                quotes = [q for q in quotes if q.delivery_lead_time_days <= max_delivery_days]

            if not quotes:
                continue

            # Select supplier based on urgency
            days_stock = risk.days_of_stock_remaining if risk else 15.0
            if days_stock <= 3.0:
                # Urgent: prefer fastest supplier to avert immediate stockout
                best_quote = self.supplier_engine.find_best_supplier(pid, quotes, criterion="fastest", needed_qty=needed_qty)
            else:
                # Normal: prefer best overall fit (balance between landed cost and MOQ)
                best_quote = self.supplier_engine.find_best_supplier(pid, quotes, criterion="best_fit", needed_qty=needed_qty)

            if not best_quote:
                continue

            # Calculate priority urgency score (0 - 100)
            urgency_score = 0.0

            # Stockout urgency component (up to 45 pts)
            if days_stock <= 1.0:
                urgency_score += 45.0
            elif days_stock <= 3.0:
                urgency_score += 35.0
            elif days_stock <= 7.0:
                urgency_score += 25.0
            elif days_stock <= 14.0:
                urgency_score += 15.0

            # Demand trend momentum component (up to 25 pts)
            if trend:
                if "Emerging" in trend.trend_classification:
                    urgency_score += 25.0
                elif "Established" in trend.trend_classification:
                    urgency_score += 20.0
                elif "Stable" in trend.trend_classification:
                    urgency_score += 10.0
                elif "Softening" in trend.trend_classification:
                    urgency_score -= 10.0

            # Margin contribution component (up to 15 pts)
            margin = p.gross_margin_pct
            if margin >= 35.0:
                urgency_score += 15.0
            elif margin >= 20.0:
                urgency_score += 10.0
            elif margin >= 10.0:
                urgency_score += 5.0

            # Priority boost (up to 15 pts)
            if is_priority:
                urgency_score += 20.0

            # Expiry risk penalty: if currently holding high expiry risk, penalize heavy reorders
            if risk and "Critical" in risk.expiry_risk_level:
                urgency_score -= 25.0

            urgency_score = max(5.0, min(100.0, urgency_score))

            candidates.append({
                "product": p,
                "quote": best_quote,
                "needed_qty": needed_qty,
                "urgency_score": round(urgency_score, 1),
                "risk": risk,
                "trend": trend,
                "segment": seg_info.price_segment if seg_info else "Standard/Mid-Range",
            })

        # Sort candidates deterministically by Urgency Score descending
        candidates.sort(key=lambda x: x["urgency_score"], reverse=True)

        # Greedy allocation respecting Budget, MOQs, and Capacity
        allocated_items: List[PurchaseRecommendationItem] = []
        remaining_budget = total_budget
        unsatisfied = []
        total_units_allocated = 0.0

        for cand in candidates:
            p = cand["product"]
            q = cand["quote"]
            risk = cand["risk"]
            trend = cand["trend"]

            # Order quantity must respect supplier MOQ
            order_qty = max(cand["needed_qty"], q["min_order_qty"])

            # Check capacity constraint
            if inventory_capacity_units is not None:
                if (total_units_allocated + order_qty) > inventory_capacity_units:
                    unsatisfied.append(f"Skipped {p.product_name}: exceeds maximum storage capacity of {inventory_capacity_units} units.")
                    continue

            # Calculate landed costs
            gross = order_qty * q["base_unit_price"]
            discount = gross * (q["discount_pct"] / 100.0)
            net_items = gross - discount
            total_item_landed = net_items + q["delivery_charge"]
            unit_landed = total_item_landed / order_qty if order_qty > 0 else q["base_unit_price"]

            if total_item_landed <= remaining_budget:
                # Build narrative benefits and risks
                benefit_parts = []
                risk_parts = []

                if risk and risk.days_of_stock_remaining <= 3.0:
                    urgency_reason = f"Imminent stockout ({risk.days_of_stock_remaining:.1f} days remaining)"
                    benefit_parts.append("Protects daily revenue flow and customer retention")
                elif trend and "Emerging" in trend.trend_classification:
                    urgency_reason = f"Surging customer demand (+{trend.demand_change_pct}%)"
                    benefit_parts.append("Captures trending category demand before competitors")
                else:
                    urgency_reason = "Maintaining target safety stock and buffer"
                    benefit_parts.append("Maintains supply continuity")

                if q["delivery_lead_time_days"] <= 2:
                    benefit_parts.append(f"Fast delivery ({q['delivery_lead_time_days']} days via {q['supplier_scale']})")
                if q["discount_pct"] > 0:
                    benefit_parts.append(f"{q['discount_pct']}% negotiated supplier volume discount")

                if q["delivery_lead_time_days"] > (risk.days_of_stock_remaining if risk else 99):
                    risk_parts.append("Lead time exceeds days of remaining stock: potential temporary outage before arrival")
                if order_qty > (p.avg_daily_sales * 30) and p.avg_daily_sales > 0:
                    risk_parts.append("MOQ covers >30 days of sales; monitor holding cost")
                if not risk_parts:
                    risk_parts.append("Low operational risk; verified supplier track record")

                item = PurchaseRecommendationItem(
                    product_id=p.product_id,
                    product_name=p.product_name,
                    category=p.category,
                    price_segment=cand["segment"],
                    supplier_id=q["supplier_id"],
                    supplier_name=q["business_name"],
                    supplier_scale=q["supplier_scale"],
                    quantity=order_qty,
                    unit_purchase_price=q["base_unit_price"],
                    discount_pct=q["discount_pct"],
                    allocated_delivery=q["delivery_charge"],
                    effective_unit_cost=round(unit_landed, 2),
                    total_cost=round(total_item_landed, 2),
                    urgency_score=cand["urgency_score"],
                    reason_for_urgency=urgency_reason,
                    expected_benefit="; ".join(benefit_parts),
                    key_risk="; ".join(risk_parts),
                    lead_time_days=q["delivery_lead_time_days"],
                    stockout_days_remaining=risk.days_of_stock_remaining if risk else 999.0,
                )

                allocated_items.append(item)
                remaining_budget -= total_item_landed
                remaining_budget = round(remaining_budget, 2)
                total_units_allocated += order_qty
            else:
                unsatisfied.append(
                    f"Insufficient budget for {p.product_name}: Requires ₹{total_item_landed:.2f} (MOQ {q['min_order_qty']}), but only ₹{remaining_budget:.2f} remaining."
                )

        total_allocated = round(total_budget - remaining_budget, 2)
        summary = (
            f"Generated purchase plan allocating ₹{total_allocated:,.2f} across {len(allocated_items)} priority items "
            f"from available budget of ₹{total_budget:,.2f} (₹{remaining_budget:,.2f} remaining)."
        )

        return PurchasePlan(
            plan_id=plan_id,
            total_budget=round(total_budget, 2),
            total_allocated=total_allocated,
            remaining_budget=round(remaining_budget, 2),
            items=allocated_items,
            unsatisfied_constraints=unsatisfied,
            summary=summary,
        )
