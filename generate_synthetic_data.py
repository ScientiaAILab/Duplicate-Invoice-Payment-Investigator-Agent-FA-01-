#!/usr/bin/env python3
"""
SCIENTIAPARTNERS AI LAB - BENCHMARK SYNTHETIC DATA GENERATOR
Generates realistic UAE enterprise invoice & payment datasets with seeded error scenarios:
- Normal clean invoices
- Exact duplicates (double billing)
- Fuzzy invoice numbers (OCR/typo: '0' vs 'O', '1' vs 'I', trailing suffix '-A')
- Split POs evading AED 50,000 approval thresholds
- Collusive/Ghost vendors sharing destination bank IBANs
"""

import csv
import random
from datetime import datetime, timedelta

UAE_VENDORS = [
    {"id": "V-101", "name": "Al Futtaim Facilities & Logistics LLC", "trn": "100234567800003", "iban": "AE070331234567890123456"},
    {"id": "V-102", "name": "Emirates Cloud Infrastructure FZ-LLC", "trn": "100456789000003", "iban": "AE210260000001234567890"},
    {"id": "V-103", "name": "Gulf Engineering & MEP Contracting", "trn": "100987654300003", "iban": "AE440500987654321098765"},
    {"id": "V-104", "name": "Al Habtoor Office Supplies Trading", "trn": "100112233400003", "iban": "AE880400000000001234567"},
    {"id": "V-105", "name": "Dubai Silicon Security Solutions", "trn": "100998877600003", "iban": "AE650220000112233445566"},
    {"id": "V-106", "name": "Apex Legal & Statutory Advisory DMCC", "trn": "100334455600003", "iban": "AE120330009988776655443"},
    {"id": "V-107", "name": "Emaar Tech Maintenance Services", "trn": "100556677800003", "iban": "AE930260001112223334445"},
    {"id": "V-108", "name": "Sharjah Freight & Customs Logistics", "trn": "100778899000003", "iban": "AE550500123123123123123"},
]

