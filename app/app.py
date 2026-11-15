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
import plotly.graph_objects as go

import charts
import config
import data_loader
import tree

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

def tree_legend():
    """The lane colours in words, under the tree (colour is never the only clue)."""
    swatches = [("upper levels", config.UPPER_COLOUR)] + [
        (config.LANE_WORDS[lane].split(" (")[0], colour) for lane, colour in config.LANE_COLOURS.items()
        if lane != "judgement (one-sale)"]                                       # same colour as new launch
    return ui.div(*[ui.span(ui.span(style=f"display:inline-block;width:12px;height:12px;background:{colour};"
                                           "border:1px solid #999;margin-right:4px;vertical-align:-1px"),
                            name.replace("judgement: new launch", "judgement"), class_="me-3 small")
                    for name, colour in swatches], class_="mt-1")


def circle_legend():
    """What the circle tree's colours and outlines mean, in words (Step 16)."""
    def dot(fill, border="#1D2430", width=1):
        return ui.span(style=f"display:inline-block;width:12px;height:12px;border-radius:50%;background:{fill};"
                             f"border:{width}px solid {border};margin-right:4px;vertical-align:-1px")
    items = [(dot(colour), config.LANE_WORDS[lane].split(" (")[0].replace("judgement: new launch", "judgement"))
             for lane, colour in config.LANE_COLOURS.items() if lane != "judgement (one-sale)"]
    items += [(dot("#FFFFFF", config.FLAG_COLOUR, 3), "review flag"), (dot(config.PATH_FILL), "on the selected path")]
    return ui.div(*[ui.span(mark, text, class_="me-3 small") for mark, text in items], class_="mt-1")


