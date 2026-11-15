"""
app.py - the EABL Product Forecaster (Shiny for Python).   STEPS 9-11: SKELETON + FINAL FORECAST TAB.

What this step builds:
  - the top bar with the app title, three pages (Forecast / Model evidence / Product explorer) and a version badge;
  - the left panel: what the app does, the series picker (type to search), look-back, and the version switch;
  - the Forecast page: a title strip for the selected series, a space for the hierarchy tree, and the tabs
    (final forecast, test cv1, test cv2, backtest, flags, Step 10) - their contents come in Steps 11-16;
  - if a data check fails at start-up, ONE card with the message instead of the app (nothing wrong is drawn).
Step 11 adds the Final forecast tab: real sales + forecast + 80% / 95% ranges + base (charts.py), info pills,
  the children table ("sum of children = parent"), and two download buttons in the left panel.

How it thinks: one shared value, "selected", holds the series on screen. The picker sets it (later the tree and
the explorer table will set it too), and every part of the page reads it - so they can never disagree.

Run from the project folder, in the eabl-app environment:   shiny run --reload app/app.py
Then open http://127.0.0.1:8000 in your browser. Stop with Ctrl+C in the terminal.
"""
from shiny import App, reactive, render, ui
from shinywidgets import output_widget, render_plotly
import pandas as pd                                            

import charts
import config
import data_loader

# ---- Read and check every file once, when the app starts ------------------------------------------------
try:
    DATA = data_loader.load_all()
    LOAD_ERROR = None
except data_loader.DataCheckError as error:
    DATA, LOAD_ERROR = None, str(error)


# ---- Names shown in the series picker ---------------------------------------------------------------------
def series_label(series_id, sku_names):
    """'Guinness Smooth Can [500ml x 24] (762724)' for a product; 'Guinness Smooth' for a brand; 'Total' for Total."""
    short_name = series_id.rsplit("/", 1)[-1].strip()
    if series_id in sku_names:
        return f"{sku_names[series_id]} ({short_name})"
    return short_name


def series_choices():
    """The 283 series grouped by level (Total, Category2, ...), for the picker."""
    hierarchy = DATA["hierarchy"]
    sku_names = DATA["versions"][config.DEFAULT_VERSION].routing.set_index("unique_id")["SKU"].to_dict()
    return {level: {series_id: series_label(series_id, sku_names)
                    for series_id in hierarchy.ids if hierarchy.level[series_id] == level}
            for level in config.LEVELS}

def family_line(series_id):
    """Where a series sits in the hierarchy, top to bottom, e.g. for a product:
    'Category: Beer  ›  Sub-category: Mainstream  ›  Brand: Guinness Smooth'.  Empty for Total."""
    hierarchy, names = DATA["hierarchy"], {"Category2": "Category", "Sub_Category": "Sub-category", "Brand": "Brand"}
    ancestors, current = [], hierarchy.parent.get(series_id)
    while current and current != "Total":                        # walk up: brand -> sub-category -> category
        ancestors.insert(0, current)
        current = hierarchy.parent.get(current)
    return "  ›  ".join(f"{names[hierarchy.level[a]]}: {a.rsplit('/', 1)[-1].strip()}" for a in ancestors)



def window_title(key, name):
    """'Test cv1 (weeks 28-40)' from config.WINDOWS."""
    first, last, _ = config.WINDOWS[key]
    return f"{name} (weeks {first}-{last})"


def file_safe(text):
    """'Beer/Premium/Guinness' -> 'Beer_Premium_Guinness' (for download file names)."""
    return "".join(ch if ch.isalnum() else "_" for ch in text).strip("_")


def pill(text, tone="light"):
    return ui.span(text, class_=f"badge rounded-pill text-bg-{tone} border me-1 mb-1 fw-normal fs-6")


def coming_soon(step, what):
    return ui.div(ui.p(ui.strong(f"Coming in Step {step}. "), what), class_="text-muted p-3")


