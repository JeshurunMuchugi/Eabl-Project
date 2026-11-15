"""
data_loader.py - READ every file the app needs ONCE, CHECK it, and hand it to the app.

What it does:
  1. Opens each CSV listed in config.py (read only - this file has no write commands at all).
  2. Checks it: file exists, expected columns, row counts, version label, series known in the hierarchy,
     weeks in the right window, and every level adds up to its children.
  3. If any check fails it stops with a DataCheckError that says what is wrong and what to re-run.
     The app shows that message instead of drawing wrong charts ("stop rather than mislead").
  4. Keeps the result in memory (load_all() runs once; later calls reuse it), so the app opens fast.

It makes NO forecasts and changes NO numbers: everything shown in the app is exactly what the notebook saved.
"""
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
import pandas as pd

import config


class DataCheckError(Exception):
    """A file is missing or does not look like what the notebook saved. The message says what to do."""


# ---- Small helpers ---------------------------------------------------------------------------------------
def read_csv_checked(path, must_have, parse_dates=None):
    """Open one CSV (read only). Stop if the file or one of the needed columns is missing."""
    if not path.exists():
        raise DataCheckError(f"File not found: {path}\n-> Re-run the notebook cell that saves it, then restart the app.")
    df = pd.read_csv(path, parse_dates=parse_dates)
    missing = [col for col in must_have if col not in df.columns]
    if missing:
        raise DataCheckError(f"{path.name} is missing the column(s) {missing}.\n-> Re-run the notebook cell that saves it.")
    return df


