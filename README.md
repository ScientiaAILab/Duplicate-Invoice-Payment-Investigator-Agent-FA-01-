# SCIENTIAPARTNERS AI LAB
## AGENT FA-01: Duplicate Invoice & Payment Investigator
### Production Enterprise Audit & Forensics Engine

**Confidential & Proprietary — Developed by Scientia Partners AI Lab**  
*Website: [Scientia Partners](https://scientiapartners.com) | Inquiries: hello@scientiapartners.com*

---

## 1. Executive Summary

In enterprise accounts payable (AP) ledgers across the UAE and GCC, duplicate invoice payments and invoice-splitting represent **0.5% to 2.8% of gross annual expenditure leakage**. 

Agent FA-01 is an autonomous, 100% offline, deterministic forensic audit engine that scans Accounts Payable sub-ledgers and bank disbursement queues to intercept duplicate payments **before cash release**.

### Key Detection Capabilities
1. **Exact Duplicate Invoices**: Matches on normalized Vendor VAT TRN / Trade License ID, normalized Invoice Number, and amount. Redundant payment exposure is computed with mathematical precision (`total_exposure = total_sum - min_original_invoice`).
2. **Fuzzy OCR / Clerical Typo Matching**: Detects OCR character confusions (`0` vs `O`, `1` vs `I`, `-A`, `-dup` suffixes, transposed digits) with Levenshtein / Token Ratio similarity $> 85\%$ and amount parity $> 90\%$.
3. **Fragmented / Split Invoicing & PO Multi-Billing**: Flags multiple invoices billed against the same Purchase Order or consecutive fragmented invoices to the same vendor across the entire historical ledger (zero DoA caps or 30-day cutoff limits).
4. **Shared Destination IBAN / Ghost Vendor Collusion**: Identifies multiple supposedly independent vendor entities channeling disbursements into an identical UAE bank IBAN.

---

## 2. Quickstart & Deployment

### Prerequisites
* Python 3.9+ installed locally
* Standard command prompt or terminal

### Installation

#### On Windows (Command Prompt / PowerShell):
```cmd
cd path\to\scientia-duplicate-investigator
pip install -r requirements.txt
```

#### On Mac / Linux:
```bash
cd scientia-duplicate-investigator
pip install -r requirements.txt
```

---

### Running the Interactive Streamlit Web Dashboard

#### On Windows (Command Prompt):
```cmd
cd path\to\scientia-duplicate-investigator
pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

#### On Mac / Linux:
```bash
cd scientia-duplicate-investigator
pip install -r requirements.txt
streamlit run streamlit_app.py
```
This opens an executive dashboard at `http://localhost:8501` featuring:
* **Unrestricted Full-Ledger Audit**: All DoA limit ceilings and 30-day window restrictions have been removed. Every invoice in the ledger is checked across all dates and amounts.
* Interactive file uploader for **CSV and Excel (`.xlsx`, `.xls`)** files from any ERP (SAP, Oracle, NetSuite, Dynamics 365, Tally, QuickBooks, Zoho).
* **Direct Multi-Sheet Excel Download (`.xlsx`)**: One-click download button (`📥 Download Excel Report (.XLSX)`) right below the KPI cards or in the Export section. Generates a 4-sheet workbook:
  - `Executive_Summary`: Executive KPI metrics, spend audited, cash leakage intercepted, risk rate.
  - `Discrepancy_Clusters`: High-level forensic clusters, primary vendors, total exposure AED, audit rationale.
  - `Flagged_Invoices`: Every flagged invoice with invoice #, date, amount, PO #, IBAN, and audit notes.
  - `Full_Audited_Ledger`: Entire audited ledger with `AUDIT_STATUS` ("FLAGGED" vs "CLEAN").
* Real-time controls for **Fuzzy Typo Threshold** and **Minimum Transaction Floor**.
* 6-pass deterministic detection: Exact Duplicates, Fuzzy Typo Variations, Same-Vendor Same-Amount Duplicates (cross-date), PO Multi-Billing, Fragmented Invoicing, and Ghost Vendor Shared IBANs.
* Full-visibility KPI metric cards (*Audited Invoices*, *Total Ledger Spend*, *Flagged Exposure*, and *Risk Rate*).
* Collapsible cluster drilldowns with severity badges (`CRITICAL`, `HIGH`, `MEDIUM`).
* Additional downloads for **Audit Findings (.JSON)** and **Flattened Workpaper (.CSV)**.

---

### Running the Deterministic CLI (Batch Automation) & Excel Export
```bash
# Run unrestricted forensic audit on sample benchmark data
python duplicate_investigator.py sample_invoices.csv

# Export comprehensive 4-sheet Excel report (.xlsx)
python duplicate_investigator.py sample_invoices.csv --excel

# Or specify a custom Excel report filename
python duplicate_investigator.py sample_invoices.csv --excel my_audit_findings.xlsx

# Run with custom fuzzy threshold (e.g. 0.90) and minimum floor
python duplicate_investigator.py sample_invoices.csv --fuzzy-threshold 0.90 --min-amount 100

# Output structured JSON report directly to terminal
python duplicate_investigator.py sample_invoices.csv --json

# Or save audit findings directly to a JSON file for downstream ingestion
python duplicate_investigator.py sample_invoices.csv --output audit_report.json
```

---

## 3. Zero-Cost AI Audit Copilot (Local Ollama v0.3+ Integration)

Scientia Partners AI Lab tools operate **100% locally and offline without mandatory API keys or external cloud calls**.

* **Required Local LLM Runtime:** **Ollama v0.3.0 or newer** (tested on **Ollama v0.3+ / v0.5+**, REST API `http://localhost:11434/api/generate` and `/api/tags`).
* **Recommended Local Models:** `qwen2.5:7b` (best accuracy for financial tables), `llama3.2:3b` (lightweight for 8 GB RAM laptops), or `mistral:latest`.

### 💡 Why Does `http://localhost:11434` Say "Ollama is running"?
* **Port 11434 is a background API service** (like a database daemon). It is designed to receive programmatic API calls from applications, not to serve a browser chat webpage.
* Seeing `"Ollama is running"` on a blank white page confirms Ollama is installed and actively listening.
* **Where do you ask questions?** Ask all questions directly inside the **Scientia Streamlit Dashboard (`streamlit_app.py`)** under **"🤖 Interactive AI Audit Copilot"**.

### How to Set Up & Run Locally (Windows Command Prompt):
1. **Install Python 3.9+** and **Ollama (v0.3+)** from [ollama.com/download](https://ollama.com/download).
2. **Pull a local AI model** (one-time download):
   ```cmd
   ollama pull qwen2.5:7b
   ```
   *(For lighter hardware with 8 GB RAM, run `ollama pull llama3.2:3b` instead.)*
3. **Ensure Ollama is running** (open a terminal if the tray app is not running):
   ```cmd
   ollama serve
   ```
4. **Install dependencies & launch the Streamlit Dashboard** (in a Command Prompt window inside your repository folder):
   ```cmd
   cd scientia-duplicate-investigator
   pip install -r requirements.txt
   python -m streamlit run streamlit_app.py
   ```
5. **Ask queries in the "🤖 Interactive AI Audit Copilot" console:**
   - Even without Ollama running, the built-in deterministic engine answers exact filters (`How many duplicates over AED 50000?`), vendor lookups (`Are there any duplicate invoices for [Vendor Name]?`), clean vendors, paid-vs-pending splits, and monthly stats immediately.
   - *(Want to connect an enterprise Cloud API key — OpenAI / Azure OpenAI / Gemini / Anthropic — instead of local Ollama? Keep the open-source edition 100% local & zero-key, and contact `hello@scientiapartners.com` for custom enterprise LLM/ERP deployment.)*

---

## 4. Input Data Schema & Column Flexibility

The engine includes an intelligent column resolver that automatically maps common ERP header variations:

| Target Field | Standard Header | Alternative Headers Accepted | Description |
| :--- | :--- | :--- | :--- |
| `invoice_id` | `invoice_id` | `id`, `ref`, `doc_no`, `voucher_no` | Unique transaction record key in ERP |
| `vendor_name` | `vendor_name` | `vendor`, `supplier`, `payee`, `company_name` | Registered vendor trade name |
| `invoice_number`| `invoice_number`| `invoice_no`, `inv_num`, `invoice#`, `bill_no` | Vendor invoice reference |
| `amount_aed` | `amount_aed` | `amount`, `total`, `net_amount`, `gross_amount` | Invoice payable amount |
| `invoice_date` | `invoice_date` | `date`, `bill_date`, `document_date` | Supports YYYY-MM-DD, M/D/YYYY, etc. |
| `trn` | `trn` | `tax_id`, `vat_no`, `tax_registration_number` | 15-digit UAE VAT Tax Registration Number |
| `iban` | `iban` | `bank_account`, `remittance_iban`, `account_no` | Destination bank account / IBAN |
| `po_number` | `po_number` | `po_no`, `purchase_order`, `po`, `order_no` | Linked Purchase Order reference |
| `payment_status`| `payment_status`| `status`, `payment_state` | `Pending`, `Approved`, or `Paid` |
| `currency` | `currency` | `curr`, `doc_currency` | Default: `AED` |
| `payment_ref` | `payment_reference`| `cheque_no`, `voucher_ref` | ERP payment run reference |

---

## 5. Scientia Partners Engagement

For turnkey ERP connector deployment (SAP S/4HANA, Oracle Cloud, NetSuite, Dynamics 365, Zoho Books) or retained fractional CFO and internal audit supervision:

**Contact:** `hello@scientiapartners.com`  
**Offices:** Dubai & Abu Dhabi, United Arab Emirates
