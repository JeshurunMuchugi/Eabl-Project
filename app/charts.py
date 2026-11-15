"""
charts.py - every chart and table the app shows, built from rows the notebook saved.

Rules: a chart only DRAWS the numbers it is given. Nothing here forecasts, re-scores or changes a value,
and nothing here opens or writes a file (data_loader.py does all reading).
"""
import pandas as pd
import plotly.graph_objects as go

import config

BAND_95 = "rgba(192, 57, 43, 0.10)"           # light red: 95% range
BAND_80 = "rgba(192, 57, 43, 0.22)"           # darker red: 80% range


def as_dates(dates):
    """Dates as 'YYYY-MM-DD' text, so the browser shows real dates on the axis (not raw time-stamps)."""
    return dates.dt.strftime("%Y-%m-%d")


def rows_for(df, series_id):
    """The rows of one series, in week order."""
    return df[df["unique_id"] == series_id].sort_values("ds")


def add_range(fig, rows, low_col, high_col, colour, name):
    """Shaded band between two columns (drawn only where the notebook saved a range)."""
    if rows[low_col].isna().all():
        return
    fig.add_trace(go.Scatter(x=as_dates(rows["ds"]), y=rows[low_col], mode="lines", line=dict(width=0),
                             showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=as_dates(rows["ds"]), y=rows[high_col], mode="lines", line=dict(width=0), fill="tonexty",
                             fillcolor=colour, name=name, customdata=rows[low_col],
                             hovertemplate=f"{name}: %{{customdata:,.1f}} – %{{y:,.1f}}<extra></extra>"))


def forecast_figure(actual_rows, final_rows, lookback_weeks, history_label="Real sales (weeks 1-66)"):
    """Tab 1: the weekly history (black) for the last `lookback_weeks` weeks, then weeks 67-79:
    95% and 80% ranges (shaded), base before reconciliation (dashed grey) and the forecast to use (red).
    `actual_rows` needs columns ds, week, y; `history_label` names the black line in the legend."""
    last_actual_week = config.WINDOWS["backtest"][1]                                  # 66
    history = actual_rows[actual_rows["week"] > last_actual_week - int(lookback_weeks)]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=as_dates(history["ds"]), y=history["y"], mode="lines+markers", name=history_label,
                             line=dict(color=config.ACTUAL_COLOUR, width=1.8), marker=dict(size=4),
                             customdata=history["week"],
                             hovertemplate="Week %{customdata}: %{y:,.1f} cases<extra>History</extra>"))
    add_range(fig, final_rows, "lo95", "hi95", BAND_95, "95% range")
    add_range(fig, final_rows, "lo80", "hi80", BAND_80, "80% range")
    fig.add_trace(go.Scatter(x=as_dates(final_rows["ds"]), y=final_rows["base"], mode="lines", name="Base (before reconciliation)",
                             line=dict(color=config.BASE_COLOUR, width=1.4, dash="dash"),
                             hovertemplate="Base: %{y:,.1f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=as_dates(final_rows["ds"]), y=final_rows["forecast"], mode="lines+markers", name="Forecast (weeks 67-79)",
                             line=dict(color=config.FORECAST_COLOUR, width=2.4), marker=dict(size=6),
                             customdata=final_rows["week"],
                             hovertemplate="Week %{customdata}: %{y:,.1f} cases<extra>Forecast</extra>"))
    if len(history) and len(final_rows):                       # dotted link: last real week -> first forecast week
        fig.add_trace(go.Scatter(x=as_dates(pd.concat([history["ds"].tail(1), final_rows["ds"].head(1)])),
                                 y=[history["y"].iloc[-1], final_rows["forecast"].iloc[0]], mode="lines",
                                 line=dict(color=config.FORECAST_COLOUR, width=1.4, dash="dot"),
                                 showlegend=False, hoverinfo="skip"))
    if len(final_rows):                                         # the forecast period: shaded + a "forecast starts" line
        start = final_rows["ds"].min() - pd.Timedelta(days=3)
        end = final_rows["ds"].max() + pd.Timedelta(days=3)
        fig.add_vrect(x0=start.strftime("%Y-%m-%d"), x1=end.strftime("%Y-%m-%d"), fillcolor="rgba(120,120,120,0.06)",
                      line_width=0, layer="below")
        fig.add_vline(x=start.strftime("%Y-%m-%d"), line=dict(color="#7A8089", width=1, dash="dash"))
        fig.add_annotation(x=start.strftime("%Y-%m-%d"), y=1, yref="paper", text=" Forecast →", showarrow=False,
                           xanchor="left", yanchor="top", font=dict(size=12, color="#5B6474"))
    fig.update_layout(template="plotly_white", height=460, margin=dict(l=60, r=20, t=40, b=40),
                      hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                      yaxis_title="cases per week", xaxis_title=None)
    fig.update_yaxes(rangemode="tozero")
    fig.update_xaxes(type="date", tickformat="%d %b\n%Y", showgrid=True, ticks="outside",
                     rangeslider=dict(visible=True, thickness=0.08))
    return fig


