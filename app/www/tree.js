// tree.js - draws the circle tree (Step 16) with Apache ECharts and tells Shiny which circle was clicked.
// The server sends the tree as a "tree_data" message (tree.echarts_tree in Python); a click sends "tree_click".
// It only draws what it is given: no numbers are worked out here.
(function () {
  let chart = null;

  function draw(message) {
    const box = document.getElementById("echarts_tree");
    if (!box || !window.echarts) return;
    box.style.height = message.height + "px";                 // taller when a long branch is open
    if (!chart) {
      chart = echarts.init(box);
      chart.on("click", function (p) {                        // a circle was clicked -> Shiny input "tree_click"
        if (p.data && p.data.uid) Shiny.setInputValue("tree_click", p.data.uid, { priority: "event" });
      });
      window.addEventListener("resize", function () { chart.resize(); });
    }
    chart.resize();
    chart.setOption({
      tooltip: { trigger: "item", formatter: function (p) { return p.data.tip; } },
      series: [{
        type: "tree", data: [message.data], orient: "LR",
        top: 16, bottom: 16, left: "9%", right: "26%",
        roam: false, expandAndCollapse: false, initialTreeDepth: -1, symbol: "circle",
        label: { position: "left", verticalAlign: "middle", align: "right", fontSize: 12, distance: 6 },
        leaves: { label: { position: "right", align: "left" } },
        lineStyle: { color: "#C9CFD8", width: 1.5, curveness: 0.5 },
        animationDuration: 600, animationDurationUpdate: 600, animationEasingUpdate: "cubicOut"
      }]
    });
  }

  Shiny.addCustomMessageHandler("tree_data", draw);
  // the tree was drawn while hidden (another page or the box view): fit it again when it is shown
  // (jQuery's $(document).on, because Shiny and Bootstrap announce these events through jQuery)
  $(document).on("shown.bs.tab", function () { if (chart) chart.resize(); });
  $(document).on("shiny:inputchanged", function (e) {
    if (e.name === "tree_view" && chart) setTimeout(function () { chart.resize(); }, 50);
  });
})();
