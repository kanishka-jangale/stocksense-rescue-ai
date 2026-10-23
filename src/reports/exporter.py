"""
StockSense Rescue AI - Reports & Data Exporter
Generates CSV and formatted data reports for inventory risks, expiry alerts,
trending demand, supplier comparisons, purchase orders, and audit history.
Includes required timestamps, assumption disclaimers, and data provenance tags.
"""

from datetime import datetime
import io
from typing import Dict, List, Optional, Any
import pandas as pd

from src.models import (
    InventoryRiskAnalysis,
    TrendAnalysis,
    PriceSegmentClassification,
    PurchasePlan,
)


class ReportExporter:
    def __init__(self, is_synthetic_data: bool = True):
        self.is_synthetic_data = is_synthetic_data
        self.provenance_tag = (
            "SYNTHETIC DEMO DATA (Retail FMCG Simulation)" if is_synthetic_data else "USER UPLOADED LIVE DATA"
        )

    def _add_metadata_header(self, title: str, assumptions: str) -> str:
        gen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
        header = (
            f"# StockSense Rescue AI Report: {title}\n"
            f"# Generated: {gen_time}\n"
            f"# Data Provenance: {self.provenance_tag}\n"
            f"# Assumptions & Logic: {assumptions}\n"
            f"# Notice: Purchase actions require manual review and approval prior to execution.\n"
        )
        return header

    def export_inventory_risks_csv(self, risks: List[InventoryRiskAnalysis]) -> str:
        df = pd.DataFrame([
            {
                "product_id": r.product_id,
                "product_name": r.product_name,
                "category": r.category,
                "current_stock": r.current_stock,
                "avg_daily_sales": r.avg_daily_sales,
                "days_of_stock_remaining": r.days_of_stock_remaining,
                "supplier_lead_time_days": r.supplier_lead_time_days,
                "reorder_target": r.reorder_target,
                "suggested_reorder_qty": r.suggested_reorder_qty,
                "stockout_risk_level": r.stockout_risk_level,
                "order_arrives_too_late": "YES" if r.order_arrives_too_late else "NO",
                "days_until_expiry": r.days_until_expiry if r.days_until_expiry is not None else "N/A",
                "expiry_at_risk_qty": r.expiry_at_risk_qty,
                "expiry_financial_loss_risk": r.expiry_financial_loss_risk,
                "expiry_risk_level": r.expiry_risk_level,
                "data_quality_warning": r.data_quality_warning or "None",
            }
            for r in risks
        ])
        meta = self._add_metadata_header(
            "Inventory & Expiry Risk Assessment",
            "Days of stock = current_stock / avg_daily_sales; Reorder target = lead_time_demand + safety_stock; Expiry risk calculated against sales velocity before expiry date."
        )
        return meta + df.to_csv(index=False)

    def export_trends_csv(self, trends: List[TrendAnalysis]) -> str:
        df = pd.DataFrame([
            {
                "product_id": t.product_id,
                "product_name": t.product_name,
                "category": t.category,
                "baseline_daily_sales": t.baseline_daily_sales,
                "recent_daily_sales": t.recent_daily_sales,
                "demand_change_pct": t.demand_change_pct,
                "trend_classification": t.trend_classification,
                "action_recommendation": t.action_recommendation,
                "action_explanation": t.action_explanation,
                "confidence_score": t.confidence_score,
                "data_period_days": t.data_period_days,
            }
            for t in trends
        ])
        meta = self._add_metadata_header(
            "Trending & Emerging Product Intelligence",
            "Baseline window = 46 days, Recent window = 14 days. Growth classified as Emerging Surge if low baseline and growth > 30%."
        )
        return meta + df.to_csv(index=False)

    def export_price_segments_csv(self, segments: List[PriceSegmentClassification]) -> str:
        df = pd.DataFrame([
            {
                "product_id": s.product_id,
                "product_name": s.product_name,
                "category": s.category,
                "selling_price": s.selling_price,
                "cost_price": s.cost_price,
                "gross_margin_pct": s.gross_margin_pct,
                "price_segment": s.price_segment,
                "method_used": s.method_used,
                "explanation": s.explanation,
            }
            for s in segments
        ])
        meta = self._add_metadata_header(
            "Smart Price Segmentation Matrix",
            "Products classified into 4 tiers (Budget, Value, Standard, Premium) based on category-specific thresholds or quantiles."
        )
        return meta + df.to_csv(index=False)

    def export_purchase_order_csv(self, plan: PurchasePlan) -> str:
        df = pd.DataFrame([
            {
                "product_id": i.product_id,
                "product_name": i.product_name,
                "category": i.category,
                "price_segment": i.price_segment,
                "supplier_id": i.supplier_id,
                "supplier_name": i.supplier_name,
                "supplier_scale": i.supplier_scale,
                "order_quantity": i.quantity,
                "unit_base_price": i.unit_purchase_price,
                "discount_pct": i.discount_pct,
                "allocated_delivery": i.allocated_delivery,
                "effective_unit_cost": i.effective_unit_cost,
                "total_landed_cost": i.total_cost,
                "urgency_score": i.urgency_score,
                "lead_time_days": i.lead_time_days,
                "urgency_reason": i.reason_for_urgency,
                "expected_benefit": i.expected_benefit,
                "primary_risk": i.key_risk,
            }
            for i in plan.items
        ])
        meta = self._add_metadata_header(
            f"Suggested Purchase Order (Plan: {plan.plan_id})",
            f"Budget limit: ₹{plan.total_budget:,.2f}; Total committed: ₹{plan.total_allocated:,.2f}; Remaining cash: ₹{plan.remaining_budget:,.2f}."
        )
        return meta + df.to_csv(index=False)

    def export_supplier_comparison_csv(self, comparison_data: List[Dict[str, Any]]) -> str:
        df = pd.DataFrame(comparison_data)
        meta = self._add_metadata_header(
            "Supplier Directory & Multi-Criteria Comparison",
            "Effective cost includes discounts & delivery fees. Fit score balances price, speed, MOQ, and reliability."
        )
        return meta + df.to_csv(index=False)

    def export_audit_trail_csv(self, decisions_df: pd.DataFrame) -> str:
        meta = self._add_metadata_header(
            "Human Approval & Decision Audit Trail",
            "Permanent record of user-approved, rejected, and revised inventory purchase orders."
        )
        return meta + decisions_df.to_csv(index=False)