def children_table(final_df, hierarchy, series_id, sku_names):
    """Each direct child's 13-week forecast, then the sum of the children and the parent itself.
    Returns None for a product (it has no children)."""
    kids = hierarchy.children.get(series_id, [])
    if not kids:
        return None
    totals = final_df[final_df["unique_id"].isin(kids + [series_id])].groupby("unique_id")["forecast"].sum()
    lanes = final_df.drop_duplicates("unique_id").set_index("unique_id")["lane"]
    rows = [{"Child": sku_names.get(kid, kid.rsplit("/", 1)[-1].strip()), "Level": hierarchy.level[kid],
             "13-week forecast (cases)": round(totals[kid], 1),
             "Lane": lanes.get(kid) if isinstance(lanes.get(kid), str) else "-"} for kid in kids]
    rows.sort(key=lambda row: -row["13-week forecast (cases)"])
    children_sum, parent_total = totals[kids].sum(), totals[series_id]
    adds_up = abs(children_sum - parent_total) <= config.ADDS_UP_TOLERANCE * config.HORIZON
    rows.append({"Child": "Sum of children", "Level": "", "13-week forecast (cases)": round(children_sum, 1), "Lane": ""})
    rows.append({"Child": "Parent (this series)", "Level": hierarchy.level[series_id],
                 "13-week forecast (cases)": round(parent_total, 1), "Lane": "adds up ✓" if adds_up else "DOES NOT ADD UP ✗"})
    return pd.DataFrame(rows)


def download_rows(final_df, series_ids):
    """The saved final-forecast rows for some series (for the download buttons) - exactly as in the CSV."""
    return final_df[final_df["unique_id"].isin(series_ids)].sort_values(["unique_id", "ds"])


# ---- Step 12: the evidence tabs (cv1, cv2, backtest) ------------------------------------------------------
def test_window_figure(actual, forecast, forecast_name, ranges=None, candidates=None, naive=None):
    """One test window (13 weeks): real sales (black) against the forecast that was used (red).
    Optional: the 80% / 95% ranges (shaded), every other candidate model (thin grey) and Naive (dotted grey).
    `actual` and `forecast` need columns ds, week, value; `candidates` needs ds, model, forecast."""
    fig = go.Figure()
    if ranges is not None:
        add_range(fig, ranges, "lo95", "hi95", BAND_95, "95% range")
        add_range(fig, ranges, "lo80", "hi80", BAND_80, "80% range")
    if candidates is not None and len(candidates):
        for i, (model, rows) in enumerate(candidates.sort_values("ds").groupby("model", sort=True)):
            fig.add_trace(go.Scatter(x=as_dates(rows["ds"]), y=rows["forecast"], mode="lines", name="Other candidate models",
                                     legendgroup="candidates", showlegend=(i == 0), line=dict(color="#B8BEC7", width=1),
                                     hovertemplate=f"{model}: %{{y:,.1f}}<extra></extra>"))
    if naive is not None and len(naive):
        fig.add_trace(go.Scatter(x=as_dates(naive["ds"]), y=naive["value"], mode="lines", name="Naive (benchmark)",
                                 line=dict(color=config.BASE_COLOUR, width=1.4, dash="dot"),
                                 hovertemplate="Naive: %{y:,.1f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=as_dates(actual["ds"]), y=actual["value"], mode="lines+markers", name="Real sales",
                             line=dict(color=config.ACTUAL_COLOUR, width=2), marker=dict(size=6), customdata=actual["week"],
                             hovertemplate="Week %{customdata}: %{y:,.1f} cases<extra>Real sales</extra>"))
    fig.add_trace(go.Scatter(x=as_dates(forecast["ds"]), y=forecast["value"], mode="lines+markers", name=forecast_name,
                             line=dict(color=config.FORECAST_COLOUR, width=2.4), marker=dict(size=6),
                             customdata=forecast["week"],
                             hovertemplate="Week %{customdata}: %{y:,.1f} cases<extra>Forecast</extra>"))
    fig.update_layout(template="plotly_white", height=400, margin=dict(l=60, r=20, t=40, b=40), hovermode="x unified",
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), yaxis_title="cases per week")
    fig.update_yaxes(rangemode="tozero")
    fig.update_xaxes(type="date", tickformat="%d %b\n%Y", showgrid=True, ticks="outside")
    return fig


