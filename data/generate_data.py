import csv
from datetime import datetime, timedelta
import random

# Seed for reproducible realistic data
random.seed(42)

today = datetime.now().date()

# 1. SAMPLE INVENTORY
inventory_data = [
    # Dairy & Perishables (high expiry sensitivity)
    {"product_id": "P-101", "product_name": "Fresh Cow Milk 1L", "category": "Dairy", "current_stock": 12, "avg_daily_sales": 25.0, "cost_price": 42.0, "selling_price": 50.0, "expiry_date": (today + timedelta(days=3)).strftime("%Y-%m-%d"), "safety_stock": 15, "primary_supplier_id": "SUP-LOC-01", "unit": "pack"},
    {"product_id": "P-102", "product_name": "Greek Yogurt 400g", "category": "Dairy", "current_stock": 45, "avg_daily_sales": 4.0, "cost_price": 85.0, "selling_price": 115.0, "expiry_date": (today + timedelta(days=6)).strftime("%Y-%m-%d"), "safety_stock": 8, "primary_supplier_id": "SUP-REG-01", "unit": "cup"},
    {"product_id": "P-103", "product_name": "Artisanal Cheddar 200g", "category": "Dairy", "current_stock": 8, "avg_daily_sales": 1.5, "cost_price": 210.0, "selling_price": 290.0, "expiry_date": (today + timedelta(days=45)).strftime("%Y-%m-%d"), "safety_stock": 5, "primary_supplier_id": "SUP-NAT-01", "unit": "block"},
    {"product_id": "P-104", "product_name": "Paneer Fresh 500g", "category": "Dairy", "current_stock": 6, "avg_daily_sales": 10.0, "cost_price": 140.0, "selling_price": 175.0, "expiry_date": (today + timedelta(days=5)).strftime("%Y-%m-%d"), "safety_stock": 10, "primary_supplier_id": "SUP-LOC-01", "unit": "pack"},

    # Staples & Grains
    {"product_id": "P-201", "product_name": "Premium Basmati Rice 5kg", "category": "Staples", "current_stock": 18, "avg_daily_sales": 3.0, "cost_price": 420.0, "selling_price": 520.0, "expiry_date": (today + timedelta(days=360)).strftime("%Y-%m-%d"), "safety_stock": 10, "primary_supplier_id": "SUP-REG-01", "unit": "bag"},
    {"product_id": "P-202", "product_name": "Economy Sona Masoori Rice 5kg", "category": "Staples", "current_stock": 35, "avg_daily_sales": 6.0, "cost_price": 210.0, "selling_price": 255.0, "expiry_date": (today + timedelta(days=300)).strftime("%Y-%m-%d"), "safety_stock": 15, "primary_supplier_id": "SUP-NAT-01", "unit": "bag"},
    {"product_id": "P-203", "product_name": "Organic Quinoa 1kg", "category": "Staples", "current_stock": 5, "avg_daily_sales": 1.2, "cost_price": 280.0, "selling_price": 395.0, "expiry_date": (today + timedelta(days=180)).strftime("%Y-%m-%d"), "safety_stock": 4, "primary_supplier_id": "SUP-REG-01", "unit": "pouch"},
    {"product_id": "P-204", "product_name": "Refined Sunflower Oil 1L", "category": "Staples", "current_stock": 8, "avg_daily_sales": 8.0, "cost_price": 110.0, "selling_price": 135.0, "expiry_date": (today + timedelta(days=210)).strftime("%Y-%m-%d"), "safety_stock": 12, "primary_supplier_id": "SUP-LOC-02", "unit": "pouch"},
    {"product_id": "P-205", "product_name": "Cold Pressed Mustard Oil 1L", "category": "Staples", "current_stock": 22, "avg_daily_sales": 2.5, "cost_price": 165.0, "selling_price": 225.0, "expiry_date": (today + timedelta(days=240)).strftime("%Y-%m-%d"), "safety_stock": 6, "primary_supplier_id": "SUP-REG-02", "unit": "bottle"},
    {"product_id": "P-206", "product_name": "Iodized Salt 1kg", "category": "Staples", "current_stock": 50, "avg_daily_sales": 5.0, "cost_price": 18.0, "selling_price": 25.0, "expiry_date": "", "safety_stock": 20, "primary_supplier_id": "SUP-NAT-01", "unit": "pack"},

    # Beverages
    {"product_id": "P-301", "product_name": "Everyday Black Tea 500g", "category": "Beverages", "current_stock": 14, "avg_daily_sales": 4.0, "cost_price": 145.0, "selling_price": 190.0, "expiry_date": (today + timedelta(days=270)).strftime("%Y-%m-%d"), "safety_stock": 10, "primary_supplier_id": "SUP-NAT-02", "unit": "box"},
    {"product_id": "P-302", "product_name": "Single Origin Coffee Beans 250g", "category": "Beverages", "current_stock": 4, "avg_daily_sales": 1.8, "cost_price": 310.0, "selling_price": 450.0, "expiry_date": (today + timedelta(days=90)).strftime("%Y-%m-%d"), "safety_stock": 5, "primary_supplier_id": "SUP-LOC-02", "unit": "pouch"},
    {"product_id": "P-303", "product_name": "Herbal Green Tea 25 Bags", "category": "Beverages", "current_stock": 28, "avg_daily_sales": 2.0, "cost_price": 120.0, "selling_price": 165.0, "expiry_date": (today + timedelta(days=150)).strftime("%Y-%m-%d"), "safety_stock": 8, "primary_supplier_id": "SUP-REG-01", "unit": "box"},
    {"product_id": "P-304", "product_name": "Instant Energy Drink 500ml", "category": "Beverages", "current_stock": 3, "avg_daily_sales": 6.5, "cost_price": 35.0, "selling_price": 50.0, "expiry_date": (today + timedelta(days=120)).strftime("%Y-%m-%d"), "safety_stock": 10, "primary_supplier_id": "SUP-LOC-01", "unit": "can"},

    # Snacks & Packaged Foods (Emerging demand items included)
    {"product_id": "P-401", "product_name": "Roasted Makhana Herbs 100g", "category": "Snacks", "current_stock": 7, "avg_daily_sales": 5.2, "cost_price": 68.0, "selling_price": 110.0, "expiry_date": (today + timedelta(days=75)).strftime("%Y-%m-%d"), "safety_stock": 8, "primary_supplier_id": "SUP-REG-02", "unit": "pouch"},
    {"product_id": "P-402", "product_name": "Classic Salted Chips 50g", "category": "Snacks", "current_stock": 65, "avg_daily_sales": 12.0, "cost_price": 15.0, "selling_price": 20.0, "expiry_date": (today + timedelta(days=60)).strftime("%Y-%m-%d"), "safety_stock": 25, "primary_supplier_id": "SUP-NAT-02", "unit": "pack"},
    {"product_id": "P-403", "product_name": "Artisanal Dark Chocolate 80g", "category": "Snacks", "current_stock": 9, "avg_daily_sales": 1.0, "cost_price": 125.0, "selling_price": 195.0, "expiry_date": (today + timedelta(days=110)).strftime("%Y-%m-%d"), "safety_stock": 4, "primary_supplier_id": "SUP-LOC-02", "unit": "bar"},
    {"product_id": "P-404", "product_name": "Millet Cookies 200g", "category": "Snacks", "current_stock": 6, "avg_daily_sales": 3.8, "cost_price": 75.0, "selling_price": 120.0, "expiry_date": (today + timedelta(days=80)).strftime("%Y-%m-%d"), "safety_stock": 8, "primary_supplier_id": "SUP-REG-01", "unit": "box"},

    # Personal Care & Hygiene
    {"product_id": "P-501", "product_name": "Ayurvedic Neem Soap 125g", "category": "Personal Care", "current_stock": 40, "avg_daily_sales": 4.5, "cost_price": 28.0, "selling_price": 40.0, "expiry_date": (today + timedelta(days=450)).strftime("%Y-%m-%d"), "safety_stock": 15, "primary_supplier_id": "SUP-NAT-01", "unit": "bar"},
    {"product_id": "P-502", "product_name": "Luxury Argan Hair Serum 50ml", "category": "Personal Care", "current_stock": 2, "avg_daily_sales": 0.8, "cost_price": 380.0, "selling_price": 599.0, "expiry_date": (today + timedelta(days=365)).strftime("%Y-%m-%d"), "safety_stock": 3, "primary_supplier_id": "SUP-REG-02", "unit": "bottle"},
    {"product_id": "P-503", "product_name": "Herbal Toothpaste 150g", "category": "Personal Care", "current_stock": 18, "avg_daily_sales": 3.2, "cost_price": 62.0, "selling_price": 85.0, "expiry_date": (today + timedelta(days=400)).strftime("%Y-%m-%d"), "safety_stock": 10, "primary_supplier_id": "SUP-NAT-02", "unit": "tube"},
    {"product_id": "P-504", "product_name": "Eco Bamboo Toothbrush 4pk", "category": "Personal Care", "current_stock": 11, "avg_daily_sales": 1.4, "cost_price": 95.0, "selling_price": 160.0, "expiry_date": "", "safety_stock": 5, "primary_supplier_id": "SUP-LOC-02", "unit": "pack"},
    
    # Dead / Slow Mover (zero or near-zero sales for testing)
    {"product_id": "P-601", "product_name": "Specialty Truffle Glaze 150ml", "category": "Staples", "current_stock": 14, "avg_daily_sales": 0.0, "cost_price": 450.0, "selling_price": 650.0, "expiry_date": (today + timedelta(days=40)).strftime("%Y-%m-%d"), "safety_stock": 2, "primary_supplier_id": "SUP-LOC-02", "unit": "bottle"},
]

