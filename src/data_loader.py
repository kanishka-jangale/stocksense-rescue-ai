"""
StockSense Rescue AI - Safe Data Loader & Schema Validator
Handles reading, sanitizing, and validating inventory, supplier, and historical sales datasets.
Rejects malformed inputs, protects against CSV formula injection, and handles zero/negative values safely.
"""

from datetime import datetime
import os
from typing import Dict, List, Optional, Tuple, Any
import pandas as pd

from src.models import Product, SupplierQuote


REQUIRED_INVENTORY_COLUMNS = [
    "product_id",
    "product_name",
    "category",
    "current_stock",
    "avg_daily_sales",
    "cost_price",
    "selling_price",
]

REQUIRED_SUPPLIER_COLUMNS = [
    "supplier_id",
    "business_name",
    "supplier_scale",
    "product_id",
    "unit_purchase_price",
    "min_order_qty",
    "available_qty",
    "delivery_lead_time_days",
    "delivery_charge",
]

REQUIRED_SALES_COLUMNS = [
    "date",
    "product_id",
    "units_sold",
]


class ValidationResult:
    def __init__(self, is_valid: bool, errors: List[str], warnings: List[str], cleaned_df: Optional[pd.DataFrame] = None):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings
        self.cleaned_df = cleaned_df


def sanitize_cell_value(val: Any) -> Any:
    """Guards against CSV formula injection (=, +, -, @) and trims whitespace."""
    if isinstance(val, str):
        cleaned = val.strip()
        if cleaned.startswith(("=", "+", "-", "@")) and not cleaned.replace(".", "", 1).lstrip("+-").isdigit():
            cleaned = "'" + cleaned
        return cleaned
    return val


def validate_inventory_df(df: pd.DataFrame) -> ValidationResult:
    """Validates inventory dataset columns, ranges, and types."""
    errors = []
    warnings = []

    # Column presence check
    missing_cols = [c for c in REQUIRED_INVENTORY_COLUMNS if c not in df.columns]
    if missing_cols:
        return ValidationResult(False, [f"Missing required inventory columns: {', '.join(missing_cols)}"], warnings)

    cleaned = df.copy()

    # Sanitize string columns
    for col in ["product_id", "product_name", "category", "primary_supplier_id", "unit"]:
        if col in cleaned.columns:
            cleaned[col] = cleaned[col].astype(str).map(sanitize_cell_value)

    # Validate and clean numeric fields
    numeric_cols = ["current_stock", "avg_daily_sales", "cost_price", "selling_price", "safety_stock", "min_reorder_qty"]
    for col in numeric_cols:
        if col in cleaned.columns:
            cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce").fillna(0.0)
            # Detect negative values
            neg_count = (cleaned[col] < 0).sum()
            if neg_count > 0:
                warnings.append(f"Found {neg_count} negative values in '{col}'. Clamped negative numbers to 0.0.")
                cleaned[col] = cleaned[col].clip(lower=0.0)

    # Expiry date parsing
    if "expiry_date" in cleaned.columns:
        parsed_dates = []
        for idx, val in cleaned["expiry_date"].items():
            if pd.isna(val) or str(val).strip() in ("", "nan", "None", "NaT"):
                parsed_dates.append(None)
            else:
                try:
                    dt = pd.to_datetime(val).strftime("%Y-%m-%d")
                    parsed_dates.append(dt)
                except Exception:
                    warnings.append(f"Row {idx}: Invalid expiry date '{val}', treating as non-perishable.")
                    parsed_dates.append(None)
        cleaned["expiry_date"] = parsed_dates
    else:
        cleaned["expiry_date"] = None
        warnings.append("No 'expiry_date' column found; expiry tracking will be inactive for these items.")

    # Check for empty products
    cleaned = cleaned[cleaned["product_id"].astype(str).str.strip() != ""]
    if len(cleaned) == 0:
        errors.append("Inventory dataset is empty after removing invalid rows.")
        return ValidationResult(False, errors, warnings)

    return ValidationResult(True, errors, warnings, cleaned)