def candidate_scores_table(score_rows, winner=None):
    """Every candidate model's score for one series in one round, best (lowest MASE) first.
    Copied from the notebook's saved scores (cell 9e) - nothing is re-scored."""
    if score_rows.empty:
        return None
    table = score_rows[["model", "candidate_set", "MASE", "MAE", "WAPE", "RMSSE"]].copy()
    table["candidate_set"] = table["candidate_set"].str.split(" ").str[0] + " " + table["candidate_set"].str.split(" ").str[1]
    table["note"] = ""
    table.loc[table["model"] == "Naive", "note"] = "benchmark"
    if winner:
        table.loc[table["model"] == winner, "note"] = "winner (both rounds, MASE)"
    table.loc[table["model"] == "Zero", "note"] = "always 0 - comparison only"
    table = table.sort_values("MASE", na_position="last")
    table.insert(0, "rank", range(1, len(table) + 1))
    return table.rename(columns={"model": "Model", "candidate_set": "Group", "note": "Note"}).round(3)


def window_summary(chosen_rows):
    """Scores of the forecast that was used in one practice round, from the saved columns (cell 9e):
    MASE = mean |r| (r = scaled error the notebook saved); bias = sum forecast / sum real; share inside the ranges."""
    real_sum = chosen_rows["y"].sum()
    out = {"weeks": len(chosen_rows), "MASE": chosen_rows["r"].abs().mean() if chosen_rows["r"].notna().any() else None,
           "bias": chosen_rows["chosen"].sum() / real_sum if real_sum > 0 else None}
    for pct in ("80%", "95%"):
        inside = chosen_rows[f"inside {pct}"].dropna()
        out[f"inside {pct}"] = inside.astype(bool).mean() if len(inside) else None
    return out


# ---- Step 13: the Model evidence page (all series at once) -----------------------------------------------
TESTS = {"cv1": "cv1 (weeks 28-40)", "cv2": "cv2 (weeks 41-53)", "backtest": "backtest (weeks 54-66)"}


