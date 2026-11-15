"""
test_data_loader.py - automatic checks that the app reads EXACTLY what the F1 notebook saved.

Run from the project folder (in the eabl-app environment):
    python -m pytest app/tests -v
Every line should end in PASSED. Run again after the notebook saves new files or after you change app code.

Nothing here writes a file: the "bad data" tests break COPIES in memory only.
"""
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))     # the app/ folder, so "import config" works
import config                                                    # noqa: E402
import data_loader as dl                                         # noqa: E402

# Numbers the notebook printed (cells 9d and 9e, 14 Nov 2026) - the app must show the same
NOTEBOOK_TOTAL_13WK = {"dec_cleaned": 193_933.6, "with_spikes": 195_370.3}     # 9d: "193,934" / "195,370"
NOTEBOOK_CV2_COVERAGE = {"dec_cleaned": (0.775, 0.931), "with_spikes": (0.764, 0.904)}   # 9e: 80% / 95% overall
PRACTICE_ROWS = {"practice_forecasts": 76_388, "practice_scores": 5_876, "practice_chosen": 6_305, "practice_winners": 217,
                 "practice_reconciliation": 6, "practice_coverage": 7}


@pytest.fixture(scope="module")
def data():
    return dl.load_all()


# ---- 1. Every file opens and passes the loader's own checks -------------------------------------------------
def test_files_load(data):
    assert set(data["versions"]) == set(config.VERSIONS)


def test_hierarchy_levels(data):
    h = data["hierarchy"]
    counts = {lv: list(h.level.values()).count(lv) for lv in config.LEVELS}
    assert counts == {"Total": 1, "Category2": 3, "Sub_Category": 8, "Brand": 83, "Product": 188}
    assert h.children["Total"] == ["Beer", "RTD", "Spirits"]


def test_actuals_weeks(data):
    assert data["actuals"]["week"].min() == 1 and data["actuals"]["week"].max() == 66


# ---- 2. Row counts --------------------------------------------------------------------------------------------
@pytest.mark.parametrize("version", list(config.VERSIONS))
def test_row_counts(data, version):
    vd = data["versions"][version]
    assert len(vd.final) == len(vd.backtest) == len(vd.step8) == config.FORECAST_ROWS
    assert len(vd.routing) == config.ROUTING_ROWS
    assert len(vd.percentiles) == config.PERCENTILE_GROUPS
    for key, rows in PRACTICE_ROWS.items():
        assert len(getattr(vd, key)) == rows, key


# ---- 3. No file carries the wrong version ------------------------------------------------------------------
@pytest.mark.parametrize("version", list(config.VERSIONS))
def test_version_columns(data, version):
    vd = data["versions"][version]
    for key in dl.NEEDED_COLUMNS:
        assert set(getattr(vd, key)["version"]) == {version}, key


# ---- 4. Every level adds up -------------------------------------------------------------------------------
@pytest.mark.parametrize("version", list(config.VERSIONS))
def test_adds_up(data, version):
    vd, h = data["versions"][version], data["hierarchy"]
    for key in ["final", "backtest", "step8"]:
        assert dl.adds_up_gap(getattr(vd, key), "forecast", h) <= config.ADDS_UP_TOLERANCE, key


# ---- 5. The app's numbers equal the numbers the notebook printed ----------------------------------------------
@pytest.mark.parametrize("version", list(config.VERSIONS))
def test_total_matches_notebook(data, version):
    vd = data["versions"][version]
    total = vd.final.loc[vd.final["level"] == "Total", "forecast"].sum()
    assert total == pytest.approx(NOTEBOOK_TOTAL_13WK[version], abs=0.1)
    for level in config.LEVELS:                                          # every level carries the same 13-week total
        assert vd.final.loc[vd.final["level"] == level, "forecast"].sum() == pytest.approx(total, abs=0.1), level


@pytest.mark.parametrize("version", list(config.VERSIONS))
def test_cv2_coverage_matches_notebook(data, version):
    chosen = data["versions"][version].practice_chosen
    with_range = chosen[chosen["lo80"].notna()]
    cov80, cov95 = with_range["inside 80%"].astype(bool).mean(), with_range["inside 95%"].astype(bool).mean()
    assert (round(cov80, 3), round(cov95, 3)) == NOTEBOOK_CV2_COVERAGE[version]


def test_mint_was_chosen(data):
    for vd in data["versions"].values():
        assert vd.practice_reconciliation.loc[vd.practice_reconciliation["chosen"], "method"].tolist() == ["MinT shrink"]


