"""
SCIENTIAPARTNERS AI LAB - DUPLICATE INVOICE & PAYMENT INVESTIGATOR
Streamlit Production Dashboard Edition (Unrestricted Full-Ledger Audit)
-------------------------------------------------------------------------------
Agent FA-01 Enterprise AP Forensic Engine (100% Offline, Zero Cloud Dependency)

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

import streamlit as st
import pandas as pd
import json
import os
import io
import re
import base64
import requests
from difflib import SequenceMatcher
from datetime import datetime
from duplicate_investigator import DuplicateInvestigatorEngine, InvoiceRecord

# Set page configuration
st.set_page_config(
    page_title="Scientia AI Lab - Duplicate Payment Investigator",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom enterprise styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 0.95rem;
        color: #475569;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 1rem 1.1rem;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
        min-height: 112px;
    }
    .metric-label {
        font-size: 0.85rem;
        font-weight: 600;
        color: #475569;
        margin-bottom: 0.35rem;
    }
    .metric-value {
        font-size: clamp(1.15rem, 1.65vw, 1.65rem);
        font-weight: 700;
        color: #0f172a;
        line-height: 1.25;
        font-variant-numeric: tabular-nums;
        white-space: normal;
        overflow-wrap: anywhere;
    }
    .metric-delta {
        display: inline-block;
        margin-top: 0.45rem;
        padding: 2px 8px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        background-color: #fee2e2;
        color: #b91c1c;
    }
    .badge-critical {
        background-color: #fee2e2;
        color: #991b1b;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.75rem;
    }
    .badge-high {
        background-color: #ffedd5;
        color: #9a3412;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.75rem;
    }
    .badge-medium {
        background-color: #fef9c3;
        color: #854d0e;
        padding: 3px 8px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 0.75rem;
    }
    .unrestricted-badge {
        background-color: #ecfdf5;
        color: #065f46;
        border: 1px solid #a7f3d0;
        padding: 8px 14px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.85rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Helper: Intelligent ERP Column Auto-Mapper
def map_dataframe_to_records(df: pd.DataFrame) -> list:
    col_map = {str(c).strip().lower(): c for c in df.columns}

    def get_col(candidates):
        for c in candidates:
            if c in col_map:
                return col_map[c]
        # Substring / partial match
        for key, orig in col_map.items():
            if any(cand in key for cand in candidates):
                return orig
        return None

    inv_id_col = get_col(["invoice_id", "id", "record_id", "ref", "doc_no", "voucher_no"])
    vendor_col = get_col(["vendor_name", "vendor", "supplier", "payee", "company_name", "party_name"])
    vendor_id_col = get_col(["vendor_id", "supplier_id", "payee_id", "vendor_code"])
    inv_num_col = get_col(["invoice_number", "invoice_no", "inv_num", "inv_no", "invoice#", "bill_no", "bill_number"])
    amount_col = get_col(["amount_aed", "amount", "total", "net_amount", "gross_amount", "invoice_amount", "value"])
    date_col = get_col(["invoice_date", "date", "bill_date", "doc_date", "document_date", "posting_date"])
    trn_col = get_col(["trn", "tax_registration_number", "vat_no", "tax_id", "vat_number"])
    po_col = get_col(["po_number", "po_no", "purchase_order", "po", "order_no"])
    iban_col = get_col(["iban", "bank_account", "bank_account_number", "account_no", "remittance_iban"])
    desc_col = get_col(["description", "memo", "narration", "line_description", "item_desc", "notes"])
    status_col = get_col(["payment_status", "status", "payment_state"])
    currency_col = get_col(["currency", "curr", "doc_currency"])
    ref_col = get_col(["payment_reference", "payment_ref", "cheque_no", "trans_ref"])
    pdate_col = get_col(["payment_date", "paid_date"])

    records = []
    for idx, row in df.iterrows():
        raw_amt = row.get(amount_col) if amount_col else 0
        try:
            amt = float(str(raw_amt).replace(",", "").strip())
        except (ValueError, TypeError):
            amt = 0.0

        inv_id = str(row.get(inv_id_col)) if inv_id_col and pd.notna(row.get(inv_id_col)) else f"REC-{idx+1:04d}"
        v_name = str(row.get(vendor_col)) if vendor_col and pd.notna(row.get(vendor_col)) else "Unknown Vendor"
        v_id = str(row.get(vendor_id_col)) if vendor_id_col and pd.notna(row.get(vendor_id_col)) else "V-N/A"
        inv_num = str(row.get(inv_num_col)) if inv_num_col and pd.notna(row.get(inv_num_col)) else f"INV-{idx+1}"
        inv_date = str(row.get(date_col)) if date_col and pd.notna(row.get(date_col)) else datetime.now().strftime("%Y-%m-%d")
        trn = str(row.get(trn_col)) if trn_col and pd.notna(row.get(trn_col)) else ""
        po_num = str(row.get(po_col)) if po_col and pd.notna(row.get(po_col)) else "PO-N/A"
        iban = str(row.get(iban_col)) if iban_col and pd.notna(row.get(iban_col)) else ""
        desc = str(row.get(desc_col)) if desc_col and pd.notna(row.get(desc_col)) else "General Services / Goods"
        status = str(row.get(status_col)) if status_col and pd.notna(row.get(status_col)) else "Pending"
        currency = str(row.get(currency_col)) if currency_col and pd.notna(row.get(currency_col)) else "AED"
        payment_ref = str(row.get(ref_col)) if ref_col and pd.notna(row.get(ref_col)) else ""
        payment_date = str(row.get(pdate_col)) if pdate_col and pd.notna(row.get(pdate_col)) else ""

        records.append(InvoiceRecord(
            invoice_id=inv_id,
            vendor_id=v_id,
            vendor_name=v_name,
            trn=trn,
            invoice_number=inv_num,
            invoice_date=inv_date,
            amount_aed=amt,
            po_number=po_num,
            iban=iban,
            description=desc,
            payment_status=status,
            currency=currency,
            payment_reference=payment_ref,
            payment_date=payment_date
        ))
    return records


def generate_excel_workbook(result: dict, df_raw: pd.DataFrame, clusters: list) -> bytes:
    """Generates an executive-grade 4-sheet formatted Excel workbook in memory."""
    output = io.BytesIO()
    meta = result.get("metadata", {})

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        # Sheet 1: Executive Summary
        summary_rows = [
            {"Audit Metric": "Report Title", "Value": "SCIENTIAPARTNERS AI LAB - FORENSIC DUPLICATE AUDIT REPORT"},
            {"Audit Metric": "Generated Timestamp", "Value": datetime.now().strftime("%Y-%m-%d %H:%M:%S")},
            {"Audit Metric": "Audit Engine Mode", "Value": "UNRESTRICTED FULL-LEDGER AUDIT (Zero DoA Limits, Zero Day Restrictions)"},
            {"Audit Metric": "Total Records Audited", "Value": meta.get("audited_records", len(df_raw))},
            {"Audit Metric": "Total Spend Audited (AED)", "Value": meta.get("total_spend_audited_aed", 0.0)},
            {"Audit Metric": "Potential Overpayment Exposure (AED)", "Value": meta.get("total_exposure_flagged_aed", 0.0)},
            {"Audit Metric": "Deduplication Risk Rate (%)", "Value": f"{meta.get('deduplication_risk_rate_pct', 0.0)} %"},
            {"Audit Metric": "Total Discrepancy Clusters Flagged", "Value": len(clusters)},
            {"Audit Metric": "Critical Severity Clusters", "Value": len([c for c in clusters if c.get("severity") == "CRITICAL"])},
            {"Audit Metric": "High Severity Clusters", "Value": len([c for c in clusters if c.get("severity") == "HIGH"])},
            {"Audit Metric": "Medium Severity Clusters", "Value": len([c for c in clusters if c.get("severity") == "MEDIUM"])},
        ]
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Executive_Summary", index=False)

        # Sheet 2: Discrepancy Clusters
        cluster_rows = []
        for cl in clusters:
            cluster_rows.append({
                "Cluster ID": cl.get("cluster_id"),
                "Category": cl.get("category"),
                "Severity": cl.get("severity"),
                "Primary Vendor": cl.get("primary_vendor"),
                "Primary TRN": cl.get("primary_trn") or "N/A",
                "Total Overpayment Exposure (AED)": cl.get("total_exposure_aed", 0.0),
                "Invoices Flagged Count": len(cl.get("invoices", [])),
                "Confidence Score": f"{round(cl.get('confidence_score', 1.0) * 100)}%",
                "Audit Rationale": cl.get("rationale", ""),
                "Recommended Action": cl.get("recommended_action", "")
            })
        if cluster_rows:
            pd.DataFrame(cluster_rows).to_excel(writer, sheet_name="Discrepancy_Clusters", index=False)
        else:
            pd.DataFrame(columns=["Cluster ID", "Category", "Severity", "Primary Vendor", "Total Overpayment Exposure (AED)"]).to_excel(writer, sheet_name="Discrepancy_Clusters", index=False)

        # Sheet 3: Detailed Flagged Invoices
        flagged_rows = []
        flagged_ids = set()
        for cl in clusters:
            for inv in cl.get("invoices", []):
                flagged_ids.add(str(inv.get("invoice_id", "")))
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
        if flagged_rows:
            pd.DataFrame(flagged_rows).to_excel(writer, sheet_name="Flagged_Invoices", index=False)
        else:
            pd.DataFrame(columns=["Cluster ID", "Invoice Number", "Amount (AED)"]).to_excel(writer, sheet_name="Flagged_Invoices", index=False)

        # Sheet 4: Full Audited Ledger with flags
        if df_raw is not None and not df_raw.empty:
            df_full = df_raw.copy()
            # Try to identify invoice id column
            id_col = None
            for cand in ["invoice_id", "id", "record_id", "ref"]:
                for c in df_full.columns:
                    if cand == str(c).strip().lower():
                        id_col = c
                        break
                if id_col:
                    break

            if id_col:
                df_full["AUDIT_STATUS"] = df_full[id_col].astype(str).apply(
                    lambda x: "FLAGGED" if x in flagged_ids else "CLEAN"
                )
            else:
                df_full["AUDIT_STATUS"] = "AUDITED"

            df_full.to_excel(writer, sheet_name="Full_Audited_Ledger", index=False)

    output.seek(0)
    return output.getvalue()


def check_ollama_engine():
    """Checks if local Ollama HTTP server is running on localhost:11434 and discovers installed models."""
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=1.0)
        if r.status_code == 200:
            models = [m.get("name") for m in r.json().get("models", []) if m.get("name")]
            return True, models
    except Exception:
        pass
    return False, []


def _parse_amount_filter(q: str):
    """Parses numeric threshold filters such as 'over AED 50000', 'above 50k', 'under 10,000', 'between 10000 and 50000'."""
    def _to_num(num_str: str, k_suffix: str = "") -> float:
        val = float(num_str.replace(",", ""))
        if k_suffix and k_suffix.lower() == "k":
            val *= 1000.0
        return val

    m_between = re.search(
        r"\bbetween\s+(?:aed|usd|\$)?\s*([\d,]+(?:\.\d+)?)\s*(k)?\s+(?:and|to|-)\s+(?:aed|usd|\$)?\s*([\d,]+(?:\.\d+)?)\s*(k)?\b",
        q,
        re.IGNORECASE,
    )
    if m_between:
        low = _to_num(m_between.group(1), m_between.group(2) or "")
        high = _to_num(m_between.group(3), m_between.group(4) or "")
        return ("between", min(low, high), max(low, high))

    m_gt = re.search(
        r"(?:\b(?:over|above|greater\s+than|more\s+than|exceeding|at\s+least|minimum|min)\b|>=|>)\s*(?:aed|usd|\$)?\s*([\d,]+(?:\.\d+)?)\s*(k)?\b",
        q,
        re.IGNORECASE,
    )
    if m_gt:
        val = _to_num(m_gt.group(1), m_gt.group(2) or "")
        return ("gt", val, None)

    m_lt = re.search(
        r"(?:\b(?:under|below|less\s+than|up\s+to|maximum|max)\b|<=|<)\s*(?:aed|usd|\$)?\s*([\d,]+(?:\.\d+)?)\s*(k)?\b",
        q,
        re.IGNORECASE,
    )
    if m_lt:
        val = _to_num(m_lt.group(1), m_lt.group(2) or "")
        return ("lt", val, None)

    return None


def _match_vendors_in_query(query: str, clusters: list, records: list):
    """Matches any vendor name in the loaded dataset against the user query, and detects explicit unknown vendor asks."""
    q_clean = re.sub(r"[^a-z0-9\s]", " ", query.lower())
    q_tokens = [t for t in q_clean.split() if len(t) >= 2]

    stop_words = {
        "are", "there", "any", "for", "the", "and", "with", "about", "from", "that", "this",
        "vendor", "vendors", "supplier", "suppliers", "company", "llc", "ltd", "dmcc", "fz", "fze",
        "inc", "corp", "est", "duplicate", "duplicates", "duplicated", "invoice", "invoices",
        "payment", "payments", "bill", "bills", "billing", "over", "above", "under", "below",
        "aed", "usd", "amount", "total", "how", "many", "much", "show", "list", "check", "find",
        "give", "tell", "me", "please", "status", "flagged", "clean", "cluster", "clusters",
        "risk", "exposure", "identified", "found", "have", "has", "does", "did", "is", "was"
    }
    meaningful_q_tokens = [t for t in q_tokens if t not in stop_words]

    # Collect all unique vendor names across full ledger + clusters
    all_vendors = []
    seen_v = set()
    for r in records or []:
        vn = str(getattr(r, "vendor_name", "") or "").strip()
        if vn and vn.lower() not in seen_v:
            seen_v.add(vn.lower())
            all_vendors.append(vn)
    for cl in clusters or []:
        pv = str(cl.get("primary_vendor", "") or "").strip()
        if pv and pv.lower() not in seen_v:
            seen_v.add(pv.lower())
            all_vendors.append(pv)
        for inv in cl.get("invoices", []):
            ivn = str(inv.get("vendor_name", "") or "").strip()
            if ivn and ivn.lower() not in seen_v:
                seen_v.add(ivn.lower())
                all_vendors.append(ivn)

    matched = []
    for vn in all_vendors:
        v_clean = re.sub(r"[^a-z0-9\s]", " ", vn.lower()).strip()
        if not v_clean:
            continue
        # 1. Exact substring match of full vendor name
        if len(v_clean) >= 4 and v_clean in q_clean:
            matched.append((100, vn))
            continue

        v_tokens = [t for t in v_clean.split() if len(t) >= 2 and t not in {"llc", "ltd", "fz", "fze", "dmcc", "inc", "corp", "co", "the", "and", "of"}]
        if not v_tokens:
            continue

        # 2. Multi-token or distinctive-token overlap
        overlap = [t for t in v_tokens if t in meaningful_q_tokens]
        if len(overlap) >= 2 or (len(v_tokens) == 1 and len(overlap) == 1):
            score = int((len(overlap) / len(v_tokens)) * 90) + len(overlap) * 5
            matched.append((score, vn))
            continue

        # 3. Distinctive single token match (non-generic word >= 4 chars)
        generic_biz = {
            "services", "service", "trading", "contracting", "solutions", "engineering",
            "logistics", "maintenance", "advisory", "group", "general", "international",
            "gulf", "dubai", "emirates", "arabia", "middle", "east", "marine", "shipping",
            "freight", "transport", "technologies", "technology", "tech", "systems",
            "global", "supplies", "supply", "infra", "infrastructure", "facilities"
        }
        distinctive_overlap = [t for t in overlap if t not in generic_biz and len(t) >= 4]
        if distinctive_overlap and (len(meaningful_q_tokens) <= 1 or len(v_tokens) == 1):
            matched.append((70, vn))

    # Fuzzy check on extracted target vendor phrase if no direct overlap found
    non_vendor_phrase_tokens = stop_words | {
        "over", "above", "under", "below", "between", "more", "than", "less", "greater",
        "equal", "at", "least", "all", "any", "every", "each", "pending", "paid", "approved",
        "exact", "fuzzy", "typo", "split", "fragmented", "iban", "ghost", "top", "highest",
        "worst", "riskiest", "cfo", "memo", "recovery", "letter", "vat", "tax", "fta"
    }
    explicit_phrase = None
    m_phrase = re.search(
        r"(?:\bfor\b|\babout\b|\bvendor\b|\bsupplier\b|\bagainst\b|\bfrom\b)\s+([a-z0-9][a-z0-9\s&\.\-]{1,50}?)(?:\s+(?:vendor|supplier|company|account|invoices?|duplicates?|payments?)\b|\?|$|\.|,)",
        query.strip(),
        re.IGNORECASE,
    )
    if m_phrase:
        cand = m_phrase.group(1).strip()
        cand_clean = re.sub(r"[^a-z0-9\s]", " ", cand.lower()).strip()
        cand_meaningful = [
            w for w in cand_clean.split()
            if w not in non_vendor_phrase_tokens and not re.fullmatch(r"\d+k?", w)
        ]
        if cand_meaningful:
            explicit_phrase = " ".join(cand.split())
            # Strip trailing generic filler words if captured
            explicit_phrase = re.sub(r"\s+(?:vendor|supplier|company|account)$", "", explicit_phrase, flags=re.IGNORECASE).strip()

    if not matched and explicit_phrase:
        ep_clean = re.sub(r"[^a-z0-9\s]", " ", explicit_phrase.lower()).strip()
        for vn in all_vendors:
            v_clean = re.sub(r"[^a-z0-9\s]", " ", vn.lower()).strip()
            ratio = SequenceMatcher(None, ep_clean, v_clean).ratio()
            if ratio >= 0.72:
                matched.append((int(ratio * 80), vn))

    matched.sort(key=lambda x: x[0], reverse=True)
    matched_names = [vn for _, vn in matched]
    return matched_names, explicit_phrase, all_vendors


def run_forensic_copilot_query(query: str, result: dict, clusters: list, records: list = None):
    """
    Executes an exact, data-grounded forensic audit query across all clusters and all raw ledger records.
    Returns (is_exact_data_query: bool, markdown_response: str).
    """
    records = records or []
    meta = result.get("metadata", {})
    total_spend = meta.get("total_spend_audited_aed", 0.0)
    total_exposure = meta.get("total_exposure_flagged_aed", 0.0)
    records_count = meta.get("audited_records", len(records))
    q = query.lower().strip()

    # Sort vendors by total exposure
    vendor_exposure = {}
    for cl in clusters:
        v = cl["primary_vendor"]
        vendor_exposure[v] = vendor_exposure.get(v, 0.0) + cl["total_exposure_aed"]
    sorted_vendors = sorted(vendor_exposure.items(), key=lambda x: x[1], reverse=True)

    # 1. Parse Numeric Threshold Filter (e.g., "over AED 50000")
    amt_filter = _parse_amount_filter(query)

    # 2. Match Specific Vendor Names (or detect an explicit unknown vendor query)
    matched_vendors, explicit_vendor_phrase, all_vendors = _match_vendors_in_query(query, clusters, records)

    # 3. Check Category Filter
    cat_filter = None
    cat_label = None
    if "exact" in q:
        cat_filter = {"EXACT_DUPLICATE"}
        cat_label = "Exact Duplicate"
    elif "fuzzy" in q or "typo" in q or "ocr" in q:
        cat_filter = {"FUZZY_INVOICE_MATCH"}
        cat_label = "Fuzzy / Typographical Match"
    elif "same amount" in q or "identical amount" in q or "cross-date" in q:
        cat_filter = {"SAME_AMOUNT_DUPLICATE"}
        cat_label = "Same Vendor + Same Amount"
    elif "multi-billing" in q or "same po" in q or re.search(r"\bpo\b", q):
        cat_filter = {"PO_MULTI_BILLING"}
        cat_label = "PO Multi-Billing"
    elif "fragment" in q or "split" in q or "sub-bill" in q:
        cat_filter = {"FRAGMENTED_INVOICING", "SPLIT_INVOICE_LIMIT"}
        cat_label = "Fragmented / Split Invoicing"
    elif "iban" in q or "ghost" in q or "bank" in q or "shell" in q:
        cat_filter = {"IBAN_DIVERGENCE"}
        cat_label = "Shared IBAN / Ghost Vendor"

    # 4. Check Payment Status Filter
    status_filter = None
    if "pending" in q or "unpaid" in q or "hold" in q:
        status_filter = "pending"
    elif "paid" in q or "disbursed" in q:
        status_filter = "paid"
    elif "approved" in q:
        status_filter = "approved"

    # ==========================================================================
    # PRIORITY A: Specific Vendor Lookup (Found OR Explicitly Asked & Missing)
    # ==========================================================================
    if matched_vendors:
        lines = [f"### 🔎 Vendor Forensic Audit Lookup: {', '.join(matched_vendors)}\n"]
        matched_set = {v.lower() for v in matched_vendors}

        for vname in matched_vendors:
            # Find all ledger records for this vendor
            v_records = [r for r in records if str(getattr(r, "vendor_name", "")).strip().lower() == vname.lower()]
            # Find all clusters involving this vendor (primary or inside cluster invoices)
            v_clusters = [
                cl for cl in clusters
                if cl.get("primary_vendor", "").strip().lower() == vname.lower()
                or any(str(inv.get("vendor_name", "")).strip().lower() == vname.lower() for inv in cl.get("invoices", []))
            ]

            if amt_filter:
                op, v1, v2 = amt_filter
                if op == "gt":
                    v_clusters = [c for c in v_clusters if c["total_exposure_aed"] > v1 or any(inv["amount_aed"] > v1 for inv in c["invoices"])]
                elif op == "lt":
                    v_clusters = [c for c in v_clusters if c["total_exposure_aed"] < v1 or any(inv["amount_aed"] < v1 for inv in c["invoices"])]
                elif op == "between":
                    v_clusters = [c for c in v_clusters if v1 <= c["total_exposure_aed"] <= v2 or any(v1 <= inv["amount_aed"] <= v2 for inv in c["invoices"])]

            v_total_spend = sum(getattr(r, "amount_aed", 0.0) for r in v_records)
            v_exposure = sum(c["total_exposure_aed"] for c in v_clusters)
            flagged_inv_ids = {inv.get("invoice_id") for c in v_clusters for inv in c.get("invoices", [])}

            lines.append(f"#### Vendor: **{vname}**")
            lines.append(f"* **Total Invoices in Ledger:** {len(v_records)} record(s) totaling **AED {v_total_spend:,.2f}**")
            lines.append(f"* **Duplicate / Risk Clusters Flagged:** **{len(v_clusters)}** cluster(s) | **Flagged Exposure:** **AED {v_exposure:,.2f}**")

            if v_clusters:
                lines.append("\n**Flagged Discrepancy Clusters:**")
                for cl in v_clusters:
                    lines.append(f"- **`{cl['cluster_id']}`** | `{cl['category']}` ({cl['severity']}) — Exposure: **AED {cl['total_exposure_aed']:,.2f}**")
                    lines.append(f"  - *Rationale:* {cl['rationale']}")
                    for inv in cl.get("invoices", []):
                        lines.append(
                            f"    • Inv `#{inv.get('invoice_number')}` | Date: `{inv.get('invoice_date')}` | "
                            f"Amount: **AED {inv.get('amount_aed', 0.0):,.2f}** | PO: `{inv.get('po_number')}` | Status: `{inv.get('payment_status')}`"
                        )
            else:
                lines.append("\n✅ **Clean Result:** **0 duplicate or anomalous clusters** were identified for this vendor.")
                if v_records:
                    lines.append("\n**Clean Ledger Invoices Found:**")
                    for r in v_records[:15]:
                        lines.append(
                            f"- Inv `#{r.invoice_number}` | Date: `{r.invoice_date}` | Amount: **AED {r.amount_aed:,.2f}** | PO: `{r.po_number}` | Status: `{r.payment_status}`"
                        )
                    if len(v_records) > 15:
                        lines.append(f"- *...and {len(v_records) - 15} more clean invoice(s).*")
            lines.append("")

        return True, "\n".join(lines)

    if explicit_vendor_phrase and not any(w in q for w in ["top", "highest", "worst", "cfo", "memo", "recovery", "vat", "tax"]):
        sample_vendors = ", ".join(all_vendors[:12]) if all_vendors else "None"
        more_count = max(0, len(all_vendors) - 12)
        more_note = f" *(+{more_count} more)*" if more_count > 0 else ""
        return True, f"""### 🔍 Vendor Lookup Result: "{explicit_vendor_phrase}"
