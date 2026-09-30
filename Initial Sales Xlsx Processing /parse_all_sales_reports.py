import argparse
import logging
import sys
from pathlib import Path

import openpyxl
import pandas as pd

from parse_sales_reports import parse_sheet

DEFAULT_INPUT_DIR = Path("EABL dataset")
DEFAULT_OUTPUT_DIR = Path("eabl parsed data")
DEFAULT_PATTERN = "DailySalesReportNew_*.xlsx"


def setup_logging(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "parse_log.txt"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.stdout)],
    )


def parse_one_file(source_path: Path) -> pd.DataFrame:
    wb = openpyxl.load_workbook(source_path, read_only=True, data_only=True)
    try:
        all_records = []
        for sheet_name in wb.sheetnames:
            try:
                records = parse_sheet(wb[sheet_name], sheet_name, source_path.name)
            except Exception:
                logging.exception("Failed to parse sheet %r in %s", sheet_name, source_path.name)
                continue
            all_records.extend(records)
    finally:
        wb.close()
    return pd.DataFrame(all_records)


def main() -> int:
    arg_parser = argparse.ArgumentParser(
        description="Parse all Daily Sales Report workbooks into one transaction table per file. "
                     "Source workbooks are opened read-only and are never modified."
    )
    arg_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    arg_parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    arg_parser.add_argument("--pattern", default=DEFAULT_PATTERN)
    arg_parser.add_argument(
        "--overwrite", action="store_true",
        help="Reparse files whose output already exists (default: skip them)",
    )
    args = arg_parser.parse_args()

    setup_logging(args.output_dir)

    source_files = sorted(args.input_dir.glob(args.pattern))
    if not source_files:
        logging.error("No files matched %s in %s", args.pattern, args.input_dir)
        return 1

    logging.info("Found %d source files to parse", len(source_files))

    summary: list[tuple[str, int, str]] = []
    had_errors = False

    for source_path in source_files:
        output_path = args.output_dir / f"{source_path.stem}_parsed.xlsx"

        if output_path.exists() and not args.overwrite:
            logging.info("Skipping %s (already parsed -> %s; use --overwrite to redo)",
                         source_path.name, output_path.name)
            continue

        logging.info("Parsing %s ...", source_path.name)
        try:
            df = parse_one_file(source_path)
        except Exception:
            logging.exception("Failed to open/parse %s -- skipping", source_path.name)
            had_errors = True
            summary.append((source_path.name, 0, "ERROR"))
            continue

        if df.empty:
            logging.warning("%s produced 0 records -- check its sheet structure", source_path.name)

        df.to_excel(output_path, index=False)
        logging.info("Wrote %d rows to %s", len(df), output_path.name)
        summary.append((source_path.name, len(df), "OK"))

    logging.info("=" * 80)
    logging.info("SUMMARY")
    total_records = sum(n for _, n, status in summary if status == "OK")
    for name, n, status in summary:
        logging.info("  %-55s %8d records  [%s]", name, n, status)
    logging.info("Total: %d file(s) processed this run, %d record(s) written", len(summary), total_records)

    return 1 if had_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
