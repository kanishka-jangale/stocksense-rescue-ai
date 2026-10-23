"""
StockSense Rescue AI - Main Application Entrypoint
Retail Intelligence • Price Segmentation • Supplier Comparison • Agentic AI
Built for small and medium retailers with Gemini Function Calling & deterministic engines.
"""

from datetime import datetime
import json
import os
import sys
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.models import Product, SupplierQuote, PurchasePlan
from src.data_loader import DataLoader, validate_inventory_df, validate_supplier_df, validate_sales_df
from src.analytics.inventory_engine import InventoryEngine
from src.analytics.trend_engine import TrendEngine
from src.analytics.pricing_engine import PricingEngine
from src.analytics.supplier_engine import SupplierEngine
from src.analytics.optimizer_engine import PurchaseOptimizer
from src.decisions.decision_logger import DecisionLogger
from src.reports.exporter import ReportExporter
from src.agent.tools import StockSenseToolContext, set_active_tool_context
from src.agent.gemini_agent import StockSenseGeminiAgent


# -----------------------------------------------------------------------------
# Page Configuration & Styling
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="StockSense Rescue AI",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom High-Contrast CSS
st.markdown("""
<style>
    /* Metric Card Styling */
    div[data-testid="stMetricValue"] {
        font-size: 1.85rem !important;
        font-weight: 700 !important;
        color: #1E293B !important;
    }
    div[data-testid="stMetricLabel"] {
        font-weight: 600 !important;
        color: #475569 !important;
        font-size: 0.95rem !important;
    }
    /* Clean Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #FFFFFF;
        border-right: 1px solid #E2E8F0;
    }
    /* Badge styling */
    .badge-critical {
        background-color: #FEE2E2;
        color: #991B1B;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-high {
        background-color: #FFEDD5;
        color: #C2410C;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.8rem;
    }
    .badge-healthy {
        background-color: #DCFCE7;
        color: #166534;
        padding: 4px 10px;
        border-radius: 9999px;
        font-weight: 600;
        font-size: 0.8rem;
    }
</style>
""", unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# Session State Initialization
# -----------------------------------------------------------------------------
if "data_loader" not in st.session_state:
    st.session_state.data_loader = DataLoader(data_dir=os.path.join(os.path.dirname(__file__), "data"))
    st.session_state.inventory_df = st.session_state.data_loader.load_default_inventory()
    st.session_state.suppliers_df = st.session_state.data_loader.load_default_suppliers()
    st.session_state.sales_df = st.session_state.data_loader.load_default_sales()
    st.session_state.is_synthetic = True

if "gemini_api_key" not in st.session_state:
    st.session_state.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")

if "gemini_model" not in st.session_state:
    st.session_state.gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

if "decision_logger" not in st.session_state:
    db_path = os.path.join(os.path.dirname(__file__), "data", "decisions.db")
    st.session_state.decision_logger = DecisionLogger(db_path=db_path)

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = [
        {
            "role": "assistant",
            "content": "👋 Welcome to **StockSense Rescue AI**! I am your retail purchasing and stock rescue copilot. "
                       "You can ask me to inspect stockout risks, detect expiring goods, compare local vs regional suppliers, "
                       "or generate a budget-optimized purchasing plan (e.g. *'I have ₹10,000 to purchase stock. Find urgent items and build a purchase plan.'*).",
            "traces": [],
            "plan_id": None,
        }
    ]

if "active_proposed_plan" not in st.session_state:
    st.session_state.active_proposed_plan = None


# Helper to instantiate active models and context
def get_current_context():
    loader = st.session_state.data_loader
    products = loader.products_from_df(st.session_state.inventory_df)
    quotes = loader.suppliers_from_df(st.session_state.suppliers_df)
    ctx = StockSenseToolContext(
        products=products,
        supplier_quotes=quotes,
        sales_df=st.session_state.sales_df,
        decision_logger=st.session_state.decision_logger,
    )
    set_active_tool_context(ctx)
    return ctx


# -----------------------------------------------------------------------------
# Sidebar Navigation & Settings
# -----------------------------------------------------------------------------
st.sidebar.image("https://img.icons8.com/color/96/000000/box--v1.png", width=55)
st.sidebar.title("StockSense Rescue AI")
st.sidebar.caption("Retail Intelligence & Inventory Copilot")

nav_choice = st.sidebar.radio(
    "Navigation",
    [
        "📊 Retail Intelligence Dashboard",
        "⚠️ Inventory & Expiry Rescue",
        "📈 Trending & Emerging Demand",
        "🏷️ Smart Price Segmentation",
        "🚚 Supplier Comparison Matrix",
        "💰 Budget Purchasing Optimizer",
        "🤖 Gemini AI Purchasing Agent",
        "📋 Reports & Decision History",
        "⚙️ Settings & Data Provenance",
    ],
    index=0,
)

st.sidebar.markdown("---")
# Quick Status Widget
st.sidebar.subheader("System Status")
if st.session_state.gemini_api_key:
    st.sidebar.success(f"🟢 Gemini Connected (`{st.session_state.gemini_model}`)")
else:
    st.sidebar.info("🟡 Gemini Key Unset (Deterministic Fallback Mode Active)")

if st.session_state.is_synthetic:
    st.sidebar.warning("📊 Data: Synthetic FMCG Demo")
else:
    st.sidebar.success("📊 Data: Custom Uploaded Live Data")


# -----------------------------------------------------------------------------
# Module A: Retail Intelligence Dashboard
# -----------------------------------------------------------------------------
if nav_choice == "📊 Retail Intelligence Dashboard":
    st.title("📊 Retail Intelligence Dashboard")
    st.caption("Live, computed retail metrics calculated from active catalog and supplier quotes (Zero fabricated statistics).")

    ctx = get_current_context()
    risks = ctx.inventory_risks
    trends = ctx.trend_analyses
    prices = ctx.price_classifications

    # Compute KPI values
    total_products = len(ctx.products)
    total_units = sum(p.current_stock for p in ctx.products)
    total_inv_cost = sum(p.current_stock * p.cost_price for p in ctx.products)
    total_retail_val = sum(p.current_stock * p.selling_price for p in ctx.products)

    stockouts = [r for r in risks if r.stockout_risk_level in ("Critical Stockout Risk", "Stocked Out")]
    expiries = [r for r in risks if r.expiry_at_risk_qty > 0]
    total_expiry_loss = sum(r.expiry_financial_loss_risk for r in expiries)
    emerging = [t for t in trends if "Emerging" in t.trend_classification]

    # Row 1: Key Performance Metrics
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Total Products", f"{total_products}", help="Unique active SKUs in catalog")
    kpi2.metric("Inventory Cost Value", f"₹{total_inv_cost:,.0f}", f"₹{total_retail_val:,.0f} Retail Value")
    kpi3.metric("Critical Stockouts", f"{len(stockouts)}", "- Urgent Reorder", delta_color="inverse")
    kpi4.metric("Expiry Loss Exposure", f"₹{total_expiry_loss:,.0f}", f"{len(expiries)} Perishables", delta_color="inverse")
    kpi5.metric("Emerging Trend Surges", f"{len(emerging)}", "+ Demand Breakouts")

    st.markdown("---")

    # Row 2: Visual Charts
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("Inventory Stock Health Distribution")
        status_counts = pd.Series([r.stockout_risk_level for r in risks]).value_counts().reset_index()
        status_counts.columns = ["Stock Health Status", "SKU Count"]
        fig_health = px.pie(
            status_counts,
            names="Stock Health Status",
            values="SKU Count",
            hole=0.45,
            color="Stock Health Status",
            color_discrete_map={
                "Critical Stockout Risk": "#EF4444",
                "Stocked Out": "#B91C1C",
                "High Stockout Risk": "#F97316",
                "Moderate Stockout Risk": "#FBBF24",
                "Healthy Stock": "#10B981",
                "Overstocked": "#6366F1",
                "Dormant/Dead Stock": "#94A3B8",
            },
        )
        fig_health.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300)
        st.plotly_chart(fig_health, use_container_width=True)

    with col_right:
        st.subheader("Category Valuation & Stock Units")
        cat_data = pd.DataFrame([
            {"Category": p.category, "Stock Units": p.current_stock, "Total Cost (₹)": p.current_stock * p.cost_price}
            for p in ctx.products
        ]).groupby("Category").sum().reset_index()

        fig_cat = px.bar(
            cat_data,
            x="Category",
            y="Total Cost (₹)",
            text_auto=True,
            color="Category",
            color_discrete_sequence=px.colors.qualitative.Safe,
        )
        fig_cat.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=300, showlegend=False)
        st.plotly_chart(fig_cat, use_container_width=True)

    # Row 3: Actionable Urgent Radar
    st.subheader("🚨 Priority Operational Warnings")
    alert_col1, alert_col2 = st.columns(2)

    with alert_col1:
        st.markdown("**Stockout Warnings (Days Remaining < Lead Time)**")
        urgent_df = pd.DataFrame([
            {
                "Product": r.product_name,
                "Category": r.category,
                "Current Stock": int(r.current_stock),
                "Daily Sales": r.avg_daily_sales,
                "Days Left": f"{r.days_of_stock_remaining:.1f} d",
                "Lead Time": f"{r.supplier_lead_time_days} d",
                "Too Late?": "⚠️ YES" if r.order_arrives_too_late else "OK",
            }
            for r in risks
            if r.stockout_risk_level in ("Critical Stockout Risk", "Stocked Out", "High Stockout Risk")
        ])
        if not urgent_df.empty:
            st.dataframe(urgent_df, use_container_width=True, hide_index=True)
        else:
            st.info("No imminent stockouts detected in active catalog.")

    with alert_col2:
        st.markdown("**Perishable Expiry Exposure (Expected Unsold)**")
        exp_df = pd.DataFrame([
            {
                "Product": r.product_name,
                "Days to Expiry": r.days_until_expiry,
                "Current Stock": int(r.current_stock),
                "At Risk Qty": r.expiry_at_risk_qty,
                "Potential Loss": f"₹{r.expiry_financial_loss_risk:,.2f}",
                "Risk Tier": r.expiry_risk_level,
            }
            for r in expiries
        ])
        if not exp_df.empty:
            st.dataframe(exp_df, use_container_width=True, hide_index=True)
        else:
            st.success("No perishable items at immediate expiry risk.")