❌ **No vendor matching `"{explicit_vendor_phrase}"` was found in the currently loaded dataset.**

* **Currently Audited Dataset:** {records_count:,} invoices across **{len(all_vendors)}** unique vendor(s).
* **Vendors Present in Loaded Dataset:** {sample_vendors}{more_note}.

💡 **Tip:** If you meant to audit your own file containing **"{explicit_vendor_phrase}"**, make sure you uploaded it via the **Upload Accounts Payable Ledger** box at the top of the page (otherwise the benchmark `sample_invoices.csv` is loaded by default).
"""

    # ==========================================================================
    # PRIORITY B: Numeric Amount Filter Queries (e.g. "duplicates over AED 50000")
    # ==========================================================================
    if amt_filter:
        op, v1, v2 = amt_filter
        if op == "gt":
            cond_label = f"over AED {v1:,.2f}"
            match_cluster_exp = lambda x: x > v1
            match_inv_amt = lambda x: x > v1
        elif op == "lt":
            cond_label = f"under AED {v1:,.2f}"
            match_cluster_exp = lambda x: x < v1
            match_inv_amt = lambda x: x < v1
        else:
            cond_label = f"between AED {v1:,.2f} and AED {v2:,.2f}"
            match_cluster_exp = lambda x: v1 <= x <= v2
            match_inv_amt = lambda x: v1 <= x <= v2

        base_clusters = clusters
        if cat_filter:
            base_clusters = [c for c in base_clusters if c.get("category") in cat_filter]
        if status_filter:
            base_clusters = [
                c for c in base_clusters
                if any(
                    (status_filter == "pending" and any(k in str(inv.get("payment_status", "")).lower() for k in ["pend", "unpaid", "hold"]))
                    or (status_filter in str(inv.get("payment_status", "")).lower())
                    for inv in c.get("invoices", [])
                )
            ]

        # 1. Clusters whose potential overpayment exposure matches the threshold
        exp_clusters = [c for c in base_clusters if match_cluster_exp(float(c.get("total_exposure_aed", 0.0)))]
        exp_clusters_total = sum(float(c.get("total_exposure_aed", 0.0)) for c in exp_clusters)

        # 2. Clusters that contain individual flagged invoices matching the threshold
        inv_clusters = [
            c for c in base_clusters
            if any(match_inv_amt(float(inv.get("amount_aed", 0.0))) for inv in c.get("invoices", []))
        ]
        matching_flagged_invs = {}
        for c in inv_clusters:
            for inv in c.get("invoices", []):
                if match_inv_amt(float(inv.get("amount_aed", 0.0))):
                    matching_flagged_invs[inv.get("invoice_id")] = (c, inv)

        # 3. Total records in full ledger matching threshold (for complete reconciliation)
        ledger_matching_count = sum(1 for r in records if match_inv_amt(float(getattr(r, "amount_aed", 0.0))))

        # Combined union count
        union_cluster_count = len({c["cluster_id"] for c in exp_clusters + inv_clusters})

        scope_parts = []
        if cat_label:
            scope_parts.append(cat_label)
        if status_filter:
            scope_parts.append(f"Status: {status_filter.title()}")
        scope_note = f" ({' · '.join(scope_parts)})" if scope_parts else ""
        lines = [f"### 📊 Filtered Duplicate Analysis: **{cond_label}**{scope_note}\n"]
        lines.append(f"**Exact Forensic Counts ({cond_label}):**")
        lines.append(f"* **Total Matching Duplicate / Discrepancy Clusters:** **{union_cluster_count}** cluster(s) out of {len(clusters)} total")
        lines.append(f"* **Clusters with Flagged Overpayment Exposure {cond_label}:** **{len(exp_clusters)}** cluster(s) (Combined Exposure: **AED {exp_clusters_total:,.2f}**)")
        lines.append(f"* **Clusters Containing Individual Flagged Invoices {cond_label}:** **{len(inv_clusters)}** cluster(s) (**{len(matching_flagged_invs)}** unique flagged invoice record(s))")
        if records:
            lines.append(f"* **All Invoices in Full Ledger {cond_label} (Clean + Flagged):** {ledger_matching_count} record(s) out of {records_count:,}\n")

        # Merge union of matching clusters so user sees every relevant item
        union_ids = []
        seen_cid = set()
        for c in exp_clusters + inv_clusters:
            cid = c["cluster_id"]
            if cid not in seen_cid:
                seen_cid.add(cid)
                union_ids.append(c)

        if union_ids:
            lines.append("**Detailed Breakdown of Matching Flagged Clusters:**")
            for c in union_ids:
                invs_over = [inv for inv in c.get("invoices", []) if match_inv_amt(float(inv.get("amount_aed", 0.0)))]
                exp_match_tag = "✓ Exposure matches" if match_cluster_exp(float(c.get("total_exposure_aed", 0.0))) else "✓ Contains matching invoice(s)"
                lines.append(
                    f"- **`{c['cluster_id']}`** | `{c['category']}` ({c['severity']}) | **{c['primary_vendor']}** — "
                    f"Exposure: **AED {c['total_exposure_aed']:,.2f}** *({exp_match_tag})*"
                )
                lines.append(f"  - *Rationale:* {c['rationale']}")
                for inv in c.get("invoices", []):
                    marker = "👉 " if inv in invs_over else "   "
                    lines.append(
                        f"  {marker}• Inv `#{inv.get('invoice_number')}` | Date: `{inv.get('invoice_date')}` | "
                        f"Amount: **AED {inv.get('amount_aed', 0.0):,.2f}** | Status: `{inv.get('payment_status')}`"
                    )
        else:
            lines.append(f"✅ **0 duplicate clusters or flagged invoices** matched the filter **{cond_label}**.")

        return True, "\n".join(lines)

    # ==========================================================================
    # PRIORITY C: Category-Specific Queries
    # ==========================================================================
    if cat_filter and not any(w in q for w in ["cfo", "memo", "recovery", "letter", "vat", "tax"]):
        cat_clusters = [c for c in clusters if c.get("category") in cat_filter]
        cat_exp = sum(float(c.get("total_exposure_aed", 0.0)) for c in cat_clusters)
        lines = [f"### 🏷️ Category Audit Filter: **{cat_label}**\n"]
        lines.append(f"* **Matching Clusters:** **{len(cat_clusters)}** out of {len(clusters)} total clusters")
        lines.append(f"* **Combined Overpayment Exposure:** **AED {cat_exp:,.2f}**\n")
        if cat_clusters:
            for c in cat_clusters:
                lines.append(f"- **`{c['cluster_id']}`** ({c['severity']}) | **{c['primary_vendor']}** — Exposure: **AED {c['total_exposure_aed']:,.2f}**")
                lines.append(f"  - *Details:* {c['rationale']}")
        else:
            lines.append(f"✅ No anomalies were flagged under **{cat_label}**.")
        return True, "\n".join(lines)

    # ==========================================================================
    # PRIORITY D: Payment Status Queries (Pending / Paid / Approved)
    # ==========================================================================
    if status_filter and not ("paid" in q and "pending" in q) and "payment status" not in q and "breakdown by status" not in q and not any(w in q for w in ["cfo", "memo", "recovery", "letter", "vat", "tax"]):
        matching_rows = []
        seen_keys = set()
        for c in clusters:
            for inv in c.get("invoices", []):
                st_val = str(inv.get("payment_status", "")).strip().lower()
                if (status_filter == "pending" and ("pend" in st_val or "unpaid" in st_val or "hold" in st_val)) or (status_filter in st_val):
                    key = (c["cluster_id"], inv.get("invoice_id"))
                    if key not in seen_keys:
                        seen_keys.add(key)
                        matching_rows.append((c, inv))

        unique_inv_amt = {}
        for _, inv in matching_rows:
            unique_inv_amt[inv.get("invoice_id")] = float(inv.get("amount_aed", 0.0))
        total_status_amt = sum(unique_inv_amt.values())

        lines = [f"### 💳 Flagged Duplicate Invoices by Payment Status: **{status_filter.upper()}**\n"]
        lines.append(f"* **Flagged Invoices with Status '{status_filter.title()}':** **{len(unique_inv_amt)}** unique invoice(s)")
        lines.append(f"* **Gross Value of These Flagged Invoices:** **AED {total_status_amt:,.2f}**\n")
        if matching_rows:
            for c, inv in matching_rows[:25]:
                lines.append(
                    f"- `{c['cluster_id']}` (`{c['category']}`) | **{inv.get('vendor_name')}** | Inv `#{inv.get('invoice_number')}` | "
                    f"**AED {inv.get('amount_aed', 0.0):,.2f}** | Status: `{inv.get('payment_status')}`"
                )
            if len(matching_rows) > 25:
                lines.append(f"- *...and {len(matching_rows) - 25} more matching records.*")
        else:
            lines.append(f"No flagged invoices currently have status matching `{status_filter}`.")
        return True, "\n".join(lines)

    # ==========================================================================
    # PRIORITY E: Action Templates (CFO Memo, Recovery Letter, VAT, Top Vendors)
    # ==========================================================================
    if "cfo" in q or "memo" in q or "executive" in q:
        top_v_text = ", ".join([f"{v[0]} (AED {v[1]:,.2f})" for v in sorted_vendors[:3]]) if sorted_vendors else "None"
        return False, f"""### 📑 Executive Forensic Audit Memorandum for Chief Financial Officer