with open("C:/Users/Admin/.gemini/antigravity/scratch/stocksense-rescue-ai/data/sample_inventory.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(inventory_data[0].keys()))
    writer.writeheader()
    writer.writerows(inventory_data)

# 2. SAMPLE SUPPLIERS (Multiple supplier options for each product across Local, Regional, National Wholesalers)
supplier_names = {
    "SUP-LOC-01": {"name": "Metro Local Fresh Wholesale", "scale": "Local/Small", "area": "Within 15km City Zone"},
    "SUP-LOC-02": {"name": "Sunrise Local Traders", "scale": "Local/Small", "area": "Metro Area Express"},
    "SUP-REG-01": {"name": "Apex Regional Distribution Hub", "scale": "Regional Distributor", "area": "Statewide / Tri-County"},
    "SUP-REG-02": {"name": "Vanguard Regional Logistics", "scale": "Regional Distributor", "area": "Northern Regional Grid"},
    "SUP-NAT-01": {"name": "Bharat Mega Wholesale Corp", "scale": "Large Wholesaler", "area": "National Freight Network"},
    "SUP-NAT-02": {"name": "Global Direct FMCG Mills", "scale": "Large Wholesaler", "area": "Direct Factory Rail"},
}

supplier_rows = [
    # Milk
    {"supplier_id": "SUP-LOC-01", "product_id": "P-101", "unit_purchase_price": 42.0, "min_order_qty": 10, "available_qty": 200, "delivery_lead_time_days": 1, "delivery_charge": 50.0, "discount_pct": 0.0, "return_policy": "Full Credit on souring", "reliability_score": 0.96},
    {"supplier_id": "SUP-REG-01", "product_id": "P-101", "unit_purchase_price": 39.5, "min_order_qty": 50, "available_qty": 1000, "delivery_lead_time_days": 3, "delivery_charge": 120.0, "discount_pct": 2.0, "return_policy": "Credit memo within 24h", "reliability_score": 0.91},
    
    # Yogurt
    {"supplier_id": "SUP-REG-01", "product_id": "P-102", "unit_purchase_price": 85.0, "min_order_qty": 20, "available_qty": 300, "delivery_lead_time_days": 2, "delivery_charge": 80.0, "discount_pct": 3.0, "return_policy": "Expiry return 50% buyback", "reliability_score": 0.94},
    {"supplier_id": "SUP-LOC-01", "product_id": "P-102", "unit_purchase_price": 90.0, "min_order_qty": 5, "available_qty": 50, "delivery_lead_time_days": 1, "delivery_charge": 30.0, "discount_pct": 0.0, "return_policy": "Same-day replacement", "reliability_score": 0.97},

    # Basmati Rice
    {"supplier_id": "SUP-REG-01", "product_id": "P-201", "unit_purchase_price": 420.0, "min_order_qty": 10, "available_qty": 250, "delivery_lead_time_days": 3, "delivery_charge": 150.0, "discount_pct": 3.0, "return_policy": "30-day exchange", "reliability_score": 0.92},
    {"supplier_id": "SUP-NAT-01", "product_id": "P-201", "unit_purchase_price": 385.0, "min_order_qty": 40, "available_qty": 1500, "delivery_lead_time_days": 6, "delivery_charge": 300.0, "discount_pct": 5.0, "return_policy": "Damaged sacks replaced only", "reliability_score": 0.88},
    {"supplier_id": "SUP-LOC-02", "product_id": "P-201", "unit_purchase_price": 435.0, "min_order_qty": 5, "available_qty": 80, "delivery_lead_time_days": 1, "delivery_charge": 50.0, "discount_pct": 0.0, "return_policy": "100% money back", "reliability_score": 0.98},

    # Economy Rice
    {"supplier_id": "SUP-NAT-01", "product_id": "P-202", "unit_purchase_price": 210.0, "min_order_qty": 30, "available_qty": 2000, "delivery_lead_time_days": 5, "delivery_charge": 250.0, "discount_pct": 4.0, "return_policy": "Damaged sacks only", "reliability_score": 0.89},
    {"supplier_id": "SUP-REG-01", "product_id": "P-202", "unit_purchase_price": 222.0, "min_order_qty": 15, "available_qty": 500, "delivery_lead_time_days": 3, "delivery_charge": 120.0, "discount_pct": 1.5, "return_policy": "Standard exchange", "reliability_score": 0.93},

    # Sunflower Oil
    {"supplier_id": "SUP-LOC-02", "product_id": "P-204", "unit_purchase_price": 110.0, "min_order_qty": 12, "available_qty": 150, "delivery_lead_time_days": 1, "delivery_charge": 40.0, "discount_pct": 1.0, "return_policy": "Immediate swap for leaks", "reliability_score": 0.95},
    {"supplier_id": "SUP-NAT-01", "product_id": "P-204", "unit_purchase_price": 98.0, "min_order_qty": 60, "available_qty": 1200, "delivery_lead_time_days": 7, "delivery_charge": 200.0, "discount_pct": 4.5, "return_policy": "Credit invoice on proof", "reliability_score": 0.86},

    # Black Tea
    {"supplier_id": "SUP-NAT-02", "product_id": "P-301", "unit_purchase_price": 145.0, "min_order_qty": 24, "available_qty": 800, "delivery_lead_time_days": 5, "delivery_charge": 180.0, "discount_pct": 3.5, "return_policy": "Carton replacement", "reliability_score": 0.90},
    {"supplier_id": "SUP-REG-01", "product_id": "P-301", "unit_purchase_price": 152.0, "min_order_qty": 10, "available_qty": 180, "delivery_lead_time_days": 2, "delivery_charge": 70.0, "discount_pct": 1.0, "return_policy": "Full refund if damaged", "reliability_score": 0.95},

    # Energy Drink
    {"supplier_id": "SUP-LOC-01", "product_id": "P-304", "unit_purchase_price": 35.0, "min_order_qty": 24, "available_qty": 400, "delivery_lead_time_days": 1, "delivery_charge": 30.0, "discount_pct": 2.0, "return_policy": "Dented cans accepted", "reliability_score": 0.96},
    {"supplier_id": "SUP-NAT-02", "product_id": "P-304", "unit_purchase_price": 31.0, "min_order_qty": 120, "available_qty": 3000, "delivery_lead_time_days": 6, "delivery_charge": 250.0, "discount_pct": 6.0, "return_policy": "Case level only", "reliability_score": 0.88},

    # Makhana (Emerging Trend)
    {"supplier_id": "SUP-REG-02", "product_id": "P-401", "unit_purchase_price": 68.0, "min_order_qty": 15, "available_qty": 350, "delivery_lead_time_days": 3, "delivery_charge": 80.0, "discount_pct": 2.5, "return_policy": "Standard exchange", "reliability_score": 0.94},
    {"supplier_id": "SUP-LOC-02", "product_id": "P-401", "unit_purchase_price": 74.0, "min_order_qty": 5, "available_qty": 60, "delivery_lead_time_days": 1, "delivery_charge": 30.0, "discount_pct": 0.0, "return_policy": "Full replacement", "reliability_score": 0.98},

    # Salted Chips
    {"supplier_id": "SUP-NAT-02", "product_id": "P-402", "unit_purchase_price": 15.0, "min_order_qty": 50, "available_qty": 2500, "delivery_lead_time_days": 4, "delivery_charge": 100.0, "discount_pct": 3.0, "return_policy": "Crushed bags credited", "reliability_score": 0.92},
    {"supplier_id": "SUP-LOC-01", "product_id": "P-402", "unit_purchase_price": 16.2, "min_order_qty": 20, "available_qty": 200, "delivery_lead_time_days": 1, "delivery_charge": 25.0, "discount_pct": 0.0, "return_policy": "Immediate credit", "reliability_score": 0.97},

    # Millet Cookies
    {"supplier_id": "SUP-REG-01", "product_id": "P-404", "unit_purchase_price": 75.0, "min_order_qty": 12, "available_qty": 180, "delivery_lead_time_days": 2, "delivery_charge": 60.0, "discount_pct": 2.0, "return_policy": "Standard replacement", "reliability_score": 0.93},
    {"supplier_id": "SUP-LOC-02", "product_id": "P-404", "unit_purchase_price": 82.0, "min_order_qty": 6, "available_qty": 50, "delivery_lead_time_days": 1, "delivery_charge": 25.0, "discount_pct": 0.0, "return_policy": "Immediate replacement", "reliability_score": 0.96},

    # Neem Soap
    {"supplier_id": "SUP-NAT-01", "product_id": "P-501", "unit_purchase_price": 28.0, "min_order_qty": 48, "available_qty": 1500, "delivery_lead_time_days": 5, "delivery_charge": 120.0, "discount_pct": 4.0, "return_policy": "Full case exchange", "reliability_score": 0.91},
    {"supplier_id": "SUP-LOC-01", "product_id": "P-501", "unit_purchase_price": 31.5, "min_order_qty": 12, "available_qty": 100, "delivery_lead_time_days": 1, "delivery_charge": 20.0, "discount_pct": 0.0, "return_policy": "Immediate credit", "reliability_score": 0.96},

    # Luxury Serum
    {"supplier_id": "SUP-REG-02", "product_id": "P-502", "unit_purchase_price": 380.0, "min_order_qty": 4, "available_qty": 80, "delivery_lead_time_days": 3, "delivery_charge": 75.0, "discount_pct": 2.0, "return_policy": "Breakage covered", "reliability_score": 0.95},
    {"supplier_id": "SUP-LOC-02", "product_id": "P-502", "unit_purchase_price": 410.0, "min_order_qty": 2, "available_qty": 25, "delivery_lead_time_days": 1, "delivery_charge": 30.0, "discount_pct": 0.0, "return_policy": "100% refund", "reliability_score": 0.99},
]

# Enrich supplier details
enriched_suppliers = []
for row in supplier_rows:
    sup_info = supplier_names[row["supplier_id"]]
    entry = {
        "supplier_id": row["supplier_id"],
        "business_name": sup_info["name"],
        "supplier_scale": sup_info["scale"],
        "service_area": sup_info["area"],
        "product_id": row["product_id"],
        "unit_purchase_price": row["unit_purchase_price"],
        "min_order_qty": row["min_order_qty"],
        "available_qty": row["available_qty"],
        "delivery_lead_time_days": row["delivery_lead_time_days"],
        "delivery_charge": row["delivery_charge"],
        "discount_pct": row["discount_pct"],
        "return_policy": row["return_policy"],
        "reliability_score": row["reliability_score"],
        "last_price_update": (today - timedelta(days=random.randint(1, 14))).strftime("%Y-%m-%d"),
    }
    enriched_suppliers.append(entry)

with open("C:/Users/Admin/.gemini/antigravity/scratch/stocksense-rescue-ai/data/sample_suppliers.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(enriched_suppliers[0].keys()))
    writer.writeheader()
    writer.writerows(enriched_suppliers)

# 3. SAMPLE HISTORICAL SALES (60 days of daily sales to demonstrate baseline vs recent trends)
sales_records = []
start_date = today - timedelta(days=60)

for p in inventory_data:
    pid = p["product_id"]
    base_sales = p["avg_daily_sales"]
    
    # Specific trend behaviors:
    # P-401 (Makhana) has emerging explosive trend in last 14 days (+65%)
    # P-404 (Millet Cookies) is emerging (+45%)
    # P-101 (Milk) is high velocity established
    # P-601 (Truffle Glaze) is dead mover (0 sales)
    # P-304 (Energy Drink) has rising trend (+30%)
    
    for day_offset in range(61):
        curr_date = start_date + timedelta(days=day_offset)
        is_recent = day_offset >= 46 # Last 14 days
        
        if pid == "P-601":
            qty = 0
        elif pid == "P-401":
            # Baseline was 2.5/day, jumped to 5.5/day recently
            mean_val = 5.5 if is_recent else 2.5
            qty = max(0, int(round(random.gauss(mean_val, 1.2))))
        elif pid == "P-404":
            mean_val = 4.2 if is_recent else 2.1
            qty = max(0, int(round(random.gauss(mean_val, 1.0))))
        elif pid == "P-304":
            mean_val = 7.5 if is_recent else 4.8
            qty = max(0, int(round(random.gauss(mean_val, 1.5))))
        else:
            mean_val = base_sales
            qty = max(0, int(round(random.gauss(mean_val, max(0.5, mean_val * 0.25)))))
            
        sales_records.append({
            "date": curr_date.strftime("%Y-%m-%d"),
            "product_id": pid,
            "units_sold": qty,
            "channel": "In-Store Counter" if random.random() > 0.3 else "Phone Delivery"
        })

with open("C:/Users/Admin/.gemini/antigravity/scratch/stocksense-rescue-ai/data/sample_historical_sales.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(sales_records[0].keys()))
    writer.writeheader()
    writer.writerows(sales_records)

print(f"Sample data generated: {len(inventory_data)} products, {len(enriched_suppliers)} supplier quotes, {len(sales_records)} sales records.")