def accuracy_by_level(vd, levels):
    """Average MASE per level in each test, next to Naive on the SAME series, and the pooled bias.
    cv1 / cv2: the chosen base forecast (before reconciliation), from cell 9e; backtest: the final reconciled
    forecast, from Step 8.  Only summarises saved numbers - nothing is re-forecast."""
    rows = []
    for test in ("cv1", "cv2"):
        ch = vd.practice_chosen[vd.practice_chosen["set"] == test]
        per = ch.groupby(["level", "unique_id"]).agg(mase=("r", lambda r: r.abs().mean()), fc=("chosen", "sum"), real=("y", "sum"))
        naive = vd.practice_scores[(vd.practice_scores["set"] == test) & (vd.practice_scores["model"] == "Naive")]
        per = per.join(naive.set_index(["level", "unique_id"])["MASE"].rename("naive"))
        rows.append(per.reset_index().assign(test=test))
    s8 = vd.step8
    per = s8.groupby(["level", "unique_id"]).agg(mase=("series MASE (weeks 54-66)", "first"), fc=("forecast", "sum"),
                                                 real=("actual", "sum"), scale=("scale (real weeks 1-53)", "first"))
    naive_err = (s8["actual"] - s8["Naive"]).abs().groupby([s8["level"], s8["unique_id"]]).mean()
    per["naive"] = naive_err / per["scale"].where(per["scale"] > 0)
    rows.append(per.drop(columns="scale").reset_index().assign(test="backtest"))
    per = pd.concat(rows, ignore_index=True)
    out = []
    for (test, level), g in per.groupby(["test", "level"]):
        both = g.dropna(subset=["mase", "naive"])
        out.append({"Test": TESTS[test], "Level": level, "Series": len(g),
                    "MASE": both["mase"].mean(), "Naive MASE (same series)": both["naive"].mean(),
                    "Bias (1.00 = right total)": g["fc"].sum() / g["real"].sum() if g["real"].sum() > 0 else None})
    table = pd.DataFrame(out)
    table["Beats Naive?"] = (table["MASE"] < table["Naive MASE (same series)"]).map({True: "yes", False: "no"})
    order = {name: i for i, name in enumerate(list(TESTS.values()) + list(levels))}       # cv1, cv2, backtest; Total ... Product
    table = table.sort_values(["Test", "Level"], key=lambda col: col.map(order))
    return table.round(3).reset_index(drop=True)


def accuracy_figure(table, levels):
    """MASE as a share of Naive's MASE (same series): below 1.0 = the models beat Naive."""
    fig = go.Figure()
    colours = {"cv1 (weeks 28-40)": "#9BB7D4", "cv2 (weeks 41-53)": "#4A7FB5", "backtest (weeks 54-66)": "#1F3A5F"}
    for test, colour in colours.items():
        rows = table[table["Test"] == test].set_index("Level").reindex(levels)
        ratio = rows["MASE"] / rows["Naive MASE (same series)"]
        fig.add_trace(go.Bar(x=levels, y=ratio, name=test, marker_color=colour,
                             customdata=rows[["MASE", "Naive MASE (same series)"]].values,
                             hovertemplate="%{x}: model %{customdata[0]:.2f} vs Naive %{customdata[1]:.2f}"
                                           " (ratio %{y:.2f})<extra>" + test + "</extra>"))
    fig.add_hline(y=1, line=dict(color=config.FORECAST_COLOUR, dash="dash"))
    fig.add_annotation(x=1, xref="paper", y=1, yref="y", text="Naive = 1.0  (below = better than Naive)", showarrow=False,
                       xanchor="right", yanchor="bottom", bgcolor="white", font=dict(size=11, color=config.FORECAST_COLOUR))
    fig.update_layout(template="plotly_white", barmode="group", height=360, margin=dict(l=60, r=20, t=40, b=40),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0), yaxis_title="model MASE ÷ Naive MASE")
    return fig


def winners_table(winners, levels):
    """How many series each standard model won (cv1 + cv2 together, picked by MASE), and the winners' average MASE vs Naive."""
    counts = pd.crosstab(winners["level"], winners["winner"])
    counts = counts.loc[:, counts.sum().sort_values(ascending=False).index]
    avg = winners.groupby("level")[["winner_avg_MASE", "Naive_avg_MASE"]].mean().round(3)
    table = counts.join(avg.rename(columns={"winner_avg_MASE": "winner avg MASE", "Naive_avg_MASE": "Naive avg MASE"}))
    table.insert(0, "series", counts.sum(axis=1))
    return table.reindex([lv for lv in levels if lv in table.index]).rename_axis("Level").reset_index()


def reconciliation_table(recon):
    """The 6 ways of making levels add up, scored on cv2 (MASE, lower = better); the chosen one marked."""
    table = recon.drop(columns=["version", "role"], errors="ignore").copy()
    table["chosen"] = table["chosen"].map({True: "✓ chosen", False: ""})
    return table.round(3).rename(columns={"method": "Method"})