# ---- The page layout ------------------------------------------------------------------------------------
def build_ui():
    sidebar = ui.sidebar(
        ui.h5("What it does"),
        ui.p("Shows the checked forecast for weeks 67-79 at any level of the product hierarchy, "
             "and how the models did against real sales in the tests (cv1, cv2, weeks 54-66)."),
        ui.hr(),
        ui.h5("How it works"),
        ui.input_selectize("series", "Select a series (type to search)", choices=series_choices(), selected="Total"),
        ui.input_radio_buttons("lookback", "Look-back (weeks of history)", choices=config.LOOKBACK_CHOICES,
                               selected=config.DEFAULT_LOOKBACK),
        ui.input_radio_buttons("version", "Version", choices=config.VERSION_LABELS, selected=config.DEFAULT_VERSION),
        ui.hr(),
        ui.h6("Download (final forecast, weeks 67-79)"),
        ui.download_button("download_series", "This series (CSV)", class_="btn-sm w-100 mb-2"),
        ui.download_button("download_children", "Its children (CSV)", class_="btn-sm w-100"),
        ui.hr(),
        ui.p("Reads the files saved by the F1 notebook (Steps 7-9). It never changes them.", class_="text-muted small"),
        width=320,
    )
    forecast_page = ui.nav_panel(
        "Forecast",
        ui.output_ui("title_strip"),
        ui.card(ui.card_header("Product hierarchy"),
                coming_soon(14, "A clickable tree: Total -> Beer / RTD / Spirits -> sub-category -> brand -> product.")),
        ui.navset_card_underline(
            ui.nav_panel(window_title("final", "Final forecast"),
                         ui.output_ui("final_pills"),
                         output_widget("forecast_chart"),
                        ui.output_ui("history_note"),

                         ui.p("Ranges are per week: each week has its own 80% / 95% range. Do not add the weekly ranges "
                              "together to get a 13-week range - that would be far too wide.", class_="text-muted small"),
                         ui.h6("Its children: do they add up to this series?", class_="mt-3"),
                         ui.output_ui("children_note"),
                         ui.output_data_frame("children_grid"),
                         value="final"),
                        ui.nav_panel(window_title("cv1", "Test cv1"),
                         ui.output_ui("cv1_summary"), output_widget("cv1_chart"),
                         ui.h6("Every candidate model in this round (lower MASE = better)", class_="mt-3"),
                         ui.output_data_frame("cv1_scores"), value="cv1"),
            ui.nav_panel(window_title("cv2", "Test cv2"),
                         ui.output_ui("cv2_summary"), output_widget("cv2_chart"),
                         ui.h6("Every candidate model in this round (lower MASE = better)", class_="mt-3"),
                         ui.output_data_frame("cv2_scores"), value="cv2"),
            ui.nav_panel(window_title("backtest", "Backtest"),
                         ui.output_ui("backtest_summary"), output_widget("backtest_chart"),
                         ui.p("The backtest forecast was made on 6 Apr 2026 from weeks 1-53 and sealed; weeks 54-66 were "
                              "opened once, in Step 8.", class_="text-muted small"), value="backtest"),

            ui.nav_panel("Flags", coming_soon(15, "Review notes for this series and its children."), value="flags"),
            ui.nav_panel("Step 10", coming_soon("10 (later)", "EABL's real sales for weeks 67-79."), value="step10"),
            id="tabs", selected="final",
        ),
    )
    return ui.page_navbar(
        forecast_page,
        ui.nav_panel("Model evidence", coming_soon(13, "Winners, accuracy per window, why MinT, do the ranges work.")),
        ui.nav_panel("Product explorer", coming_soon(15, "All 188 products with their labels, lane and method.")),
        ui.nav_spacer(),
        ui.nav_control(ui.output_ui("badge")),
        title=config.APP_TITLE, id="page", sidebar=sidebar, window_title=config.APP_TITLE,
    )


def build_error_ui():
    return ui.page_fluid(
        ui.h2(config.APP_TITLE, class_="mt-4"),
        ui.card(
            ui.card_header("The app did not start: a data check failed"),
            ui.pre(LOAD_ERROR),
            ui.p("Nothing was drawn, so no wrong numbers are shown. Fix the cause (usually: re-run the notebook cell "
                 "named above), then stop the app (Ctrl+C) and start it again. To see every check: "
                 "python -m pytest app/tests -v"),
        ),
    )


