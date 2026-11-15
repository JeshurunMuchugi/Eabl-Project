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
