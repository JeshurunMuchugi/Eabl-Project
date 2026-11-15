"""
tree.py - the data behind the hierarchy tree (Step 14: Plotly icicle; Step 16 adds the ECharts tree here).

It only re-arranges numbers the app has already read and checked (data_loader.py). It reads no file and writes nothing.

The icicle needs, for each of the 283 series: an id, its parent, a box size, a colour and a hover text.
  - Box size = the series' 13-week forecast (weeks 67-79).  In an icicle a parent's box is exactly as wide as its
    children together (branchvalues="total"), so the sizes must add up - they do, because the forecast is reconciled.
  - Very small products would be invisible and could not be clicked (44 products forecast under 1 case; the 15
    stopped products forecast 0).  So every product box is at least MIN_SHARE of its brand's forecast (and at least
    1 case), and each parent box is re-added from its children.  The hover text always shows the TRUE forecast.
  - Colour = the product's lane (Okabe-Ito colours from config.py); the upper levels have no lane, so one neutral
    colour.  The lane is also written in words in the hover text, so the colour is never the only clue.
"""
import config

MIN_SHARE = 0.01            # smallest product box = 1% of its brand's 13-week forecast
MIN_CASES = 1.0             # ... and never smaller than 1 case (a brand whose products all forecast 0)


def short_name(series_id):
    """'Beer/Premium/Guinness' -> 'Guinness' (the last part of the id)."""
    return series_id.rsplit("/", 1)[-1].strip()


def box_sizes(hierarchy, totals):
    """Box size per series: products get at least MIN_SHARE of their brand (and MIN_CASES); parents = sum of children."""
    size = {}
    for product in hierarchy.products:
        brand_total = totals[hierarchy.parent[product]]
        size[product] = max(totals[product], MIN_SHARE * brand_total, MIN_CASES)
    for level in reversed(config.LEVELS[:-1]):                       # Brand, Sub_Category, Category2, Total
        for series_id in hierarchy.ids:
            if hierarchy.level[series_id] == level:
                size[series_id] = sum(size[child] for child in hierarchy.children[series_id])
    return size


def icicle_data(hierarchy, final, routing):
    """Lists for the icicle, one entry per series in hierarchy order:
    ids, parents, labels, values (box size), colours, hover (name, level, true 13-week forecast, lane in words, method)."""
    totals = final.groupby("unique_id")["forecast"].sum()
    method = final.drop_duplicates("unique_id").set_index("unique_id")["method"]
    lane = routing.set_index("unique_id")["lane"]
    sku = routing.set_index("unique_id")["SKU"]
    size = box_sizes(hierarchy, totals)

    data = {"ids": [], "parents": [], "labels": [], "values": [], "colours": [], "hover": []}
    for series_id in hierarchy.ids:
        level = hierarchy.level[series_id]
        is_product = level == "Product"
        series_lane = lane[series_id] if is_product else None
        name = f"{sku[series_id]} ({short_name(series_id)})" if is_product else short_name(series_id)
        lane_text = config.LANE_WORDS[series_lane] if is_product else "upper level (adds up its products)"
        data["ids"].append(series_id)
        data["parents"].append(hierarchy.parent.get(series_id, ""))
        data["labels"].append(name)                                      # products: "SKU (code)" - two SKUs share a name
        data["values"].append(size[series_id])
        data["colours"].append(config.LANE_COLOURS[series_lane] if is_product else config.UPPER_COLOUR)
        data["hover"].append(f"<b>{name}</b><br>Level: {level}<br>13-week forecast: {totals[series_id]:,.1f} cases"
                             f"<br>Lane: {lane_text}<br>Method: {method[series_id]}")
    return data