def week_number(dates):
    """Monday date -> week number (week 1 = 7 Apr 2025)."""
    return ((dates - pd.Timestamp(config.WEEK1_MONDAY)).dt.days // 7 + 1).astype(int)


# ---- The hierarchy (who is whose child) -------------------------------------------------------------------
@dataclass(frozen=True)
class Hierarchy:
    S: pd.DataFrame          # 283 x 188 of 0/1: row = series, column = product; 1 = the product is inside the series
    ids: list                # the 283 series, in S order (Total first)
    products: list           # the 188 products (bottom level)
    level: dict              # series -> "Total" / "Category2" / "Sub_Category" / "Brand" / "Product"
    parent: dict             # series -> its parent (Total has none)
    children: dict           # series -> list of its direct children (products have none)


def level_of(series_id):
    """Level from the name: "Total"; "Beer" (no "/") = Category2; 1 "/" = Sub_Category; 2 = Brand; 3 = Product."""
    if series_id == "Total":
        return "Total"
    return config.LEVELS[series_id.count("/") + 1]


def load_hierarchy():
    path = config.file_path("hierarchy")
    raw = read_csv_checked(path, ["unique_id"])
    S = raw.drop(columns=[col for col in raw.columns if col.startswith("Unnamed")]).set_index("unique_id")
    if S.shape != (config.N_SERIES, config.N_PRODUCTS):
        raise DataCheckError(f"{path.name} has shape {S.shape}, expected ({config.N_SERIES}, {config.N_PRODUCTS}).")
    if S.index.duplicated().any() or not np.isin(S.values, [0, 1]).all():
        raise DataCheckError(f"{path.name}: repeated series or values other than 0/1.")
    products = list(S.columns)
    if (S.loc[products].values != np.eye(len(products))).any():
        raise DataCheckError(f"{path.name}: the product rows are not one product each.")
    ids = list(S.index)
    level = {series_id: level_of(series_id) for series_id in ids}
    parent = {series_id: ("Total" if "/" not in series_id else series_id.rsplit("/", 1)[0])
              for series_id in ids if series_id != "Total"}
    children = {series_id: [] for series_id in ids}
    for child, mother in parent.items():
        if mother not in children:
            raise DataCheckError(f"{path.name}: '{child}' has no parent series '{mother}'.")
        children[mother].append(child)
    for mother, kids in children.items():                               # S row of a parent = sum of its children's rows
        if kids and (S.loc[kids].sum().values != S.loc[mother].values).any():
            raise DataCheckError(f"{path.name}: the row of '{mother}' is not the sum of its children.")
    return Hierarchy(S=S.astype(int), ids=ids, products=products, level=level, parent=parent, children=children)


# ---- Real weekly sales ------------------------------------------------------------------------------------
def load_actuals(hierarchy):
    path = config.file_path("actuals")
    df = read_csv_checked(path, ["unique_id", "ds", "y"], parse_dates=["ds"])
    df["week"] = week_number(df["ds"])
    unknown = sorted(set(df["unique_id"]) - set(hierarchy.ids))
    if unknown:
        raise DataCheckError(f"{path.name}: {len(unknown)} series not in the hierarchy, e.g. {unknown[:3]}.")
    if df["week"].min() != 1 or df["week"].max() != config.WINDOWS["backtest"][1]:
        raise DataCheckError(f"{path.name}: weeks run {df['week'].min()}-{df['week'].max()}, expected 1-66.")
    if df.duplicated(["unique_id", "ds"]).any():
        raise DataCheckError(f"{path.name}: a series has the same week twice.")
    return df


# ---- One version (dec_cleaned or with_spikes) -------------------------------------------------------------
@dataclass(frozen=True)
class VersionData:
    version: str
    final: pd.DataFrame                    # final forecast, weeks 67-79 (cell 9d)
    routing: pd.DataFrame                  # 188 products: labels, lane, method (cell 9d)
    percentiles: pd.DataFrame              # the range recipe, 7 groups (cell 9d)
    backtest: pd.DataFrame                 # sealed forecast for weeks 54-66 (Step 7)
    step8: pd.DataFrame                    # weeks 54-66 scored against real sales (Step 8)
    practice_forecasts: pd.DataFrame       # every candidate model, cv1 + cv2 (cell 9e)
    practice_scores: pd.DataFrame          # every candidate's score, cv1 + cv2 (cell 9e)
    practice_chosen: pd.DataFrame          # chosen forecast + cv2 ranges (cell 9e)
    practice_winners: pd.DataFrame         # winner per series (cell 9e)
    practice_reconciliation: pd.DataFrame  # why MinT (cell 9e)
    practice_coverage: pd.DataFrame    
    history_forecast: pd.DataFrame   
    challengers_bt_normal: pd.DataFrame    # challengers, NOT official (cell 9g): backtest 54-66, 210 series switched
    challengers_fc_normal: pd.DataFrame    # ... frozen forecast 67-79, 210 series switched
    challengers_bt_option2: pd.DataFrame   # ... backtest 54-66, 195 switched (sparse brands keep their model)
    challengers_fc_option2: pd.DataFrame   # ... frozen forecast 67-79, 195 switched
      # weeks 1-66 the models learned from + weeks 67-79 forecast (cell 9f)
    # cv2 range coverage (cell 9e)


# columns each file must have (others may exist too)
NEEDED_COLUMNS = {
    "final": ["level", "unique_id", "ds", "week", "method", "base", "forecast", "lo80", "hi80", "lo95", "hi95", "flag list", "version"],
    "routing": ["unique_id", "SKU", "lane", "method", "version"],
    "percentiles": ["group", "errors used", "version"],
    "backtest": ["level", "unique_id", "ds", "week", "forecast", "lo80", "hi80", "lo95", "hi95", "version"],
    "step8": ["level", "unique_id", "ds", "week", "forecast", "actual", "Naive", "series MASE (weeks 54-66)", "version"],
    "practice_forecasts": ["set", "unique_id", "ds", "week", "y", "candidate_set", "model", "forecast", "version"],
    "practice_scores": ["set", "unique_id", "candidate_set", "model", "MASE", "version"],
    "practice_chosen": ["set", "unique_id", "ds", "week", "y", "chosen", "lo80", "hi80", "lo95", "hi95", "version"],
    "practice_winners": ["unique_id", "winner", "winner_avg_MASE", "Naive_avg_MASE", "version"],
    "practice_reconciliation": ["method", "chosen", "version"],
    "practice_coverage": ["group", "80% coverage", "95% coverage", "version"],
    "history_forecast": ["unique_id", "ds", "week", "part", "value", "recorded", "changed by cleaning", "version"],
        **{f"challengers_{part}_{rule}": ["level", "unique_id", "ds", "week", "model used", "official forecast"]
       + [f"{m} {col}" for m in config.CHALLENGER_MODELS for col in ("base", "forecast")]
       + (["real sales"] if part == "bt" else []) + ["version", "role"]
       for part in ("bt", "fc") for rule in config.CHALLENGER_RULES},


}
WEEKLY_FILES = ["final", "backtest", "step8", "practice_forecasts", "practice_chosen", "history_forecast",
                "challengers_bt_normal", "challengers_fc_normal", "challengers_bt_option2", "challengers_fc_option2"]   # have a ds column

HISTORY_PART = "history (what the models learned from)"     # the "part" label cell 9f gives weeks 1-66


def check_version_column(df, key, version):
    found = sorted(df["version"].dropna().unique())
    if found != [version]:
        raise DataCheckError(f"{key} file for '{version}' contains version {found}.\n-> Re-run the notebook for this version.")


def check_in_hierarchy(df, key, hierarchy):
    unknown = sorted(set(df["unique_id"]) - set(hierarchy.ids))
    if unknown:
        raise DataCheckError(f"{key}: {len(unknown)} series not in the hierarchy, e.g. {unknown[:3]}.")


def check_forecast_table(df, key, first_week, last_week):
    """3,679 rows = 283 series x 13 weeks, each series once per week, weeks in the right window."""
    if len(df) != config.FORECAST_ROWS or df["unique_id"].nunique() != config.N_SERIES:
        raise DataCheckError(f"{key}: {len(df)} rows / {df['unique_id'].nunique()} series, "
                             f"expected {config.FORECAST_ROWS} / {config.N_SERIES}.")
    if df.duplicated(["unique_id", "ds"]).any():
        raise DataCheckError(f"{key}: a series has the same week twice.")
    if df["week"].min() != first_week or df["week"].max() != last_week:
        raise DataCheckError(f"{key}: weeks {df['week'].min()}-{df['week'].max()}, expected {first_week}-{last_week}.")


def adds_up_gap(df, value_col, hierarchy):
    """Largest |series - sum of its products| over all series and weeks (0 = every level adds up)."""
    wide = df.pivot(index="unique_id", columns="ds", values=value_col).reindex(hierarchy.ids)
    rebuilt = hierarchy.S.values @ wide.loc[hierarchy.products].values
    return float(np.nanmax(np.abs(rebuilt - wide.values)))


def check_adds_up(df, key, value_col, hierarchy):
    gap = adds_up_gap(df, value_col, hierarchy)
    if not gap <= config.ADDS_UP_TOLERANCE:
        raise DataCheckError(f"{key}: '{value_col}' does not add up - largest gap {gap:.4f} cases "
                             f"(allowed {config.ADDS_UP_TOLERANCE}).")


def check_history_forecast(hf, version, final, actuals, hierarchy):
    """Cell 9f's file: history = recorded sales except the cleaned December weeks (official only); forecast = 9d's file."""
    hist = hf[hf["part"] == HISTORY_PART]
    if len(hist) != len(actuals) or len(hf) - len(hist) != len(final):
        raise DataCheckError(f"history_forecast: {len(hist)} history + {len(hf) - len(hist)} forecast rows, expected "
                             f"{len(actuals)} + {len(final)}.\n-> Re-run notebook cell 9f for '{version}'.")
    rec = hist.merge(actuals[["unique_id", "ds", "y"]], on=["unique_id", "ds"], how="left", validate="one_to_one")
    if not np.allclose(rec["recorded"], rec["y"], equal_nan=False):
        raise DataCheckError("history_forecast: the 'recorded' column differs from the real-sales file.")
    changed = hist.loc[hist["changed by cleaning"].astype(bool), "ds"].dt.strftime("%Y-%m-%d")
    allowed = set(config.CLEANED_WEEKS) if version == "dec_cleaned" else set()
    if not set(changed) <= allowed:
        raise DataCheckError(f"history_forecast ({version}): values changed outside the allowed weeks: "
                             f"{sorted(set(changed) - allowed)[:5]}.")
    check_adds_up(hist, "history_forecast (history)", "value", hierarchy)
    fc = hf[hf["part"] != HISTORY_PART].merge(final[["unique_id", "ds", "forecast"]], on=["unique_id", "ds"],
                                             how="left", validate="one_to_one")
    if not np.allclose(fc["value"], fc["forecast"], atol=1e-6):
        raise DataCheckError("history_forecast: its forecast part differs from the final forecast file (cell 9d).")

def check_challengers(tables, hierarchy):
    """Cell 9g's files: 283 x 13 rows, labelled not official, every level adds up, and their OFFICIAL columns are exactly
    the official files - so the challenger tab can never show a different official number from the rest of the app."""
    for rule in config.CHALLENGER_RULES:
        for part, window, official_key in [("bt", "backtest", "backtest"), ("fc", "final", "final")]:
            key = f"challengers_{part}_{rule}"
            df = tables[key]
            check_forecast_table(df, key, *config.WINDOWS[window][:2])
            if set(df["role"]) != {"challenger - not official"}:
                raise DataCheckError(f"{key}: role must be 'challenger - not official', found {sorted(set(df['role']))}.")
            for model in config.CHALLENGER_MODELS:
                check_adds_up(df, key, f"{model} forecast", hierarchy)
            same = df.merge(tables[official_key][["unique_id", "ds", "forecast"]], on=["unique_id", "ds"], validate="one_to_one")
            if not np.allclose(same["official forecast"], same["forecast"], atol=1e-6):
                raise DataCheckError(f"{key}: its 'official forecast' differs from the {official_key} file.\n"
                                     f"-> Re-run notebook cell 9g (or 9g option 2) for this version.")
        real = tables[f"challengers_bt_{rule}"].merge(tables["step8"][["unique_id", "ds", "actual"]], on=["unique_id", "ds"])
        if not np.allclose(real["real sales"], real["actual"], atol=1e-6):
            raise DataCheckError(f"challengers_bt_{rule}: its 'real sales' differ from the Step 8 file.")



def load_version(version, hierarchy, actuals):
    tables = {}
    for key, columns in NEEDED_COLUMNS.items():
        df = read_csv_checked(config.file_path(key, version), columns,
                              parse_dates=["ds"] if key in WEEKLY_FILES else None)
        check_version_column(df, key, version)
        if "unique_id" in df.columns:
            check_in_hierarchy(df, key, hierarchy)
        tables[key] = df

    check_forecast_table(tables["final"], "final", *config.WINDOWS["final"][:2])
    check_forecast_table(tables["backtest"], "backtest", *config.WINDOWS["backtest"][:2])
    check_forecast_table(tables["step8"], "step8", *config.WINDOWS["backtest"][:2])
    for key in ["final", "backtest", "step8"]:
        check_adds_up(tables[key], key, "forecast", hierarchy)

    if len(tables["routing"]) != config.ROUTING_ROWS or tables["routing"]["unique_id"].nunique() != config.ROUTING_ROWS:
        raise DataCheckError(f"routing: {len(tables['routing'])} rows, expected {config.ROUTING_ROWS} products once each.")
    unknown_lanes = set(tables["routing"]["lane"]) - set(config.LANE_COLOURS)
    if unknown_lanes:
        raise DataCheckError(f"routing: lane(s) {sorted(unknown_lanes)} have no colour in config.LANE_COLOURS.")
    if len(tables["percentiles"]) != config.PERCENTILE_GROUPS:
        raise DataCheckError(f"percentiles: {len(tables['percentiles'])} groups, expected {config.PERCENTILE_GROUPS}.")
    practice_weeks = tables["practice_forecasts"]["week"]
    if practice_weeks.min() != config.WINDOWS["cv1"][0] or practice_weeks.max() != config.WINDOWS["cv2"][1]:
        raise DataCheckError(f"practice_forecasts: weeks {practice_weeks.min()}-{practice_weeks.max()}, expected "
                             f"{config.WINDOWS['cv1'][0]}-{config.WINDOWS['cv2'][1]}.")
    if tables["practice_reconciliation"]["chosen"].sum() != 1:
        raise DataCheckError("practice_reconciliation: exactly one method must be marked as chosen.")
    check_history_forecast(tables["history_forecast"], version, tables["final"], actuals, hierarchy)
    check_challengers(tables, hierarchy)

    return VersionData(version=version, **tables)


# ---- Everything, once -------------------------------------------------------------------------------------
@lru_cache(maxsize=1)
def load_all():
    """Read and check every file for both versions. Runs once; later calls reuse the result.
    Returns {"hierarchy": Hierarchy, "actuals": DataFrame, "versions": {"dec_cleaned": VersionData, "with_spikes": ...}}."""
    hierarchy = load_hierarchy()
    actuals = load_actuals(hierarchy)
    versions = {version: load_version(version, hierarchy, actuals) for version in config.VERSIONS}
    return {"hierarchy": hierarchy, "actuals": actuals, "versions": versions}