# -----------------------------------------------------------------------------
# Module E: Inventory & Expiry Rescue
# -----------------------------------------------------------------------------
elif nav_choice == "⚠️ Inventory & Expiry Rescue":
    st.title("⚠️ Inventory & Expiry Rescue Analytics")
    st.caption("Transparent mathematical calculations: Days of Stock = Current / Daily Sales; Reorder Target = Lead Time Demand + Safety Stock.")

    ctx = get_current_context()
    risks = ctx.inventory_risks

    # Filters
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        categories = ["All"] + sorted(list({r.category for r in risks}))
        sel_cat = st.selectbox("Filter Category", categories)
    with fcol2:
        risk_levels = ["All"] + sorted(list({r.stockout_risk_level for r in risks}))
        sel_risk = st.selectbox("Filter Stockout Risk", risk_levels)
    with fcol3:
        search_query = st.text_input("Search Product Name", "").strip().lower()

    # Apply filters
    filtered_risks = risks
    if sel_cat != "All":
        filtered_risks = [r for r in filtered_risks if r.category == sel_cat]
    if sel_risk != "All":
        filtered_risks = [r for r in filtered_risks if r.stockout_risk_level == sel_risk]
    if search_query:
        filtered_risks = [r for r in filtered_risks if search_query in r.product_name.lower()]

    # Detailed Table
    data_rows = []
    for r in filtered_risks:
        data_rows.append({
            "SKU": r.product_id,
            "Product Name": r.product_name,
            "Category": r.category,
            "Stock": r.current_stock,
            "Daily Sales": r.avg_daily_sales,
            "Days Left": r.days_of_stock_remaining,
            "Lead Time": f"{r.supplier_lead_time_days}d",
            "Reorder Target": r.reorder_target,
            "Suggested Reorder": r.suggested_reorder_qty,
            "Stockout Status": r.stockout_risk_level,
            "Order Too Late?": "⚠️ Arrives Late" if r.order_arrives_too_late else "Timely",
            "Days to Expiry": r.days_until_expiry if r.days_until_expiry is not None else "N/A",
            "Expiry Risk Qty": r.expiry_at_risk_qty,
            "Loss Exposure (₹)": r.expiry_financial_loss_risk,
        })

    df_view = pd.DataFrame(data_rows)
    st.dataframe(
        df_view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Days Left": st.column_config.NumberColumn(format="%.1f days"),
            "Loss Exposure (₹)": st.column_config.NumberColumn(format="₹%.2f"),
        },
    )

    # Explanation callout
    with st.expander("ℹ️ Calculation Formulas & Transparent Logic"):
        st.markdown("""
        - **Days of Stock Remaining** = `Current Stock / Average Daily Sales` (when daily sales > 0).
        - **Reorder Target** = `(Average Daily Sales × Supplier Lead Time) + Safety Stock`.
        - **Suggested Reorder Quantity** = `max(0, Reorder Target - Current Stock)`.
        - **Arrival Warning (`Arrives Late`)**: Flagged when supplier lead time exceeds remaining days of stock.
        - **Expiry Risk Calculation**: `max(0, Current Stock - (Days to Expiry × Average Daily Sales))`.
        """)