**Subject:** Accounts Payable Interception & Duplicate Payment Exposure Review
**Date:** {datetime.now().strftime('%d %B %Y')}
**Author:** Senior Forensic Internal Auditor · Scientia AI Lab

**1. Executive Summary & Exposure Magnitude:**
* A comprehensive full-ledger forensic audit was completed across **{records_count:,} invoices** representing **AED {total_spend:,.2f}** in gross disbursements.
* The deterministic engine intercepted **{len(clusters)} risk clusters** representing a combined cash leakage exposure of **AED {total_exposure:,.2f}** ({meta.get('deduplication_risk_rate_pct', 0.0)}% leakage risk rate).
* **Top Exposure Entities:** {top_v_text}.

**2. Core Root-Cause Vulnerabilities:**
* **Bypass of ERP 3-Way Match:** Invoices submitted with minor typographical variants or serial re-billings bypassing legacy standard matching.
* **Fragmented Sub-Invoicing:** Vendors submitting consecutive lower-value invoices for related purchase orders across dates.
* **Bank Remittance IBAN Collisions:** Multiple vendor entity names tied to single beneficiary accounts, representing high-probability ghost vendor collusion.

**3. Immediate Management Directives:**
1. **Immediate Disbursement Freeze:** Place instant automated payment holds on all {len(clusters)} flagged voucher clusters pending dual-signoff reconciliation.
2. **Vendor Ledger Confirmation:** Issue formal balance confirmation statements to top exposure vendors to reconcile open balances vs credit notes.
3. **KYV & Bank Verification:** Mandate stamped bank account confirmation letters from UAE Central Bank licensed institutions for all flagged remittance accounts.
"""

    if "recovery" in q or "letter" in q or "dispute" in q or "demand" in q:
        target_vendor = sorted_vendors[0][0] if sorted_vendors else "Vendor Management"
        target_exp = sorted_vendors[0][1] if sorted_vendors else total_exposure
        target_clusters = [c for c in clusters if c["primary_vendor"] == target_vendor]
        inv_list = []
        if target_clusters:
            for inv in target_clusters[0]["invoices"]:
                inv_list.append(f"  - Invoice #{inv.get('invoice_number', 'N/A')} dated {inv.get('invoice_date', 'N/A')} for AED {inv.get('amount_aed', 0.0):,.2f}")
        inv_str = "\n".join(inv_list) if inv_list else "  - Reference vouchers currently under formal audit hold"

        return False, f"""### ✉️ Formal Commercial Payment Recovery & Discrepancy Notice
