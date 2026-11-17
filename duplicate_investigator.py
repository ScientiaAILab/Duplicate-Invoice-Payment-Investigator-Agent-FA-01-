#!/usr/bin/env python3
"""
SCIENTIAPARTNERS AI LAB - AGENT FA-01
Duplicate Invoice & Payment Investigator
-------------------------------------------------------------------------------
Core Deterministic Detection Engine (Zero External API Dependency)
Enterprise Forensic AP Audit & UAE Tax / VAT Compliance Ready

UNRESTRICTED FULL-LEDGER AUDIT:
- Zero DoA limit barriers (audits transactions of any amount)
- Zero arbitrary day cutoffs (evaluates the entire historical ledger)

Detection Passes:
1. Exact Invoices (Same Vendor / TRN, Normalized Invoice #)
2. Fuzzy Typographical Variations (Transpositions, OCR 'O'/'0', Suffixes)
3. Same Vendor + Identical Amount Duplicate Payments (Cross-Date / Different Invoice #)
4. Purchase Order Multi-Billing (Multiple invoices charged to identical PO)
5. Fragmented / Split Invoicing (Serial sub-billing without DoA / day constraints)
6. Shared IBAN / Ghost Vendor Collusion (Different vendors sharing same bank account)
"""

import sys
import os
import csv
import json
import argparse
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Tuple, Set

# Attempt import of rapidfuzz for ultra-fast C-accelerated string metrics
try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

def calculate_similarity(s1: str, s2: str) -> float:
    """Calculates normalized similarity between 0.0 and 1.0 using RapidFuzz or fallback."""
    if not s1 or not s2:
        return 0.0
    s1_clean = "".join(ch for ch in str(s1).upper() if ch.isalnum())
    s2_clean = "".join(ch for ch in str(s2).upper() if ch.isalnum())
    if s1_clean == s2_clean:
        return 1.0

    if HAS_RAPIDFUZZ:
        ratio = fuzz.ratio(s1_clean, s2_clean) / 100.0
        token_sort = fuzz.token_sort_ratio(s1_clean, s2_clean) / 100.0
        return max(ratio, token_sort)
    else:
        from difflib import SequenceMatcher
        return SequenceMatcher(None, s1_clean, s2_clean).ratio()

@dataclass
class InvoiceRecord:
    invoice_id: str
    vendor_id: str
    vendor_name: str
    trn: str
    invoice_number: str
    invoice_date: str
    amount_aed: float
    po_number: str
    iban: str
    description: str
    payment_status: str
    currency: str = "AED"
    payment_reference: str = ""
    payment_date: str = ""

@dataclass
class DiscrepancyCluster:
    cluster_id: str
    category: str              # EXACT_DUPLICATE, FUZZY_INVOICE_MATCH, SAME_AMOUNT_DUPLICATE, PO_MULTI_BILLING, FRAGMENTED_INVOICING, IBAN_DIVERGENCE
    severity: str              # CRITICAL, HIGH, MEDIUM
    total_exposure_aed: float
    confidence_score: float
    primary_vendor: str
    rationale: str
    recommended_action: str
    invoices: List[Dict[str, Any]]