# -----------------------------------------------------------------------------
# Module B: Trending & Emerging Demand
# -----------------------------------------------------------------------------
elif nav_choice == "📈 Trending & Emerging Demand":
    st.title("📈 Trending & Emerging Demand Intelligence")
    st.caption("Compares recent 14-day demand against a 46-day baseline to differentiate high-volume staples from emerging demand breakouts.")

    ctx = get_current_context()
    trends = ctx.trend_analyses

    # Metrics
    t1, t2, t3 = st.columns(3)
    surges = [t for t in trends if "Emerging" in t.trend_classification]
    established = [t for t in trends if "Established" in t.trend_classification]
    decaying = [t for t in trends if "Softening" in t.trend_classification or "Dead" in t.trend_classification]

    t1.metric("Emerging Demand Surges", len(surges), "Recommend Pilot Test Quantity")
    t2.metric("Established High-Velocity Core", len(established), "Recommend Bulk Replenishment")
    t3.metric("Softening or Inactive Demand", len(decaying), "Caution / Do Not Overorder")

    st.markdown("---")

    # Interactive Bubble / Scatter Plot
    trend_df = pd.DataFrame([
        {
            "Product": t.product_name,
            "Category": t.category,
            "Baseline Daily": t.baseline_daily_sales,
            "Recent Daily": t.recent_daily_sales,
            "Demand Change (%)": t.demand_change_pct,
            "Classification": t.trend_classification,
            "Recommendation": t.action_recommendation,
            "Confidence": t.confidence_score,
            "Explanation": t.action_explanation,
        }
        for t in trends
    ])

    fig_trend = px.scatter(
        trend_df,
        x="Baseline Daily",
        y="Recent Daily",
        size=[abs(x) + 5 for x in trend_df["Demand Change (%)"]],
        color="Classification",
        hover_name="Product",
        hover_data=["Demand Change (%)", "Recommendation", "Confidence"],
        title="Demand Momentum: Recent 14-Day Velocity vs Baseline Velocity",
    )
    # Add diagonal parity line
    max_val = max(trend_df["Baseline Daily"].max(), trend_df["Recent Daily"].max()) + 2
    fig_trend.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val], mode="lines", name="Baseline Parity (0% Growth)", line=dict(dash="dash", color="gray")))
    fig_trend.update_layout(height=420)
    st.plotly_chart(fig_trend, use_container_width=True)

    # Detailed Actionable Table
    st.subheader("Actionable Guidance by SKU")
    st.dataframe(
        trend_df[["Product", "Category", "Baseline Daily", "Recent Daily", "Demand Change (%)", "Classification", "Recommendation", "Confidence", "Explanation"]],
        use_container_width=True,
        hide_index=True,
    )