**To:** Finance & Accounts Department — {target_vendor}
**From:** Internal Audit & Accounts Payable Governance Team
**Date:** {datetime.now().strftime('%d %B %Y')}
**Reference:** AP-AUDIT-DISCREPANCY-{datetime.now().strftime('%Y%m')}-01

**Subject: Notice of Identified Duplicate / Conflicting Invoices & Request for Statement Reconciliation**

Dear Vendor Finance Team,

During our regular statutory accounts payable internal audit and reconciliation review, our automated forensic audit system identified conflicting invoice submissions and duplicate charges against our account:

**Details of Flagged Invoices:**
{inv_str}

**Total In Dispute / Under Hold:** AED {target_exp:,.2f}

**Required Immediate Action:**
1. Please review your sub-ledger and confirm whether credit notes have already been processed for these duplicate references.
2. If payments have been disbursed, please issue a credit memo or transfer the refund to our operating bank account within **7 business days**.
3. Provide your updated Statement of Account (SOA) as of today's date.

All pending disbursements against the above references are held in suspense pending this reconciliation.

Sincerely,
**Accounts Payable Internal Audit & Internal Controls Committee**
"""

    if "vat" in q or "tax" in q or "fta" in q or "compliance" in q:
        return False, f"""### ⚖️ UAE Tax & VAT Statutory Compliance Analysis
**Regulatory Jurisdiction:** UAE Federal Tax Authority (FTA) · Federal Decree-Law No. 8 of 2017 (VAT) & Federal Decree-Law No. 47 of 2022 (Corporate Tax)

**1. Input VAT Deduction Exposure:**
* If your company inadvertently recovered 5% Input VAT twice on duplicate invoices (e.g. from the **AED {total_exposure:,.2f}** flagged overpayment pool), this constitutes an **excessive Input Tax reclaim** under FTA Audit standards.
* **Penalty Risk:** FTA administrative penalties under Cabinet Decision No. 49 of 2021 include a fixed penalty of AED 1,000 to AED 20,000 plus percentage-based penalties (up to 50%) on unpaid or erroneously recovered tax.

**2. Corporate Tax Deductibility (Decree-Law No. 47):**
* Duplicate disbursements not backed by bona fide commercial goods/services cannot qualify as deductible business expenditure under Corporate Tax rules.
* Any unrecovered duplicate payments must be added back to taxable income or pursued as recoverable vendor debts.