def help_modal(vd, version):
    """The "? Help" window: how to read every part of the app, with numbers from the files of the version on screen."""
    ex = charts.range_example(vd.final, vd.percentiles)
    lanes = ui.tags.ul(*[ui.tags.li(ui.span(style=f"display:inline-block;width:11px;height:11px;border-radius:50%;"
                                                  f"background:{colour};margin-right:6px"), config.LANE_WORDS[lane])
                         for lane, colour in config.LANE_COLOURS.items()])
    recipe = charts.percentile_table(vd.percentiles).to_html(index=False, classes="table table-sm small", border=0,
                                                             justify="left")      # headings line up with the numbers
    section = lambda title, *body: ui.div(ui.h5(title, class_="mt-3"), *body)
    return ui.modal(
        section("The tree",
                ui.p("Circles (or boxes) are the 283 series: Total > 3 categories > 8 sub-categories > 83 brands > 188 "
                     "products. Click one to select it everywhere; click the selected one again to go back up. Circle size "
                     "= square root of the 13-week forecast, so small products stay visible. Light blue = the path to your "
                     "selection; a thick orange-red outline = a review flag (see the Flags tab). A product's colour is its lane:"),
                lanes),
        section("The 80% and 95% ranges",
                ui.p(f"Each range comes from the models' real mistakes in the practice rounds cv1 + cv2: for each group, the "
                     f"10% / 90% (and 2.5% / 97.5%) points of the errors, measured in units of the series' usual weekly change "
                     f"(its scale). Example - the Total, week {ex['week']}: forecast {ex['forecast']:,.0f}, scale "
                     f"{ex['scale']:,.0f} cases, so the 80% range is {ex['forecast']:,.0f} {ex['low_p']:+.2f} x {ex['scale']:,.0f} "
                     f"to {ex['forecast']:,.0f} + {ex['high_p']:.2f} x {ex['scale']:,.0f} = {ex['lo80']:,.0f} to {ex['hi80']:,.0f}. "
                     "The ranges reach further above the forecast than below, because in the practice rounds real sales "
                     "went above the forecast by more than they went below it."),
                ui.p(ui.strong("Ranges are per week. "), "Never add the 13 weekly ranges together to get a range for the "
                     "13-week total - that would be far too wide. Judgement and stopped products have no range: a planner sets it."),
                ui.HTML(recipe)),
        section("Official (December cleaned) and With spikes",
                ui.p("December 2025 had a one-off surge. The OFFICIAL forecast learned from sales in which the 84 product-weeks "
                     "flagged as spikes in the 5 December weeks were replaced by that product's usual week (tested in Step 7: "
                     "11.9% better on cv2), because July-October has no December. 'With spikes' learned from the sales exactly "
                     "as recorded - it is shown for comparison only. "
                     "The badge in the top bar always says which one is on screen."),
                ui.p(f"On screen now: {config.VERSION_LABELS[version]}.", class_="text-muted small")),
        section("The tests (why you can trust the models)",
                ui.p("cv1 (learned weeks 1-27, tested on 28-40) and cv2 (1-40, tested on 41-53) chose the models; the backtest "
                     "(learned 1-53, sealed on 6 Apr 2026, tested on 54-66) checked them once on weeks nobody had used. "
                     "MASE = the average mistake divided by the series' usual week-to-week change in the weeks it learned "
                     "from (FPP2 3.4): below 1 means the mistakes are smaller than that usual change. "
                     "Bias = total forecast / total real sales: 1.00 is right, above 1 too high.")),
        section("Challengers (not official)",
                ui.p(f"Two other models (ARIMA + calendar, and the last-13-week average) were frozen for weeks 67-79 on "
                     f"{config.CHALLENGER_FROZEN}. They were chosen after looking at weeks 54-66, so their backtest scores prove "
                     "nothing yet. Step 10 compares all three with EABL's real weeks 67-79; the official method changes only "
                     "if a challenger wins there.")),
        section("Flags",
                ui.p("A flag is a note from the notebook that a forecast needs a planner's look (for example: low confidence, "
                     "set to 0 by reconciliation, new launch). A flag does not mean the forecast is wrong.")),
        title="How to read this app", size="xl", easy_close=True, footer=ui.modal_button("Close"),
    )



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
                     ui.card(ui.card_header("Product hierarchy: click to select a series (click the selected one again to go back up)"),
                ui.input_radio_buttons("tree_view", None, {"circles": "Circles", "boxes": "Boxes"}, inline=True),
                ui.panel_conditional("input.tree_view === 'circles'",
                    ui.div(id="echarts_tree", style="width:100%;height:420px"),
                    circle_legend(),
                    ui.p("Circle size = square root of the 13-week forecast (weeks 67-79), so small products stay visible; "
                         "hover for the true number.", class_="text-muted small mb-0")),
                ui.panel_conditional("input.tree_view === 'boxes'",
                    output_widget("tree_chart"),
                    tree_legend(),
                    ui.p("Box size = 13-week forecast (weeks 67-79); very small and stopped products are drawn at a minimum "
                         "size so they can be clicked - hover for the true number.", class_="text-muted small mb-0"))),

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

            ui.nav_panel("Flags",
                         ui.p("Review notes the notebook wrote for this series and its children. A flag does not mean the "
                              "forecast is wrong - it means a planner should look at it before using it.", class_="text-muted small"),
                         ui.output_ui("flags_note"), ui.output_data_frame("flags_grid"), value="flags"),
                        ui.nav_panel("Challengers (not official)",
                         ui.p("Two other models, tested on the backtest weeks and frozen for weeks 67-79 on "
                              f"{config.CHALLENGER_FROZEN} (cell 9g). They are NOT the forecast. They were picked after looking at "
                              "weeks 54-66, so the backtest below cannot prove they are better; Step 10 (EABL's real weeks "
                              "67-79) is the fair test.", class_="text-muted small"),
                         ui.input_radio_buttons("challenger_rule", "Which series got the challenger models",
                                                config.CHALLENGER_RULES, inline=True),
                                                                         ui.input_switch("challenger_zoom", "Zoom in on the lines (axis fits the lines instead of starting at 0)"),
                         ui.output_ui("challenger_summary"),
                         ui.h6("Backtest (weeks 54-66): all three against real sales", class_="mt-3"),
                         output_widget("challenger_bt_chart"),
                         ui.h6("Frozen forecast (weeks 67-79): to be judged in Step 10", class_="mt-3"),
                         output_widget("challenger_fc_chart"), value="challengers"),

            ui.nav_panel("Step 10", coming_soon("10 (later)", "EABL's real sales for weeks 67-79."), value="step10"),
            id="tabs", selected="final",
        ),
    )
    return ui.page_navbar(
        forecast_page,
        ui.nav_panel(
            "Model evidence",
            ui.p("Do the models work? All series at once, for the version chosen in the left panel. cv1 and cv2 are the "
                 "practice rounds used to choose the models; the backtest is the sealed test (Step 8).", class_="text-muted"),
            ui.card(ui.card_header("1. Accuracy in each test, by level (MASE: lower is better)"),
                    output_widget("accuracy_chart"), ui.output_data_frame("accuracy_grid"),
                    ui.p("cv1 / cv2 score the chosen base forecasts (before reconciliation); the backtest scores the final "
                         "reconciled forecast. Naive is compared on the same series. Bias = total forecast / total real.",
                         class_="text-muted small")),
            ui.card(ui.card_header("2. Which standard models won (picked on MASE over cv1 + cv2)"),
                    ui.output_data_frame("winners_grid")),
            ui.card(ui.card_header("3. Why MinT: making all levels add up, scored on cv2 (MASE, lower is better)"),
                    ui.output_data_frame("recon_grid")),
            ui.card(ui.card_header("4. Do the ranges work? Share of real weeks inside them (targets: 80% and 95%)"),
                    ui.output_data_frame("coverage_grid")),
            ui.card(ui.card_header("5. Known weak spots"), ui.output_ui("weak_spots")),
                        ui.card(ui.card_header("6. Challengers (NOT official): backtest weeks 54-66, average MASE by level (lower is better)"),
                    ui.output_data_frame("challenger_grid"), ui.output_ui("challenger_totals"),
                    ui.p("These two models were chosen after looking at weeks 54-66, so this table cannot prove they are "
                         "better. Their weeks 67-79 forecasts were frozen and will be judged in Step 10.",
                         class_="text-muted small")),

        ),
        ui.nav_panel("Product explorer",
                     ui.p("All 188 products for the version chosen in the left panel. Type in the boxes under the column "
                          "names to filter; click a column name to sort. Click a row to open that product on the Forecast page.",
                          class_="text-muted"),
                     ui.output_data_frame("explorer_grid"), value="explorer"),
        ui.nav_spacer(),
        ui.nav_control(ui.input_action_button("help", "? Help", class_="btn-sm btn-outline-secondary me-2")),

        ui.nav_control(ui.output_ui("badge")),
        title=config.APP_TITLE, id="page", sidebar=sidebar, window_title=config.APP_TITLE,
        header=ui.TagList(ui.tags.script(src="echarts.min.js"), ui.tags.script(src="tree.js")),   # Step 16 circle tree

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
        if input.series() and input.series() != selected():   # a real change only (the tree also moves the picker)
            selected.set(input.series())

    @reactive.calc
    def version_data():                                   # every view reads the chosen version through this
        return DATA["versions"][input.version()]


    # ---- Step 14: the hierarchy tree ----
    @reactive.effect
    def _picker_follows():                                # the tree (or any other part) changed the selection
        if input.series() != selected():
            ui.update_selectize("series", selected=selected())

    @reactive.calc
    def tree_focus():                                     # the box shown at the top of the tree
        series_id = selected()
        return series_id if DATA["hierarchy"].children[series_id] else DATA["hierarchy"].parent[series_id]

    @render_plotly
    def tree_chart():
        focus = tree_focus()
        vd = version_data()
        widget = go.FigureWidget(charts.icicle_figure(tree.icicle_data(DATA["hierarchy"], vd.final, vd.routing), focus))

        def on_click(trace, points, state):               # a box was clicked
            if not points.point_inds:
                return
            clicked = trace.ids[points.point_inds[0]]
            if clicked == focus and clicked != "Total":   # the top box = go back up one level
                clicked = DATA["hierarchy"].parent[clicked]
            selected.set(clicked)

        widget.data[0].on_click(on_click)
        return widget

    # ---- Step 16: the circle tree (drawn in the browser by www/tree.js) ----
    @reactive.effect
    async def _send_circle_tree():                        # the selection or the version changed: redraw the circles
        vd = version_data()
        await session.send_custom_message("tree_data", tree.echarts_tree(DATA["hierarchy"], vd.final, vd.routing, selected()))

    @reactive.effect
    @reactive.event(input.tree_click)
    def _from_circle_tree():                              # a circle was clicked
        clicked = input.tree_click()
        if clicked == selected() and clicked != "Total":  # the selected circle again = go back up one level
            clicked = DATA["hierarchy"].parent[clicked]
        if clicked != selected():
            selected.set(clicked)

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
        # ---- Step 15: the Flags tab and the Product explorer page ----
    @render.ui
    def flags_note():
        if charts.flags_table(version_data().final, DATA["hierarchy"], selected(), sku_names()) is None:
            return ui.p("No review flags for this series or its children.", class_="text-muted")
        return None

    @render.data_frame
    def flags_grid():
        table = charts.flags_table(version_data().final, DATA["hierarchy"], selected(), sku_names())
        return None if table is None else render.DataGrid(table, width="100%")

    @reactive.calc
    def explorer():
        return charts.explorer_table(version_data().final, version_data().routing, DATA["hierarchy"])

    @render.data_frame
    def explorer_grid():
        return render.DataGrid(explorer().drop(columns="id"), filters=True, selection_mode="row", width="100%", height="75vh",
                               styles={"location": "body", "style": {"white-space": "nowrap"}})   # one line per product

    @reactive.effect
    @reactive.event(input.explorer_grid_cell_selection)
    async def _from_explorer():                           # a row was clicked: open that product on the Forecast page
        rows = (input.explorer_grid_cell_selection() or {}).get("rows") or []
        if rows:
            product = explorer()["id"].iloc[rows[0]]
            if product != selected():
                selected.set(product)
            ui.update_navset("page", selected="Forecast")
            await explorer_grid.update_cell_selection(None)   # un-select, so clicking the same row again works
    # ---- Step 17: the help panel ----
    @reactive.effect
    @reactive.event(input.help)
    def _show_help():
        ui.modal_show(help_modal(version_data(), input.version()))


    # ---- Challengers (cell 9g) - NOT official ----
    def challenger_rows(part):                            # this series' rows, backtest ("bt") or frozen forecast ("fc")
        df = getattr(version_data(), f"challengers_{part}_{input.challenger_rule()}")
        return charts.rows_for(df, selected())

    @render.ui
    def challenger_summary():
        bt, fc = challenger_rows("bt"), challenger_rows("fc")
        scale = version_data().step8.set_index("unique_id").loc[selected(), "scale (real weeks 1-53)"].iloc[0]
        scores = charts.challenger_scores(bt, scale)
        items = [pill(f"This series {charts.challenger_used(bt)}")]
        for name in charts.CHALLENGER_LINES:
            s, label = scores[name], ("Official" if name == "official" else name)
            text = f"{label}: MASE {s['MASE']:.2f}" if s["MASE"] is not None else f"{label}: MASE -"
            text += f", bias {s['bias']:.2f}" if s["bias"] is not None else ""
            text += f", weeks 67-79 total {fc[f'{name} forecast'].sum():,.1f}"
            items.append(pill(text))
        return ui.div(*items, class_="mb-2")

    @render_plotly
    def challenger_bt_chart():
        return charts.challenger_figure(challenger_rows("bt"), with_real=True, zoom=input.challenger_zoom())

    @render_plotly
    def challenger_fc_chart():
        return charts.challenger_figure(challenger_rows("fc"), with_real=False, zoom=input.challenger_zoom())

    @render.data_frame
    def challenger_grid():
        vd = version_data()
        table = charts.challenger_level_table({"normal": vd.challengers_bt_normal, "option2": vd.challengers_bt_option2},
                                              vd.step8, config.LEVELS)
        return render.DataGrid(table, width="100%")

    @render.ui
    def challenger_totals():
        vd, items = version_data(), []
        for rule, label in config.CHALLENGER_RULES.items():
            bt = getattr(vd, f"challengers_bt_{rule}").query("unique_id == 'Total'")
            fc = getattr(vd, f"challengers_fc_{rule}").query("unique_id == 'Total'")
            parts = [f"{'official' if n == 'official' else n} {bt[f'{n} forecast'].sum() / bt['real sales'].sum():.3f} / "
                     f"{fc[f'{n} forecast'].sum():,.0f}" for n in charts.CHALLENGER_LINES]
            items.append(ui.tags.li(f"{label} - Total bias (1.00 = right) / frozen weeks 67-79 total: " + "  |  ".join(parts)))
        return ui.tags.ul(*items, class_="small mt-2")


    # ---- Step 13: the Model evidence page ----
    @reactive.calc
    def accuracy():
        return charts.accuracy_by_level(version_data(), config.LEVELS)

    @render_plotly
    def accuracy_chart():
        return charts.accuracy_figure(accuracy(), config.LEVELS)

    @render.data_frame
    def accuracy_grid():
        return render.DataGrid(accuracy(), width="100%")

    @render.data_frame
    def winners_grid():
        return render.DataGrid(charts.winners_table(version_data().practice_winners, config.LEVELS), width="100%")

    @render.data_frame
    def recon_grid():
        return render.DataGrid(charts.reconciliation_table(version_data().practice_reconciliation), width="100%")

    @render.data_frame
    def coverage_grid():
        return render.DataGrid(charts.coverage_table(version_data(), config.LEVELS), width="100%")

    @render.ui
    def weak_spots():
        acc = accuracy().set_index(["Test", "Level"])
        total_bt = acc.loc[(charts.TESTS["backtest"], "Total")]
        sparse = version_data().practice_coverage.set_index("group")
        launches = int((version_data().routing["lane"] == "judgement (new launch)").sum())
        items = [
            f"The official backtest forecast was {total_bt['Bias (1.00 = right total)'] - 1:+.1%} too high in total on the sealed weeks "
            f"54-66 (bias {total_bt['Bias (1.00 = right total)']:.3f}).",
            f"At the Total, Naive did {'better' if total_bt['MASE'] > total_bt['Naive MASE (same series)'] else 'worse'} "
            f"than the model in the backtest (MASE {total_bt['Naive MASE (same series)']:.2f} vs {total_bt['MASE']:.2f}).",
            "cv1's test weeks (28-40) contain the December 2025 spike (week 38), so every model scored badly there; "
            "compare cv2 and the backtest for normal weeks.",
        ]
        if "Brand (sparse)" in sparse.index:
            items.append(f"Sparse-brand ranges are too narrow: on cv2 only {sparse.loc['Brand (sparse)', '80% coverage']:.0%} "
                         f"of real weeks fell inside the 80% range.")
        items.append(f"{launches} new-launch products are forecast by judgement: they had too little history to test.")
        items.append("Products with a short history (AICc lane) did worse than Naive in Step 8. Improvements are planned "
                     "for Step 10, judged on EABL's real weeks 67-79.")
        return ui.tags.ul(*[ui.tags.li(item) for item in items])


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


app = (App(build_ui(), server, static_assets=config.WWW_DIR) if LOAD_ERROR is None      # www/: ECharts + tree.js
       else App(build_error_ui(), server_when_data_failed))