# -----------------------------------------------------------------------------
# Module C: Smart Price Segmentation
# -----------------------------------------------------------------------------
elif nav_choice == "🏷️ Smart Price Segmentation":
    st.title("🏷️ Smart Price Segmentation & Assortment Mix")
    st.caption("Classifies inventory across 4 tiers: Budget/Economy, Value/Affordable Quality, Standard, and Premium.")

    ctx = get_current_context()
    pricing_engine = ctx.pricing_engine

    col_cfg, col_mix = st.columns([1, 2])
    with col_cfg:
        st.subheader("Segmentation Method")
        method_choice = st.radio(
            "Classification Technique",
            ["Category-Specific Absolute Thresholds", "Category-Relative Quantiles (25/50/75th Percentiles)"],
        )
        pricing_engine.use_relative_quantiles = "Quantiles" in method_choice
        active_classifications = pricing_engine.classify_products(ctx.products)

    with col_mix:
        st.subheader("Customer Segment Target Mix vs Current Assortment")
        target_mix = {"Budget/Economy": 30.0, "Value/Affordable Quality": 40.0, "Standard/Mid-Range": 20.0, "Premium": 10.0}
        eval_mix = pricing_engine.evaluate_assortment_balance(active_classifications, target_mix)

        mix_df = pd.DataFrame([
            {"Segment": seg, "Target Mix (%)": target_mix[seg], "Actual Mix (%)": eval_mix["actual_mix"][seg], "Variance (%)": eval_mix["variance"][seg]}
            for seg in target_mix
        ])
        st.dataframe(mix_df, use_container_width=True, hide_index=True)

        if eval_mix.get("recommendations"):
            for rec in eval_mix["recommendations"]:
                st.info(f"💡 {rec}")

    st.markdown("---")

    # Segment Explorer & Alternative Finder
    st.subheader("Product Alternatives & Price Tier Matrix")
    sel_prod_id = st.selectbox(
        "Select a product to view lower-cost, similar, and premium alternatives in its category:",
        [p.product_id for p in ctx.products],
        format_func=lambda pid: f"{pid} - {next(p.product_name for p in ctx.products if p.product_id == pid)} ({next(p.category for p in ctx.products if p.product_id == pid)})",
    )

    alts = pricing_engine.find_alternatives(sel_prod_id, ctx.products, active_classifications)
    a1, a2, a3 = st.columns(3)

    with a1:
        st.markdown("**🟢 Lower-Cost / Budget Alternatives**")
        if alts["cheaper"]:
            for ch in alts["cheaper"]:
                st.write(f"- **{ch['product_name']}**: ₹{ch['selling_price']} ({ch['price_diff_pct']}%) [{ch['price_segment']}]")
        else:
            st.caption("No lower-cost options found in this category.")

    with a2:
        st.markdown("**🔵 Similar Price / Comparable Tier**")
        if alts["similar"]:
            for sm in alts["similar"]:
                st.write(f"- **{sm['product_name']}**: ₹{sm['selling_price']} ({sm['price_diff_pct']}%) [{sm['price_segment']}]")
        else:
            st.caption("No directly similar alternatives.")

    with a3:
        st.markdown("**🟣 Premium / Higher-Margin Alternatives**")
        if alts["premium"]:
            for pr in alts["premium"]:
                st.write(f"- **{pr['product_name']}**: ₹{pr['selling_price']} (+{pr['price_diff_pct']}%) [{pr['price_segment']}]")
        else:
            st.caption("No premium alternatives in this category.")