# ---- 6. The checks really stop bad data (copies in memory only) -------------------------------------------
def test_check_catches_bad_data(data):
    vd, h = data["versions"]["dec_cleaned"], data["hierarchy"]
    broken_sum = vd.final.copy()
    broken_sum.loc[broken_sum["unique_id"] == "Beer", "forecast"] += 5                # Beer no longer = its children
    with pytest.raises(dl.DataCheckError):
        dl.check_adds_up(broken_sum, "final", "forecast", h)
    with pytest.raises(dl.DataCheckError):
        dl.check_forecast_table(vd.final.iloc[1:], "final", 67, 79)                 # a row lost
    with pytest.raises(dl.DataCheckError):
        dl.check_version_column(vd.final.assign(version="with_spikes"), "final", "dec_cleaned")
    with pytest.raises(dl.DataCheckError):
        dl.check_in_hierarchy(vd.final.assign(unique_id="Ghost brand"), "final", h)
    with pytest.raises(dl.DataCheckError):
        dl.read_csv_checked(config.OUT_DIR / "no_such_file.csv", [])


# ---- 7. The app never writes a file -------------------------------------------------------------------------
def test_app_never_writes():
    # .to_csv(index=False) with no file name only makes text for a browser download - allowed; a file name is not
    write_commands = re.compile(r"\.to_(csv|excel|parquet)\((?!\s*(index\s*=|\)))|open\(.*['\"][wa]|os\.remove|unlink|rmtree")
    offenders = [f"{py.name}:{n}" for py in config.APP_DIR.glob("*.py")          # app code only (not this test file)
                 for n, line in enumerate(py.read_text().splitlines(), 1) if write_commands.search(line)]
    assert offenders == [], f"write commands found in app code: {offenders}"



# ---- 8. Each version's history = what its models learned from (cell 9f) ------------------------------------
NOTEBOOK_BEER_22_DEC = {"dec_cleaned": 10_356.9, "with_spikes": 15_014.8}          # 9f: "learned from" value
RECORDED_BEER_22_DEC = 15_014.8                                                    # the real-sales file


@pytest.mark.parametrize("version", list(config.VERSIONS))
def test_history_matches_what_models_learned(data, version):
    hf = data["versions"][version].history_forecast
    hist = hf[hf["part"] == dl.HISTORY_PART]
    assert len(hist) == len(data["actuals"])                                       # every recorded week is there
    beer = hist[(hist["unique_id"] == "Beer") & (hist["ds"] == "2025-12-22")].iloc[0]
    assert beer["value"] == pytest.approx(NOTEBOOK_BEER_22_DEC[version], abs=0.1)
    assert beer["recorded"] == pytest.approx(RECORDED_BEER_22_DEC, abs=0.1)
    changed = set(hist.loc[hist["changed by cleaning"].astype(bool), "ds"].dt.strftime("%Y-%m-%d"))
    if version == "dec_cleaned":
        assert changed and changed <= set(config.CLEANED_WEEKS)                    # only December was cleaned
    else:
        assert changed == set()                                                    # nothing cleaned


def test_check_catches_cleaning_outside_december(data):
    vd, h = data["versions"]["dec_cleaned"], data["hierarchy"]
    broken = vd.history_forecast.copy()
    rows = (broken["unique_id"] == "Total") & (broken["ds"] == "2025-06-02")         # a June week, never cleaned
    broken.loc[rows, "changed by cleaning"] = True
    with pytest.raises(dl.DataCheckError):
        dl.check_history_forecast(broken, "dec_cleaned", vd.final, data["actuals"], h)


# ---- 9. Model evidence page: its summaries agree with what the notebook found (Step 8 / cell 9e) ----------
import charts                                                                     # noqa: E402


def test_model_evidence_summaries(data):
    vd = data["versions"]["dec_cleaned"]
    acc = charts.accuracy_by_level(vd, config.LEVELS).set_index(["Test", "Level"])
    total_bt = acc.loc[(charts.TESTS["backtest"], "Total")]
    assert total_bt["Bias (1.00 = right total)"] == pytest.approx(1.059, abs=0.001)            # Step 8: +5.9% too high
    assert total_bt["Naive MASE (same series)"] < total_bt["MASE"]                              # Step 8: Naive won at Total
    cov = charts.coverage_table(vd, config.LEVELS)
    bt = vd.step8[vd.step8["lo80"].notna()]
    assert bt["inside 80%"].astype(bool).mean() == pytest.approx(0.836, abs=0.001)             # Step 8: 0.84 / 0.96
    assert bt["inside 95%"].astype(bool).mean() == pytest.approx(0.960, abs=0.001)
    assert len(cov) == len(vd.practice_coverage) + len(config.LEVELS)
    recon = charts.reconciliation_table(vd.practice_reconciliation)
    assert recon.loc[recon["chosen"] == "✓ chosen", "Method"].tolist() == ["MinT shrink"]
    assert charts.winners_table(vd.practice_winners, config.LEVELS)["series"].sum() == len(vd.practice_winners)


