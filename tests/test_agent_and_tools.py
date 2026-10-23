"""
Unit Tests for StockSense Rescue AI - Agent Tool Registry, Security & Audit Logging
"""

import json
import os
import tempfile
import pytest

from src.models import Product, SupplierQuote, PurchasePlan, PurchaseRecommendationItem
from src.agent.tools import (
    StockSenseToolContext,
    set_active_tool_context,
    REGISTERED_TOOL_MAP,
    analyse_inventory,
    detect_stockout_risks,
    detect_expiry_risks,
    compare_suppliers,
)
from src.agent.gemini_agent import StockSenseGeminiAgent
from src.decisions.decision_logger import DecisionLogger


@pytest.fixture
def agent_context():
    temp_dir = tempfile.mkdtemp()
    db_file = os.path.join(temp_dir, "test_decisions.db")
    logger = DecisionLogger(db_path=db_file)

    products = [
        Product("P-1", "Cow Milk 1L", "Dairy", 5, 10, 40, 50, 10, "S-1", expiry_date="2026-10-26"),
        Product("P-2", "Wheat Flour 5kg", "Staples", 20, 2, 150, 200, 5, "S-2"),
    ]
    quotes = [
        SupplierQuote("S-1", "Fresh Farm", "Local/Small", "Local", "P-1", 40.0, 5.0, 100, 1, 20.0, 0.0, "Good", 0.95, "2026-10-20"),
        SupplierQuote("S-2", "Wheat Mills", "Regional Distributor", "Reg", "P-2", 145.0, 10.0, 200, 3, 50.0, 2.0, "Standard", 0.92, "2026-10-20"),
    ]
    ctx = StockSenseToolContext(products, quotes, None, decision_logger=logger)
    set_active_tool_context(ctx)
    yield ctx


def test_analyse_inventory_tool(agent_context):
    raw = analyse_inventory()
    data = json.loads(raw)
    assert data["status"] == "success"
    assert data["total_products"] == 2
    assert data["total_units_in_stock"] == 25


def test_detect_stockout_risks_tool(agent_context):
    raw = detect_stockout_risks()
    data = json.loads(raw)
    assert data["status"] == "success"
    # P-1 has 5 stock and 10 sales/day (0.5 days remaining) -> Critical stockout!
    assert data["urgent_stockout_count"] >= 1
    p1 = next(p for p in data["products"] if p["product_id"] == "P-1")
    assert p1["days_of_stock_remaining"] == 0.5


def test_unregistered_tool_security_rejection(agent_context):
    agent = StockSenseGeminiAgent(api_key="")
    # Model attempts to run unauthorized or shell tool
    res_str = agent.execute_tool_safely("execute_arbitrary_shell_command", {"command": "rm -rf /"})
    res = json.loads(res_str)
    assert res["status"] == "error"
    assert "not an authorized or registered tool" in res["error"]


def test_deterministic_agent_fallback_runs_without_api_key(agent_context):
    agent = StockSenseGeminiAgent(api_key="")
    result = agent.run("I have ₹5,000 to purchase stock. Find urgent items.", agent_context)
    assert result.is_live_gemini is False
    assert result.error_message is not None
    assert "Deterministic" in result.model_used
    assert len(result.tool_calls) > 0
    assert result.generated_plan_id is not None
    assert "Stockout Vulnerability Analysis" in result.response_text


def test_decision_logger_persists_and_retrieves(agent_context):
    plan = PurchasePlan(
        plan_id="PLAN-TEST01",
        total_budget=5000.0,
        total_allocated=3200.0,
        remaining_budget=1800.0,
        items=[],
        summary="Test Plan Summary",
    )
    rec = agent_context.decision_logger.log_decision(plan, "Approved", user_notes="Approved for immediate delivery")
    assert rec.plan_id == "PLAN-TEST01"
    assert rec.user_decision == "Approved"

    all_decs = agent_context.decision_logger.get_all_decisions()
    assert len(all_decs) == 1
    assert all_decs[0]["plan_id"] == "PLAN-TEST01"
    assert all_decs[0]["user_notes"] == "Approved for immediate delivery"
