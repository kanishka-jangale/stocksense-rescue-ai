"""
Unit Tests for StockSense Rescue AI - Budget Purchasing Optimizer
"""

import pytest

from src.models import Product, SupplierQuote
from src.analytics.inventory_engine import InventoryEngine
from src.analytics.optimizer_engine import PurchaseOptimizer


@pytest.fixture
def test_setup():
    products = [
        Product("P-1", "Product Urgent", "Dairy", current_stock=2, avg_daily_sales=5, cost_price=50, selling_price=70, safety_stock=10, primary_supplier_id="S-1"),
        Product("P-2", "Product Moderate", "Staples", current_stock=15, avg_daily_sales=2, cost_price=100, selling_price=130, safety_stock=10, primary_supplier_id="S-2"),
        Product("P-3", "Product Healthy", "Beverages", current_stock=50, avg_daily_sales=1, cost_price=120, selling_price=160, safety_stock=5, primary_supplier_id="S-1"),
    ]
    quotes = [
        SupplierQuote("S-1", "Local 1", "Local/Small", "Local", "P-1", 50.0, 10.0, 200, 1, 30.0, 0.0, "Standard", 0.95, "2026-10-20"),
        SupplierQuote("S-2", "Reg 2", "Regional Distributor", "Reg", "P-2", 95.0, 15.0, 500, 3, 50.0, 2.0, "Standard", 0.90, "2026-10-20"),
        SupplierQuote("S-1", "Local 1", "Local/Small", "Local", "P-3", 120.0, 5.0, 100, 1, 20.0, 0.0, "Standard", 0.95, "2026-10-20"),
    ]
    inv_engine = InventoryEngine()
    risks = inv_engine.analyze_all(products, quotes)
    optimizer = PurchaseOptimizer()
    return products, quotes, risks, optimizer


def test_budget_strict_compliance(test_setup):
    products, quotes, risks, optimizer = test_setup
    budget_limit = 1000.0
    plan = optimizer.generate_plan(
        products=products,
        supplier_quotes=quotes,
        inventory_risks=risks,
        total_budget=budget_limit,
    )
    # Total allocated must NEVER exceed total budget
    assert plan.total_allocated <= budget_limit
    assert plan.remaining_budget >= 0.0
    assert plan.total_allocated + plan.remaining_budget == pytest.approx(budget_limit, 0.01)


def test_insufficient_budget_unsatisfied_constraints(test_setup):
    products, quotes, risks, optimizer = test_setup
    tiny_budget = 50.0  # Cannot afford even one MOQ of any item
    plan = optimizer.generate_plan(
        products=products,
        supplier_quotes=quotes,
        inventory_risks=risks,
        total_budget=tiny_budget,
    )
    assert len(plan.items) == 0
    assert plan.total_allocated == 0.0
    assert len(plan.unsatisfied_constraints) > 0


def test_zero_budget_handling(test_setup):
    products, quotes, risks, optimizer = test_setup
    plan = optimizer.generate_plan(
        products=products,
        supplier_quotes=quotes,
        inventory_risks=risks,
        total_budget=0.0,
    )
    assert plan.total_allocated == 0.0
    assert "zero" in plan.unsatisfied_constraints[0].lower()


def test_moq_respected_in_plan(test_setup):
    products, quotes, risks, optimizer = test_setup
    plan = optimizer.generate_plan(
        products=products,
        supplier_quotes=quotes,
        inventory_risks=risks,
        total_budget=5000.0,
    )
    for item in plan.items:
        # Quote MOQ for P-1 is 10.0
        if item.product_id == "P-1":
            assert item.quantity >= 10.0
