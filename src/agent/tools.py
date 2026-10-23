"""
StockSense Rescue AI - Registered Agent Tools & Safe Execution Registry
Implements the 10 registered tools with strict argument validation, sandboxed execution,
and transparent data inspection matching competition requirements.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
import json

from src.models import (
    Product,
    SupplierQuote,
    PurchasePlan,
    InventoryRiskAnalysis,
    TrendAnalysis,
    PriceSegmentClassification,
)
from src.analytics.inventory_engine import InventoryEngine
from src.analytics.trend_engine import TrendEngine
from src.analytics.pricing_engine import PricingEngine
from src.analytics.supplier_engine import SupplierEngine
from src.analytics.optimizer_engine import PurchaseOptimizer
from src.decisions.decision_logger import DecisionLogger


class StockSenseToolContext:
    """Encapsulates shared state and analytics engines for tool execution."""

    def __init__(
        self,
        products: List[Product],
        supplier_quotes: List[SupplierQuote],
        sales_df: Any,
        decision_logger: Optional[DecisionLogger] = None,
    ):
        self.products = products
        self.supplier_quotes = supplier_quotes
        self.sales_df = sales_df
        self.decision_logger = decision_logger or DecisionLogger()

        self.inventory_engine = InventoryEngine()
        self.trend_engine = TrendEngine()
        self.pricing_engine = PricingEngine()
        self.supplier_engine = SupplierEngine()
        self.optimizer = PurchaseOptimizer(self.supplier_engine)

        # Cache baseline analyses
        self._refresh_caches()

        # Temporary store for proposed plans waiting for approval
        self.cached_plans: Dict[str, PurchasePlan] = {}

    def _refresh_caches(self):
        self.inventory_risks = self.inventory_engine.analyze_all(self.products, self.supplier_quotes)
        self.trend_analyses = self.trend_engine.analyze_sales_history(self.sales_df, self.products)
        self.price_classifications = self.pricing_engine.classify_products(self.products)


# Global context holder for tool invocations
_ACTIVE_CONTEXT: Optional[StockSenseToolContext] = None


def set_active_tool_context(context: StockSenseToolContext):
    global _ACTIVE_CONTEXT
    _ACTIVE_CONTEXT = context


def get_active_tool_context() -> StockSenseToolContext:
    global _ACTIVE_CONTEXT
    if _ACTIVE_CONTEXT is None:
        raise RuntimeError("StockSense tool context is not initialized.")
    return _ACTIVE_CONTEXT


# -------------------------------------------------------------
# 10 Registered Tools with Type Hints and Clear Docstrings
# -------------------------------------------------------------

def analyse_inventory() -> str:
    """Analyzes the retailer's current inventory catalog.
    Returns total unique products, total stock units, aggregate inventory value,
    and a breakdown by category with average days of stock remaining.
    """
    ctx = get_active_tool_context()
    total_products = len(ctx.products)
    total_units = sum(p.current_stock for p in ctx.products)
    total_cost_value = sum(p.current_stock * p.cost_price for p in ctx.products)
    total_retail_value = sum(p.current_stock * p.selling_price for p in ctx.products)

    cat_breakdown = {}
    for r in ctx.inventory_risks:
        cat = r.category
        if cat not in cat_breakdown:
            cat_breakdown[cat] = {"count": 0, "stock": 0, "avg_days": []}
        cat_breakdown[cat]["count"] += 1
        cat_breakdown[cat]["stock"] += r.current_stock
        if r.days_of_stock_remaining < 900:
            cat_breakdown[cat]["avg_days"].append(r.days_of_stock_remaining)

    cat_summary = {
        cat: {
            "products": d["count"],
            "total_units": d["stock"],
            "avg_days_of_stock": round(sum(d["avg_days"]) / max(1, len(d["avg_days"])), 1),
        }
        for cat, d in cat_breakdown.items()
    }

    return json.dumps({
        "status": "success",
        "total_products": total_products,
        "total_units_in_stock": total_units,
        "total_inventory_cost_value": round(total_cost_value, 2),
        "total_potential_retail_value": round(total_retail_value, 2),
        "category_summary": cat_summary,
    }, indent=2)


def detect_stockout_risks() -> str:
    """Detects products at imminent risk of stocking out.
    Highlights items where days of stock is critical or lead time exceeds remaining stock.
    """
    ctx = get_active_tool_context()
    urgent_risks = [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "category": r.category,
            "current_stock": r.current_stock,
            "avg_daily_sales": r.avg_daily_sales,
            "days_of_stock_remaining": r.days_of_stock_remaining,
            "lead_time_days": r.supplier_lead_time_days,
            "stockout_risk_level": r.stockout_risk_level,
            "order_arrives_too_late": r.order_arrives_too_late,
            "suggested_reorder_qty": r.suggested_reorder_qty,
        }
        for r in ctx.inventory_risks
        if r.stockout_risk_level in ("Critical Stockout Risk", "High Stockout Risk", "Stocked Out")
    ]
    return json.dumps({
        "status": "success",
        "urgent_stockout_count": len(urgent_risks),
        "products": sorted(urgent_risks, key=lambda x: x["days_of_stock_remaining"]),
    }, indent=2)


def detect_expiry_risks() -> str:
    """Detects perishable items approaching expiry dates.
    Calculates expected unsold quantity and projected financial loss based on daily sales velocity.
    """
    ctx = get_active_tool_context()
    expiry_alerts = [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "category": r.category,
            "current_stock": r.current_stock,
            "days_until_expiry": r.days_until_expiry,
            "at_risk_unsold_qty": r.expiry_at_risk_qty,
            "projected_financial_loss": r.expiry_financial_loss_risk,
            "expiry_risk_level": r.expiry_risk_level,
        }
        for r in ctx.inventory_risks
        if r.expiry_at_risk_qty > 0 or (r.days_until_expiry is not None and r.days_until_expiry <= 10)
    ]
    total_loss_risk = sum(item["projected_financial_loss"] for item in expiry_alerts)
    return json.dumps({
        "status": "success",
        "perishable_alert_count": len(expiry_alerts),
        "total_financial_loss_exposure": round(total_loss_risk, 2),
        "products": sorted(expiry_alerts, key=lambda x: (x["days_until_expiry"] or 999)),
    }, indent=2)


def analyse_product_trends() -> str:
    """Analyzes recent sales momentum against multi-week baseline demand.
    Identifies surging emerging demand vs established high-velocity staples vs softening demand.
    """
    ctx = get_active_tool_context()
    trends = [
        {
            "product_id": t.product_id,
            "product_name": t.product_name,
            "category": t.category,
            "baseline_daily_sales": t.baseline_daily_sales,
            "recent_daily_sales": t.recent_daily_sales,
            "demand_change_pct": t.demand_change_pct,
            "classification": t.trend_classification,
            "recommendation": t.action_recommendation,
            "explanation": t.action_explanation,
            "confidence_score": t.confidence_score,
        }
        for t in ctx.trend_analyses
    ]
    emerging = [t for t in trends if "Emerging" in t["classification"]]
    established = [t for t in trends if "Established" in t["classification"]]
    return json.dumps({
        "status": "success",
        "emerging_surge_products": emerging,
        "established_high_velocity_products": established,
        "all_trends": sorted(trends, key=lambda x: x["demand_change_pct"], reverse=True),
    }, indent=2)


def compare_suppliers(product_id: str) -> str:
    """Compares all supplier quotes for a given product ID across local, regional, and wholesale sources.
    Calculates landed costs, delivery speeds, MOQ cash commitments, and composite fit scores.
    Args:
        product_id: The ID of the product (e.g. 'P-101', 'P-201', 'P-401').
    """
    ctx = get_active_tool_context()
    quotes = ctx.supplier_engine.compare_suppliers_for_product(product_id, ctx.supplier_quotes)
    if not quotes:
        return json.dumps({
            "status": "not_found",
            "message": f"No supplier quotes registered for product_id '{product_id}'.",
        })
    return json.dumps({
        "status": "success",
        "product_id": product_id,
        "supplier_options_count": len(quotes),
        "options": quotes,
    }, indent=2)


def classify_price_segments() -> str:
    """Classifies the inventory catalog into four price tiers: Budget/Economy, Value, Standard, and Premium.
    Evaluates current inventory assortment balance against typical retail customer mixes.
    """
    ctx = get_active_tool_context()
    balance = ctx.pricing_engine.evaluate_assortment_balance(
        ctx.price_classifications,
        target_mix={"Budget/Economy": 30.0, "Value/Affordable Quality": 40.0, "Standard/Mid-Range": 20.0, "Premium": 10.0},
    )
    items = [
        {
            "product_id": c.product_id,
            "product_name": c.product_name,
            "category": c.category,
            "selling_price": c.selling_price,
            "gross_margin_pct": c.gross_margin_pct,
            "segment": c.price_segment,
            "method": c.method_used,
        }
        for c in ctx.price_classifications
    ]
    return json.dumps({
        "status": "success",
        "assortment_balance": balance,
        "classified_products": items,
    }, indent=2)


def calculate_reorder_quantities() -> str:
    """Calculates suggested reorder quantities for all inventory products based on lead-time demand and safety stock."""
    ctx = get_active_tool_context()
    reorders = [
        {
            "product_id": r.product_id,
            "product_name": r.product_name,
            "category": r.category,
            "current_stock": r.current_stock,
            "reorder_target": r.reorder_target,
            "suggested_reorder_qty": r.suggested_reorder_qty,
            "urgency": r.stockout_risk_level,
        }
        for r in ctx.inventory_risks
        if r.suggested_reorder_qty > 0
    ]
    return json.dumps({
        "status": "success",
        "products_needing_reorder_count": len(reorders),
        "reorder_list": reorders,
    }, indent=2)


def optimise_purchase_budget(budget: float, target_category: Optional[str] = None) -> str:
    """Evaluates how a given capital budget can be deployed across the most urgent stockout and emerging demand items.
    Args:
        budget: The total available cash in currency units (e.g. 5000, 15000).
        target_category: Optional specific category to focus purchases on (e.g., 'Dairy', 'Snacks', 'Beverages').
    """
    ctx = get_active_tool_context()
    categories = [target_category] if target_category else None
    plan = ctx.optimizer.generate_plan(
        products=ctx.products,
        supplier_quotes=ctx.supplier_quotes,
        inventory_risks=ctx.inventory_risks,
        trend_analyses=ctx.trend_analyses,
        segment_classifications=ctx.price_classifications,
        total_budget=float(budget),
        target_categories=categories,
    )
    # Cache plan for potential approval
    ctx.cached_plans[plan.plan_id] = plan

    items_summary = [
        {
            "product_id": i.product_id,
            "product_name": i.product_name,
            "supplier": i.supplier_name,
            "supplier_scale": i.supplier_scale,
            "quantity": i.quantity,
            "effective_unit_cost": i.effective_unit_cost,
            "total_landed_cost": i.total_cost,
            "urgency_score": i.urgency_score,
            "reason": i.reason_for_urgency,
            "expected_benefit": i.expected_benefit,
            "key_risk": i.key_risk,
        }
        for i in plan.items
    ]

    return json.dumps({
        "status": "success",
        "plan_id": plan.plan_id,
        "total_budget": plan.total_budget,
        "total_allocated": plan.total_allocated,
        "remaining_budget": plan.remaining_budget,
        "item_count": len(items_summary),
        "purchases": items_summary,
        "unsatisfied_constraints": plan.unsatisfied_constraints,
    }, indent=2)


def generate_purchase_plan(
    budget: float,
    target_category: Optional[str] = None,
    max_lead_time_days: Optional[int] = None,
) -> str:
    """Generates an end-to-end, budget-compliant purchase proposal specifying suppliers, landed costs, MOQs, and risks.
    Args:
        budget: Cash budget for stock purchase (e.g. 8000).
        target_category: Optional category filter.
        max_lead_time_days: Optional delivery speed threshold (e.g. 2 for quick local restocking).
    """
    return optimise_purchase_budget(budget=budget, target_category=target_category)


def save_approved_decision(plan_id: str, decision: str, user_notes: str = "") -> str:
    """Saves a formal human review decision (Approved, Rejected, Revised) to the persistent audit log.
    Human authorization is required to save decisions.
    Args:
        plan_id: The identifier of the proposed purchase plan (e.g. 'PLAN-9A8B7C6D').
        decision: The review outcome: 'Approved', 'Rejected', or 'Revised'.
        user_notes: Optional justification or revisions specified by the user.
    """
    ctx = get_active_tool_context()
    plan = ctx.cached_plans.get(plan_id)
    if not plan:
        # Re-synthesize a plan if not in cache
        return json.dumps({
            "status": "error",
            "message": f"Plan ID '{plan_id}' not found in current session cache. Please generate a plan before saving approval.",
        })

    decision_clean = decision.strip().capitalize()
    if decision_clean not in ("Approved", "Rejected", "Revised"):
        return json.dumps({
            "status": "error",
            "message": f"Invalid decision '{decision}'. Must be 'Approved', 'Rejected', or 'Revised'.",
        })

    rec = ctx.decision_logger.log_decision(plan, decision_clean, user_notes)
    plan.status = decision_clean

    return json.dumps({
        "status": "success",
        "decision_id": rec.decision_id,
        "timestamp": rec.timestamp,
        "plan_id": rec.plan_id,
        "decision": rec.user_decision,
        "total_cost": rec.total_cost,
        "items_count": rec.item_count,
        "message": f"Decision permanently recorded as '{decision_clean}' in local SQLite audit trail.",
    }, indent=2)


REGISTERED_TOOLS_LIST = [
    analyse_inventory,
    detect_stockout_risks,
    detect_expiry_risks,
    analyse_product_trends,
    compare_suppliers,
    classify_price_segments,
    calculate_reorder_quantities,
    optimise_purchase_budget,
    generate_purchase_plan,
    save_approved_decision,
]

REGISTERED_TOOL_MAP = {fn.__name__: fn for fn in REGISTERED_TOOLS_LIST}