# -----------------------------------------------------------------------------
# Module D: Small-to-Large Supplier Comparison
# -----------------------------------------------------------------------------
elif nav_choice == "🚚 Supplier Comparison Matrix":
    st.title("🚚 Small-to-Large Supplier Intelligence Engine")
    st.caption("Compares Local/Small suppliers, Regional Distributors, and Large Wholesalers. Evaluates Landed Costs, MOQs, Lead Times, and Reliability.")

    ctx = get_current_context()
    sup_engine = ctx.supplier_engine

    # Product Selector
    prod_options = [p.product_id for p in ctx.products]
    sel_pid = st.selectbox(
        "Select Product to Compare Suppliers",
        prod_options,
        format_func=lambda pid: f"{pid} - {next(p.product_name for p in ctx.products if p.product_id == pid)}",
    )

    needed_units = st.number_input("Desired Order Quantity (Units)", min_value=1, value=20, step=5)

    compared_quotes = sup_engine.compare_suppliers_for_product(sel_pid, ctx.supplier_quotes, needed_qty=float(needed_units))

    if compared_quotes:
        comp_df = pd.DataFrame(compared_quotes)
        st.dataframe(
            comp_df[[
                "business_name", "supplier_scale", "base_unit_price", "discount_pct",
                "delivery_charge", "min_order_qty", "effective_unit_cost", "total_landed_cost",
                "delivery_lead_time_days", "reliability_score", "fit_score", "key_advantages", "trade_off_caveat"
            ]],
            use_container_width=True,
            hide_index=True,
            column_config={
                "effective_unit_cost": st.column_config.NumberColumn("Effective Unit Cost", format="₹%.2f"),
                "total_landed_cost": st.column_config.NumberColumn("Total Landed Cost", format="₹%.2f"),
                "fit_score": st.column_config.ProgressColumn("Composite Fit Score", min_value=0, max_value=100, format="%d"),
                "reliability_score": st.column_config.NumberColumn("Reliability", format="%.0f%%"),
            },
        )

        st.subheader("Transparent Trade-off Analysis")
        for q in compared_quotes:
            with st.container():
                st.markdown(f"**{q['business_name']}** ({q['supplier_scale']}) — Fit Score: **{q['fit_score']}/100**")
                st.write(f"- **Key Strengths**: {q['key_advantages']}")
                st.write(f"- **Caveats & Trade-offs**: {q['trade_off_caveat']}")
                st.write(f"- *Calculation*: Order Qty {q['order_qty']} × Base ₹{q['base_unit_price']} - {q['discount_pct']}% Vol. Discount + ₹{q['delivery_charge']} Delivery = **₹{q['total_landed_cost']:,.2f} Landed Cost** (₹{q['effective_unit_cost']:.2f}/unit).")
                st.markdown("---")
    else:
        st.warning(f"No supplier quotes registered for {sel_pid}.")