class DuplicateInvestigatorEngine:
    def __init__(
        self,
        fuzzy_threshold: float = 0.85,
        min_amount_floor: float = 0.0,
        fuzzy_amount_ratio: float = 0.90
    ):
        """
        :param fuzzy_threshold: Minimum string similarity (0.60 to 0.99) for typographical duplicates.
        :param min_amount_floor: Optional minimum invoice amount to consider (default 0.0 = inspect all).
        :param fuzzy_amount_ratio: Minimum ratio between two amounts to consider them near-identical (e.g. 0.90).
        """
        self.fuzzy_threshold = float(fuzzy_threshold)
        self.min_amount_floor = float(min_amount_floor)
        self.fuzzy_amount_ratio = float(fuzzy_amount_ratio)

    def normalize_invoice_no(self, inv_no: str) -> str:
        """Removes punctuation, leading zeros, and standardized separators."""
        cleaned = "".join(ch for ch in str(inv_no).upper() if ch.isalnum())
        return cleaned

    def parse_date(self, date_str: Any) -> Optional[datetime]:
        """Robust date parser handling ISO strings, timestamps, slashes, dashes, dots."""
        if date_str is None:
            return None
        s = str(date_str).strip()
        if not s or s.lower() in ("nan", "none", "nat", ""):
            return None
        # Remove trailing timestamp portion if present
        s_date = s.split("T")[0].split(" ")[0].strip()
        formats = [
            "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d", "%d-%m-%Y",
            "%d.%m.%Y", "%Y.%m.%d", "%m-%d-%Y", "%b %d, %Y", "%d %b %Y",
            "%Y%m%d"
        ]
        for fmt in formats:
            try:
                return datetime.strptime(s_date, fmt)
            except ValueError:
                continue
        for fmt in ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"]:
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        return None

    def analyze(self, records: List[InvoiceRecord]) -> Dict[str, Any]:
        # Filter only if user explicitly set a floor > 0
        if self.min_amount_floor > 0:
            records = [r for r in records if r.amount_aed >= self.min_amount_floor]

        clusters: List[DiscrepancyCluster] = []
        cluster_counter = 1

        total_spend_audited = sum(r.amount_aed for r in records)
        n = len(records)

        # -------------------------------------------------------------
        # 1. Exact Duplicate Invoices (Same Vendor / TRN, Same Normalized Invoice No)
        # -------------------------------------------------------------
        exact_groups: Dict[Tuple[str, str], List[InvoiceRecord]] = {}
        for r in records:
            norm_key = (
                r.trn.strip() if r.trn.strip() else r.vendor_name.strip().upper(),
                self.normalize_invoice_no(r.invoice_number)
            )
            exact_groups.setdefault(norm_key, []).append(r)

        exact_flagged_ids: Set[str] = set()
        for (vendor_key, inv_key), grp in exact_groups.items():
            if len(grp) > 1:
                total_exp = sum(r.amount_aed for r in grp)
                redundant_exposure = total_exp - min(r.amount_aed for r in grp)
                dates = [r.invoice_date for r in grp if r.invoice_date]
                date_span_str = f" across dates: {', '.join(dates)}" if dates else ""
                clusters.append(DiscrepancyCluster(
                    cluster_id=f"CLUSTER-EXACT-{cluster_counter:03d}",
                    category="EXACT_DUPLICATE",
                    severity="CRITICAL",
                    total_exposure_aed=round(redundant_exposure, 2),
                    confidence_score=1.00,
                    primary_vendor=grp[0].vendor_name,
                    rationale=f"Multiple invoices ({len(grp)}) registered with identical normalized number '{inv_key}' under vendor '{grp[0].vendor_name}'{date_span_str}. High likelihood of double disbursement.",
                    recommended_action="Place immediate hold on payment disbursements. Verify vendor statement of accounts against general ledger.",
                    invoices=[asdict(r) for r in grp]
                ))
                cluster_counter += 1
                for r in grp:
                    exact_flagged_ids.add(r.invoice_id)

        # -------------------------------------------------------------
        # 2. Fuzzy Invoice Number Match (Typos, Suffixes, OCR Glitches)
        # -------------------------------------------------------------
        fuzzy_flagged_ids: Set[str] = set()
        for i in range(n):
            r1 = records[i]
            if r1.invoice_id in exact_flagged_ids or r1.invoice_id in fuzzy_flagged_ids:
                continue
            matched_pair = []
            for j in range(i + 1, n):
                r2 = records[j]
                if r2.invoice_id in exact_flagged_ids or r2.invoice_id in fuzzy_flagged_ids:
                    continue

                same_vendor = (
                    (r1.trn and r2.trn and r1.trn.strip() == r2.trn.strip()) or
                    (r1.vendor_name.strip().upper() == r2.vendor_name.strip().upper())
                )
                if not same_vendor:
                    continue

                norm1 = self.normalize_invoice_no(r1.invoice_number)
                norm2 = self.normalize_invoice_no(r2.invoice_number)

                if norm1 == norm2:
                    continue

                sim = calculate_similarity(norm1, norm2)
                is_suffix_variant = (
                    norm1.startswith(norm2) or norm2.startswith(norm1)
                ) and abs(len(norm1) - len(norm2)) <= 3

                if sim >= self.fuzzy_threshold or is_suffix_variant:
                    max_amt = max(r1.amount_aed, r2.amount_aed)
                    amount_ratio = (min(r1.amount_aed, r2.amount_aed) / max_amt) if max_amt > 0 else 0
                    if amount_ratio >= self.fuzzy_amount_ratio:
                        matched_pair.append(r2)

            if matched_pair:
                all_cluster_records = [r1] + matched_pair
                total_exp = sum(r.amount_aed for r in all_cluster_records)
                redundant_exp = total_exp - min(r.amount_aed for r in all_cluster_records)
                for r in all_cluster_records:
                    fuzzy_flagged_ids.add(r.invoice_id)
                clusters.append(DiscrepancyCluster(
                    cluster_id=f"CLUSTER-FUZZY-{cluster_counter:03d}",
                    category="FUZZY_INVOICE_MATCH",
                    severity="HIGH",
                    total_exposure_aed=round(redundant_exp, 2),
                    confidence_score=0.92,
                    primary_vendor=r1.vendor_name,
                    rationale=f"High-similarity invoice numbers detected for vendor '{r1.vendor_name}' ({r1.invoice_number} vs {', '.join(r.invoice_number for r in matched_pair)}) with near-identical amounts (AED {r1.amount_aed:,.2f}).",
                    recommended_action="Inspect physical tax invoice PDFs for re-billing, credit note re-entry, or clerical digit transpositions.",
                    invoices=[asdict(r) for r in all_cluster_records]
                ))
                cluster_counter += 1

        # -------------------------------------------------------------
        # 3. Same Vendor + Identical Amount (Regardless of Date or Invoice #)
        # -------------------------------------------------------------
        # Unrestricted by days or DoA: catches payments made twice under different invoice numbers
        vendor_amount_groups: Dict[Tuple[str, float], List[InvoiceRecord]] = {}
        for r in records:
            if r.invoice_id in exact_flagged_ids or r.invoice_id in fuzzy_flagged_ids:
                continue
            if r.amount_aed <= 0:
                continue
            v_key = r.trn.strip() if r.trn.strip() else r.vendor_name.strip().upper()
            # Round amount to 2 decimal places to catch identical payments
            amt_key = round(r.amount_aed, 2)
            vendor_amount_groups.setdefault((v_key, amt_key), []).append(r)

        same_amt_flagged_ids: Set[str] = set()
        for (v_key, amt_val), grp in vendor_amount_groups.items():
            if len(grp) > 1:
                total_exp = sum(r.amount_aed for r in grp)
                redundant_exp = total_exp - amt_val  # If paid multiple times, all but one are redundant
                for r in grp:
                    same_amt_flagged_ids.add(r.invoice_id)
                inv_nums = ", ".join(r.invoice_number for r in grp)
                dates = ", ".join(r.invoice_date for r in grp if r.invoice_date)
                clusters.append(DiscrepancyCluster(
                    cluster_id=f"CLUSTER-AMT-{cluster_counter:03d}",
                    category="SAME_AMOUNT_DUPLICATE",
                    severity="HIGH",
                    total_exposure_aed=round(redundant_exp, 2),
                    confidence_score=0.88,
                    primary_vendor=grp[0].vendor_name,
                    rationale=(
                        f"Detected {len(grp)} separate invoices for vendor '{grp[0].vendor_name}' "
                        f"with the EXACT SAME amount of AED {amt_val:,.2f} under different invoice numbers "
                        f"({inv_nums}) on dates ({dates}). Unrestricted cross-date check."
                    ),
                    recommended_action="Review vendor ledger and delivery notes to confirm whether these represent legitimate repeat orders or duplicate disbursements under revised invoice numbers.",
                    invoices=[asdict(r) for r in grp]
                ))
                cluster_counter += 1

        # -------------------------------------------------------------
        # 4. Same Vendor + Same Purchase Order (PO Multi-Billing)
        # -------------------------------------------------------------
        po_groups: Dict[Tuple[str, str], List[InvoiceRecord]] = {}
        for r in records:
            po = r.po_number.strip().upper()
            if not po or po in ("PO-N/A", "N/A", "NONE", "NULL", "-", ""):
                continue
            v_key = r.vendor_name.strip().upper()
            po_groups.setdefault((v_key, po), []).append(r)

        for (v_key, po_num), grp in po_groups.items():
            # If multiple invoices reference the exact same PO number (and not already in exact cluster)
            if len(grp) > 1:
                # Check how many were not already flagged
                unflagged = [r for r in grp if r.invoice_id not in exact_flagged_ids and r.invoice_id not in fuzzy_flagged_ids]
                if len(unflagged) >= 2:
                    total_po_billed = sum(r.amount_aed for r in grp)
                    clusters.append(DiscrepancyCluster(
                        cluster_id=f"CLUSTER-PO-{cluster_counter:03d}",
                        category="PO_MULTI_BILLING",
                        severity="MEDIUM",
                        total_exposure_aed=round(total_po_billed, 2),
                        confidence_score=0.85,
                        primary_vendor=grp[0].vendor_name,
                        rationale=(
                            f"Purchase Order '{po_num}' for vendor '{grp[0].vendor_name}' "
                            f"has been billed {len(grp)} times across invoices ({', '.join(r.invoice_number for r in grp)}) "
                            f"for a cumulative total of AED {total_po_billed:,.2f}. Unrestricted date audit."
                        ),
                        recommended_action=f"Cross-check original PO line commitment amount for '{po_num}' in ERP to ensure cumulative invoices do not exceed approved PO cap.",
                        invoices=[asdict(r) for r in grp]
                    ))
                    cluster_counter += 1

        # -------------------------------------------------------------
        # 5. Fragmented Invoicing & Serial Sub-Billing (Unrestricted by DoA / Days)
        # -------------------------------------------------------------
        # Groups multiple sub-invoices for the same vendor with identical / repetitive descriptions
        # or back-to-back project phases without requiring any DoA ceiling or 30-day cutoff!
        vendor_records: Dict[str, List[InvoiceRecord]] = {}
        for r in records:
            if r.invoice_id in exact_flagged_ids or r.invoice_id in fuzzy_flagged_ids:
                continue
            v_key = r.vendor_name.strip().upper()
            vendor_records.setdefault(v_key, []).append(r)

        for v_name, v_list in vendor_records.items():
            if len(v_list) < 2:
                continue

            # Group by normalized description or common phase keywords
            desc_groups: Dict[str, List[InvoiceRecord]] = {}
            for r in v_list:
                # Extract first 20 alphanumeric chars of description or generic fallback
                clean_desc = "".join(ch for ch in r.description.upper() if ch.isalnum())[:25]
                if not clean_desc or len(clean_desc) < 4:
                    clean_desc = "GENERIC_SERVICES"
                desc_groups.setdefault(clean_desc, []).append(r)

            for d_key, d_invoices in desc_groups.items():
                if len(d_invoices) >= 2:
                    # Check if they weren't all captured in same_amount
                    tot_fragmented = sum(x.amount_aed for x in d_invoices)
                    inv_nums = ", ".join(x.invoice_number for x in d_invoices)
                    dates = ", ".join(x.invoice_date for x in d_invoices if x.invoice_date)
                    clusters.append(DiscrepancyCluster(
                        cluster_id=f"CLUSTER-SPLIT-{cluster_counter:03d}",
                        category="FRAGMENTED_INVOICING",
                        severity="MEDIUM",
                        total_exposure_aed=round(tot_fragmented, 2),
                        confidence_score=0.82,
                        primary_vendor=v_name,
                        rationale=(
                            f"Detected {len(d_invoices)} related sub-invoices ({inv_nums}) "
                            f"totaling AED {tot_fragmented:,.2f} for vendor '{v_name}' with matching line scope "
                            f"('{d_invoices[0].description[:50]}...'). Inspected across entire ledger with zero DoA limits or day barriers."
                        ),
                        recommended_action=(
                            f"Audit contract requisition history for vendor '{v_name}'. Check if unified commercial scope "
                            f"was divided into {len(d_invoices)} sub-invoices."
                        ),
                        invoices=[asdict(x) for x in d_invoices]
                    ))
                    cluster_counter += 1

        # -------------------------------------------------------------
        # 6. Shared IBAN / Bank Account Divergence (Ghost Vendor Collusion)
        # -------------------------------------------------------------
        iban_map: Dict[str, List[InvoiceRecord]] = {}
        for r in records:
            if r.iban and len(r.iban.strip()) > 8:
                clean_iban = "".join(ch for ch in r.iban.strip().upper() if ch.isalnum())
                iban_map.setdefault(clean_iban, []).append(r)

        for iban, iban_recs in iban_map.items():
            unique_vendors = list({r.vendor_name.strip().upper() for r in iban_recs})
            if len(unique_vendors) > 1:
                tot = sum(r.amount_aed for r in iban_recs)
                clusters.append(DiscrepancyCluster(
                    cluster_id=f"CLUSTER-IBAN-{cluster_counter:03d}",
                    category="IBAN_DIVERGENCE",
                    severity="CRITICAL",
                    total_exposure_aed=round(tot, 2),
                    confidence_score=0.96,
                    primary_vendor=", ".join(unique_vendors),
                    rationale=f"Multiple separate vendors ({', '.join(unique_vendors)}) share the identical bank IBAN account ('{iban[:4]}...{iban[-4:]}'). High risk of ghost vendor setup.",
                    recommended_action="Place payment freeze on this bank account. Request bank certificate and trade license verification from DET / Freezone Authority.",
                    invoices=[asdict(r) for r in iban_recs]
                ))
                cluster_counter += 1

        total_exposure = sum(c.total_exposure_aed for c in clusters)
        flagged_invoice_ids = set()
        for c in clusters:
            for inv in c.invoices:
                flagged_invoice_ids.add(inv["invoice_id"])

        dedup_rate = (len(flagged_invoice_ids) / n * 100) if n > 0 else 0.0

        return {
            "metadata": {
                "audited_records": n,
                "total_spend_audited_aed": round(total_spend_audited, 2),
                "total_exposure_flagged_aed": round(total_exposure, 2),
                "deduplication_risk_rate_pct": round(dedup_rate, 2),
                "clusters_identified": len(clusters),
                "audit_mode": "UNRESTRICTED_FULL_LEDGER (Zero DoA Limits, Zero Day Restrictions)"
            },
            "clusters": [asdict(c) for c in clusters]
        }

