(function () {
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  if (!location.hash) window.scrollTo(0, 0);
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => [...document.querySelectorAll(s)];
  const reduced = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  const engine = window.LightEngine;
  const UP = window.UPBRINGING;
  const AB = window.ABLATION;

  function themeName() {
    return document.documentElement.classList.contains("light") ? "light" : "dark";
  }
  function palette() {
    return themeName() === "light"
      ? { txt: "#141413", mut: "#6b6862", fnt: "#8f8c85", line: "#1414130f", line2: "#14141330", acc: "#2f6bed", accSoft: "#2f6bed33", grey: "#a7a39a", card: "#f3f1ea", heat: ["#ebe8df", "#c9d7f7", "#7fa2ef", "#2f6bed"], tt: "#fffefbf5" }
      : { txt: "#ecebe8", mut: "#9b9993", fnt: "#74726c", line: "#f5f0e614", line2: "#f5f0e626", acc: "#5b8ef5", accSoft: "#2f6bed40", grey: "#8b8983", card: "#201f1c", heat: ["#24231f", "#1d3366", "#2a58c4", "#5b8ef5"], tt: "#24231ff5" };
  }
  function axis() {
    const C = palette();
    return { axisLine: { lineStyle: { color: C.line2 } }, axisTick: { show: false }, axisLabel: { color: C.mut, fontFamily: "JetBrains Mono", fontSize: 11 }, splitLine: { lineStyle: { color: C.line } } };
  }
  function tip() {
    const C = palette();
    return { backgroundColor: C.tt, borderColor: C.line2, textStyle: { color: C.txt, fontFamily: "Mona Sans", fontSize: 12 }, extraCssText: "border-radius:10px;box-shadow:0 10px 30px #0003", confine: true, triggerOn: "mousemove|click" };
  }
  function base() {
    return { backgroundColor: "transparent", animationDuration: reduced() ? 0 : 900, animationDurationUpdate: reduced() ? 0 : 400 };
  }

  const charts = {};
  function mount(id) {
    const el = document.getElementById(id);
    if (!el || !window.echarts) return null;
    const prev = echarts.getInstanceByDom(el);
    if (prev) prev.dispose();
    const chart = echarts.init(el);
    charts[id] = chart;
    return chart;
  }
  let wasNarrow = narrow();
  addEventListener("resize", () => {
    Object.values(charts).forEach((chart) => chart.resize());
    const now = narrow();
    if (now !== wasNarrow) { wasNarrow = now; restyle(); }
  });

  const NAME = {
    depth2_learned_minus_untrained: "depth-2 · learned − untrained",
    depth2_learned_minus_shuffled: "depth-2 · learned − shuffled",
    depth2_curiosity_on_minus_off: "depth-2 · curiosity on − off",
    society_minus_single_curious: "society − one searcher",
    depth1_learned_minus_untrained: "depth-1 · learned − untrained",
    depth1_learned_minus_shuffled: "depth-1 · learned − shuffled",
    geo_tasks_geo_minus_colour: "geo tasks · geo − colour",
    geo_tasks_geo_minus_object: "geo tasks · geo − object",
    colour_tasks_colour_minus_geo: "colour tasks · colour − geo",
    colour_tasks_colour_minus_object: "colour tasks · colour − object",
    object_tasks_object_minus_geo: "object tasks · object − geo",
    object_tasks_object_minus_colour: "object tasks · object − colour",
    society_minus_best_single: "society − best single (mixed)",
    society_minus_generalist: "society − generalist",
  };

  function narrow() { return innerWidth < 760; }
  function drawFig1() {
    const C = palette();
    const AX = axis();
    const n = narrow();
    const learned = AB.contrasts.find((row) => row.name === "depth2_learned_minus_untrained");
    const shuffled = AB.contrasts.find((row) => row.name === "depth2_learned_minus_shuffled");
    const rows = [
      { name: "Learned", value: learned.left_solved },
      { name: "Untrained", value: learned.right_solved },
      { name: "Shuffled", value: shuffled.right_solved },
    ];
    const chart = mount("fig1");
    if (!chart) return;
    chart.setOption(Object.assign({}, base(), {
      tooltip: Object.assign({}, tip(), { formatter: (p) => "<b>" + p.name + "</b><br><span style=\"font-family:JetBrains Mono\">" + p.value + "/" + learned.n + " hidden-test solves</span>" }),
      grid: { left: n ? 78 : 90, right: n ? 48 : 60, top: 6, bottom: 24 },
      xAxis: Object.assign({}, AX, { type: "value", max: learned.n }),
      yAxis: Object.assign({}, AX, { type: "category", inverse: true, data: rows.map((row) => row.name), axisLabel: Object.assign({}, AX.axisLabel, { fontFamily: "Mona Sans", fontSize: 13, color: C.txt }), splitLine: { show: false } }),
      series: [{
        type: "bar",
        barWidth: 22,
        data: rows.map((row, index) => ({ value: row.value, itemStyle: { color: index === 0 ? C.acc : C.grey } })),
        itemStyle: { borderRadius: [0, 4, 4, 0] },
        label: { show: true, position: "right", color: C.txt, fontFamily: "JetBrains Mono", fontSize: 12, formatter: (p) => p.value + "/" + learned.n },
      }],
    }), true);
  }

  function drawFig2() {
    const C = palette();
    const AX = axis();
    const n = narrow();
    const subs = ["geo", "colour", "object", "mixed", "noisy"];
    const fams = ["geo", "colour", "object", "cross"];
    const data = [];
    subs.forEach((subject, y) => fams.forEach((family, x) => data.push([x, y, UP.matrix[subject][family].solved])));
    const chart = mount("fig2");
    if (!chart) return;
    chart.setOption(Object.assign({}, base(), {
      tooltip: Object.assign({}, tip(), { formatter: (p) => "<b>" + subs[p.value[1]] + "</b> on <b>" + fams[p.value[0]] + "</b> tasks<br><span style=\"font-family:JetBrains Mono\">" + p.value[2] + " / 16 solved</span>" }),
      grid: { left: n ? 58 : 70, right: n ? 8 : 110, top: 6, bottom: n ? 48 : 30 },
      xAxis: Object.assign({}, AX, { type: "category", data: fams, splitLine: { show: false }, axisLabel: Object.assign({}, AX.axisLabel, { fontFamily: "Mona Sans", fontSize: 13, color: C.txt }) }),
      yAxis: Object.assign({}, AX, { type: "category", data: subs, inverse: true, splitLine: { show: false }, axisLabel: Object.assign({}, AX.axisLabel, { fontFamily: "Mona Sans", fontSize: 13, color: C.txt }) }),
      visualMap: n
        ? { min: 0, max: 16, orient: "horizontal", left: "center", bottom: 0, itemWidth: 10, itemHeight: 110, text: ["16", "0"], textStyle: { color: C.mut, fontFamily: "JetBrains Mono", fontSize: 10 }, inRange: { color: C.heat } }
        : { min: 0, max: 16, orient: "vertical", right: 10, top: "middle", itemWidth: 10, itemHeight: 150, text: ["16", "0"], textStyle: { color: C.mut, fontFamily: "JetBrains Mono", fontSize: 10 }, inRange: { color: C.heat } },
      series: [{
        type: "heatmap",
        data: data,
        label: { show: true, formatter: (p) => (p.value[2] >= 10 ? "{d|" : "{l|") + p.value[2] + "}", rich: { d: { color: "#fff", fontFamily: "JetBrains Mono", fontSize: 13, fontWeight: 600 }, l: { color: C.txt, fontFamily: "JetBrains Mono", fontSize: 13 } } },
        itemStyle: { borderColor: C.card, borderWidth: 3, borderRadius: 6 },
        emphasis: { itemStyle: { borderColor: C.txt, borderWidth: 2 } },
      }],
    }), true);
  }

  let fig3mode = "upbringing";
  function drawFig3() {
    const C = palette();
    const AX = axis();
    const n = narrow();
    const rows = (fig3mode === "ablation" ? AB.contrasts : UP.contrasts).slice().reverse();
    const cats = rows.map((row) => NAME[row.name] || row.name);
    const chart = mount("fig3");
    if (!chart) return;
    chart.setOption(Object.assign({}, base(), {
      tooltip: Object.assign({}, tip(), { formatter: (p) => { const row = rows[p.value[0]]; return "<b>" + cats[p.value[0]] + "</b><br><span style=\"font-family:JetBrains Mono\">" + row.left_solved + "/" + row.n + " vs " + row.right_solved + "/" + row.n + "<br>Δ " + (+row.diff_pp).toFixed(2) + " pp · [" + (+row.ci_low_pp).toFixed(2) + ", " + (+row.ci_high_pp).toFixed(2) + "]<br>" + (row.clears ? "clears" : "does not clear") + "</span>"; } }),
      grid: { left: n ? 118 : 220, right: 12, top: 8, bottom: 28 },
      xAxis: Object.assign({}, AX, { type: "value", min: -20, max: 100 }),
      yAxis: Object.assign({}, AX, { type: "category", data: cats, splitLine: { show: false }, axisLabel: Object.assign({}, AX.axisLabel, { fontFamily: "Mona Sans", fontSize: n ? 10.5 : 12.5, color: C.txt, width: n ? 108 : 200, overflow: "truncate" }) }),
      series: [{
        type: "custom",
        data: rows.map((row, index) => [index, +row.ci_low_pp, +row.ci_high_pp, +row.diff_pp, row.clears ? 1 : 0]),
        encode: { y: 0, x: [1, 2] },
        renderItem: (params, api) => {
          const y = api.value(0);
          const lo = api.coord([api.value(1), y]);
          const hi = api.coord([api.value(2), y]);
          const pt = api.coord([api.value(3), y]);
          const ok = api.value(4);
          const col = ok ? C.acc : C.grey;
          const hh = api.size([0, 1])[1] * 0.34;
          return { type: "group", children: [
            { type: "rect", shape: { x: lo[0], y: lo[1] - hh / 2, width: Math.max(2, hi[0] - lo[0]), height: hh, r: 4 }, style: { fill: ok ? C.accSoft : C.line2 } },
            { type: "line", shape: { x1: lo[0], y1: lo[1] - hh / 2, x2: lo[0], y2: lo[1] + hh / 2 }, style: { stroke: col, lineWidth: 1.5 } },
            { type: "line", shape: { x1: hi[0], y1: hi[1] - hh / 2, x2: hi[0], y2: hi[1] + hh / 2 }, style: { stroke: col, lineWidth: 1.5 } },
            { type: "circle", shape: { cx: pt[0], cy: pt[1], r: 5 }, style: { fill: C.card, stroke: col, lineWidth: 2 } },
          ] };
        },
        markLine: { silent: true, symbol: "none", lineStyle: { color: C.line2, type: "dashed" }, data: [{ xAxis: 0 }], label: { show: false } },
      }],
    }), true);
  }

  const drawers = { fig1: drawFig1, fig2: drawFig2, fig3: drawFig3 };
  const started = {};
  function startChart(id) {
    if (started[id] || !drawers[id]) return;
    started[id] = true;
    drawers[id]();
  }
  function restyle() {
    Object.keys(started).forEach((id) => drawers[id]());
  }

  $$("#ctoggle button").forEach((button) => {
    button.addEventListener("click", () => {
      $$("#ctoggle button").forEach((other) => other.classList.toggle("on", other === button));
      fig3mode = button.dataset.k;
      if (started.fig3) drawFig3();
    });
  });

  const themeButton = $("#theme");
  function syncTheme(next, persist) {
    document.documentElement.classList.remove("dark", "light");
    document.documentElement.classList.add(next);
    if (themeButton) {
      const light = next === "light";
      themeButton.setAttribute("aria-pressed", light ? "true" : "false");
      themeButton.setAttribute("aria-label", light ? "Switch to dark theme" : "Switch to light theme");
    }
    if (persist) {
      try { localStorage.setItem("light-agents-theme", next); } catch (error) { /* private mode */ }
    }
    restyle();
  }
  if (themeButton) {
    themeButton.addEventListener("click", () => syncTheme(themeName() === "dark" ? "light" : "dark", true));
    syncTheme(themeName(), false);
  }
  const menuBtn = $("#menubtn");
  const siteNav = $("#sitenav");
  function closeMenu() {
    if (!siteNav) return;
    siteNav.classList.remove("open");
    if (menuBtn) menuBtn.setAttribute("aria-expanded", "false");
  }
  if (menuBtn && siteNav) {
    menuBtn.addEventListener("click", () => {
      const open = siteNav.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".nav")) closeMenu();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeMenu();
    });
  }
  const contents = document.querySelector(".contents");
  const wideContents = matchMedia("(min-width: 1221px)");
  function syncContents() { if (contents && wideContents.matches) contents.open = true; }
  wideContents.addEventListener("change", syncContents);
  $$("#toc a").forEach((link) => link.addEventListener("click", () => {
    if (contents && !wideContents.matches) contents.open = false;
  }));

  const reveals = $$(".rv");
  if (reduced() || !("IntersectionObserver" in window)) {
    reveals.forEach((el) => el.classList.add("in"));
    Object.keys(drawers).forEach(startChart);
  } else {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("in");
        const chart = entry.target.querySelector(".chart");
        if (chart) startChart(chart.id);
        io.unobserve(entry.target);
      });
    }, { threshold: 0.12 });
    reveals.forEach((el) => io.observe(el));
  }

  const links = $$("#toc a");
  const targets = links.map((link) => document.querySelector(link.getAttribute("href")));
  function spy() {
    const y = scrollY + 150;
    let current = 0;
    targets.forEach((target, index) => {
      if (target && target.getBoundingClientRect().top + scrollY <= y) current = index;
    });
    links.forEach((link, index) => link.classList.toggle("on", index === current));
    const art = $(".article");
    const prog = $("#prog");
    if (art && prog) {
      const top = art.offsetTop;
      const height = Math.max(1, art.offsetHeight - innerHeight);
      prog.style.width = Math.max(0, Math.min(100, (scrollY - top + 200) / height * 100)) + "%";
    }
  }
  addEventListener("scroll", spy, { passive: true });
  spy();

  const pop = $("#pop");
  let pinned = null;
  function showPop(node) {
    const note = node.classList.contains("fn");
    const html = note ? window.FN[node.dataset.fn] : window.REFS[node.dataset.ref];
    pop.innerHTML = "<span class=\"pk\">" + (note ? "Note " + node.dataset.fn : "Reference [" + node.dataset.ref + "]") + "</span>" + html;
    const rect = node.getBoundingClientRect();
    const width = Math.min(360, innerWidth - 24);
    pop.style.position = "fixed";
    pop.style.maxWidth = width + "px";
    pop.style.left = Math.max(12, Math.min(rect.left, innerWidth - width - 12)) + "px";
    const below = rect.bottom + 8;
    pop.style.top = (below + 140 > innerHeight ? Math.max(8, rect.top - 120) : below) + "px";
    pop.classList.add("on");
  }
  $$("sup.fn, sup.cite").forEach((node) => {
    node.addEventListener("mouseenter", () => { if (!pinned) showPop(node); });
    node.addEventListener("mouseleave", () => { if (!pinned) pop.classList.remove("on"); });
    node.addEventListener("focusin", () => showPop(node));
    node.addEventListener("focusout", () => { if (!pinned) pop.classList.remove("on"); });
    node.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (pinned === node) { pinned = null; pop.classList.remove("on"); return; }
      pinned = node;
      showPop(node);
    });
  });
  document.addEventListener("click", (event) => {
    if (event.target.closest("sup.fn, sup.cite")) return;
    pinned = null;
    pop.classList.remove("on");
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { pinned = null; pop.classList.remove("on"); }
  });

  const BIBTEX = "@misc{tiwari2026lightagents,\n  author = {Tiwari, Utkarsh},\n  title = {Light agents: growing small learners, then letting a society settle tasks on {NEAR}},\n  year = {2026},\n  month = nov,\n  howpublished = {NEAR Hackathon, AI Swarms track},\n  note = {Testnet demonstration, not an ARC-AGI score. Contract: lightswarm16771.testnet}\n}\n";
  const cite = $("#cite");
  if (cite) {
    cite.addEventListener("click", async () => {
      const label = cite.textContent;
      let ok = false;
      try {
        await navigator.clipboard.writeText(BIBTEX);
        ok = true;
      } catch (error) {
        const area = document.createElement("textarea");
        area.value = BIBTEX;
        area.setAttribute("readonly", "");
        area.style.position = "fixed";
        area.style.left = "-999px";
        document.body.appendChild(area);
        area.select();
        try { ok = document.execCommand("copy"); } catch (err) { ok = false; }
        area.remove();
      }
      cite.textContent = ok ? "Copied" : "Copy failed";
      setTimeout(() => { cite.textContent = label; }, 1600);
    });
  }

  const ARC = ["#16171b", "#1e6fe0", "#e5484d", "#2ea44f", "#f5c518", "#9aa0a6", "#d63ac6", "#f08a24", "#68c2f0", "#8b1e2b"];
  const NAMES = ["geo", "colour", "object", "mixed", "noisy"];
  const task = (UP.examples || []).find((item) => item.id === "geo-00") || (UP.examples || [])[0];
  const mini = $("#mini");
  const runButton = $("#runmini");
  if (mini && task) {
    const rows = String(task.test_input).split(";");
    const width = rows[0].length;
    const count = rows.join("").length;
    const label = $("#fig4label");
    if (label) label.textContent = "Frozen " + task.id + " · " + task.program.join(" · ");
    mini.innerHTML = NAMES.map((name) => "<div class=\"lc\"><span>" + name + "</span><span class=\"gr\" id=\"mg-" + name + "\" style=\"grid-template-columns:repeat(" + width + ",9px)\">" + "<i></i>".repeat(count) + "</span><span class=\"op\" id=\"mo-" + name + "\">idle</span><span class=\"pill\" id=\"mp-" + name + "\">—</span></div>").join("");
    const wait = (ms) => new Promise((resolve) => setTimeout(resolve, reduced() ? 0 : ms));
    let models = null;
    let loading = null;
    function loadModels() {
      if (loading) return loading;
      loading = Promise.all(NAMES.map((name) => fetch("weights/" + name + ".json").then((res) => {
        if (!res.ok) throw new Error(name + " weights " + res.status);
        return res.json();
      }))).then((packed) => {
        models = {};
        packed.forEach((item) => { models[item.name] = engine.decodeWeights(item); });
        return models;
      });
      return loading;
    }
    let busy = false;
    async function animateOne(name, found, delay) {
      await wait(delay);
      const beam = found.ranking.slice(0, 6);
      const op = $("#mo-" + name);
      const pill = $("#mp-" + name);
      pill.textContent = "searching";
      pill.className = "pill";
      for (let i = 0; i < beam.length; i += 1) {
        op.textContent = beam[i].name;
        await wait(180);
      }
      if (found.program) op.textContent = found.program.join(" · ");
      else op.textContent = "no program";
      const cells = [...$("#mg-" + name).children];
      const digits = (found.predicted || "").replace(/;/g, "");
      if (found.predicted && digits.length === cells.length) {
        for (let i = 0; i < cells.length; i += 1) {
          cells[i].style.background = ARC[+digits[i]] || palette().card;
          await wait(24);
        }
      }
      pill.textContent = found.correct ? "✓ match" : "✕ miss";
      pill.className = "pill " + (found.correct ? "ok" : "no");
      return found.correct;
    }
    runButton.addEventListener("click", async () => {
      if (busy) return;
      busy = true;
      runButton.disabled = true;
      const stat = $("#ministat");
      stat.textContent = "loading weights";
      try {
        await loadModels();
        stat.textContent = "searching · beam 6 · " + task.id;
        const results = NAMES.map((name) => engine.predict(models[name], task, { beam: 6, budget: 48, archive: new Set() }));
        const flags = await Promise.all(results.map((found, index) => animateOne(NAMES[index], found, index * 140)));
        const hits = flags.filter(Boolean).length;
        stat.textContent = hits + " of 5 match the hidden grid · " + task.id + " · " + task.program.join(" · ");
      } catch (error) {
        stat.textContent = error.message;
      }
      runButton.disabled = false;
      busy = false;
    });
  }
})();
