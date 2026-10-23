"""
End-to-End Workflow Verification Script for StockSense Rescue AI
Validates the entire pipeline from data loading to report export.
"""

import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.data_loader import DataLoader
from src.analytics.inventory_engine import InventoryEngine
from src.analytics.trend_engine import TrendEngine
from src.analytics.pricing_engine import PricingEngine
from src.analytics.supplier_engine import SupplierEngine
from src.analytics.optimizer_engine import PurchaseOptimizer
from src.decisions.decision_logger import DecisionLogger
from src.reports.exporter import ReportExporter
from src.agent.tools import StockSenseToolContext, set_active_tool_context
from src.agent.gemini_agent import StockSenseGeminiAgent


def run_full_verification():
    print("Step 1: Loading default sample datasets...")
    loader = DataLoader(data_dir=os.path.join(os.path.dirname(__file__), "data"))
    inv_df = loader.load_default_inventory()
    sup_df = loader.load_default_suppliers()
    sales_df = loader.load_default_sales()

    products = loader.products_from_df(inv_df)
    quotes = loader.suppliers_from_df(sup_df)
    print(f" Loaded {len(products)} products, {len(quotes)} supplier quotes, {len(sales_df)} sales records.")

    print("\nStep 2: Analyzing Inventory & Expiry Risks...")
    inv_engine = InventoryEngine()
    risks = inv_engine.analyze_all(products, quotes)
    urgent_stockouts = [r for r in risks if "Stockout" in r.stockout_risk_level]
    expiries = [r for r in risks if r.expiry_at_risk_qty > 0]
    print(f" Identified {len(urgent_stockouts)} stockout risks and {len(expiries)} perishable expiry exposures.")

    print("\nStep 3: Analyzing Demand Trends...")
    trend_engine = TrendEngine()
    trends = trend_engine.analyze_sales_history(sales_df, products)
    emerging = [t for t in trends if "Emerging" in t.trend_classification]
    print(f" Analyzed {len(trends)} products. Found {len(emerging)} emerging demand surges.")

    print("\nStep 4: Segmenting Prices across 4 tiers...")
    pricing_engine = PricingEngine()
    segments = pricing_engine.classify_products(products)
    print(f" Classified {len(segments)} products into Budget, Value, Standard, and Premium.")

    print("\nStep 5: Testing Small-to-Large Supplier Comparison...")
    sup_engine = SupplierEngine()
    milk_comparison = sup_engine.compare_suppliers_for_product("P-101", quotes, desired_qty=20)
    print(f" Found {len(milk_comparison)} supplier options for P-101 (Milk). Top fit: {milk_comparison[0]['business_name']} ({milk_comparison[0]['supplier_scale']}).")

    print("\nStep 6: Executing Budget Purchasing Optimizer (Budget = ₹10,000)...")
    optimizer = PurchaseOptimizer(sup_engine)
    plan = optimizer.generate_plan(
        products=products,
        supplier_quotes=quotes,
        inventory_risks=risks,
        trend_analyses=trends,
        segment_classifications=segments,
        total_budget=10000.0,
    )
    print(f" Plan generated: {plan.summary}")
    assert plan.total_allocated <= 10000.0, "Budget exceeded!"
    print(f" Budget constraint satisfied: Allocated ₹{plan.total_allocated:,.2f} <= ₹10,000.00.")

    print("\nStep 7: Testing Gemini Agent Execution...")
    db_path = os.path.join(os.path.dirname(__file__), "data", "test_verify_decisions.db")
    dec_logger = DecisionLogger(db_path=db_path)
    ctx = StockSenseToolContext(products, quotes, sales_df, decision_logger=dec_logger)
    set_active_tool_context(ctx)

    agent = StockSenseGeminiAgent(api_key="")
    query = "I have ₹5,000 to purchase stock. Identify urgent items, suggest rising products, and prepare a purchase plan."
    result = agent.run(query, ctx)
    print(f" Agent executed query. Model: {result.model_used}. Tools invoked: {len(result.tool_calls)}.")
    print(f" Response text snippet:\n{result.response_text[:350]}...\n")

    print("Step 8: Recording Human Approval in SQLite Ledger...")
    approval_rec = dec_logger.log_decision(plan, "Approved", user_notes="Verified by automated integration runner.")
    print(f" Decision permanently logged with ID: {approval_rec.decision_id}. Total cost: ₹{approval_rec.total_cost:,.2f}.")

    print("\nStep 9: Testing Report Exporter...")
    exporter = ReportExporter(is_synthetic_data=True)
    csv_report = exporter.export_purchase_order_csv(plan)
    assert len(csv_report) > 100, "Report export failed!"
    print(" Report generation verified successfully!")

    # Cleanup temp db safely
    try:
        if os.path.exists(db_path):
            os.remove(db_path)
    except Exception:
        pass

    print("\n🎉 ALL 9 WORKFLOW STEPS COMPLETED AND VERIFIED SUCCESSFULLY!")


if __name__ == "__main__":
    run_full_verification()