**3. Remediation Directive:**
* Perform an immediate VAT Voluntary Disclosure (Form 211) if the aggregate error exceeds AED 10,000 on previous tax returns.
* Ensure all tax credit notes are matched against original Tax Registration Numbers (TRNs).
"""

    if any(w in q for w in ["top", "highest", "worst", "riskiest", "rank", "by vendor", "which vendor"]) and not any(w in q for w in ["clean vendor", "no duplicate", "zero duplicate", "safe vendor", "unflagged vendor"]):
        breakdown_lines = []
        for rank, (vname, exp) in enumerate(sorted_vendors[:5], 1):
            cl_for_v = [c for c in clusters if c["primary_vendor"] == vname]
            cats = ", ".join(set([c["category"] for c in cl_for_v]))
            breakdown_lines.append(f"**{rank}. {vname}**\n* Total Exposure: **AED {exp:,.2f}** across {len(cl_for_v)} cluster(s)\n* Anomaly Types: `{cats}`\n* Rationale: {cl_for_v[0]['rationale'] if cl_for_v else 'Duplicate billing pattern'}")
        
        breakdown_text = "\n\n".join(breakdown_lines) if breakdown_lines else "No high-risk vendors identified."
        return True, f"""### 🚨 High-Risk Vendor Overpayment Assessment
Out of {records_count:,} audited vouchers, the following vendors represent the highest financial exposure:

{breakdown_text}

**Forensic Audit Recommendation:**
Instruct Accounts Payable to suspend payment batch releases for these accounts until trade license and physical delivery notes (PODs) are validated.
"""

    # ==========================================================================
    # PRIORITY E2: Dynamic Stats, Clean Vendors, Paid-vs-Pending, Date/ID/Keyword Search
    # ==========================================================================
    if any(w in q for w in ["clean vendor", "no duplicate", "zero duplicate", "safe vendor", "unflagged vendor"]):
        flagged_vendor_set = {c["primary_vendor"].lower() for c in clusters}
        for c in clusters:
            for inv in c.get("invoices", []):
                flagged_vendor_set.add(str(inv.get("vendor_name", "")).strip().lower())
        clean_v_map = {}
        for r in records:
            vn = str(getattr(r, "vendor_name", "")).strip()
            if vn and vn.lower() not in flagged_vendor_set:
                if vn not in clean_v_map:
                    clean_v_map[vn] = [0, 0.0]
                clean_v_map[vn][0] += 1
                clean_v_map[vn][1] += float(getattr(r, "amount_aed", 0.0))
        lines = [f"### ✅ Clean Vendors (Zero Flagged Duplicates): **{len(clean_v_map)}** vendor(s)\n"]
        if clean_v_map:
            for vn, (cnt, amt) in sorted(clean_v_map.items(), key=lambda x: x[1][1], reverse=True):
                lines.append(f"- **{vn}** — {cnt} clean invoice(s) totaling **AED {amt:,.2f}**")
        else:
            lines.append("Every vendor in the loaded dataset appears in at least one flagged risk cluster.")
        return True, "\n".join(lines)

    if ("paid" in q and "pending" in q) or "payment status" in q or "breakdown by status" in q:
        status_totals = {}
        for r in records:
            st_k = str(getattr(r, "payment_status", "Unknown")).strip() or "Unknown"
            if st_k not in status_totals:
                status_totals[st_k] = [0, 0.0]
            status_totals[st_k][0] += 1
            status_totals[st_k][1] += float(getattr(r, "amount_aed", 0.0))
        flagged_by_status = {}
        seen_f = set()
        for c in clusters:
            for inv in c.get("invoices", []):
                iid = inv.get("invoice_id")
                if iid in seen_f:
                    continue
                seen_f.add(iid)
                st_k = str(inv.get("payment_status", "Unknown")).strip() or "Unknown"
                if st_k not in flagged_by_status:
                    flagged_by_status[st_k] = [0, 0.0]
                flagged_by_status[st_k][0] += 1
                flagged_by_status[st_k][1] += float(inv.get("amount_aed", 0.0))
        lines = ["### 💳 Payment Status Breakdown (Full Ledger vs Flagged Duplicates)\n", "**Full Ledger:**"]
        for st_k, (cnt, amt) in sorted(status_totals.items(), key=lambda x: x[1][1], reverse=True):
            lines.append(f"- **`{st_k}`**: {cnt} invoice(s) — **AED {amt:,.2f}**")
        lines.append("\n**Flagged Duplicate / Risk Invoices Only:**")
        for st_k, (cnt, amt) in sorted(flagged_by_status.items(), key=lambda x: x[1][1], reverse=True):
            lines.append(f"- **`{st_k}`**: {cnt} flagged invoice(s) — **AED {amt:,.2f}**")
        return True, "\n".join(lines)

    if any(w in q for w in ["average", "mean", "largest", "biggest", "smallest", "minimum", "maximum", "monthly", "by month", "summary stats"]):
        amounts = [float(getattr(r, "amount_aed", 0.0)) for r in records]
        avg_amt = sum(amounts) / len(amounts) if amounts else 0.0
        max_rec = max(records, key=lambda r: float(getattr(r, "amount_aed", 0.0))) if records else None
        min_rec = min(records, key=lambda r: float(getattr(r, "amount_aed", 0.0))) if records else None
        monthly_map = {}
        for r in records:
            m_key = str(getattr(r, "invoice_date", ""))[:7] or "Unknown"
            if m_key not in monthly_map:
                monthly_map[m_key] = [0, 0.0]
            monthly_map[m_key][0] += 1
            monthly_map[m_key][1] += float(getattr(r, "amount_aed", 0.0))
        lines = ["### 📈 Full-Ledger Statistical & Monthly Breakdown\n"]
        lines.append(f"* **Total Records:** {records_count:,} | **Total Spend:** AED {total_spend:,.2f}")
        lines.append(f"* **Average Invoice Amount:** AED {avg_amt:,.2f}")
        if max_rec:
            lines.append(f"* **Largest Single Invoice:** Inv `#{max_rec.invoice_number}` ({max_rec.vendor_name}) — **AED {max_rec.amount_aed:,.2f}**")
        if min_rec:
            lines.append(f"* **Smallest Single Invoice:** Inv `#{min_rec.invoice_number}` ({min_rec.vendor_name}) — **AED {min_rec.amount_aed:,.2f}**")
        lines.append("\n**Monthly Volume & Spend:**")
        for m_key, (cnt, amt) in sorted(monthly_map.items()):
            lines.append(f"- **`{m_key}`**: {cnt} invoice(s) — **AED {amt:,.2f}**")
        return True, "\n".join(lines)

    # Dynamic search for specific Invoice #, PO #, IBAN, TRN, Month name, or Description keywords
    month_map = {
        "january": "-01-", "jan": "-01-", "february": "-02-", "feb": "-02-", "march": "-03-", "mar": "-03-",
        "april": "-04-", "apr": "-04-", "may": "-05-", "june": "-06-", "jun": "-06-",
        "july": "-07-", "jul": "-07-", "august": "-08-", "aug": "-08-", "september": "-09-", "sep": "-09-",
        "october": "-10-", "oct": "-10-", "november": "-11-", "nov": "-11-", "december": "-12-", "dec": "-12-"
    }
    matched_month_codes = [code for name, code in month_map.items() if re.search(rf"\b{name}\b", q)]
    search_stop = {
        "what", "when", "where", "which", "who", "whom", "whose", "why", "how", "are", "there", "any",
        "the", "and", "for", "with", "from", "that", "this", "these", "those", "have", "has", "had",
        "can", "you", "tell", "show", "list", "give", "find", "check", "all", "total", "many", "much",
        "duplicate", "duplicates", "duplicated", "invoice", "invoices", "vendor", "vendors", "supplier",
        "payment", "payments", "amount", "aed", "usd", "audit", "cluster", "clusters", "flagged", "risk",
        "identified", "explain", "describe", "summarize", "summary", "report", "month", "date", "records"
    }
    raw_terms = [t for t in re.findall(r"[a-z0-9\-_]{3,}", q) if t not in search_stop and t not in month_map]
    # Include YYYY-MM or full codes cleanly
    if matched_month_codes or raw_terms:
        matched_recs = []
        for r in records:
            haystack = " ".join([
                str(getattr(r, "invoice_id", "")), str(getattr(r, "vendor_name", "")),
                str(getattr(r, "trn", "")), str(getattr(r, "invoice_number", "")),
                str(getattr(r, "invoice_date", "")), str(getattr(r, "po_number", "")),
                str(getattr(r, "iban", "")), str(getattr(r, "description", "")),
                str(getattr(r, "payment_status", ""))
            ]).lower()
            m_ok = any(mc.strip("-") in str(getattr(r, "invoice_date", ""))[5:7] for mc in matched_month_codes) if matched_month_codes else True
            t_ok = any(term in haystack for term in raw_terms) if raw_terms else True
            if m_ok and t_ok:
                matched_recs.append(r)

        matched_cls = []
        for c in clusters:
            c_haystack = (
                f"{c.get('cluster_id','')} {c.get('category','')} {c.get('primary_vendor','')} {c.get('rationale','')} " +
                " ".join(f"{inv.get('invoice_number','')} {inv.get('po_number','')} {inv.get('invoice_date','')} {inv.get('description','')}" for inv in c.get("invoices", []))
            ).lower()
            m_ok = any(mc.strip("-") in str(inv.get("invoice_date", ""))[5:7] for mc in matched_month_codes for inv in c.get("invoices", [])) if matched_month_codes else True
            t_ok = any(term in c_haystack for term in raw_terms) if raw_terms else True
            if m_ok and t_ok:
                matched_cls.append(c)

        if matched_recs or matched_cls:
            matched_amt = sum(float(getattr(r, "amount_aed", 0.0)) for r in matched_recs)
            matched_exp = sum(float(c.get("total_exposure_aed", 0.0)) for c in matched_cls)
            lines = [f"### 🔎 Ledger Search Results for: *\"{query}\"*\n"]
            lines.append(f"* **Matching Ledger Invoices:** **{len(matched_recs)}** record(s) totaling **AED {matched_amt:,.2f}**")
            lines.append(f"* **Matching Discrepancy Clusters:** **{len(matched_cls)}** cluster(s) (Exposure: **AED {matched_exp:,.2f}**)\n")
            if matched_cls:
                lines.append("**Matching Flagged Clusters:**")
                for c in matched_cls[:15]:
                    lines.append(f"- **`{c['cluster_id']}`** (`{c['category']}`) | **{c['primary_vendor']}** — Exposure: **AED {c['total_exposure_aed']:,.2f}**")
                    lines.append(f"  - *Details:* {c['rationale']}")
            if matched_recs:
                lines.append("\n**Matching Ledger Rows:**")
                for r in matched_recs[:20]:
                    lines.append(f"- Inv `#{r.invoice_number}` | {r.vendor_name} | Date: `{r.invoice_date}` | **AED {r.amount_aed:,.2f}** | PO: `{r.po_number}` | Status: `{r.payment_status}`")
                if len(matched_recs) > 20:
                    lines.append(f"- *...and {len(matched_recs) - 20} more matching record(s).*")
            return False, "\n".join(lines)

    # ==========================================================================
    # PRIORITY F: Total Counts / Summary Breakdown
    # ==========================================================================
    cat_counts = {}
    cat_exp_map = {}
    for c in clusters:
        cat = c["category"]
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        cat_exp_map[cat] = cat_exp_map.get(cat, 0.0) + float(c.get("total_exposure_aed", 0.0))

    cat_summary_lines = "\n".join([
        f"- **`{cat}`**: {cnt} cluster(s) — AED {cat_exp_map[cat]:,.2f}"
        for cat, cnt in sorted(cat_counts.items(), key=lambda x: cat_exp_map[x[0]], reverse=True)
    ]) or "- No discrepancy clusters flagged."

    flagged_unique_ids = {inv.get("invoice_id") for c in clusters for inv in c.get("invoices", [])}

    return False, f"""### 🔍 Audit Copilot Summary & Breakdown
