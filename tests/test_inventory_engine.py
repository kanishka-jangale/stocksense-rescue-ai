"""
Unit Tests for StockSense Rescue AI - Inventory & Expiry Analytics Engine
"""

from datetime import datetime, timedelta, date
import pytest

from src.models import Product, SupplierQuote
from src.analytics.inventory_engine import InventoryEngine


@pytest.fixture
def test_engine():
    fixed_date = date(2026, 10, 23)
    return InventoryEngine(reference_date=fixed_date)


def test_days_of_stock_calculation(test_engine):
    p = Product(
        product_id="TEST-01",
        product_name="Standard Flour 1kg",
        category="Staples",
        current_stock=30.0,
        avg_daily_sales=5.0,
        cost_price=40.0,
        selling_price=55.0,
        safety_stock=10.0,
        primary_supplier_id="SUP-01",
    )
    risk = test_engine.analyze_product_inventory(p)
    assert risk.days_of_stock_remaining == 6.0


def test_reorder_target_and_suggested_quantity(test_engine):
    # Daily sales = 10, lead time = 3 days -> Lead time demand = 30.
    # Safety stock = 15 -> Reorder target = 45.
    # Current stock = 10 -> Suggested reorder = 35.
    p = Product(
        product_id="TEST-02",
        product_name="Fresh Milk 1L",
        category="Dairy",
        current_stock=10.0,
        avg_daily_sales=10.0,
        cost_price=30.0,
        selling_price=40.0,
        safety_stock=15.0,
        primary_supplier_id="SUP-01",
    )
    quote = SupplierQuote(
        supplier_id="SUP-01",
        business_name="Local Dairy",
        supplier_scale="Local/Small",
        service_area="Local",
        product_id="TEST-02",
        unit_purchase_price=30.0,
        min_order_qty=5.0,
        available_qty=500.0,
        delivery_lead_time_days=3,
        delivery_charge=20.0,
        discount_pct=0.0,
        return_policy="Standard",
        reliability_score=0.95,
        last_price_update="2026-10-20",
    )
    risk = test_engine.analyze_product_inventory(p, [quote])
    assert risk.reorder_target == 45.0
    assert risk.suggested_reorder_qty == 35.0


def test_order_arrives_too_late_flag(test_engine):
    # Current stock = 2, avg sales = 2/day -> 1 day stock remaining.
    # Supplier lead time = 3 days -> Order arrives too late!
    p = Product(
        product_id="TEST-03",
        product_name="Yogurt Cup",
        category="Dairy",
        current_stock=2.0,
        avg_daily_sales=2.0,
        cost_price=20.0,
        selling_price=30.0,
        safety_stock=5.0,
        primary_supplier_id="SUP-01",
    )
    quote = SupplierQuote(
        supplier_id="SUP-01",
        business_name="Regional Hub",
        supplier_scale="Regional Distributor",
        service_area="Regional",
        product_id="TEST-03",
        unit_purchase_price=20.0,
        min_order_qty=10.0,
        available_qty=200.0,
        delivery_lead_time_days=3,
        delivery_charge=40.0,
        discount_pct=0.0,
        return_policy="Standard",
        reliability_score=0.90,
        last_price_update="2026-10-20",
    )
    risk = test_engine.analyze_product_inventory(p, [quote])
    assert risk.order_arrives_too_late is True
    assert "Critical" in risk.stockout_risk_level


def test_zero_sales_dead_stock_safety(test_engine):
    p = Product(
        product_id="TEST-04",
        product_name="Dormant Sauce",
        category="Staples",
        current_stock=15.0,
        avg_daily_sales=0.0,  # Zero sales
        cost_price=50.0,
        selling_price=80.0,
        safety_stock=5.0,
        primary_supplier_id="SUP-01",
    )
    risk = test_engine.analyze_product_inventory(p)
    assert risk.days_of_stock_remaining == 999.0
    assert risk.stockout_risk_level == "Dormant/Dead Stock"
    assert risk.data_quality_warning is not None


def test_expiry_risk_loss_calculation(test_engine):
    # Today is 2026-10-23. Expiry is 2026-10-27 (4 days away).
    # Daily sales = 2. Expected sales in 4 days = 8 units.
    # Current stock = 20 units. At risk unsold = 20 - 8 = 12 units.
    # Cost price = ₹50 -> Financial loss risk = 12 * 50 = ₹600.
    p = Product(
        product_id="TEST-05",
        product_name="Artisan Cheese",
        category="Dairy",
        current_stock=20.0,
        avg_daily_sales=2.0,
        cost_price=50.0,
        selling_price=75.0,
        safety_stock=5.0,
        primary_supplier_id="SUP-01",
        expiry_date="2026-10-27",
    )
    risk = test_engine.analyze_product_inventory(p)
    assert risk.days_until_expiry == 4
    assert risk.expected_sales_before_expiry == 8.0
    assert risk.expiry_at_risk_qty == 12.0
    assert risk.expiry_financial_loss_risk == 600.0
    assert "Critical Expiry Risk" in risk.expiry_risk_level


def test_non_perishable_missing_expiry_safe(test_engine):
    p = Product(
        product_id="TEST-06",
        product_name="Sea Salt 1kg",
        category="Staples",
        current_stock=50.0,
        avg_daily_sales=3.0,
        cost_price=15.0,
        selling_price=22.0,
        safety_stock=10.0,
        primary_supplier_id="SUP-01",
        expiry_date=None,  # No expiry
    )
    risk = test_engine.analyze_product_inventory(p)
    assert risk.days_until_expiry is None
    assert risk.expiry_at_risk_qty == 0.0
    assert risk.expiry_risk_level == "None (Non-Perishable)"