def load_records_from_csv(csv_path: str) -> List[InvoiceRecord]:
    """Loads invoice records from CSV with intelligent header auto-mapping."""
    records = []
    with open(csv_path, mode="r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            col_map = {str(k).strip().lower(): v for k, v in row.items() if k}

            def get_val(candidates, default=""):
                for c in candidates:
                    if c in col_map and col_map[c] is not None:
                        return str(col_map[c]).strip()
                for k, v in col_map.items():
                    if any(cand in k for cand in candidates) and v is not None:
                        return str(v).strip()
                return default

            raw_amt = get_val(["amount_aed", "amount", "total", "net_amount", "gross_amount", "value"], "0")
            try:
                amt = float(str(raw_amt).replace(",", "").strip())
            except ValueError:
                amt = 0.0

            records.append(InvoiceRecord(
                invoice_id=get_val(["invoice_id", "id", "record_id", "ref", "doc_no"], f"REC-{len(records)+1:04d}"),
                vendor_id=get_val(["vendor_id", "supplier_id", "vendor_code"], "V-UNKNOWN"),
                vendor_name=get_val(["vendor_name", "vendor", "supplier", "payee", "company_name"], "Unknown Vendor"),
                trn=get_val(["trn", "tax_registration_number", "vat_no", "tax_id"], ""),
                invoice_number=get_val(["invoice_number", "invoice_no", "inv_num", "inv_no", "bill_no"], f"INV-{len(records)+1}"),
                invoice_date=get_val(["invoice_date", "date", "bill_date", "doc_date", "posting_date"], datetime.now().strftime("%Y-%m-%d")),
                amount_aed=amt,
                po_number=get_val(["po_number", "po_no", "purchase_order", "po"], "PO-N/A"),
                iban=get_val(["iban", "bank_account", "account_no", "remittance_iban"], ""),
                description=get_val(["description", "memo", "narration", "item_desc"], "General Services / Goods"),
                payment_status=get_val(["payment_status", "status"], "Pending"),
                currency=get_val(["currency", "curr"], "AED"),
                payment_reference=get_val(["payment_reference", "payment_ref", "cheque_no"], ""),
                payment_date=get_val(["payment_date", "paid_date"], "")
            ))
    return records

def export_to_excel(result: dict, records: List[InvoiceRecord], output_path: str = "duplicate_investigation_report.xlsx") -> bool:
    """Exports audit findings to a comprehensive multi-sheet Excel workbook using pandas and openpyxl."""
    try:
        import pandas as pd
    except ImportError:
        print("[!] Error: 'pandas' and 'openpyxl' packages are required to export to Excel.")
        print("    Please install them by running: pip install pandas openpyxl")
        return False

    try:
        meta = result.get("metadata", {})
        clusters = result.get("clusters", [])

        # 1. Executive Summary Sheet
        summary_rows = [
            {"Audit Metric": "Report Title", "Value": "SCIENTIAPARTNERS AI LAB - DUPLICATE INVOICE & PAYMENT AUDIT"},
            {"Audit Metric": "Generated Timestamp", "Value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            {"Audit Metric": "Audit Engine Mode", "Value": meta.get("audit_mode", "Unrestricted Full-Ledger Audit")},
            {"Audit Metric": "Total Records Audited", "Value": meta.get("audited_records", len(records))},
            {"Audit Metric": "Total Spend Audited (AED)", "Value": meta.get("total_spend_audited_aed", 0.0)},
            {"Audit Metric": "Total Overpayment Exposure (AED)", "Value": meta.get("total_exposure_flagged_aed", 0.0)},
            {"Audit Metric": "Deduplication Risk Rate (%)", "Value": f"{meta.get('deduplication_risk_rate_pct', 0.0)} %"},
            {"Audit Metric": "Total Discrepancy Clusters", "Value": len(clusters)},
            {"Audit Metric": "Critical Severity Clusters", "Value": len([c for c in clusters if c.get("severity") == "CRITICAL"])},
            {"Audit Metric": "High Severity Clusters", "Value": len([c for c in clusters if c.get("severity") == "HIGH"])},
            {"Audit Metric": "Medium Severity Clusters", "Value": len([c for c in clusters if c.get("severity") == "MEDIUM"])},
        ]
        df_summary = pd.DataFrame(summary_rows)

        # 2. Discrepancy Clusters Sheet
        cluster_rows = []
        for cl in clusters:
            cluster_rows.append({
                "Cluster ID": cl.get("cluster_id"),
                "Risk Category": cl.get("category"),
                "Severity": cl.get("severity"),
                "Primary Vendor": cl.get("primary_vendor"),
                "Primary TRN": cl.get("primary_trn") or "N/A",
                "Total Overpayment Exposure (AED)": cl.get("total_exposure_aed", 0.0),
                "Invoices Flagged Count": len(cl.get("invoices", [])),
                "Confidence Score": f"{round(cl.get('confidence_score', 1.0) * 100)}%",
                "Forensic Audit Rationale": cl.get("rationale", ""),
                "Recommended Action": cl.get("recommended_action", "")
            })
        df_clusters = pd.DataFrame(cluster_rows) if cluster_rows else pd.DataFrame(columns=["Cluster ID", "Risk Category", "Severity", "Primary Vendor", "Total Overpayment Exposure (AED)"])

        # 3. Flagged Invoices Sheet
        flagged_rows = []
        flagged_ids = set()
        for cl in clusters:
            for inv in cl.get("invoices", []):
                flagged_ids.add(inv.get("invoice_id"))
                flagged_rows.append({
                    "Cluster ID": cl.get("cluster_id"),
                    "Risk Category": cl.get("category"),
                    "Severity": cl.get("severity"),
                    "Invoice ID": inv.get("invoice_id"),
                    "Vendor Name": inv.get("vendor_name"),
                    "Vendor TRN": inv.get("trn"),
                    "Invoice Number": inv.get("invoice_number"),
                    "Invoice Date": inv.get("invoice_date"),
                    "Amount (AED)": inv.get("amount_aed"),
                    "Currency": inv.get("currency", "AED"),
                    "PO Number": inv.get("po_number"),
                    "Payment Status": inv.get("payment_status"),
                    "IBAN": inv.get("iban"),
                    "Description": inv.get("description"),
                    "Audit Rationale": cl.get("rationale")
                })
        df_flagged = pd.DataFrame(flagged_rows) if flagged_rows else pd.DataFrame(columns=["Cluster ID", "Invoice Number", "Amount (AED)"])

        # 4. Full Audited Ledger Sheet
        all_records_rows = []
        for r in records:
            d = asdict(r)
            d["Audit_Status"] = "FLAGGED" if d["invoice_id"] in flagged_ids else "CLEAN"
            all_records_rows.append(d)
        df_ledger = pd.DataFrame(all_records_rows)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            df_summary.to_excel(writer, sheet_name="Executive_Summary", index=False)
            df_clusters.to_excel(writer, sheet_name="Discrepancy_Clusters", index=False)
            df_flagged.to_excel(writer, sheet_name="Flagged_Invoices", index=False)
            df_ledger.to_excel(writer, sheet_name="Full_Audited_Ledger", index=False)

        print(f"[✓] Successfully exported forensic Excel report: {output_path}")
        print(f"    Sheets created: Executive_Summary, Discrepancy_Clusters, Flagged_Invoices, Full_Audited_Ledger")
        return True
    except Exception as e:
        print(f"[!] Warning: Could not generate Excel report: {e}")
        return False

def run_cli():
    parser = argparse.ArgumentParser(
        description="Scientia Partners AI Lab - Agent FA-01: Duplicate Invoice & Payment Investigator (Unrestricted Ledger Scan)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument("file", help="Path to input invoice ledger CSV file")
    parser.add_argument("--fuzzy-threshold", type=float, default=0.85, help="Fuzzy match similarity threshold (0.60 to 0.99)")
    parser.add_argument("--min-amount", type=float, default=0.0, help="Optional minimum invoice amount to inspect (default 0.0 = all)")
    parser.add_argument("--excel", "-x", nargs="?", const="duplicate_investigation_report.xlsx", default=None, help="Export complete multi-sheet results to Excel workbook (.xlsx)")
    parser.add_argument("--output", "-o", type=str, default="", help="Optional path to write full JSON audit findings")
    parser.add_argument("--json", action="store_true", help="Print entire result as formatted JSON to stdout")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: Input file '{args.file}' not found.")
        sys.exit(1)

    records = load_records_from_csv(args.file)
    engine = DuplicateInvestigatorEngine(
        fuzzy_threshold=args.fuzzy_threshold,
        min_amount_floor=args.min_amount
    )
    result = engine.analyze(records)

    # Save output if specified
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2)
            print(f"[✓] Full audit findings written to {args.output}")
        except Exception as e:
            print(f"[!] Warning: Could not write output file: {e}")

    # Export to Excel if requested
    if args.excel:
        export_to_excel(result, records, args.excel)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        meta = result["metadata"]
        print("=" * 80)
        print("SCIENTIAPARTNERS AI LAB - DUPLICATE INVOICE & PAYMENT INVESTIGATOR REPORT")
        print("AUDIT MODE: UNRESTRICTED FULL-LEDGER (Zero DoA Limits, Zero Day Restrictions)")
        print("=" * 80)
        print(f"Audited Invoices:        {meta['audited_records']}")
        print(f"Total Spend Audited:     AED {meta['total_spend_audited_aed']:,.2f}")
        print(f"Potential Cash Leakage:  AED {meta['total_exposure_flagged_aed']:,.2f}")
        print(f"Risk Clusters Flagged:   {meta['clusters_identified']}")
        print(f"Deduplication Risk Rate: {meta['deduplication_risk_rate_pct']} %")
        print("-" * 80)
        print("IDENTIFIED DISCREPANCY CLUSTERS:")
        for cl in result["clusters"]:
            print(f"\n[{cl['severity']}] {cl['cluster_id']} | Type: {cl['category']}")
            print(f"Vendor: {cl['primary_vendor']} | Exposure: AED {cl['total_exposure_aed']:,.2f}")
            print(f"Rationale: {cl['rationale']}")
            print(f"Action:    {cl['recommended_action']}")
            print("Involved Records:")
            for inv in cl["invoices"]:
                print(f"  • Inv #{inv['invoice_number']} | Date: {inv['invoice_date']} | AED {inv['amount_aed']:,.2f} | Status: {inv['payment_status']}")
        print("=" * 80)

if __name__ == "__main__":
    run_cli()