# -----------------------------------------------------------------------------
# Module F: Budget Purchasing Optimizer
# -----------------------------------------------------------------------------
elif nav_choice == "💰 Budget Purchasing Optimizer":
    st.title("💰 Budget-Aware Purchasing Optimizer")
    st.caption("Mathematically constrained optimization: Selects feasible purchasing bundles satisfying strict budget limits, supplier MOQs, landed costs, and lead times.")

    ctx = get_current_context()

    bcol1, bcol2, bcol3 = st.columns([1, 1, 1])
    with bcol1:
        budget_input = st.number_input("Available Capital Budget (₹)", min_value=500.0, max_value=500000.0, value=15000.0, step=1000.0)
    with bcol2:
        cat_choices = ["All Categories"] + sorted(list({p.category for p in ctx.products}))
        selected_cat = st.selectbox("Focus Category", cat_choices)
        target_cats = None if selected_cat == "All Categories" else [selected_cat]
    with bcol3:
        max_days = st.slider("Maximum Supplier Lead Time (Days)", 1, 14, 7)

    if st.button("🚀 Generate Optimal Purchase Plan", type="primary"):
        with st.spinner("Executing multi-attribute priority allocation algorithm..."):
            plan = ctx.optimizer.generate_plan(
                products=ctx.products,
                supplier_quotes=ctx.supplier_quotes,
                inventory_risks=ctx.inventory_risks,
                trend_analyses=ctx.trend_analyses,
                segment_classifications=ctx.price_classifications,
                total_budget=budget_input,
                target_categories=target_cats,
                max_delivery_days=max_days,
            )
            st.session_state.active_proposed_plan = plan
            ctx.cached_plans[plan.plan_id] = plan

    active_plan = st.session_state.active_proposed_plan
    if active_plan:
        st.success(active_plan.summary)

        # Plan metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Budget", f"₹{active_plan.total_budget:,.2f}")
        m2.metric("Allocated Capital", f"₹{active_plan.total_allocated:,.2f}", f"{(active_plan.total_allocated/active_plan.total_budget)*100:.1f}% Utilized")
        m3.metric("Remaining Unused Cash", f"₹{active_plan.remaining_budget:,.2f}")
        m4.metric("Purchase Items", f"{len(active_plan.items)} SKUs")

        if active_plan.items:
            st.subheader(f"Proposed Order Breakdown (Plan ID: `{active_plan.plan_id}`)")
            items_df = pd.DataFrame([
                {
                    "Product": i.product_name,
                    "Category": i.category,
                    "Price Segment": i.price_segment,
                    "Supplier": i.supplier_name,
                    "Scale": i.supplier_scale,
                    "Quantity": i.quantity,
                    "Unit Cost": i.effective_unit_cost,
                    "Total Landed Cost": i.total_cost,
                    "Lead Time": f"{i.lead_time_days}d",
                    "Urgency Score": i.urgency_score,
                    "Reason": i.reason_for_urgency,
                    "Expected Benefit": i.expected_benefit,
                    "Operational Risk": i.key_risk,
                }
                for i in active_plan.items
            ])
            st.dataframe(items_df, use_container_width=True, hide_index=True)

            if active_plan.unsatisfied_constraints:
                st.markdown("**Unsatisfied Constraints / Budget Exclusions:**")
                for u in active_plan.unsatisfied_constraints:
                    st.caption(f"• {u}")

            # Human Approval Workflow (Module H)
            st.markdown("### ✍️ Human Authorization & Decision Record")
            st.caption("Consequential actions require explicit human review. Approved orders are committed to the SQLite audit ledger.")

            review_col1, review_col2 = st.columns([2, 1])
            with review_col1:
                review_notes = st.text_input("Reviewer Notes / Authorisation Memo", f"Approved by store manager at {datetime.now().strftime('%H:%M')}")
            with review_col2:
                btn_approve, btn_reject = st.columns(2)
                with btn_approve:
                    if st.button("✅ Approve Plan", type="primary", use_container_width=True):
                        rec = ctx.decision_logger.log_decision(active_plan, "Approved", review_notes)
                        active_plan.status = "Approved"
                        st.balloons()
                        st.success(f"Plan `{active_plan.plan_id}` permanently approved as Decision `{rec.decision_id}`!")
                with btn_reject:
                    if st.button("❌ Reject Plan", use_container_width=True):
                        rec = ctx.decision_logger.log_decision(active_plan, "Rejected", review_notes)
                        active_plan.status = "Rejected"
                        st.warning(f"Plan `{active_plan.plan_id}` marked as Rejected in audit log.")


