"""
StockSense Rescue AI - Decision Logger & Audit Trail (SQLite)
Maintains transparent, tamper-evident audit logs of proposed vs approved/rejected/revised purchasing plans.
Uses parameterized queries to safeguard against SQL injection and never persists API keys.
"""

from datetime import datetime
import json
import os
import sqlite3
from typing import Dict, List, Optional, Any
import pandas as pd

from src.models import DecisionRecord, PurchasePlan


class DecisionLogger:
    def __init__(self, db_path: str = "data/decisions.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    plan_id TEXT NOT NULL,
                    user_decision TEXT NOT NULL,
                    total_budget REAL NOT NULL,
                    total_cost REAL NOT NULL,
                    item_count INTEGER NOT NULL,
                    user_notes TEXT,
                    raw_plan_summary TEXT NOT NULL
                )
            """)
            conn.commit()

    def log_decision(
        self,
        plan: PurchasePlan,
        decision: str,  # "Approved", "Rejected", "Revised"
        user_notes: str = "",
    ) -> DecisionRecord:
        """Saves an approval/rejection decision with parameterized SQL query."""
        decision_id = f"DEC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{plan.plan_id[-4:]}"
        timestamp = datetime.now().isoformat()

        plan_summary = {
            "plan_id": plan.plan_id,
            "total_budget": plan.total_budget,
            "total_allocated": plan.total_allocated,
            "remaining_budget": plan.remaining_budget,
            "items": [
                {
                    "product_id": i.product_id,
                    "product_name": i.product_name,
                    "category": i.category,
                    "price_segment": i.price_segment,
                    "supplier_id": i.supplier_id,
                    "supplier_name": i.supplier_name,
                    "quantity": i.quantity,
                    "total_cost": i.total_cost,
                    "urgency_score": i.urgency_score,
                }
                for i in plan.items
            ],
            "unsatisfied_constraints": plan.unsatisfied_constraints,
        }

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO decisions (
                    decision_id, timestamp, plan_id, user_decision,
                    total_budget, total_cost, item_count, user_notes, raw_plan_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id,
                    timestamp,
                    plan.plan_id,
                    decision,
                    plan.total_budget,
                    plan.total_allocated,
                    len(plan.items),
                    user_notes,
                    json.dumps(plan_summary),
                ),
            )
            conn.commit()

        return DecisionRecord(
            decision_id=decision_id,
            timestamp=timestamp,
            plan_id=plan.plan_id,
            user_decision=decision,
            total_budget=plan.total_budget,
            total_cost=plan.total_allocated,
            item_count=len(plan.items),
            user_notes=user_notes,
            raw_plan_summary=plan_summary,
        )

    def get_all_decisions(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM decisions ORDER BY timestamp DESC")
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def to_dataframe(self) -> pd.DataFrame:
        records = self.get_all_decisions()
        if not records:
            return pd.DataFrame(columns=[
                "decision_id", "timestamp", "plan_id", "user_decision",
                "total_budget", "total_cost", "item_count", "user_notes"
            ])
        df = pd.DataFrame(records)
        if "raw_plan_summary" in df.columns:
            df = df.drop(columns=["raw_plan_summary"])
        return df
