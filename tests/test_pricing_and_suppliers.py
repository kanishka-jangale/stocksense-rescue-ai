"""
Unit Tests for StockSense Rescue AI - Pricing & Supplier Intelligence Engines
"""

import pytest

from src.models import Product, SupplierQuote
from src.analytics.pricing_engine import PricingEngine, DEFAULT_CATEGORY_THRESHOLDS
from src.analytics.supplier_engine import SupplierEngine


def test_category_specific_price_segmentation():
    engine = PricingEngine(use_relative_quantiles=False)
    products = [
        # Dairy thresholds: budget <= 55, value <= 120, standard <= 220, premium > 220
        Product("P-D1", "Milk 1L", "Dairy", 10, 5, 40, 50, 5, "S1"),      # Budget (<= 55)
        Product("P-D2", "Greek Yogurt", "Dairy", 10, 5, 75, 100, 5, "S1"), # Value (55 - 120)
        Product("P-D3", "Butter 500g", "Dairy", 10, 5, 150, 190, 5, "S1"), # Standard (120 - 220)
        Product("P-D4", "Truffle Cheese", "Dairy", 10, 5, 300, 420, 5, "S1"), # Premium (> 220)
    ]
    classifications = engine.classify_products(products)
    assert len(classifications) == 4
    seg_map = {c.product_id: c.price_segment for c in classifications}
    assert seg_map["P-D1"] == "Budget/Economy"
    assert seg_map["P-D2"] == "Value/Affordable Quality"
    assert seg_map["P-D3"] == "Standard/Mid-Range"
    assert seg_map["P-D4"] == "Premium"


def test_supplier_landed_cost_with_discount_and_delivery():
    quote = SupplierQuote(
        supplier_id="SUP-REG",
        business_name="Regional Hub",
        supplier_scale="Regional Distributor",
        service_area="North",
        product_id="P-01",
        unit_purchase_price=100.0,
        min_order_qty=20.0,
        available_qty=500.0,
        delivery_lead_time_days=3,
        delivery_charge=50.0,
        discount_pct=5.0,  # 5% discount
        return_policy="Standard",
        reliability_score=0.92,
        last_price_update="2026-10-20",
    )
    # Order 20 units:
    # Gross cost = 20 * 100 = 2000.
    # Discount = 5% of 2000 = 100.
    # Net cost = 1900.
    # Delivery = 50.
    # Total landed cost = 1950.
    # Effective unit cost = 1950 / 20 = 97.5.
    landed = quote.calculate_landed_cost(20.0)
    assert landed["gross_item_cost"] == 2000.0
    assert landed["discount_amount"] == 100.0
    assert landed["total_landed_cost"] == 1950.0
    assert landed["effective_unit_cost"] == 97.5


def test_supplier_moq_enforcement_in_landed_cost():
    quote = SupplierQuote(
        supplier_id="SUP-NAT",
        business_name="National Wholesale",
        supplier_scale="Large Wholesaler",
        service_area="National",
        product_id="P-01",
        unit_purchase_price=80.0,
        min_order_qty=50.0,  # MOQ is 50
        available_qty=2000.0,
        delivery_lead_time_days=7,
        delivery_charge=150.0,
        discount_pct=0.0,
        return_policy="Bulk only",
        reliability_score=0.88,
        last_price_update="2026-10-20",
    )
    # Requested 10 units, but MOQ is 50 -> must evaluate at least 50
    landed = quote.calculate_landed_cost(10.0)
    assert landed["order_qty"] == 50.0
    assert landed["total_landed_cost"] == (50 * 80.0) + 150.0


def test_supplier_comparison_fit_scoring():
    engine = SupplierEngine()
    quotes = [
        SupplierQuote("S-LOC", "Local Fast", "Local/Small", "Local", "P-01", 105.0, 5.0, 100, 1, 20.0, 0.0, "Easy", 0.98, "2026-10-20"),
        SupplierQuote("S-REG", "Regional Dist", "Regional Distributor", "Reg", "P-01", 95.0, 20.0, 500, 3, 60.0, 2.0, "Good", 0.92, "2026-10-20"),
        SupplierQuote("S-NAT", "National Bulk", "Large Wholesaler", "Nat", "P-01", 85.0, 100.0, 5000, 7, 200.0, 5.0, "Bulk", 0.85, "2026-10-20"),
    ]
    compared = engine.compare_suppliers_for_product("P-01", quotes, desired_qty=20.0)
    assert len(compared) == 3
    # Verify fit_score exists and is between 0 and 100
    for c in compared:
        assert 0.0 <= c["fit_score"] <= 100.0
        assert "key_advantages" in c
        assert "trade_off_caveat" in c

    # Fastest supplier should be S-LOC (1 day lead time)
    fastest = engine.find_best_supplier("P-01", quotes, criterion="fastest")
    assert fastest["supplier_id"] == "S-LOC"

    # Lowest MOQ should be S-LOC (5 units)
    lowest_moq = engine.find_best_supplier("P-01", quotes, criterion="lowest_moq")
    assert lowest_moq["supplier_id"] == "S-LOC"
