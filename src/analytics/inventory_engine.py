"""
StockSense Rescue AI - Inventory & Expiry Rescue Analytics Engine
Implements deterministic, transparent inventory math, stockout risk scoring,
expiry loss estimation, and supplier lead-time arrival checks.
"""

from datetime import datetime, date
from typing import Dict, List, Optional
import math

from src.models import Product, SupplierQuote, InventoryRiskAnalysis


class InventoryEngine:
    def __init__(self, reference_date: Optional[date] = None):
        self.reference_date = reference_date or datetime.now().date()

    def analyze_product_inventory(
        self, product: Product, supplier_quotes: Optional[List[SupplierQuote]] = None
    ) -> InventoryRiskAnalysis:
        """Performs rigorous inventory and expiry risk calculations for a single product."""
        # 1. Determine supplier lead time
        lead_time_days = 3  # default fallback
        if supplier_quotes:
            matched_quotes = [q for q in supplier_quotes if q.product_id == product.product_id]
            if matched_quotes:
                # Prefer primary supplier quote, else lowest lead time
                primary = [q for q in matched_quotes if q.supplier_id == product.primary_supplier_id]
                lead_time_days = primary[0].delivery_lead_time_days if primary else min(q.delivery_lead_time_days for q in matched_quotes)

        # 2. Days of stock remaining calculation
        if product.avg_daily_sales > 0:
            days_of_stock = round(product.current_stock / product.avg_daily_sales, 1)
        else:
            days_of_stock = 999.0 if product.current_stock > 0 else 0.0

        # 3. Reorder Target & Suggested Reorder Quantity
        expected_demand_during_lead_time = product.avg_daily_sales * lead_time_days
        reorder_target = round(expected_demand_during_lead_time + product.safety_stock, 1)
        raw_reorder = max(0.0, reorder_target - product.current_stock)
        suggested_reorder_qty = math.ceil(raw_reorder / max(1.0, product.min_reorder_qty)) * product.min_reorder_qty if raw_reorder > 0 else 0.0

        # 4. Stockout Risk Level & Too Late Flag
        order_arrives_too_late = False
        data_quality_warning = None

        if product.avg_daily_sales <= 0:
            if product.current_stock > 0:
                stockout_risk_level = "Dormant/Dead Stock"
                data_quality_warning = "Zero daily sales recorded with positive inventory. Risk of perpetual holding cost."
            else:
                stockout_risk_level = "Inactive (Zero Stock & Sales)"
        else:
            if days_of_stock <= 0.0:
                stockout_risk_level = "Stocked Out"
                order_arrives_too_late = True
            elif days_of_stock <= lead_time_days:
                stockout_risk_level = "Critical Stockout Risk"
                order_arrives_too_late = True
            elif days_of_stock <= (lead_time_days + 3):
                stockout_risk_level = "High Stockout Risk"
            elif days_of_stock <= (lead_time_days + 10):
                stockout_risk_level = "Moderate Stockout Risk"
            elif days_of_stock > 60:
                stockout_risk_level = "Overstocked"
            else:
                stockout_risk_level = "Healthy Stock"

        # 5. Expiry Risk Calculations
        days_until_expiry = None
        expected_sales_before_expiry = None
        expiry_at_risk_qty = 0.0
        expiry_financial_loss_risk = 0.0
        expiry_risk_level = "None (Non-Perishable)"

        if product.expiry_date:
            try:
                exp_date = datetime.strptime(str(product.expiry_date).split(" ")[0], "%Y-%m-%d").date()
                delta_days = (exp_date - self.reference_date).days
                days_until_expiry = delta_days

                if delta_days <= 0:
                    expiry_risk_level = "Expired"
                    expiry_at_risk_qty = product.current_stock
                    expiry_financial_loss_risk = round(product.current_stock * product.cost_price, 2)
                else:
                    expected_sales_before_expiry = round(delta_days * product.avg_daily_sales, 1)
                    if product.current_stock > expected_sales_before_expiry:
                        expiry_at_risk_qty = round(product.current_stock - expected_sales_before_expiry, 1)
                        expiry_financial_loss_risk = round(expiry_at_risk_qty * product.cost_price, 2)

                    if delta_days <= 4 and expiry_at_risk_qty > 0:
                        expiry_risk_level = "Critical Expiry Risk (<4 days)"
                    elif delta_days <= 10 and expiry_at_risk_qty > 0:
                        expiry_risk_level = "High Expiry Risk (<10 days)"
                    elif delta_days <= 30 and expiry_at_risk_qty > 0:
                        expiry_risk_level = "Medium Expiry Risk (<30 days)"
                    else:
                        expiry_risk_level = "Low Expiry Risk"
            except Exception as e:
                data_quality_warning = f"Expiry date parse failure '{product.expiry_date}': {str(e)}"
                expiry_risk_level = "Invalid Expiry Format"

        return InventoryRiskAnalysis(
            product_id=product.product_id,
            product_name=product.product_name,
            category=product.category,
            current_stock=product.current_stock,
            avg_daily_sales=product.avg_daily_sales,
            days_of_stock_remaining=days_of_stock,
            supplier_lead_time_days=lead_time_days,
            reorder_target=reorder_target,
            suggested_reorder_qty=suggested_reorder_qty,
            stockout_risk_level=stockout_risk_level,
            order_arrives_too_late=order_arrives_too_late,
            days_until_expiry=days_until_expiry,
            expected_sales_before_expiry=expected_sales_before_expiry,
            expiry_at_risk_qty=expiry_at_risk_qty,
            expiry_financial_loss_risk=expiry_financial_loss_risk,
            expiry_risk_level=expiry_risk_level,
            data_quality_warning=data_quality_warning,
        )

    def analyze_all(
        self, products: List[Product], supplier_quotes: Optional[List[SupplierQuote]] = None
    ) -> List[InventoryRiskAnalysis]:
        return [self.analyze_product_inventory(p, supplier_quotes) for p in products]