# -----------------------------------------------------------------------------
# Module G: Gemini AI Purchasing Agent
# -----------------------------------------------------------------------------
elif nav_choice == "🤖 Gemini AI Purchasing Agent":
    st.title("🤖 Gemini AI Purchasing Agent")
    st.caption("Official Google GenAI SDK integration with genuine function calling across 10 registered retail intelligence tools.")

    ctx = get_current_context()

    # Model Configuration & Status Bar
    agent = StockSenseGeminiAgent(
        api_key=st.session_state.gemini_api_key,
        model_name=st.session_state.gemini_model,
    )

    if not agent.api_key:
        st.info("ℹ️ **Deterministic Rule Engine Active**: No `GEMINI_API_KEY` set. The assistant executes the exact registered tools deterministically. To enable live Gemini AI generation, provide an API key in the sidebar or Settings page.")

    # Render previous messages
    for msg in st.session_state.chat_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("traces"):
                with st.expander(f"🛠️ Tool Execution Traces ({len(msg['traces'])} tools invoked)"):
                    for tr in msg["traces"]:
                        st.markdown(f"**Tool:** `{tr['tool']}`")
                        st.json(tr["arguments"])
                        st.code(tr["output_preview"], language="json")

    # Chat input
    if prompt := st.chat_input("Ask StockSense Rescue AI (e.g., 'I have ₹8,000. Identify urgent stockouts and make a purchase plan.')"):
        # Append user message
        st.session_state.chat_messages.append({"role": "user", "content": prompt, "traces": [], "plan_id": None})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Generate agent response
        with st.chat_message("assistant"):
            with st.spinner("StockSense AI analyzing catalog, evaluating risk math, and calling tools..."):
                res = agent.run(prompt, ctx)
                st.markdown(res.response_text)

                if res.error_message:
                    st.caption(f"🛡️ Note: {res.error_message}")

                if res.tool_calls:
                    with st.expander(f"🛠️ Tool Execution Traces ({len(res.tool_calls)} tools invoked)"):
                        for tr in res.tool_calls:
                            st.markdown(f"**Tool:** `{tr['tool']}`")
                            st.json(tr["arguments"])
                            st.code(tr["output_preview"], language="json")

                # Store assistant response in history
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": res.response_text,
                    "traces": res.tool_calls,
                    "plan_id": res.generated_plan_id,
                })

                # If plan generated, offer quick approval button
                if res.generated_plan_id and res.generated_plan_id in ctx.cached_plans:
                    plan_obj = ctx.cached_plans[res.generated_plan_id]
                    st.markdown("---")
                    st.markdown(f"**Quick Action for Plan `{plan_obj.plan_id}`:**")
                    col_app, col_rej = st.columns(2)
                    with col_app:
                        if st.button(f"✅ One-Click Approve Plan {plan_obj.plan_id}", key=f"app_{plan_obj.plan_id}"):
                            rec = ctx.decision_logger.log_decision(plan_obj, "Approved", "Approved via Gemini Agent chat interface")
                            st.success(f"Recorded Decision `{rec.decision_id}` in SQLite audit database!")
                    with col_rej:
                        if st.button(f"❌ Reject Plan {plan_obj.plan_id}", key=f"rej_{plan_obj.plan_id}"):
                            rec = ctx.decision_logger.log_decision(plan_obj, "Rejected", "Rejected via Gemini Agent chat interface")
                            st.warning(f"Recorded Rejection `{rec.decision_id}` in SQLite audit database.")