**Query:** *"{query}"*

* **Total Audited Records:** {records_count:,} invoices (AED {total_spend:,.2f})
* **Total Discrepancy Clusters Identified:** **{len(clusters)}** clusters involving **{len(flagged_unique_ids)}** unique invoice record(s)
* **Total Potential Overpayment Exposure:** **AED {total_exposure:,.2f}** ({meta.get('deduplication_risk_rate_pct', 0.0)}% risk rate)
* **Top High-Risk Entity:** {sorted_vendors[0][0] if sorted_vendors else 'None'} (AED {sorted_vendors[0][1] if sorted_vendors else 0.0:,.2f})

**Breakdown by Risk Category:**
{cat_summary_lines}

💡 *Tip: With Ollama connected, any open-ended question receives the full ledger dossier. You can also ask filter queries like `"How many duplicates over AED 50000?"`, `"Are there any duplicate invoices for [Vendor Name]?"`, `"Show clean vendors"`, `"Compare paid vs pending"`, or `"Monthly breakdown"`.*
"""


def build_full_ledger_ai_dossier(query: str, result: dict, clusters: list, records: list) -> str:
    """
    Builds a comprehensive, compact analytical dossier of the ENTIRE loaded spreadsheet
    (vendors, months, statuses, all clusters, and query-relevant raw rows) so Ollama / LLM
    can answer arbitrary questions accurately without missing uploaded rows.
    """
    records = records or []
    clusters = clusters or []
    meta = result.get("metadata", {})

    # Vendor rollup across ALL records + ALL clusters
    v_stats = {}
    for r in records:
        vn = str(getattr(r, "vendor_name", "Unknown")).strip()
        if vn not in v_stats:
            v_stats[vn] = {"count": 0, "spend": 0.0, "clusters": 0, "exposure": 0.0}
        v_stats[vn]["count"] += 1
        v_stats[vn]["spend"] += float(getattr(r, "amount_aed", 0.0))
    for c in clusters:
        pv = str(c.get("primary_vendor", "")).strip()
        if pv not in v_stats:
            v_stats[pv] = {"count": 0, "spend": 0.0, "clusters": 0, "exposure": 0.0}
        v_stats[pv]["clusters"] += 1
        v_stats[pv]["exposure"] += float(c.get("total_exposure_aed", 0.0))

    vendor_lines = "\n".join([
        f"- {vn}: {s['count']} inv | Spend AED {s['spend']:,.2f} | Flagged Clusters: {s['clusters']} | Exposure AED {s['exposure']:,.2f}"
        for vn, s in sorted(v_stats.items(), key=lambda x: (x[1]["exposure"], x[1]["spend"]), reverse=True)[:100]
    ])

    # Monthly rollup
    m_stats = {}
    for r in records:
        mk = str(getattr(r, "invoice_date", ""))[:7] or "Unknown"
        if mk not in m_stats:
            m_stats[mk] = [0, 0.0]
        m_stats[mk][0] += 1
        m_stats[mk][1] += float(getattr(r, "amount_aed", 0.0))
    month_lines = "\n".join([f"- {mk}: {cnt} inv | AED {amt:,.2f}" for mk, (cnt, amt) in sorted(m_stats.items())])

    # Status rollup
    st_stats = {}
    for r in records:
        sk = str(getattr(r, "payment_status", "Unknown")).strip()
        if sk not in st_stats:
            st_stats[sk] = [0, 0.0]
        st_stats[sk][0] += 1
        st_stats[sk][1] += float(getattr(r, "amount_aed", 0.0))
    status_lines = "\n".join([f"- {sk}: {cnt} inv | AED {amt:,.2f}" for sk, (cnt, amt) in st_stats.items()])

    # Cluster context (with involved invoice numbers)
    cluster_lines = "\n".join([
        f"- {c['cluster_id']} | {c['category']} ({c['severity']}) | Vendor: {c['primary_vendor']} | "
        f"Exposure: AED {c['total_exposure_aed']:,.2f} | Invoices: [" +
        ", ".join(f"#{inv.get('invoice_number')} (AED {inv.get('amount_aed', 0):,.2f}, {inv.get('invoice_date')}, {inv.get('payment_status')})" for inv in c.get("invoices", [])) +
        f"] | {c['rationale']}"
        for c in clusters[:80]
    ]) or "None"

    # Raw rows matching query keywords (or sample rows if small ledger)
    q_terms = [t for t in re.findall(r"[a-z0-9\-_]{3,}", query.lower()) if t not in {"what", "how", "many", "are", "the", "for", "and", "with", "any", "show", "list", "vendor", "invoice", "invoices", "duplicate", "duplicates"}]
    relevant_rows = []
    if len(records) <= 60:
        relevant_rows = records
    else:
        for r in records:
            hay = f"{r.invoice_id} {r.vendor_name} {r.invoice_number} {r.invoice_date} {r.po_number} {r.description} {r.payment_status} {r.amount_aed}".lower()
            if any(t in hay for t in q_terms):
                relevant_rows.append(r)
            if len(relevant_rows) >= 60:
                break

    row_lines = "\n".join([
        f"- {r.invoice_id} | {r.vendor_name} | #{r.invoice_number} | {r.invoice_date} | AED {r.amount_aed:,.2f} | PO {r.po_number} | {r.payment_status} | {r.description}"
        for r in relevant_rows
    ])

    return (
        f"SUMMARY:\n"
        f"- Total Invoices: {meta.get('audited_records', len(records))} | Total Spend: AED {meta.get('total_spend_audited_aed', 0.0):,.2f}\n"
        f"- Flagged Clusters: {len(clusters)} | Total Exposure: AED {meta.get('total_exposure_flagged_aed', 0.0):,.2f} ({meta.get('deduplication_risk_rate_pct', 0.0)}%)\n\n"
        f"ALL VENDORS IN LEDGER ({len(v_stats)} total):\n{vendor_lines}\n\n"
        f"MONTHLY TOTALS:\n{month_lines}\n\n"
        f"PAYMENT STATUS TOTALS:\n{status_lines}\n\n"
        f"FLAGGED DISCREPANCY CLUSTERS ({len(clusters)} total):\n{cluster_lines}\n\n"
        f"RAW LEDGER SAMPLE / QUERY-MATCHED ROWS ({len(relevant_rows)} shown):\n{row_lines}"
    )


def generate_deterministic_copilot_response(query: str, result: dict, clusters: list, records: list = None) -> str:
    _, answer = run_forensic_copilot_query(query, result, clusters, records)
    return answer


def _load_logo_data_uri() -> str:
    """Loads Scientia Partners logo PNG as a base64 data URI for reliable offline display."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(script_dir, "scientia_logo.png"),
        "scientia_logo.png",
        os.path.join(script_dir, "..", "..", "src", "assets", "images", "scientia_logo_transparent.png"),
    ]
    for path in candidates:
        if os.path.exists(path):
            try:
                with open(path, "rb") as img_f:
                    encoded = base64.b64encode(img_f.read()).decode("ascii")
                    return f"data:image/png;base64,{encoded}"
            except Exception:
                pass
    return ""


# ==============================================================================
# Sidebar: Audit Controls & Configuration
# ==============================================================================
_logo_data_uri = _load_logo_data_uri()
if _logo_data_uri:
    st.sidebar.markdown(
        f"""
        <div style="background: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px 14px; margin-bottom: 0.75rem; display: flex; align-items: center; justify-content: flex-start; box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);">
            <img src="{_logo_data_uri}" alt="Scientia Partners Logo" style="height: 54px; width: auto; object-fit: contain;" />
        </div>
        """,
        unsafe_allow_html=True,
    )

