import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

DEFAULT_INPUT_DIR = Path("eabl parsed data")
DEFAULT_PATTERN = "*_parsed.xlsx"


def setup_logging(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "csv_conversion_log.txt"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.stdout)],
    )


def convert_one_file(source_path: Path, output_path: Path) -> tuple[int, int]:
    df = pd.read_excel(source_path)
    source_rows = len(df)

    df.to_csv(output_path, index=False)

    verify_df = pd.read_csv(output_path)
    written_rows = len(verify_df)

    return source_rows, written_rows


def main() -> int:
    arg_parser = argparse.ArgumentParser(
        description="Convert each parsed sales xlsx file to CSV, one-to-one, with no reformatting. "
                     "Source xlsx files are opened read-only and are never modified."
    )
    arg_parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    arg_parser.add_argument("--output-dir", type=Path, default=None,
                             help="Defaults to the same directory as --input-dir")
    arg_parser.add_argument("--pattern", default=DEFAULT_PATTERN)
    arg_parser.add_argument(
        "--overwrite", action="store_true",
        help="Reconvert files whose output CSV already exists (default: skip them)",
    )
    args = arg_parser.parse_args()

    output_dir = args.output_dir if args.output_dir is not None else args.input_dir
    setup_logging(output_dir)

    source_files = sorted(args.input_dir.glob(args.pattern))
    if not source_files:
        logging.error("No files matched %s in %s", args.pattern, args.input_dir)
        return 1

    logging.info("Found %d parsed xlsx file(s) to convert", len(source_files))

    summary: list[tuple[str, int, int, str]] = []
    had_errors = False

    for source_path in source_files:
        output_path = output_dir / f"{source_path.stem}.csv"

        if output_path.exists() and not args.overwrite:
            logging.info("Skipping %s (already converted -> %s; use --overwrite to redo)",
                         source_path.name, output_path.name)
            continue

        logging.info("Converting %s ...", source_path.name)
        try:
            source_rows, written_rows = convert_one_file(source_path, output_path)
        except Exception:
            logging.exception("Failed to convert %s -- skipping", source_path.name)
            had_errors = True
            summary.append((source_path.name, 0, 0, "ERROR"))
            continue

        if written_rows != source_rows:
            logging.error(
                "ROW MISMATCH in %s: xlsx had %d rows, csv has %d rows",
                source_path.name, source_rows, written_rows,
            )
            had_errors = True
            summary.append((source_path.name, source_rows, written_rows, "MISMATCH"))
            continue

        logging.info("Verified %s: %d rows in xlsx == %d rows in csv", source_path.name, source_rows, written_rows)
        summary.append((source_path.name, source_rows, written_rows, "OK"))

    logging.info("=" * 80)
    logging.info("SUMMARY")
    total_source = sum(s for _, s, _, status in summary if status == "OK")
    total_written = sum(w for _, _, w, status in summary if status == "OK")
    for name, source_rows, written_rows, status in summary:
        logging.info("  %-55s xlsx=%8d  csv=%8d  [%s]", name, source_rows, written_rows, status)
    logging.info("Total: %d file(s) processed this run -- %d rows in xlsx, %d rows in csv",
                 len(summary), total_source, total_written)

    return 1 if had_errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