# ---- 10. Hierarchy tree (Step 14): every series once, boxes add up, true numbers in the hover --------------
import tree                                                                       # noqa: E402


@pytest.mark.parametrize("version", list(config.VERSIONS))
def test_tree_data(data, version):
    h, vd = data["hierarchy"], data["versions"][version]
    t = tree.icicle_data(h, vd.final, vd.routing)
    assert t["ids"] == h.ids                                                             # 283 boxes, in hierarchy order
    product_labels = [label for label, sid in zip(t["labels"], t["ids"]) if h.level[sid] == "Product"]
    assert len(set(product_labels)) == config.N_PRODUCTS                                 # "SKU (code)": no two products alike
    size = dict(zip(t["ids"], t["values"]))
    for series_id, kids in h.children.items():                                           # a parent box = its children's boxes
        if kids:
            assert size[series_id] == pytest.approx(sum(size[k] for k in kids))
    truth = vd.final.groupby("unique_id")["forecast"].sum()
    assert all(size[p] >= tree.MIN_CASES and size[p] >= truth[p] for p in h.products)    # never smaller than the forecast
    assert size["Total"] <= truth["Total"] * 1.02                                        # minimum boxes add under 2%
    assert f"{truth['Total']:,.1f} cases" in t["hover"][0]                               # hover shows the TRUE forecast
    assert set(t["colours"]) <= set(config.LANE_COLOURS.values()) | {config.UPPER_COLOUR}


# ---- 11. Circle tree (Step 16): only the path is open, sizes follow the forecast, flags outlined ---------------
def test_circle_tree(data):
    import json
    h, vd = data["hierarchy"], data["versions"]["dec_cleaned"]
    t = tree.echarts_tree(h, vd.final, vd.routing, "Beer/Premium/Guinness")
    json.dumps(t)                                                                        # it can be sent to the browser

    def walk(node):
        return [node] + [n for kid in node.get("children", []) for n in walk(kid)]
    nodes = {n["uid"]: n for n in walk(t["data"])}
    assert len(nodes) == config.N_SERIES                                                 # all 283 circles are there
    opened = sorted(uid for uid, n in nodes.items() if n.get("collapsed") is False)
    assert opened == ["Beer", "Beer/Premium", "Beer/Premium/Guinness", "Total"]          # only the path is open
    assert nodes["Beer/Premium/Guinness"]["itemStyle"]["color"] == config.PATH_FILL
    truth = vd.final.groupby("unique_id")["forecast"].sum()
    assert nodes["Total"]["symbolSize"] == tree.CIRCLE_MAX
    assert nodes["Beer"]["symbolSize"] == pytest.approx(tree.CIRCLE_MAX * (truth["Beer"] / truth["Total"]) ** 0.5, abs=0.1)
    assert min(n["symbolSize"] for n in nodes.values()) >= 8                             # stopped products still visible (8 px)
    flagged = vd.final.drop_duplicates("unique_id")["flag list"].fillna("").str.strip().ne("").sum()
    assert sum(n["itemStyle"]["borderColor"] == config.FLAG_COLOUR for n in nodes.values()) == flagged
    assert tree.echarts_tree(h, vd.final, vd.routing, "Spirits/Premium")["height"] > t["height"]   # 25 brands: taller


# ---- 12. Flags tab and Product explorer (Step 15): every flag and every product, nothing lost or invented -----
def test_flags_and_explorer(data):
    h, vd = data["hierarchy"], data["versions"]["dec_cleaned"]
    sku = vd.routing.set_index("unique_id")["SKU"].to_dict()
    first = vd.final.drop_duplicates("unique_id").set_index("unique_id")
    brand = "Spirits/Mainstream/Chrome Brandy"
    raw = [first.at[s, "flag list"] for s in [brand] + h.children[brand]]
    expected = sum(text.count(";") + 1 for text in raw if isinstance(text, str))       # counted from the raw text
    flags = charts.flags_table(vd.final, h, brand, sku)
    assert len(flags) == expected and expected > 0                                       # one row per flag, none lost
    assert charts.flags_table(vd.final, h, "Beer/ANADS/Alvaro/672279", sku) is None       # no flags -> no table
    ex = charts.explorer_table(vd.final, vd.routing, h)
    assert len(ex) == config.N_PRODUCTS and ex["id"].tolist() == h.products              # all 188 products, in order
    assert ex["Product"].is_unique                                                       # "SKU (code)": no two alike
    assert ex["Lane"].value_counts().to_dict() == vd.routing["lane"].value_counts().to_dict()
    total = vd.final.groupby("unique_id")["forecast"].sum()["Total"]
    assert ex["13-week forecast (cases)"].sum() == pytest.approx(total, abs=1)              # products add up to the Total