def coverage_table(vd, levels):
    """Share of real weeks inside the 80% / 95% ranges: cv2 (ranges from cv1 errors) and the backtest."""
    cv2 = vd.practice_coverage.rename(columns={"group": "Group", "cv2 weeks": "Weeks with a range",
                                                "80% coverage": "Inside 80%", "95% coverage": "Inside 95%"})
    cv2 = cv2[["Group", "Weeks with a range", "Inside 80%", "Inside 95%"]].assign(Test=TESTS["cv2"])
    s8 = vd.step8[vd.step8["lo80"].notna()]
    bt = s8.groupby("level").agg(**{"Weeks with a range": ("week", "size"),
                                     "Inside 80%": ("inside 80%", lambda x: x.astype(bool).mean()),
                                     "Inside 95%": ("inside 95%", lambda x: x.astype(bool).mean())})
    bt = bt.reindex([lv for lv in levels if lv in bt.index]).rename_axis("Group").reset_index().assign(Test=TESTS["backtest"])
    table = pd.concat([cv2, bt], ignore_index=True)[["Test", "Group", "Weeks with a range", "Inside 80%", "Inside 95%"]]
    return table.round(3)


# ---- Step 14: the hierarchy tree (Plotly icicle) ----
def icicle_figure(data, focus):
    """Clickable icicle of the 283 series (data from tree.icicle_data). 'focus' is the box shown at the top;
    three levels are shown at a time. Box size = 13-week forecast; colour = lane; hover = the numbers in words."""
    fig = go.Figure(go.Icicle(
        ids=data["ids"], parents=data["parents"], labels=data["labels"], values=data["values"],
        branchvalues="total", level=focus, maxdepth=3, sort=False,
        marker=dict(colors=data["colours"], line=dict(color="white", width=1)),
        customdata=data["hover"], hovertemplate="%{customdata}<extra></extra>",
        textinfo="label", tiling=dict(orientation="h"), pathbar=dict(visible=True, side="top")))
    fig.update_layout(height=420, margin=dict(l=8, r=8, t=36, b=8), template="plotly_white")
    return fig


# ---- Step 15: the Flags tab and the Product explorer ----
def split_flags(text):
    """'low confidence (...); 13-week total off by > 50%' -> ['low confidence (...)', '13-week total off by > 50%']."""
    return [part.strip() for part in str(text).split(";") if part.strip()] if isinstance(text, str) else []


def flags_table(final_df, hierarchy, series_id, sku_names):
    """One row per review flag of the series and of its direct children (as the notebook wrote them), or None."""
    first = final_df.drop_duplicates("unique_id").set_index("unique_id")
    totals = final_df.groupby("unique_id")["forecast"].sum()
    rows = []
    for sid in [series_id] + hierarchy.children[series_id]:
        for flag in split_flags(first.at[sid, "flag list"]):
            code = sid.rsplit("/", 1)[-1].strip()                        # products: "SKU (code)" - two SKUs share a name
            name = f"{sku_names[sid]} ({code})" if sid in sku_names else code
            rows.append({"Series": "▶ this series" if sid == series_id else name,
                         "Level": hierarchy.level[sid], "Lane": first.at[sid, "lane"] if isinstance(first.at[sid, "lane"], str) else "-",
                         "13-week forecast (cases)": round(float(totals[sid]), 1), "Flag (please review)": flag})
    return pd.DataFrame(rows) if rows else None


def explorer_table(final_df, routing, hierarchy):
    """All 188 products in one table: where each sits, how the router labelled it, its lane, method, forecast, flags."""
    first = final_df.drop_duplicates("unique_id").set_index("unique_id")
    totals = final_df.groupby("unique_id")["forecast"].sum()
    r = routing.set_index("unique_id")
    rows = []
    for pid in hierarchy.products:
        category, sub_category, brand, code = [part.strip() for part in pid.split("/")]
        rows.append({"Product": f"{r.at[pid, 'SKU']} ({code})", "Category": category, "Sub-category": sub_category,
                     "Brand": brand, "F2 label": r.at[pid, "F2 label (weeks 1-66)"], "F5 family": r.at[pid, "F5 family (weeks 1-66)"],
                     "Weeks on sale": int(r.at[pid, "weeks_on_sale"]), "Selling weeks": int(r.at[pid, "selling_weeks"]),
                     "Lane": r.at[pid, "lane"], "Method": r.at[pid, "method"],
                     "13-week forecast (cases)": round(float(totals[pid]), 1),
                     "Flags": len(split_flags(first.at[pid, "flag list"])), "id": pid})
    return pd.DataFrame(rows)