st.sidebar.title("Scientia AI Lab")
st.sidebar.caption("Enterprise Governance, Risk & Audit Automation Suite")
st.sidebar.markdown("---")

st.sidebar.subheader("🛡️ Audit Mode")
st.sidebar.success("✓ **Unrestricted Full-Ledger Audit Active**\n\nAll DoA limits and 30-day window restrictions have been removed. Every invoice across all dates and amounts is scanned.")

st.sidebar.subheader("1. Typographical & Fuzzy Matching")
fuzzy_threshold = st.sidebar.slider(
    "Fuzzy Typo Threshold",
    min_value=0.60,
    max_value=0.99,
    value=0.85,
    step=0.01,
    help="Minimum string similarity ratio to flag transposed characters (e.g., INV-1001 vs INV-1OO1)."
)

st.sidebar.subheader("2. Minimum Transaction Floor")
min_floor = st.sidebar.number_input(
    "Minimum Invoice Floor (AED)",
    min_value=0.0,
    max_value=50000.0,
    value=0.0,
    step=50.0,
    help="Default 0.0 audits every invoice. Set higher to filter out petty cash receipts."
)

st.sidebar.markdown("---")
st.sidebar.subheader("3. AI Audit Copilot (Ollama)")

ollama_online, installed_models = check_ollama_engine()

if ollama_online:
    st.sidebar.success("🟢 **Ollama Connected** (port 11434)")
    model_choices = installed_models if installed_models else ["qwen2.5:7b", "llama3.2:3b", "mistral:latest"]
    ollama_model = st.sidebar.selectbox("Active Local Model", model_choices)
    st.sidebar.caption("100% private & offline. No data leaves your machine.")
else:
    st.sidebar.info("⚪ **Ollama API Engine: Standby**")
    ollama_model = st.sidebar.selectbox("Target Model", ["qwen2.5:7b", "llama3.2:3b", "mistral:latest"])
    with st.sidebar.expander("❓ Why does localhost:11434 say 'Ollama is running'?", expanded=True):
        st.write("""
        **Port 11434 is Ollama's background API server, not a chat webpage.**
        
        When you visit it in a browser, seeing `"Ollama is running"` confirms your backend service is alive!
        
        👉 **Where do you ask queries?**
        Right here in this Streamlit dashboard! Use the **'Interactive AI Audit Copilot'** console on the main screen below.
        """)


# ==============================================================================
# Main Dashboard
# ==============================================================================
st.markdown("<div class='main-header'>Duplicate Invoice & Payment Investigator (Agent FA-01)</div>", unsafe_allow_html=True)
st.markdown("<div class='sub-header'>High-Throughput Accounts Payable Forensic Engine | Unrestricted Full-Ledger Audit</div>", unsafe_allow_html=True)

st.markdown("""
<div class='unrestricted-badge'>
    <strong>✓ Full-Ledger Audit Mode Active:</strong> DoA limits and 30-day window restrictions have been completely removed. 100% of historical transactions are evaluated for exact matches, fuzzy typos, same-amount duplicate disbursements, PO multi-billings, fragmented invoices, and ghost vendor IBANs.
</div>
""", unsafe_allow_html=True)

# File uploader (supports CSV and Excel)
uploaded_file = st.file_uploader(
    "Upload Accounts Payable Ledger (.csv, .xlsx, .xls)",
    type=["csv", "xlsx", "xls"],
    help="Supports any ERP export format (SAP, Oracle, NetSuite, Dynamics, QuickBooks, Tally, Zoho)"
)

# Load data
df_raw = pd.DataFrame()
if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith(".csv"):
            df_raw = pd.read_csv(uploaded_file)
        else:
            df_raw = pd.read_excel(uploaded_file)
        st.success(f"✓ Successfully loaded `{uploaded_file.name}` ({len(df_raw):,} ledger records)")
    except Exception as e:
        st.error(f"Error loading uploaded file: {e}")
else:
    st.info("💡 No custom file uploaded yet. Loading pre-packaged benchmark dataset (`sample_invoices.csv`).")
    try:
        sample_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_invoices.csv")
        if os.path.exists(sample_path):
            df_raw = pd.read_csv(sample_path)
        else:
            df_raw = pd.read_csv("sample_invoices.csv")
    except Exception:
        df_raw = pd.DataFrame()

