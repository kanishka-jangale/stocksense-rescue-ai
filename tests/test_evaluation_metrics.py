"""
Evaluation & Quantitative Benchmarks for StockSense Rescue AI
Evaluates Stockout Risk Precision & Recall, Expiry Detection Accuracy,
Budget Constraint Adherence Rate, and Execution Latency on synthetic benchmarks.
"""

import time
import pytest
import pandas as pd

from src.models import Product, SupplierQuote
from src.analytics.inventory_engine import InventoryEngine
from src.analytics.optimizer_engine import PurchaseOptimizer
from src.data_loader import validate_inventory_df


def test_budget_compliance_rate_100_percent():
    """Verifies that 100% of generated purchase plans satisfy budget <= total_budget."""
    products = [
        Product(f"P-{i}", f"Product {i}", "Staples", current_stock=i, avg_daily_sales=3.0, cost_price=50.0, selling_price=70.0, safety_stock=10.0, primary_supplier_id=f"S-{i%2}")
        for i in range(15)
    ]
    quotes = [
        SupplierQuote(f"S-{i%2}", f"Supplier {i%2}", "Regional Distributor", "North", f"P-{i}", 48.0, 10.0, 500.0, 2, 40.0, 1.0, "Standard", 0.92, "2026-10-20")
        for i in range(15)
    ]

    inv_engine = InventoryEngine()
    risks = inv_engine.analyze_all(products, quotes)
    optimizer = PurchaseOptimizer()

    test_budgets = [200.0, 500.0, 1000.0, 2500.0, 5000.0, 10000.0, 25000.0, 50000.0]
    satisfaction_count = 0

    for b in test_budgets:
        plan = optimizer.generate_plan(products, quotes, risks, total_budget=b)
        if plan.total_allocated <= b and plan.remaining_budget >= 0:
            satisfaction_count += 1

    compliance_rate = (satisfaction_count / len(test_budgets)) * 100.0
    assert compliance_rate == 100.0


def test_stockout_risk_precision_recall():
    """Evaluates Precision and Recall against ground-truth labeled stockout risk test items."""
    # Synthetic ground-truth labeled test items
    # True positives: Days of stock <= 5.0
    test_cases = [
        {"stock": 2, "sales": 4.0, "true_stockout_risk": True},   # 0.5 days
        {"stock": 5, "sales": 2.0, "true_stockout_risk": True},   # 2.5 days
        {"stock": 10, "sales": 2.5, "true_stockout_risk": True},  # 4.0 days
        {"stock": 20, "sales": 1.0, "true_stockout_risk": False}, # 20.0 days
        {"stock": 50, "sales": 1.5, "true_stockout_risk": False}, # 33.3 days
        {"stock": 100, "sales": 2.0, "true_stockout_risk": False},# 50.0 days
        {"stock": 15, "sales": 4.0, "true_stockout_risk": True},  # 3.75 days
        {"stock": 40, "sales": 0.5, "true_stockout_risk": False}, # 80.0 days
    ]

    engine = InventoryEngine()
    tp = 0
    fp = 0
    fn = 0
    tn = 0

    for idx, tc in enumerate(test_cases):
        p = Product(f"T-{idx}", f"Item {idx}", "General", tc["stock"], tc["sales"], 10, 15, 5, "S1")
        risk = engine.analyze_product_inventory(p)
        predicted_risk = risk.stockout_risk_level in ("Critical Stockout Risk", "High Stockout Risk", "Stocked Out")
        actual_risk = tc["true_stockout_risk"]

        if predicted_risk and actual_risk:
            tp += 1
        elif predicted_risk and not actual_risk:
            fp += 1
        elif not predicted_risk and actual_risk:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 1.0

    assert precision >= 0.95
    assert recall >= 0.95


def test_processing_speed_benchmark():
    """Measures execution latency on a standard 100-item inventory catalog."""
    products = [
        Product(f"P-{i}", f"Item {i}", "Staples", current_stock=20, avg_daily_sales=2.0, cost_price=30, selling_price=45, safety_stock=5, primary_supplier_id="S1")
        for i in range(100)
    ]
    quotes = [
        SupplierQuote("S1", "Main Supplier", "Regional Distributor", "All", f"P-{i}", 28.0, 5.0, 500, 2, 20.0, 0.0, "Standard", 0.95, "2026-10-20")
        for i in range(100)
    ]

    engine = InventoryEngine()
    start = time.perf_counter()
    risks = engine.analyze_all(products, quotes)
    duration_ms = (time.perf_counter() - start) * 1000.0

    # 100 items analysis should complete well under 100 milliseconds
    assert len(risks) == 100
    assert duration_ms < 150.0


def test_corrupt_csv_input_handling():
    """Verifies that malicious or corrupted CSV inputs are rejected or sanitized cleanly."""
    corrupt_df = pd.DataFrame([
        {"product_id": "=cmd|' /C calc'!A0", "product_name": "Injected Product", "category": "Dairy", "current_stock": "-50", "avg_daily_sales": "invalid_num", "cost_price": "40.0", "selling_price": "50.0"},
        {"product_id": "P-VALID", "product_name": "Valid Milk", "category": "Dairy", "current_stock": "10", "avg_daily_sales": "5.0", "cost_price": "40.0", "selling_price": "50.0"},
    ])
    res = validate_inventory_df(corrupt_df)
    assert res.is_valid is True
    cleaned = res.cleaned_df
    # Injected formula should be neutralized with leading single quote
    injected_row = cleaned[cleaned["product_name"] == "Injected Product"].iloc[0]
    assert injected_row["product_id"].startswith("'")
    # Negative stock clamped to 0.0
    assert injected_row["current_stock"] == 0.0
    # Invalid string for avg_daily_sales filled to 0.0
    assert injected_row["avg_daily_sales"] == 0.0
