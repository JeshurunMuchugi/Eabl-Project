"""
config.py - ONE place for every path, file name, version, count and colour the app uses.

Every other app file imports from here, so a name is never typed twice and cannot be misspelled in two places.
This file only DESCRIBES where things are. It reads nothing and writes nothing.

Data flow (the app only reads):  F1 notebook (Steps 7-9) -> CSV files in "F1 outputs" / "eabl parsed csv" -> app
"""
from pathlib import Path

# ---- Folders ---------------------------------------------------------------------------------------------
# The project folder is found from this file's own location (app/config.py -> one level up),
# so the app works whichever folder you start it from.
APP_DIR = Path(__file__).resolve().parent                 # .../Eabl project/app
PROJECT_DIR = APP_DIR.parent                              # .../Eabl project
DATA_DIR = PROJECT_DIR / "eabl parsed csv"                # the prepared data (read only)
OUT_DIR = PROJECT_DIR / "F1 outputs"                      # the notebook's saved results (read only)
WWW_DIR = APP_DIR / "www"                                 # stylesheet + ECharts files for the browser (Steps 16-17)

# ---- Versions (the cell 3 switch in the F1 notebook) -----------------------------------------------------
VERSIONS = {"dec_cleaned": "OFFICIAL", "with_spikes": "comparison only"}   # same labels as cells 9d / 9e
DEFAULT_VERSION = "dec_cleaned"
VERSION_LABELS = {"dec_cleaned": "Official (December cleaned)", "with_spikes": "With spikes (comparison only)"}

# ---- Files the app reads ---------------------------------------------------------------------------------
# (folder, file name). "{version}" is filled with "dec_cleaned" or "with_spikes".
FILES = {
    # the same for both versions
    "hierarchy":               (DATA_DIR, "S_product_with_total.csv"),                         # who is whose child
    "actuals":                 (DATA_DIR, "Y_product_with_total.csv"),                         # real weekly sales, weeks 1-66
    # one file per version - written by the F1 notebook
    "final":                   (OUT_DIR, "F1_final_forecast_{version}_weeks67-79.csv"),        # Step 9, cell 9d
    "routing":                 (OUT_DIR, "F1_final_routing_{version}_weeks1-66.csv"),          # Step 9, cell 9d
    "percentiles":             (OUT_DIR, "F1_final_range_percentiles_{version}.csv"),          # Step 9, cell 9d
    "backtest":                (OUT_DIR, "F1_backtest_{version}_weeks54-66.csv"),              # Step 7, save cell
    "step8":                   (OUT_DIR, "F1_step8_scored_{version}_weeks54-66.csv"),          # Step 8, save cell
    "practice_forecasts":      (OUT_DIR, "F1_practice_forecasts_{version}_cv1-cv2.csv"),       # Step 9, cell 9e
    "practice_scores":         (OUT_DIR, "F1_practice_scores_{version}_cv1-cv2.csv"),          # Step 9, cell 9e
    "practice_chosen":         (OUT_DIR, "F1_practice_chosen_{version}_cv1-cv2.csv"),          # Step 9, cell 9e
    "practice_winners":        (OUT_DIR, "F1_practice_winners_{version}.csv"),                 # Step 9, cell 9e
    "practice_reconciliation": (OUT_DIR, "F1_practice_reconciliation_{version}_cv2.csv"),      # Step 9, cell 9e
    "practice_coverage":       (OUT_DIR, "F1_practice_range_coverage_{version}_cv2.csv"),
    "history_forecast":        (OUT_DIR, "F1_history_and_forecast_{version}_weeks1-79.csv"),   # Step 9, cell 9f
# Step 9, cell 9e
}
SHARED_FILES = ["hierarchy", "actuals"]                   # every other key has one file per version


def file_path(key, version=None):
    """Full path of one input file. Shared files need no version; the others need "dec_cleaned" or "with_spikes"."""
    if key not in FILES:
        raise KeyError(f"unknown file key '{key}' - known keys: {sorted(FILES)}")
    folder, name = FILES[key]
    if key in SHARED_FILES:
        return folder / name
    if version not in VERSIONS:
        raise ValueError(f"file '{key}' needs a version: one of {list(VERSIONS)} (got {version!r})")
    return folder / name.format(version=version)


# ---- Expected sizes (the start-up checks compare against these) -----------------------------------------
N_SERIES = 283                  # Total 1 + Category2 3 + Sub_Category 8 + Brand 83 + Product 188
N_PRODUCTS = 188
HORIZON = 13                    # weeks per forecast window
FORECAST_ROWS = N_SERIES * HORIZON          # 3,679 rows in the final / backtest / Step 8 files
ROUTING_ROWS = N_PRODUCTS                   # 188
PERCENTILE_GROUPS = 7
LEVELS = ["Total", "Category2", "Sub_Category", "Brand", "Product"]      # top to bottom
ADDS_UP_TOLERANCE = 0.01                    # cases; parent minus sum of children must be within this

# ---- Calendar and test windows -------------------------------------------------------------------------
WEEK1_MONDAY = "2025-04-07"       
CLEANED_WEEKS = ["2025-12-01", "2025-12-08", "2025-12-15", "2025-12-22", "2025-12-29"]   # the only weeks cell 3 may clean
          # week 1 starts here; weeks run Monday-Saturday
WINDOWS = {                                 # (first week, last week, what the models learned from)
    "cv1":      (28, 40, "learned weeks 1-27"),
    "cv2":      (41, 53, "learned weeks 1-40"),
    "backtest": (54, 66, "learned weeks 1-53 (sealed 6 Apr 2026)"),
    "final":    (67, 79, "learned weeks 1-66"),
}
LOOKBACK_CHOICES = {"13": "13 weeks", "26": "26 weeks", "52": "52 weeks", "66": "All 66 weeks"}
DEFAULT_LOOKBACK = "26"

# ---- Colours (Okabe-Ito colour-blind-safe palette; always shown with words too) -------------------------
LANE_COLOURS = {
    "standard": "#0072B2",
    "intermittent": "#E69F00",
    "judgement (new launch)": "#CC79A7",
    "judgement (one-sale)": "#CC79A7",
    "zero": "#8C8C8C",
}
FLAG_COLOUR = "#D55E00"                     # review-flag outline
PATH_FILL = "#B7C9E2"                       # circles on the selected path in the tree
ACTUAL_COLOUR = "#1D2430"                   # real sales line
FORECAST_COLOUR = "#C0392B"                 # forecast line
BASE_COLOUR = "#7A8089"                     # base forecast (before reconciliation), dashed

# ---- Text ------------------------------------------------------------------------------------------------
APP_TITLE = "EABL Product Forecaster"
HISTORY_LABELS = {                          # legend name of the history line, per version (it shows what the models learned from)
    "dec_cleaned": "Sales the models learned from (December cleaned)",
    "with_spikes": "Sales the models learned from (as recorded)",
}