if not df_raw.empty:
    records = map_dataframe_to_records(df_raw)

    # Execute Deterministic Forensic Analysis with unrestricted parameters
    engine = DuplicateInvestigatorEngine(
        fuzzy_threshold=fuzzy_threshold,
        min_amount_floor=min_floor
    )
    result = engine.analyze(records)
    meta = result["metadata"]
    clusters = result["clusters"]

    # Top KPI Metrics Cards (Full-visibility layout prevents ellipsis truncation on large AED totals)
    kpi1, kpi2, kpi3, kpi4 = st.columns([0.9, 1.45, 1.45, 0.9])
    with kpi1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Audited Invoices</div>
            <div class="metric-value">{meta['audited_records']:,}</div>
        </div>
        """, unsafe_allow_html=True)
    with kpi2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Total Ledger Spend</div>
            <div class="metric-value">AED {meta['total_spend_audited_aed']:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with kpi3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Flagged Exposure</div>
            <div class="metric-value" style="color: #b91c1c;">AED {meta['total_exposure_flagged_aed']:,.2f}</div>
            <span class="metric-delta">↑ {meta['clusters_identified']} discrepancy clusters</span>
        </div>
        """, unsafe_allow_html=True)
    with kpi4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Risk Rate</div>
            <div class="metric-value">{meta['deduplication_risk_rate_pct']:.2f}%</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    # Quick Action Download Excel Banner
    excel_report_data = generate_excel_workbook(result, df_raw, clusters)
    banner_col1, banner_col2 = st.columns([3, 1.2])
    with banner_col1:
        st.success(f"📊 **Forensic Audit Complete**: Scanned {meta['audited_records']:,} invoices across full historical dataset (Zero DoA caps, Zero day restrictions). Identified **{len(clusters)}** risk clusters totaling **AED {meta['total_exposure_flagged_aed']:,.2f}** in potential cash leakage.")
    with banner_col2:
        st.download_button(
            label="📥 Download Excel Report (.XLSX)",
            data=excel_report_data,
            file_name=f"scientia_duplicate_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # ==============================================================================
    # Interactive AI Audit Copilot Console (Prominently Placed at the Top)
    # ==============================================================================
    st.markdown("---")
    st.subheader("🤖 Interactive AI Audit Copilot (Ask Anything About Your Invoices & Findings)")
    
    st.markdown("""
    Ask natural-language questions about this accounts payable sub-ledger. The Copilot analyzes your loaded invoices, 
    explains specific duplicate flags, evaluates high-risk suppliers, or drafts formal audit memos.
    """)

    # Ollama Health & Query Guidance Banner
    if ollama_online:
        st.success(f"🟢 **Ollama Connected**: Querying local model `{ollama_model}` at `http://localhost:11434`. 100% private & zero data leaves your PC.")
    else:
        st.info(
            "💡 **Where to ask queries? Right here!**\n\n"
            "• When you open `http://localhost:11434` in a browser, seeing *'Ollama is running'* means the backend API service is active.\n"
            "• You ask all your questions and audit queries **right in the input box below**!\n"
            "• Even without Ollama running, the built-in deterministic forensic intelligence answers your questions instantly."
        )

    # Quick Action Prompt Buttons
    st.markdown("**Quick Audit Queries (Click any prompt to run):**")
    qp1, qp2, qp3, qp4 = st.columns(4)
    quick_choice = None
    with qp1:
        if st.button("📝 Draft Memo for CFO", use_container_width=True):
            quick_choice = "Draft a formal 3-bullet executive audit memo for the Chief Financial Officer summarizing total overpayment exposure, root causes, and immediate internal control actions required."
    with qp2:
        if st.button("🚨 Top High-Risk Vendors", use_container_width=True):
            quick_choice = "Which vendors represent the highest duplicate payment risk and potential cash leakage in this audit? Break down each vendor's exposure and invoice anomalies."
    with qp3:
        if st.button("✉️ Draft Recovery Letter", use_container_width=True):
            quick_choice = "Draft a professional vendor payment recovery and dispute letter for the highest exposure cluster, referencing the specific invoice numbers, duplicate amounts, and requesting credit note / refund."
    with qp4:
        if st.button("⚖️ UAE Tax & VAT Check", use_container_width=True):
            quick_choice = "Analyze the VAT and corporate tax implications of these duplicate billings under UAE Federal Tax Authority (FTA) regulations and Decree-Law No. 47."

    # Interactive Query Form (Supports both pressing Enter and clicking Submit Query)
    with st.form(key="copilot_query_form", clear_on_submit=False):
        q_col1, q_col2 = st.columns([4, 1])
        with q_col1:
            query_text = st.text_input(
                "Enter your query or filter request:",
                placeholder="e.g., How many total duplicates identified over AED 50000? Or: Are there any duplicate invoices for Jeddah Marine vendor?",
                key="audit_copilot_input",
                label_visibility="collapsed"
            )
        with q_col2:
            run_query_clicked = st.form_submit_button("Submit Query 🔍", type="primary", use_container_width=True)

    active_query = None
    if quick_choice:
        active_query = quick_choice
    elif run_query_clicked and query_text.strip():
        active_query = query_text.strip()

    if active_query:
        with st.spinner("Analyzing full ledger and generating verified forensic response..."):
            is_exact_query, deterministic_ans = run_forensic_copilot_query(active_query, result, clusters, records)
            response_text = None
            engine_source = "Verified Forensic Engine (100% Full-Ledger Grounded)"

            # Exact data filters & vendor lookups always use deterministic full-ledger computation to prevent hallucination
            if is_exact_query:
                response_text = deterministic_ans
            elif ollama_online:
                try:
                    dossier = build_full_ledger_ai_dossier(active_query, result, clusters, records)
                    system_prompt = (
                        f"You are a Senior Internal Forensic Auditor at Scientia Partners AI Lab specializing in Accounts Payable control defense.\n"
                        f"Below is the FULL analytical dossier computed from the user's loaded spreadsheet:\n\n"
                        f"{dossier}\n\n"
                        f"PRE-COMPUTED QUERY CHECK:\n{deterministic_ans}\n\n"
                        f"USER QUESTION: {active_query}\n\n"
                        f"Answer the user's question directly, concisely, and accurately using ONLY the verified numbers, vendors, invoices, and dates above. "
                        f"If something is zero or not in the dataset, state that explicitly."
                    )
                    res = requests.post(
                        "http://localhost:11434/api/generate",
                        json={"model": ollama_model, "prompt": system_prompt, "stream": False},
                        timeout=60
                    )
                    if res.status_code == 200 and res.json().get("response"):
                        response_text = res.json().get("response")
                        engine_source = f"Ollama Local Model ({ollama_model}) + Full-Ledger Dossier"
                except Exception as e:
                    st.warning(f"Note: Could not reach Ollama model ({e}). Using built-in verified forensic engine.")

            if not response_text:
                response_text = deterministic_ans

            st.session_state["copilot_last_query"] = active_query
            st.session_state["copilot_last_response"] = response_text
            st.session_state["copilot_last_source"] = engine_source
            st.session_state["copilot_last_time"] = datetime.now().strftime("%H:%M:%S")

    if st.session_state.get("copilot_last_response"):
        st.markdown("### 📋 Copilot Audit Analysis")
        st.caption(f"Query: \"{st.session_state.get('copilot_last_query', '')}\"")
        st.info(st.session_state["copilot_last_response"])
        st.caption(
            f"Generated at {st.session_state.get('copilot_last_time', '')} · "
            f"{st.session_state.get('copilot_last_source', '')} · "
            f"Scanned {meta['audited_records']:,} records across {len(clusters)} discrepancy clusters."
        )

    st.markdown("---")

    # ==========================================================================
    # Interactive Audit Filter Bar
    # ==========================================================================
    st.subheader("🔍 Filter & Investigate Findings")

    f_col1, f_col2, f_col3 = st.columns(3)
    with f_col1:
        cat_options = ["ALL CATEGORIES"] + sorted(list({c["category"] for c in clusters}))
        selected_cat = st.selectbox("Risk Category:", cat_options)

    with f_col2:
        sev_options = ["ALL SEVERITIES", "CRITICAL", "HIGH", "MEDIUM"]
        selected_sev = st.selectbox("Severity Level:", sev_options)

    with f_col3:
        unique_vendors = ["ALL VENDORS"] + sorted(list({c["primary_vendor"] for c in clusters}))
        selected_vendor = st.selectbox("Filter Primary Vendor:", unique_vendors)

    f_col4, f_col5 = st.columns([2, 1])
    with f_col4:
        search_query = st.text_input("Search (Invoice #, Vendor, TRN, IBAN, Rationale):", "")
    with f_col5:
        max_exposure_val = max([c["total_exposure_aed"] for c in clusters] + [100000.0])
        amount_range = st.slider(
            "Cluster Exposure Range (AED):",
            min_value=0.0,
            max_value=float(max_exposure_val),
            value=(0.0, float(max_exposure_val)),
            step=1000.0
        )

    # Apply interactive filters
    filtered_clusters = clusters

    if selected_cat != "ALL CATEGORIES":
        filtered_clusters = [c for c in filtered_clusters if c["category"] == selected_cat]

    if selected_sev != "ALL SEVERITIES":
        filtered_clusters = [c for c in filtered_clusters if c["severity"] == selected_sev]

    if selected_vendor != "ALL VENDORS":
        filtered_clusters = [c for c in filtered_clusters if c["primary_vendor"] == selected_vendor]

    filtered_clusters = [
        c for c in filtered_clusters
        if amount_range[0] <= c["total_exposure_aed"] <= amount_range[1]
    ]

    if search_query.strip():
        q = search_query.strip().lower()
        def matches_cluster(c):
            if q in c["primary_vendor"].lower() or q in c["rationale"].lower() or q in c["category"].lower():
                return True
            for inv in c["invoices"]:
                if (
                    q in str(inv.get("invoice_number", "")).lower() or
                    q in str(inv.get("trn", "")).lower() or
                    q in str(inv.get("iban", "")).lower() or
                    q in str(inv.get("po_number", "")).lower() or
                    q in str(inv.get("description", "")).lower()
                ):
                    return True
            return False
        filtered_clusters = [c for c in filtered_clusters if matches_cluster(c)]

    st.write(f"Showing **{len(filtered_clusters)}** of **{len(clusters)}** identified discrepancy clusters")

    # Render Discrepancy Clusters
    for cl in filtered_clusters:
        sev = cl["severity"]
        badge_cls = "badge-critical" if sev == "CRITICAL" else ("badge-high" if sev == "HIGH" else "badge-medium")

        header_title = f"{cl['cluster_id']} | {cl['category'].replace('_', ' ')} — {cl['primary_vendor']} (AED {cl['total_exposure_aed']:,.2f})"

        with st.expander(header_title, expanded=(sev == "CRITICAL")):
            st.markdown(f"<span class='{badge_cls}'>{sev} RISK</span> &nbsp; <strong>Vendor:</strong> {cl['primary_vendor']} &nbsp;|&nbsp; <strong>Potential Overpayment:</strong> AED {cl['total_exposure_aed']:,.2f}", unsafe_allow_html=True)
            st.markdown(f"**Rationale:** {cl['rationale']}")
            st.markdown(f"**Action Required:** {cl['recommended_action']}")

            # Involved records table
            inv_df = pd.DataFrame(cl["invoices"])
            show_cols = [c for c in ["invoice_id", "invoice_number", "invoice_date", "amount_aed", "po_number", "payment_status", "iban", "description"] if c in inv_df.columns]
            st.dataframe(inv_df[show_cols], use_container_width=True)

            # Individual Cluster Audit Memo Button
            copilot_key = f"copilot_{cl['cluster_id']}"
            if st.button(f"Generate Audit Memo for {cl['cluster_id']}", key=copilot_key):
                with st.spinner("Generating forensic memo..."):
                    prompt = (
                        f"You are a Senior Internal Auditor. Draft a 3-bullet executive audit memo for the Accounts Payable Manager regarding:\n"
                        f"Discrepancy: {cl['category']}\n"
                        f"Vendor: {cl['primary_vendor']}\n"
                        f"Exposure: AED {cl['total_exposure_aed']:,.2f}\n"
                        f"Details: {cl['rationale']}\n"
                        f"Involved Invoices: {json.dumps(cl['invoices'], default=str)}\n"
                        f"Be concise, professional, and reference UAE commercial audit standards."
                    )
                    memo_res = None
                    if ollama_online:
                        try:
                            res = requests.post(
                                "http://localhost:11434/api/generate",
                                json={"model": ollama_model, "prompt": prompt, "stream": False},
                                timeout=20
                            )
                            if res.status_code == 200:
                                memo_res = res.json().get("response")
                        except Exception:
                            pass
                    if not memo_res:
                        memo_res = (
                            f"**Audit Findings Memo for {cl['cluster_id']} ({cl['category']})**\n\n"
                            f"1. **Exposure & Vendor Impact:** A potential duplicate overpayment exposure of **AED {cl['total_exposure_aed']:,.2f}** was identified for **{cl['primary_vendor']}** across {len(cl['invoices'])} invoice record(s).\n"
                            f"2. **Forensic Rationale:** {cl['rationale']}\n"
                            f"3. **Internal Control Directive:** {cl['recommended_action']}"
                        )
                    st.info(f"**Copilot Audit Memo:**\n\n{memo_res}")

    st.markdown("---")

    # Export Section
    st.subheader("📥 Export Audit Findings & Workpapers")
    
    # 1. Primary Excel Workbook Export
    st.markdown("#### 📑 Standard Forensic Audit Workbook (.XLSX)")
    st.write("Download an executive 4-sheet workbook formatted for Chief Audit Executives, CFOs, and External Auditors (Executive Summary, Discrepancy Clusters, Flagged Invoices, Full Audited Ledger).")
    
    excel_full_wb = generate_excel_workbook(result, df_raw, clusters)
    st.download_button(
        label="📥 Download Full Multi-Sheet Forensic Report (.XLSX)",
        data=excel_full_wb,
        file_name=f"scientia_duplicate_audit_full_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True
    )

    st.markdown("#### 📁 Additional Formats (CSV & JSON)")
    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        json_str = json.dumps(result, indent=2, default=str)
        st.download_button(
            label="Download Complete Forensic Audit Report (.JSON)",
            data=json_str,
            file_name=f"scientia_duplicate_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            use_container_width=True
        )
    with exp_col2:
        flat_records = []
        for cl in clusters:
            for inv in cl["invoices"]:
                rec = dict(inv)
                rec["cluster_id"] = cl["cluster_id"]
                rec["cluster_category"] = cl["category"]
                rec["cluster_severity"] = cl["severity"]
                rec["cluster_exposure_aed"] = cl["total_exposure_aed"]
                flat_records.append(rec)
        if flat_records:
            export_df = pd.DataFrame(flat_records)
            csv_data = export_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Download Flattened Workpaper (.CSV)",
                data=csv_data,
                file_name=f"scientia_duplicate_workpaper_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
