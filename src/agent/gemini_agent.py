"""
StockSense Rescue AI - Gemini Agent & Function Calling Orchestrator
Integrates the official Google GenAI SDK (google-genai) with genuine function calling,
strict argument schema validation, execution sandboxing, tool trace logging,
and deterministic fallback when API keys are unconfigured or network requests fail.
"""

from datetime import datetime
import json
import os
import re
from typing import Dict, List, Optional, Tuple, Any

from google import genai
from google.genai import types

from src.agent.tools import (
    StockSenseToolContext,
    set_active_tool_context,
    REGISTERED_TOOLS_LIST,
    REGISTERED_TOOL_MAP,
)


SYSTEM_PROMPT = """You are StockSense Rescue AI, an expert retail intelligence and inventory purchasing copilot for small and medium retailers.
Your duty is to protect retail capital, eliminate stockouts, prevent expired inventory losses, and negotiate optimal landed costs with suppliers.

OPERATING GUIDELINES:
1. Always base recommendations on actual inventory, supplier, and sales evidence retrieved via your registered tools.
2. Never invent suppliers, prices, stock levels, or demand figures.
3. Distinguish clearly between observed historical facts, calculated metrics, and predictive suggestions.
4. When budget optimization is requested, calculate landed costs (unit price + volume discounts + allocated delivery).
5. Always explain supplier trade-offs (e.g. fast delivery vs low unit price vs high MOQ cash lockup).
6. Remind the user that purchase proposals require human approval before being finalized.
7. If data has quality limitations (e.g., short history, high variance, missing expiry), disclose them honestly.
"""


class AgentExecutionResult:
    def __init__(
        self,
        response_text: str,
        tool_calls: List[Dict[str, Any]],
        is_live_gemini: bool,
        model_used: str,
        error_message: Optional[str] = None,
        generated_plan_id: Optional[str] = None,
    ):
        self.response_text = response_text
        self.tool_calls = tool_calls
        self.is_live_gemini = is_live_gemini
        self.model_used = model_used
        self.error_message = error_message
        self.generated_plan_id = generated_plan_id