def validate_supplier_df(df: pd.DataFrame) -> ValidationResult:
    """Validates supplier dataset columns, lead times, prices, and MOQs."""
    errors = []
    warnings = []

    missing_cols = [c for c in REQUIRED_SUPPLIER_COLUMNS if c not in df.columns]
    if missing_cols:
        return ValidationResult(False, [f"Missing required supplier columns: {', '.join(missing_cols)}"], warnings)

    cleaned = df.copy()

    for col in ["supplier_id", "business_name", "supplier_scale", "product_id", "service_area", "return_policy"]:
        if col in cleaned.columns:
            cleaned[col] = cleaned[col].astype(str).map(sanitize_cell_value)

    num_cols = ["unit_purchase_price", "min_order_qty", "available_qty", "delivery_lead_time_days", "delivery_charge", "discount_pct", "reliability_score"]
    for col in num_cols:
        if col in cleaned.columns:
            cleaned[col] = pd.to_numeric(cleaned[col], errors="coerce").fillna(0.0)
            cleaned[col] = cleaned[col].clip(lower=0.0)

    # Reliability score bounds [0.0, 1.0]
    if "reliability_score" in cleaned.columns:
        # If user passed percentage (e.g., 95 instead of 0.95)
        cleaned["reliability_score"] = cleaned["reliability_score"].map(lambda x: x / 100.0 if x > 1.0 else x)
        cleaned["reliability_score"] = cleaned["reliability_score"].clip(lower=0.0, upper=1.0)

    if len(cleaned) == 0:
        errors.append("Supplier dataset has no valid rows.")
        return ValidationResult(False, errors, warnings)

    return ValidationResult(True, errors, warnings, cleaned)


def validate_sales_df(df: pd.DataFrame) -> ValidationResult:
    """Validates historical sales dataset."""
    errors = []
    warnings = []

    missing_cols = [c for c in REQUIRED_SALES_COLUMNS if c not in df.columns]
    if missing_cols:
        return ValidationResult(False, [f"Missing required sales columns: {', '.join(missing_cols)}"], warnings)

    cleaned = df.copy()
    cleaned["product_id"] = cleaned["product_id"].astype(str).map(sanitize_cell_value)
    cleaned["units_sold"] = pd.to_numeric(cleaned["units_sold"], errors="coerce").fillna(0.0).clip(lower=0.0)

    try:
        cleaned["date"] = pd.to_datetime(cleaned["date"]).dt.strftime("%Y-%m-%d")
    except Exception as e:
        warnings.append(f"Some dates could not be parsed: {str(e)}")

    return ValidationResult(True, errors, warnings, cleaned)


class DataLoader:
    """Encapsulates loading and providing datasets with provenance tags."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.is_synthetic = True
        self.data_source_description = "Synthetic Demonstration Dataset (Retail Kirana FMCG Model)"

    def load_default_inventory(self) -> pd.DataFrame:
        path = os.path.join(self.data_dir, "sample_inventory.csv")
        df = pd.read_csv(path)
        res = validate_inventory_df(df)
        return res.cleaned_df if res.is_valid else pd.DataFrame()

    def load_default_suppliers(self) -> pd.DataFrame:
        path = os.path.join(self.data_dir, "sample_suppliers.csv")
        df = pd.read_csv(path)
        res = validate_supplier_df(df)
        return res.cleaned_df if res.is_valid else pd.DataFrame()

    def load_default_sales(self) -> pd.DataFrame:
        path = os.path.join(self.data_dir, "sample_historical_sales.csv")
        df = pd.read_csv(path)
        res = validate_sales_df(df)
        return res.cleaned_df if res.is_valid else pd.DataFrame()

    def products_from_df(self, df: pd.DataFrame) -> List[Product]:
        products = []
        for _, r in df.iterrows():
            products.append(
                Product(
                    product_id=str(r["product_id"]),
                    product_name=str(r["product_name"]),
                    category=str(r["category"]),
                    current_stock=float(r["current_stock"]),
                    avg_daily_sales=float(r["avg_daily_sales"]),
                    cost_price=float(r["cost_price"]),
                    selling_price=float(r["selling_price"]),
                    safety_stock=float(r.get("safety_stock", 0.0)),
                    primary_supplier_id=str(r.get("primary_supplier_id", "")),
                    unit=str(r.get("unit", "unit")),
                    expiry_date=r.get("expiry_date") if pd.notna(r.get("expiry_date")) else None,
                    min_reorder_qty=float(r.get("min_reorder_qty", 1.0)),
                )
            )
        return products

    def suppliers_from_df(self, df: pd.DataFrame) -> List[SupplierQuote]:
        suppliers = []
        for _, r in df.iterrows():
            suppliers.append(
                SupplierQuote(
                    supplier_id=str(r["supplier_id"]),
                    business_name=str(r["business_name"]),
                    supplier_scale=str(r["supplier_scale"]),
                    service_area=str(r.get("service_area", "Standard Service Area")),
                    product_id=str(r["product_id"]),
                    unit_purchase_price=float(r["unit_purchase_price"]),
                    min_order_qty=float(r["min_order_qty"]),
                    available_qty=float(r["available_qty"]),
                    delivery_lead_time_days=int(r["delivery_lead_time_days"]),
                    delivery_charge=float(r["delivery_charge"]),
                    discount_pct=float(r.get("discount_pct", 0.0)),
                    return_policy=str(r.get("return_policy", "Standard")),
                    reliability_score=float(r.get("reliability_score", 0.9)),
                    last_price_update=str(r.get("last_price_update", datetime.now().strftime("%Y-%m-%d"))),
                )
            )
        return suppliers
