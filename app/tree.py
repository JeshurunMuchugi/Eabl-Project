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


# ---- Step 16: the circle tree (Apache ECharts), like the mock-up ----------------------------------------------
# Only the path from Total to the selected series is open; every other branch is closed. Circle size = square root
# of the 13-week forecast (so small products stay visible next to the Total); circles on the path are filled light
# blue; a product circle takes its lane colour; a series with a review flag gets a thick orange-red outline.
CIRCLE_MIN, CIRCLE_MAX = 8, 60              # circle diameter in pixels: smallest product ... the Total
ROW_PIXELS, MIN_HEIGHT = 26, 420            # tree height grows with the longest open column (Spirits/Premium: 25 brands)


def path_to(hierarchy, series_id):
    """['Total', 'Beer', 'Beer/Premium', ...] down to series_id."""
    path = [series_id]
    while path[0] in hierarchy.parent:
        path.insert(0, hierarchy.parent[path[0]])
    return path


def echarts_tree(hierarchy, final, routing, selected):
    """The nested tree ECharts draws, plus the height it needs. Each circle carries its series id ('uid') so a click
    can tell Shiny which series was chosen, and its hover text ('tip'), the same text as the box tree plus any flags."""
    boxes = icicle_data(hierarchy, final, routing)
    label = dict(zip(boxes["ids"], boxes["labels"]))
    colour = dict(zip(boxes["ids"], boxes["colours"]))
    hover = dict(zip(boxes["ids"], boxes["hover"]))
    totals = final.groupby("unique_id")["forecast"].sum()
    flags = final.drop_duplicates("unique_id").set_index("unique_id")["flag list"]
    path = path_to(hierarchy, selected)

    def node(series_id):
        on_path, kids = series_id in path, hierarchy.children[series_id]
        flag_text = flags[series_id] if isinstance(flags[series_id], str) and flags[series_id].strip() else ""
        fill = config.PATH_FILL if on_path else "#FFFFFF"
        item = {
            "name": label[series_id], "uid": series_id, "value": round(float(totals[series_id]), 1),
            "symbolSize": round(max(CIRCLE_MIN, CIRCLE_MAX * (max(float(totals[series_id]), 0) / float(totals["Total"])) ** 0.5), 1),
            "itemStyle": {"color": fill if kids else colour[series_id],
                          "borderColor": config.FLAG_COLOUR if flag_text else config.ACTUAL_COLOUR,
                          "borderWidth": 4 if flag_text else (3 if series_id == selected else 1.2)},
            "label": {"fontWeight": "bold" if series_id == selected else "normal"},
            "tip": hover[series_id] + (f"<br>⚑ Review: {flag_text}" if flag_text else ""),
        }
        if kids:
            item["collapsed"] = not on_path                              # only the path to the selection is open
            item["children"] = [node(kid) for kid in kids]
        return item

    longest = max(len(hierarchy.children[series_id]) for series_id in path)   # most circles in one open column
    return {"data": node("Total"), "height": max(MIN_HEIGHT, ROW_PIXELS * longest + 60)}