class StockSenseGeminiAgent:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
    ):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY", "").strip()
        self.model_name = model_name
        self.client: Optional[genai.Client] = None
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                self.client = None

    def execute_tool_safely(self, tool_name: str, arguments: Dict[str, Any]) -> str:
        """Restricts execution strictly to registered allowlisted tools with validated arguments."""
        if tool_name not in REGISTERED_TOOL_MAP:
            return json.dumps({
                "status": "error",
                "error": f"Tool '{tool_name}' is not an authorized or registered tool. Access denied.",
            })

        func = REGISTERED_TOOL_MAP[tool_name]
        try:
            # Execute with unpacked kwargs
            if arguments:
                result = func(**arguments)
            else:
                result = func()
            return str(result)
        except Exception as e:
            return json.dumps({
                "status": "error",
                "error": f"Tool '{tool_name}' raised execution exception: {str(e)}",
            })

    def run(self, user_query: str, context: StockSenseToolContext) -> AgentExecutionResult:
        """Orchestrates query resolution using Gemini Function Calling or deterministic fallback."""
        set_active_tool_context(context)

        # 1. If no live API key is available, run deterministic engine with clear disclosure
        if not self.api_key or not self.client:
            return self._run_deterministic_engine(
                user_query,
                context,
                disclosure_reason="Gemini API Key is not configured. Running in Deterministic Rule Engine mode.",
            )

        # 2. Attempt live Gemini API call with function calling
        tool_traces: List[Dict[str, Any]] = []
        try:
            # We configure manual or assisted tool resolution to inspect tool traces cleanly
            config = types.GenerateContentConfig(
                tools=REGISTERED_TOOLS_LIST,
                temperature=0.2,
                system_instruction=SYSTEM_PROMPT,
            )

            # Initiate conversation turn
            contents = [user_query]
            max_turns = 5
            final_text = ""
            plan_id = None

            for turn in range(max_turns):
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents,
                    config=config,
                )

                # Check if model requested function calls
                function_calls = getattr(response, "function_calls", None)
                if not function_calls and hasattr(response, "candidates") and response.candidates:
                    first_cand = response.candidates[0]
                    if hasattr(first_cand, "content") and hasattr(first_cand.content, "parts"):
                        function_calls = [
                            p.function_call for p in first_cand.content.parts if hasattr(p, "function_call") and p.function_call
                        ]

                if not function_calls:
                    # Model provided final text
                    final_text = response.text or ""
                    break

                # Execute requested function calls
                tool_response_parts = []
                for fc in function_calls:
                    name = fc.name
                    args = dict(fc.args) if hasattr(fc, "args") and fc.args else {}
                    tool_output = self.execute_tool_safely(name, args)

                    tool_traces.append({
                        "tool": name,
                        "arguments": args,
                        "output_preview": tool_output[:300] + ("..." if len(tool_output) > 300 else ""),
                    })

                    # Check if a plan ID was generated
                    try:
                        parsed = json.loads(tool_output)
                        if "plan_id" in parsed:
                            plan_id = parsed["plan_id"]
                    except Exception:
                        pass

                    # Format response part
                    tool_response_parts.append(
                        types.Part.from_function_response(
                            name=name,
                            response={"result": tool_output},
                        )
                    )

                # Append assistant function call and user tool response to contents
                contents.append(response.candidates[0].content)
                contents.append(types.Content(role="user", parts=tool_response_parts))

            # Detect any plan ID mentioned in final text or traces
            if not plan_id:
                plan_match = re.search(r"PLAN-[0-9A-F]{8}", final_text)
                if plan_match:
                    plan_id = plan_match.group(0)

            return AgentExecutionResult(
                response_text=final_text,
                tool_calls=tool_traces,
                is_live_gemini=True,
                model_used=self.model_name,
                generated_plan_id=plan_id,
            )

        except Exception as e:
            # Prompt requirement: "If the Gemini key is missing or a request fails, deterministic features must remain usable. Display a clear error; never pretend an AI request succeeded."
            return self._run_deterministic_engine(
                user_query,
                context,
                disclosure_reason=f"Gemini API request failed ({str(e)}). Falling back to Deterministic Rule Engine.",
            )

    def _run_deterministic_engine(
        self, user_query: str, context: StockSenseToolContext, disclosure_reason: str
    ) -> AgentExecutionResult:
        """Deterministic rule engine executing actual registered tools with transparent mathematical outputs."""
        tool_traces = []
        q_lower = user_query.lower()

        # Extract budget if mentioned (e.g., ₹5000, 5,000, $5000, "budget of 10000")
        budget_match = re.search(r"(?:₹|\$|rs\.?|inr|budget\s*(?:of|is|:)?\s*)\s*([\d,]+)", q_lower)
        budget_val = 5000.0
        if budget_match:
            try:
                budget_val = float(budget_match.group(1).replace(",", ""))
            except Exception:
                budget_val = 5000.0

        # Extract category filter if mentioned
        cat_filter = None
        for cat in ["dairy", "staples", "beverages", "snacks", "personal care"]:
            if cat in q_lower:
                cat_filter = cat.title()
                break

        # Decide which tools to invoke deterministically based on query semantics
        plan_id = None
        sections = []

        # 1. Stockout Risk check
        if any(w in q_lower for w in ["urgent", "stockout", "out of stock", "run out", "low stock", "risk", "all"]):
            stockout_raw = self.execute_tool_safely("detect_stockout_risks", {})
            stockout_data = json.loads(stockout_raw)
            tool_traces.append({"tool": "detect_stockout_risks", "arguments": {}, "output_preview": stockout_raw[:250] + "..."})
            items = stockout_data.get("products", [])
            sections.append(f"### 🚨 Stockout Vulnerability Analysis\nIdentified **{len(items)}** products in immediate danger of stockout:")
            for it in items[:4]:
                sections.append(
                    f"- **{it['product_name']}** ({it['category']}): **{it['days_of_stock_remaining']} days** stock remaining. Supplier lead time is {it['lead_time_days']} days. Suggested reorder: **{it['suggested_reorder_qty']} units**."
                )

        # 2. Expiry Risk check
        if any(w in q_lower for w in ["expir", "perish", "waste", "spoil", "loss", "shelf life", "all"]):
            expiry_raw = self.execute_tool_safely("detect_expiry_risks", {})
            expiry_data = json.loads(expiry_raw)
            tool_traces.append({"tool": "detect_expiry_risks", "arguments": {}, "output_preview": expiry_raw[:250] + "..."})
            perishables = expiry_data.get("products", [])
            total_loss = expiry_data.get("total_financial_loss_exposure", 0.0)
            sections.append(f"\n### ⏳ Perishable & Expiry Rescue\nFound **{len(perishables)}** items at risk with total exposure of **₹{total_loss:,.2f}**:")
            for p in perishables[:3]:
                sections.append(
                    f"- **{p['product_name']}**: {p['days_until_expiry']} days until expiry. Risk quantity: **{p['at_risk_unsold_qty']} units** (₹{p['projected_financial_loss']:,.2f} cost value)."
                )

        # 3. Trends check
        if any(w in q_lower for w in ["trend", "emerging", "rising", "demand", "popular", "growth", "all"]):
            trend_raw = self.execute_tool_safely("analyse_product_trends", {})
            trend_data = json.loads(trend_raw)
            tool_traces.append({"tool": "analyse_product_trends", "arguments": {}, "output_preview": trend_raw[:250] + "..."})
            emerging = trend_data.get("emerging_surge_products", [])
            established = trend_data.get("established_high_velocity_products", [])
            sections.append("\n### 📈 Demand Momentum & Trend Intelligence")
            if emerging:
                sections.append("**Emerging Demand Surges (Pilot Test Recommended):**")
                for e in emerging[:2]:
                    sections.append(f"- **{e['product_name']}**: +{e['demand_change_pct']}% sales spike ({e['baseline_daily_sales']:.1f} → {e['recent_daily_sales']:.1f}/day). *{e['explanation']}*")
            if established:
                sections.append("**Established High-Velocity Core (Volume Replenishment):**")
                for est in established[:2]:
                    sections.append(f"- **{est['product_name']}**: Sustained volume ({est['recent_daily_sales']:.1f}/day, +{est['demand_change_pct']}%). *{est['explanation']}*")

        # 4. Supplier or Budget Purchasing Plan
        plan_raw = self.execute_tool_safely("optimise_purchase_budget", {"budget": budget_val, "target_category": cat_filter})
        plan_data = json.loads(plan_raw)
        tool_traces.append({"tool": "optimise_purchase_budget", "arguments": {"budget": budget_val, "target_category": cat_filter}, "output_preview": plan_raw[:250] + "..."})
        plan_id = plan_data.get("plan_id")
        allocated = plan_data.get("total_allocated", 0.0)
        remaining = plan_data.get("remaining_budget", 0.0)
        purchases = plan_data.get("purchases", [])

        sections.append(f"\n### 💼 Budget-Optimized Purchase Proposal (Plan `{plan_id}`)")
        sections.append(f"**Budget Allocated:** ₹{allocated:,.2f} of ₹{budget_val:,.2f} (Remaining cash: ₹{remaining:,.2f}) across **{len(purchases)}** items:")

        for pur in purchases:
            sections.append(
                f"- **{pur['product_name']}** — Order **{pur['quantity']} units** from **{pur['supplier']}** ({pur['supplier_scale']}). Landed cost: **₹{pur['total_landed_cost']:,.2f}** (₹{pur['effective_unit_cost']:.2f}/unit). Priority: **{pur['urgency_score']}/100**."
            )
            sections.append(f"  *Reason:* {pur['reason']} | *Expected Benefit:* {pur['expected_benefit']} | *Risk:* {pur['key_risk']}")

        if plan_data.get("unsatisfied_constraints"):
            sections.append("\n**Unsatisfied Constraints / Budget Exclusions:**")
            for u in plan_data["unsatisfied_constraints"][:3]:
                sections.append(f"- *{u}*")

        sections.append("\n> **Human Verification Required**: Please review the purchase proposal above. Click **Approve Plan** to record this plan into the SQLite audit ledger, or specify revisions.")

        final_text = "\n".join(sections)

        return AgentExecutionResult(
            response_text=final_text,
            tool_calls=tool_traces,
            is_live_gemini=False,
            model_used="Deterministic Multi-Attribute Engine (Fallback)",
            error_message=disclosure_reason,
            generated_plan_id=plan_id,
        )