def generate_benchmark_csv(output_path: str = "sample_invoices.csv", total_clean: int = 40):
    rows = []
    base_date = datetime(2024, 1, 15)
    inv_seq = 1000

    # 1. Generate clean corporate invoices
    for i in range(total_clean):
        vendor = random.choice(UAE_VENDORS)
        inv_date = base_date + timedelta(days=random.randint(0, 90))
        amt = round(random.uniform(3200, 42000), 2)
        inv_no = f"INV-2024-{inv_seq}"
        inv_seq += 1
        rows.append({
            "invoice_id": f"REC-{len(rows)+1:04d}",
            "vendor_id": vendor["id"],
            "vendor_name": vendor["name"],
            "trn": vendor["trn"],
            "invoice_number": inv_no,
            "invoice_date": inv_date.strftime("%Y-%m-%d"),
            "amount_aed": amt,
            "po_number": f"PO-2024-{random.randint(4000, 4999)}",
            "iban": vendor["iban"],
            "description": f"Quarterly services rendered - ref {inv_no}",
            "payment_status": random.choice(["Paid", "Approved", "Pending"])
        })

    # 2. Seed Test Case 1: EXACT DUPLICATE (Double-Billing on Same PO)
    v1 = UAE_VENDORS[0]
    inv_date1 = datetime(2024, 2, 10)
    inv_date2 = datetime(2024, 2, 28)
    amt_exact = 38500.00
    rows.append({
        "invoice_id": f"REC-{len(rows)+1:04d}",
        "vendor_id": v1["id"],
        "vendor_name": v1["name"],
        "trn": v1["trn"],
        "invoice_number": "INV-2024-8842",
        "invoice_date": inv_date1.strftime("%Y-%m-%d"),
        "amount_aed": amt_exact,
        "po_number": "PO-2024-5100",
        "iban": v1["iban"],
        "description": "Logistics fleet maintenance - Feb 2024",
        "payment_status": "Paid"
    })
    rows.append({
        "invoice_id": f"REC-{len(rows)+1:04d}",
        "vendor_id": v1["id"],
        "vendor_name": v1["name"],
        "trn": v1["trn"],
        "invoice_number": "INV-2024-8842",
        "invoice_date": inv_date2.strftime("%Y-%m-%d"),
        "amount_aed": amt_exact,
        "po_number": "PO-2024-5100",
        "iban": v1["iban"],
        "description": "Logistics fleet maintenance - Duplicate Re-bill",
        "payment_status": "Pending"
    })

    # 3. Seed Test Case 2: FUZZY NUMBER MATCH (OCR / Typo: 'O' vs '0' and trailing '-A')
    v2 = UAE_VENDORS[1]
    rows.append({
        "invoice_id": f"REC-{len(rows)+1:04d}",
        "vendor_id": v2["id"],
        "vendor_name": v2["name"],
        "trn": v2["trn"],
        "invoice_number": "INV-CLD-9050",
        "invoice_date": "2024-03-01",
        "amount_aed": 74200.00,
        "po_number": "PO-2024-5211",
        "iban": v2["iban"],
        "description": "Monthly AWS/Cloud Dedicated Compute Nodes",
        "payment_status": "Paid"
    })
    rows.append({
        "invoice_id": f"REC-{len(rows)+1:04d}",
        "vendor_id": v2["id"],
        "vendor_name": v2["name"],
        "trn": v2["trn"],
        "invoice_number": "INV-CLD-9O50-A", # 'O' instead of 0 + suffix '-A'
        "invoice_date": "2024-03-06",
        "amount_aed": 74200.00,
        "po_number": "PO-2024-5211",
        "iban": v2["iban"],
        "description": "Monthly AWS/Cloud Dedicated Compute Nodes - Revised",
        "payment_status": "Approved"
    })

    # 4. Seed Test Case 3: SPLIT-INVOICING (Circumventing AED 50,000 Sign-off Ceiling)
    v3 = UAE_VENDORS[2]
    # Total job is ~AED 142,000, broken into 3 invoices right below AED 50,000 over 4 days
    rows.append({
        "invoice_id": f"REC-{len(rows)+1:04d}",
        "vendor_id": v3["id"],
        "vendor_name": v3["name"],
        "trn": v3["trn"],
        "invoice_number": "INV-MEP-4101",
        "invoice_date": "2024-03-12",
        "amount_aed": 48500.00,
        "po_number": "PO-2024-5301",
        "iban": v3["iban"],
        "description": "HVAC Chiller Replacement - Phase 1 Materials",
        "payment_status": "Paid"
    })
    rows.append({
        "invoice_id": f"REC-{len(rows)+1:04d}",
        "vendor_id": v3["id"],
        "vendor_name": v3["name"],
        "trn": v3["trn"],
        "invoice_number": "INV-MEP-4102",
        "invoice_date": "2024-03-14",
        "amount_aed": 47900.00,
        "po_number": "PO-2024-5302",
        "iban": v3["iban"],
        "description": "HVAC Chiller Replacement - Phase 2 Labor Installation",
        "payment_status": "Approved"
    })
    rows.append({
        "invoice_id": f"REC-{len(rows)+1:04d}",
        "vendor_id": v3["id"],
        "vendor_name": v3["name"],
        "trn": v3["trn"],
        "invoice_number": "INV-MEP-4103",
        "invoice_date": "2024-03-15",
        "amount_aed": 46200.00,
        "po_number": "PO-2024-5303",
        "iban": v3["iban"],
        "description": "HVAC Chiller Replacement - Commissioning & Testing",
        "payment_status": "Pending"
    })

    # 5. Seed Test Case 4: SHARED IBAN / GHOST VENDOR COLLUSION
    # A shell vendor "Al Safa Facility Cleaning" uses the exact same IBAN as "Dubai Silicon Security Solutions"
    v5 = UAE_VENDORS[4]
    rows.append({
        "invoice_id": f"REC-{len(rows)+1:04d}",
        "vendor_id": "V-SHELL-99",
        "vendor_name": "Al Safa Express Maintenance Services",
        "trn": "100889900100003",
        "invoice_number": "INV-EXP-110",
        "invoice_date": "2024-03-20",
        "amount_aed": 61250.00,
        "po_number": "PO-2024-5490",
        "iban": v5["iban"],  # Same IBAN as V-105!
        "description": "Head office deep sanitization and facilities cleaning",
        "payment_status": "Approved"
    })

    # Shuffle slightly while preserving record order
    fieldnames = [
        "invoice_id", "vendor_id", "vendor_name", "trn", "invoice_number",
        "invoice_date", "amount_aed", "po_number", "iban", "description", "payment_status"
    ]
    with open(output_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    print(f"Generated {len(rows)} records in '{output_path}'.")

if __name__ == "__main__":
    generate_benchmark_csv("sample_invoices.csv")
