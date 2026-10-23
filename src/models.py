"""
StockSense Rescue AI - Data Models & Domain Schemas
Defines structured dataclasses and validations for inventory, suppliers, sales, risks, and plans.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Any


@dataclass
class Product:
    product_id: str
    product_name: str
    category: str
    current_stock: float
    avg_daily_sales: float
    cost_price: float
    selling_price: float
    safety_stock: float
    primary_supplier_id: str
    unit: str = "unit"
    expiry_date: Optional[str] = None
    min_reorder_qty: float = 1.0

    @property
    def gross_margin_pct(self) -> float:
        if self.selling_price <= 0:
            return 0.0
        return round(((self.selling_price - self.cost_price) / self.selling_price) * 100, 2)


@dataclass
class SupplierQuote:
    supplier_id: str
    business_name: str
    supplier_scale: str  # Local/Small, Regional Distributor, Large Wholesaler
    service_area: str
    product_id: str
    unit_purchase_price: float
    min_order_qty: float
    available_qty: float
    delivery_lead_time_days: int
    delivery_charge: float
    discount_pct: float
    return_policy: str
    reliability_score: float  # 0.0 - 1.0
    last_price_update: str

    def calculate_landed_cost(self, order_qty: float) -> Dict[str, float]:
        """Calculates landed cost including volume discount and allocated delivery."""
        qty = max(order_qty, self.min_order_qty)
        gross_item_cost = qty * self.unit_purchase_price
        discount_amount = gross_item_cost * (self.discount_pct / 100.0)
        net_item_cost = gross_item_cost - discount_amount
        total_landed = net_item_cost + self.delivery_charge
        effective_unit_cost = total_landed / qty if qty > 0 else self.unit_purchase_price
        return {
            "order_qty": qty,
            "gross_item_cost": round(gross_item_cost, 2),
            "discount_amount": round(discount_amount, 2),
            "net_item_cost": round(net_item_cost, 2),
            "delivery_charge": round(self.delivery_charge, 2),
            "total_landed_cost": round(total_landed, 2),
            "effective_unit_cost": round(effective_unit_cost, 2),
        }


@dataclass
class InventoryRiskAnalysis:
    product_id: str
    product_name: str
    category: str
    current_stock: float
    avg_daily_sales: float
    days_of_stock_remaining: float
    supplier_lead_time_days: int
    reorder_target: float
    suggested_reorder_qty: float
    stockout_risk_level: str  # Critical, High, Moderate, Healthy, Overstocked
    order_arrives_too_late: bool  # lead time > days of stock remaining
    days_until_expiry: Optional[int]
    expected_sales_before_expiry: Optional[float]
    expiry_at_risk_qty: float
    expiry_financial_loss_risk: float
    expiry_risk_level: str  # Critical, High, Medium, Low, None
    data_quality_warning: Optional[str] = None


@dataclass
class TrendAnalysis:
    product_id: str
    product_name: str
    category: str
    baseline_daily_sales: float
    recent_daily_sales: float
    demand_change_pct: float
    trend_classification: str  # Emerging Demand, Established High-Velocity, Stable, Softening, Inactive
    action_recommendation: str  # Test Small Quantity, Replenish Established, Maintain & Watch, Clearance / Promotional Discount
    action_explanation: str
    confidence_score: float  # 0.0 - 1.0 based on data completeness
    data_period_days: int = 60


@dataclass
class PriceSegmentClassification:
    product_id: str
    product_name: str
    category: str
    selling_price: float
    cost_price: float
    gross_margin_pct: float
    price_segment: str  # Budget/Economy, Value/Affordable Quality, Standard/Mid-Range, Premium
    method_used: str  # Category-Relative Quantiles or Category-Specific Thresholds
    explanation: str


@dataclass
class PurchaseRecommendationItem:
    product_id: str
    product_name: str
    category: str
    price_segment: str
    supplier_id: str
    supplier_name: str
    supplier_scale: str
    quantity: float
    unit_purchase_price: float
    discount_pct: float
    allocated_delivery: float
    effective_unit_cost: float
    total_cost: float
    urgency_score: float  # 0 to 100
    reason_for_urgency: str
    expected_benefit: str
    key_risk: str
    lead_time_days: int
    stockout_days_remaining: float


@dataclass
class PurchasePlan:
    plan_id: str
    total_budget: float
    total_allocated: float
    remaining_budget: float
    items: List[PurchaseRecommendationItem] = field(default_factory=list)
    unsatisfied_constraints: List[str] = field(default_factory=list)
    generation_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "Proposed"  # Proposed, Approved, Rejected, Revised
    summary: str = ""


@dataclass
class DecisionRecord:
    decision_id: str
    timestamp: str
    plan_id: str
    user_decision: str  # Approved, Rejected, Revised
    total_budget: float
    total_cost: float
    item_count: int
    user_notes: str
    raw_plan_summary: Dict[str, Any]