# -----------------------------------------------------------------------------
# Module H & I: Reports & Decision History
# -----------------------------------------------------------------------------
elif nav_choice == "📋 Reports & Decision History":
    st.title("📋 Reports & Decision Audit Trail")
    st.caption("Full SQLite decision ledger and exportable CSV reports with timestamped assumptions and data provenance.")

    ctx = get_current_context()
    exporter = ReportExporter(is_synthetic_data=st.session_state.is_synthetic)

    tab_audit, tab_reports = st.tabs(["🏛️ Human Decision Audit Ledger", "📥 Exportable CSV Reports"])

    with tab_audit:
        st.subheader("Persistent SQLite Decision Ledger")
        decisions_df = ctx.decision_logger.to_dataframe()
        if not decisions_df.empty:
            st.dataframe(decisions_df, use_container_width=True, hide_index=True)
            csv_audit = exporter.export_audit_trail_csv(decisions_df)
            st.download_button(
                "📥 Download Decision Audit Log (CSV)",
                data=csv_audit,
                file_name=f"stocksense_decision_audit_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )
        else:
            st.info("No decisions recorded yet. Generate a purchase plan and click 'Approve Plan' to record audit entries.")

    with tab_reports:
        st.subheader("Generate & Download Standard Reports")

        rcol1, rcol2 = st.columns(2)
        with rcol1:
            # 1. Inventory & Expiry CSV
            csv_inv = exporter.export_inventory_risks_csv(ctx.inventory_risks)
            st.download_button(
                "📥 Download Inventory & Expiry Risk Report (CSV)",
                data=csv_inv,
                file_name=f"stocksense_inventory_risk_report_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

            # 2. Trending Products CSV
            csv_trend = exporter.export_trends_csv(ctx.trend_analyses)
            st.download_button(
                "📥 Download Trending & Emerging Demand Report (CSV)",
                data=csv_trend,
                file_name=f"stocksense_trending_products_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with rcol2:
            # 3. Price Segmentation CSV
            csv_price = exporter.export_price_segments_csv(ctx.price_classifications)
            st.download_button(
                "📥 Download Price Segmentation Report (CSV)",
                data=csv_price,
                file_name=f"stocksense_price_segmentation_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

            # 4. Suggested Purchase Order CSV
            if st.session_state.active_proposed_plan:
                csv_po = exporter.export_purchase_order_csv(st.session_state.active_proposed_plan)
                st.download_button(
                    f"📥 Download Purchase Order ({st.session_state.active_proposed_plan.plan_id}) (CSV)",
                    data=csv_po,
                    file_name=f"stocksense_purchase_order_{st.session_state.active_proposed_plan.plan_id}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            else:
                st.button("📥 Purchase Order CSV (Generate a plan first)", disabled=True, use_container_width=True)


# -----------------------------------------------------------------------------
# Module: Settings & Data Provenance
# -----------------------------------------------------------------------------
elif nav_choice == "⚙️ Settings & Data Provenance":
    st.title("⚙️ System Settings & Data Management")
    st.caption("Configure Gemini API credentials, validate custom CSV uploads, and review data provenance.")

    # 1. Gemini Configuration
    st.subheader("🔑 Google Gemini API Configuration")
    api_key_input = st.text_input(
        "Gemini API Key",
        value=st.session_state.gemini_api_key,
        type="password",
        help="Get your free Gemini API Key from Google AI Studio (https://aistudio.google.com/)",
    )
    model_choice = st.selectbox(
        "Supported Gemini Model",
        ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
        index=0 if st.session_state.gemini_model == "gemini-2.5-flash" else 1,
    )

    if st.button("Save Gemini Settings", type="primary"):
        st.session_state.gemini_api_key = api_key_input.strip()
        st.session_state.gemini_model = model_choice
        st.success("Gemini configuration updated successfully!")

    st.markdown("---")

    # 2. Upload Custom Retail CSVs
    st.subheader("📤 Upload Custom Retail Datasets")
    st.write("Upload your own store inventory, supplier quotes, and sales CSVs. Uploads are strictly validated.")

    u_inv = st.file_uploader("Upload Inventory CSV (columns: product_id, product_name, category, current_stock, avg_daily_sales, cost_price, selling_price)", type=["csv"])
    if u_inv:
        try:
            raw_df = pd.read_csv(u_inv)
            v_res = validate_inventory_df(raw_df)
            if v_res.is_valid:
                st.session_state.inventory_df = v_res.cleaned_df
                st.session_state.is_synthetic = False
                st.success(f"Inventory CSV validated and loaded! ({len(v_res.cleaned_df)} products)")
            else:
                st.error(f"Validation failed: {', '.join(v_res.errors)}")
        except Exception as e:
            st.error(f"Failed to read CSV: {str(e)}")

    if st.button("🔄 Reset to Default Synthetic Demo Data"):
        st.session_state.inventory_df = st.session_state.data_loader.load_default_inventory()
        st.session_state.suppliers_df = st.session_state.data_loader.load_default_suppliers()
        st.session_state.sales_df = st.session_state.data_loader.load_default_sales()
        st.session_state.is_synthetic = True
        st.success("Reset to default synthetic FMCG demonstration dataset.")
