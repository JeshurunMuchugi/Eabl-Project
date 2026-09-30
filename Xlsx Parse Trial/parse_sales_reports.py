import openpyxl
import pandas as pd

PATH = "EABL dataset/DailySalesReportNew_0101202615012026.xlsx"

NON_PRODUCT_LABELS = {'Targets', 'Achieved', 'TOTAL', 'SALE', 'Return'}


def parse_sheet(ws, sheet_name, source_file):
    rows = list(ws.iter_rows(values_only=True))

    field_row_idx, field_row = None, None
    for i, r in enumerate(rows[:15]):
        if any(isinstance(c, str) and c.strip() == 'Customer' for c in r):
            field_row_idx, field_row = i, r
            break
    if field_row_idx is None:
        return []

    col = lambda label: next((idx for idx, c in enumerate(field_row)
                               if isinstance(c, str) and c.strip() == label), None)
    custname_col, date_col = col('Customer'), col('Date')
    cust_col = custname_col - 1 if custname_col is not None else None  # code sits one column left of the label
    custtype_col, segment_col = col('Cust Type'), col('Segment')

    product_row = rows[field_row_idx - 1]
    category_row_raw = rows[field_row_idx - 2] if field_row_idx >= 2 else []

    # 'Return' (and each brand-category label) sits once at the start of a block of columns,
    # two rows above product_row -- forward-fill it so every column in that block is tagged.
    category_row = []
    current_category = None
    for i in range(len(product_row)):
        val = category_row_raw[i] if i < len(category_row_raw) else None
        if isinstance(val, str) and val.strip():
            current_category = val.strip()
        category_row.append(current_category)

    def get(r, idx):
        return r[idx] if idx is not None and idx < len(r) else None

    def to_qty(v):
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, str):
            try:
                return float(v.strip())
            except ValueError:
                return None
        return None

    records = []
    last_cust = last_type = last_seg = None
    for r in rows[field_row_idx + 1:]:
        if all(c is None or c == '' for c in r):
            last_cust = None
            continue

        cust = get(r, cust_col) if get(r, cust_col) not in (None, '') else last_cust
        custtype = get(r, custtype_col) if get(r, custtype_col) not in (None, '') else last_type
        segment = get(r, segment_col) if get(r, segment_col) not in (None, '') else last_seg
        last_cust, last_type, last_seg = cust, custtype, segment
        if not cust:
            continue

        visit_date = get(r, date_col)

        sale_qty, return_qty = {}, {}
        for i, val in enumerate(r):
            q = to_qty(val)
            if not q or i >= len(product_row) or not product_row[i]:
                continue
            product = product_row[i].strip()
            if product in NON_PRODUCT_LABELS:
                continue
            bucket = return_qty if (i < len(category_row) and category_row[i] == 'Return') else sale_qty
            bucket[product] = bucket.get(product, 0.0) + q

        for product in sale_qty.keys() | return_qty.keys():
            records.append({
                'source_file': source_file, 'salesperson': sheet_name,
                'customer_code': str(cust).split('\n')[0].strip(),
                'cust_type': custtype, 'segment': segment,
                'visit_date': visit_date, 'product': product,
                'quantity': sale_qty.get(product, 0.0),
                'return_quantity': return_qty.get(product, 0.0),
            })
    return records


if __name__ == '__main__':
    wb = openpyxl.load_workbook(PATH, read_only=True, data_only=True)
    print("Sheets found in this one file:", wb.sheetnames)
    print("=" * 80)

    all_records = []
    for sheet_name in wb.sheetnames:
        recs = parse_sheet(wb[sheet_name], sheet_name, PATH)
        print(f"{sheet_name!r}: {len(recs)} records extracted")
        all_records.extend(recs)

    df = pd.DataFrame(all_records)
    print("=" * 80)
    print("TOTAL records across all sheets in this ONE file:", len(df))
    print()
    print(df.head(20).to_string())

    OUTPUT_PATH = "DailySalesReportNew_0101202615012026_parsed.xlsx"
    df.to_excel(OUTPUT_PATH, index=False)
    print()
    print(f"Wrote {len(df)} rows to {OUTPUT_PATH} (original file untouched)")
