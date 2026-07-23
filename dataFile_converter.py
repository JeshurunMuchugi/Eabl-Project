import csv
import os
from datetime import date, datetime, time

import openpyxl

DATASET_DIR = "EABL dataset"

def list_dataset_files(folder_path=DATASET_DIR):
    files = sorted(
        f for f in os.listdir(folder_path)
        if os.path.isfile(os.path.join(folder_path, f))
    )
    for f in files:
        size_mb = os.path.getsize(os.path.join(folder_path, f)) / (1024 * 1024)
        print(f"{f}  ({size_mb:.2f} MB)")
    print(f"\nTotal files: {len(files)}")
    return files


def _serialize_cell(value):
    """Return a cell's value unchanged, except for datetime-like objects
    (openpyxl gives these back as Python objects, not text) which are
    rendered as ISO strings so csv.writer can serialize them."""
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if value is None:
        return ""
    return value


def xlsx_to_csv(xlsx_filename, csv_filename=None, sheet_names=None, folder_path=DATASET_DIR):
    """Mirror an .xlsx workbook into a .csv file cell-for-cell.

    Every row and column of every sheet (in sheet order, written
    back-to-back with nothing inserted between sheets) is written exactly
    as it appears in the workbook grid - nothing is reordered, renamed,
    dropped, added, or type-coerced. Formulas are read as their last
    computed value (data_only=True), not as their formula text. Pass
    sheet_names to restrict conversion to specific sheets; by default
    every sheet in the workbook is included, in workbook order.
    """
    xlsx_path = os.path.join(folder_path, xlsx_filename)
    if csv_filename is None:
        csv_filename = os.path.splitext(xlsx_filename)[0] + ".csv"
    csv_path = os.path.join(folder_path, csv_filename)

    wb = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    try:
        names = sheet_names if sheet_names else wb.sheetnames
        total_rows = 0

        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            for name in names:
                ws = wb[name]
                for row in ws.iter_rows(values_only=True):
                    writer.writerow([_serialize_cell(v) for v in row])
                    total_rows += 1

        print(f"Converted '{xlsx_path}' -> '{csv_path}' "
              f"({len(names)} sheet(s), {total_rows} rows)")
    finally:
        wb.close()

    return csv_path


def convert_daily_sales_reports(folder_path=DATASET_DIR, prefix="DailySalesReportNew"):
    """Convert every DailySalesReportNew*.xlsx file in folder_path to its
    own same-named .csv file (e.g. DailySalesReportNew_0101202615012026.xlsx
    -> DailySalesReportNew_0101202615012026.csv), one file at a time.

    Each file is converted independently via xlsx_to_csv, which mirrors
    every sheet of that workbook (one per salesman/route) back-to-back
    into the single output csv, exactly as found - no values, nulls, rows,
    or columns are added, dropped, or altered. If one file fails to
    convert, it is reported and the remaining files still proceed.
    """
    xlsx_filenames = sorted(
        f for f in os.listdir(folder_path)
        if f.startswith(prefix) and f.lower().endswith(".xlsx")
    )
    if not xlsx_filenames:
        print(f"No '{prefix}*.xlsx' files found in '{folder_path}'.")
        return []

    converted, failed = [], []
    for xlsx_filename in xlsx_filenames:
        try:
            converted.append(xlsx_to_csv(xlsx_filename, folder_path=folder_path))
        except Exception as exc:
            print(f"FAILED: '{xlsx_filename}' -> {exc}")
            failed.append(xlsx_filename)

    print(f"\nDone: {len(converted)}/{len(xlsx_filenames)} DailySalesReportNew files converted.")
    if failed:
        print("Failed files:", failed)
    return converted


if __name__ == "__main__":
    list_dataset_files()
    xlsx_to_csv("CustomerMaster.xlsx")
    convert_daily_sales_reports()