# ---- How the page behaves ---------------------------------------------------------------------------------
def server(input, output, session):
    selected = reactive.value("Total")                     # the ONE selected series, shared by every part of the page

    @reactive.effect
    @reactive.event(input.series)
    def _from_picker():
        if input.series():
            selected.set(input.series())

    @reactive.calc
    def version_data():                                   # every view reads the chosen version through this
        return DATA["versions"][input.version()]

    @output(suspend_when_hidden=False)                    # fill it even when the top bar is folded on a small screen
    @render.ui
    def badge():
        version = input.version()
        role = config.VERSIONS[version]
        colour = "bg-success" if version == config.DEFAULT_VERSION else "bg-warning text-dark"
        return ui.span(f"{role.upper()} · {version}", class_=f"badge {colour} fs-6")

    @reactive.calc
    def final_rows():                                     # the selected series' 13 saved forecast weeks
        return charts.rows_for(version_data().final, selected())

    @reactive.calc
    def sku_names():
        return version_data().routing.set_index("unique_id")["SKU"].to_dict()

    @render.ui
    def title_strip():
        series_id = selected()
        level = DATA["hierarchy"].level[series_id]
        role = config.VERSIONS[input.version()]
        family = family_line(series_id)                       # e.g. "Category: Beer  ›  Sub-category: Mainstream  ›  Brand: ..."
        return ui.div(ui.div(f"{series_label(series_id, sku_names())}  ·  {level}  ·  {role}", class_="fw-semibold"),
                      ui.div(family, class_="small opacity-75") if family else None,
                      class_="bg-dark text-white text-center rounded p-2 mb-3")

    # ---- Step 11: the Final forecast tab ----
    @render.ui
    def final_pills():
        rows = final_rows()
        lane = rows["lane"].iloc[0]
        flags = sorted({part.strip() for text in rows["flag list"].dropna() for part in str(text).split(";") if part.strip()})
        items = [pill(f"Level: {DATA['hierarchy'].level[selected()]}"), pill(f"Method: {rows['method'].iloc[0]}"),
                 pill(f"13-week forecast: {rows['forecast'].sum():,.1f} cases")]
        if isinstance(lane, str):
            items.append(pill(f"Lane: {lane}"))
        if rows["lo80"].isna().all():
            items.append(pill("No range: judgement / stopped / too flat - set by a planner", "warning"))
        items += [pill(f"⚑ {flag}", "warning") for flag in flags]
        return ui.div(*items, class_="mb-2")

    @reactive.calc
    def learned_history():                                # weeks 1-66 this version's models learned from (cell 9f)
        hf = version_data().history_forecast
        hist = hf[hf["part"] == data_loader.HISTORY_PART]
        return charts.rows_for(hist, selected()).rename(columns={"value": "y"})

    @render_plotly
    def forecast_chart():
        return charts.forecast_figure(learned_history(), final_rows(), input.lookback(),
                                      history_label=config.HISTORY_LABELS[input.version()])

    @render.ui
    def history_note():
        if input.version() != "dec_cleaned":
            return None
        if not learned_history()["changed by cleaning"].astype(bool).any():
            return None                                   # this series had nothing cleaned in December
        return ui.p("December 2025 is shown cleaned - what the official models learned from. "
                    "The recorded sales, with the spike, are in the 'With spikes' view.", class_="text-muted small mb-0")

    @render.ui
    def children_note():
        if not DATA["hierarchy"].children.get(selected()):
            return ui.p("This is a product (bottom level): it has no children.", class_="text-muted")
        return None

    @render.data_frame
    def children_grid():
        table = charts.children_table(version_data().final, DATA["hierarchy"], selected(), sku_names())
        return None if table is None else render.DataGrid(table, width="100%")

    # ---- Step 12: the evidence tabs ----
    def practice(set_name):                               # the forecast used + real sales, one practice round
        rows = version_data().practice_chosen
        return rows[(rows["unique_id"] == selected()) & (rows["set"] == set_name)].sort_values("ds")

    def practice_scores(set_name):
        rows = version_data().practice_scores
        return rows[(rows["unique_id"] == selected()) & (rows["set"] == set_name)]

    def winner_of_series():
        w = version_data().practice_winners
        w = w[w["unique_id"] == selected()]
        return None if w.empty else w["winner"].iloc[0]

    def no_test_message(set_name):
        first, last, learned = config.WINDOWS[set_name]
        return ui.p(f"No {set_name} test for this series: in this round the models {learned}, and this series was "
                    f"stopped, not yet on sale long enough, or set by judgement - so the notebook made no practice "
                    f"forecast for weeks {first}-{last}.", class_="text-muted")

    def practice_summary(set_name):
        rows = practice(set_name)
        if rows.empty:
            return no_test_message(set_name)
        s, scores = charts.window_summary(rows), practice_scores(set_name)
        naive = scores.loc[scores["model"] == "Naive", "MASE"]
        items = [pill(config.WINDOWS[set_name][2].capitalize()), pill(f"Forecast used: {rows['rule'].iloc[0]}")]
        if s["MASE"] is not None:
            items.append(pill(f"MASE {s['MASE']:.2f}" + (f"  (Naive {naive.iloc[0]:.2f})" if len(naive) else ""),
                              "success" if len(naive) and s["MASE"] < naive.iloc[0] else "light"))
        if s["bias"] is not None:
            items.append(pill(f"Bias {s['bias']:.2f} (1.00 = right total)"))
        for pct in ("80%", "95%"):
            if s[f"inside {pct}"] is not None:
                items.append(pill(f"Inside {pct} range: {s[f'inside {pct}']:.0%} of weeks"))
        if winner_of_series():
            items.append(pill(f"Winner over both rounds: {winner_of_series()}"))
        return ui.div(*items, class_="mb-2")

    def practice_chart(set_name, with_ranges):
        rows = practice(set_name)
        if rows.empty:
            return None
        cands = version_data().practice_forecasts
        cands = cands[(cands["unique_id"] == selected()) & (cands["set"] == set_name)]
        naive = cands[cands["model"] == "Naive"].drop_duplicates("ds").rename(columns={"forecast": "value"})
        others = cands[~cands["model"].isin(["Naive", "Zero"])]
        return charts.test_window_figure(rows.rename(columns={"y": "value"}), rows.rename(columns={"chosen": "value"}),
                                         f"Forecast used ({rows['rule'].iloc[0]})",
                                         ranges=rows if with_ranges else None, candidates=others, naive=naive)

    @render.ui
    def cv1_summary():
        return practice_summary("cv1")

    @render_plotly
    def cv1_chart():
        return practice_chart("cv1", with_ranges=False)

    @render.data_frame
    def cv1_scores():
        table = charts.candidate_scores_table(practice_scores("cv1"), winner_of_series())
        return None if table is None else render.DataGrid(table, width="100%")

    @render.ui
    def cv2_summary():
        return practice_summary("cv2")

    @render_plotly
    def cv2_chart():
        return practice_chart("cv2", with_ranges=True)                 # cv2 ranges were built from cv1's errors

    @render.data_frame
    def cv2_scores():
        table = charts.candidate_scores_table(practice_scores("cv2"), winner_of_series())
        return None if table is None else render.DataGrid(table, width="100%")

    def backtest_rows():
        rows = version_data().step8
        return rows[rows["unique_id"] == selected()].sort_values("ds")

    @render.ui
    def backtest_summary():
        rows, all_rows = backtest_rows(), version_data().step8
        scale = rows["scale (real weeks 1-53)"].iloc[0]
        mase = rows["series MASE (weeks 54-66)"].iloc[0]
        naive_mase = (rows["actual"] - rows["Naive"]).abs().mean() / scale if scale > 0 else None
        level = DATA["hierarchy"].level[selected()]
        level_mase = all_rows[all_rows["level"] == level].drop_duplicates("unique_id")["series MASE (weeks 54-66)"].mean()
        items = [pill("Learned weeks 1-53 (sealed 6 Apr 2026)"), pill(f"Method: {rows['base method'].iloc[0]}")]
        if pd.notna(mase):
            items.append(pill(f"MASE {mase:.2f}" + (f"  (Naive {naive_mase:.2f})" if naive_mase is not None else ""),
                              "success" if naive_mase is not None and mase < naive_mase else "light"))
            items.append(pill(f"{level} average MASE {level_mase:.2f}"))
        if rows["actual"].sum() > 0:
            items.append(pill(f"Bias {rows['forecast'].sum() / rows['actual'].sum():.2f} (1.00 = right total)"))
        for pct in ("80%", "95%"):
            inside = rows[f"inside {pct}"].dropna()
            if len(inside) and rows["lo80"].notna().any():
                items.append(pill(f"Inside {pct} range: {inside.astype(bool).mean():.0%} of weeks"))
        return ui.div(*items, class_="mb-2")

    @render_plotly
    def backtest_chart():
        rows = backtest_rows()
        return charts.test_window_figure(rows.rename(columns={"actual": "value"}), rows.rename(columns={"forecast": "value"}),
                                         "Backtest forecast (sealed)", ranges=rows,
                                         naive=rows[["ds", "week", "Naive"]].rename(columns={"Naive": "value"}))

    @render.download_button(filename=lambda: f"{file_safe(selected())}_{input.version()}_weeks67-79.csv")
    def download_series():
        yield charts.download_rows(version_data().final, [selected()]).to_csv(index=False)

    @render.download_button(filename=lambda: f"{file_safe(selected())}_children_{input.version()}_weeks67-79.csv")
    def download_children():
        kids = DATA["hierarchy"].children.get(selected()) or [selected()]       # a product: its own rows
        yield charts.download_rows(version_data().final, kids).to_csv(index=False)


def server_when_data_failed(input, output, session):
    pass                                                   # nothing to do: the page only shows the error card


app = App(build_ui(), server) if LOAD_ERROR is None else App(build_error_ui(), server_when_data_failed)
