# EABL Customer Churn Prediction — Data & Feature Reference

Reference for the datasets and features needed to predict customer churn from the EABL sales/distribution data. Raw data is DVC-tracked and stored privately on DagsHub — never committed to this GitHub repo directly (see `EABL dataset.dvc`).

## Datasets

### 1. Customer Master
- **File**: `EABL dataset/CustomerMaster.xlsx`
- **Size**: 2,237 customers
- **Note**: the real header row is not row 1 — load with `skiprows=3` to skip the title/blank rows above it.
- **Join key**: `DMS Customer Code`

### 2. Product Master
- **File**: `EABL dataset/PRODUCT MASTER UPDATED-JULY 2026.xlsx`
- **Size**: 883 SKUs
- **Status**: clean, loads as-is, no header fix needed
- **Join key**: `Product_Description`

### 3. Daily Sales Reports (raw)
- **Files**: `EABL dataset/DailySalesReportNew_*.xlsx` — 31 half-month files spanning ~Jan 2025–Jun 2026
- **Structure**: each file is a multi-sheet workbook, one sheet per salesperson/route (15–18 sheets per file, roster varies). Within a sheet:
  - Customer code/name is stored in a merged cell spanning that customer's multiple visit rows — must be forward-filled when parsed.
  - Quantities are stored as **text strings** (e.g. `'54.00'`), not numbers — must be cast explicitly.
  - Product columns are headed by product names one row above the field-label row (`Customer | Cust Type | Segment | Date | Time-In | Time-Out | TIME AT CALL`).
  - A few columns (`Achieved`, `Targets`, `TOTAL`, `SALE`, `Return`) are subtotal columns mixed in among the product columns — must be excluded or they get miscounted as real SKUs.
  - Do **not** use the `.csv` exports of these files — they're broken (ragged rows) from the multi-sheet-to-single-CSV flattening. Use the `.xlsx` files directly.
- **Status**: parser built and verified against 1 of 31 files (`parse_sales_reports.py`, project root) — 36,174 clean transaction records extracted correctly. Still needs generalizing to loop over all 31 files (2 filenames are malformed and need manual handling: `DailySalesReportNew_1105202531062025.xlsx`, `DailySalesReportNew_162202628022026.xlsx`).

### 4. Parsed sales table (derived, not a raw file)
Output of `parse_sales_reports.py` — one row per real sale:

| Column | Description |
|---|---|
| `source_file` | which of the 31 files this came from |
| `salesperson` | the sheet name |
| `customer_code` | forward-filled through merged cells |
| `cust_type`, `segment` | as recorded in the sheet |
| `visit_date` | the actual visit date |
| `product` | resolved from the header row |
| `quantity` | cast from text to a number |

This table is the raw material the churn features are aggregated from — none of its columns are themselves model inputs.

## Final feature list (model input, one row per customer)

**From Daily Sales, aggregated per customer:**

| Feature | Computed from |
|---|---|
| `recency_periods` | time since last order |
| `frequency` | count of active periods |
| `avg_order_value` | mean of `quantity × price` (price from Product Master) |
| `order_value_std` | volatility of order value |
| `volume_trend` | recent-half vs. early-half average volume |
| `product_diversity` | count of distinct products bought |

**From Customer Master, used directly or lightly computed:**

| Feature | Computed from |
|---|---|
| `global Channel` | as-is |
| `Sub-Channel` | as-is |
| `Division` | as-is (region) |
| `Mode of Payment` | as-is |
| `credit_utilization` | `Outstanding Balance ÷ Cust Credit Limit` |
| `tenure_days` | cutoff date − `Open Account Date` |
| `rss_recency` | cutoff date − `RSS Last Login Date` |

## Target

`is_churned` — derived from whether a customer has zero order activity across a defined future window of periods, in the activity matrix. Validate this against `Cust Status` for sanity, but do not use `Cust Status` itself as an input feature (see below).

## Explicitly excluded fields

| Field | Reason |
|---|---|
| `customer_code` | join key / row identifier, not a predictor — unique IDs carry no generalizable signal |
| `Product_Description` | join key only |
| `Cust Status` | this is the label source — including it as a feature too is leakage |
| `salesperson` | not used for churn (relevant only to a separate route-performance analysis) |
| `visit_date`, `quantity`, `product` | raw transaction-level fields — material the 13 features above are built from, not features themselves |

## Pipeline status

- [x] Parser built and verified against 1 of 31 Daily Sales files
- [ ] Generalize parser across all 31 files (handle 2 malformed filenames)
- [ ] Load Customer Master with header fix, Product Master as-is
- [ ] Join parsed sales → Customer Master + Product Master
- [ ] Build customer × period activity matrix
- [ ] Compute the 13 features above
- [ ] Build chronologically-derived churn label
- [ ] Chronological train/test split
- [ ] Baseline model (logistic regression) → compare against random forest/gradient boosting
- [ ] Evaluate on precision/recall (not plain accuracy), interpret with SHAP
- [ ] Design a control-group experiment before trusting campaign impact

## How to run the parser

```bash
cd "/Users/jeshurun/Documents/Eabl project"
.venv/bin/python3 parse_sales_reports.py
```

Currently parses one file (`DailySalesReportNew_0101202615012026.xlsx`) and writes the result to `DailySalesReportNew_0101202615012026_parsed.xlsx` for inspection. Read-only against the source file — nothing in `EABL dataset/` is modified.