# ---- Challengers (cell 9g) - NOT official ----
CHALLENGER_LINES = ["official"] + config.CHALLENGER_MODELS            # the three forecasts compared


def challenger_figure(rows, with_real):
    """Official forecast vs the two challengers for one series; with_real adds the real sales (backtest weeks 54-66)."""
    fig = go.Figure()
    x = as_dates(rows["ds"])
    if with_real:
        fig.add_trace(go.Scatter(x=x, y=rows["real sales"], name="Real sales", mode="lines+markers",
                                 line=dict(color=config.ACTUAL_COLOUR, width=2), marker=dict(size=6)))
    for name in CHALLENGER_LINES:
        fig.add_trace(go.Scatter(x=x, y=rows[f"{name} forecast"], name=name.capitalize() if name == "official" else name,
                                 mode="lines+markers", marker=dict(size=5),
                                 line=dict(color=config.CHALLENGER_COLOURS[name], width=3 if name == "official" else 2,
                                           dash=None if name == "official" else "dash")))
    fig.update_layout(height=340, margin=dict(l=56, r=16, t=30, b=36), template="plotly_white", hovermode="x unified",
                      legend=dict(orientation="h", y=1.12), yaxis=dict(title="cases per week", rangemode="tozero"),
                      xaxis=dict(type="date"))                         # from 0, like the other forecast charts
    return fig


def challenger_scores(rows, scale):
    """MASE (scale = mean weekly change of real weeks 1-53, as Step 8) and bias of each forecast, one series, weeks 54-66."""
    real = rows["real sales"]
    out = {}
    for name in CHALLENGER_LINES:
        f = rows[f"{name} forecast"]
        out[name] = {"MASE": (real - f).abs().mean() / scale if scale > 0 else None,
                     "bias": f.sum() / real.sum() if real.sum() > 0 else None}
    return out


def challenger_used(rows):
    """In words: did this series get the challenger models, or keep its official method?"""
    if (rows["model used"] != "challenger").all():
        return "kept its official method (stopped, judgement, intermittent or sparse - see the Final forecast tab)"
    same = all((rows[f"{m} base"] - rows["official base"]).abs().max() < 1e-9 for m in config.CHALLENGER_MODELS)
    if same:                                                   # 9g labelled it "challenger" but had nothing to fit
        return "kept its official forecast (the challengers had nothing to learn from, so cell 9g used the official base)"
    return "used the challenger models"


def challenger_level_table(bt_by_rule, step8, levels):
    """Average backtest MASE per level, official vs each challenger, for each rule (same series as Step 8 scores)."""
    scale = step8.drop_duplicates("unique_id").set_index("unique_id")["scale (real weeks 1-53)"]
    rows = []
    for rule, bt in bt_by_rule.items():
        for (level, sid), g in bt.groupby(["level", "unique_id"]):
            s = challenger_scores(g, scale[sid])
            if s["official"]["MASE"] is not None:
                rows.append({"Rule": config.CHALLENGER_RULES[rule], "Level": level, **{n: s[n]["MASE"] for n in CHALLENGER_LINES}})
    table = pd.DataFrame(rows).groupby(["Rule", "Level"], sort=False)[CHALLENGER_LINES].mean().reset_index()
    table["order"] = table["Level"].map({lv: i for i, lv in enumerate(levels)})
    table = table.sort_values(["Rule", "order"], kind="stable").drop(columns="order")
    return table.rename(columns={"official": "Official MASE", **{m: f"{m} MASE" for m in config.CHALLENGER_MODELS}}).round(3)
