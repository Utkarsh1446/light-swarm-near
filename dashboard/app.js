(function () {
  const Qearly = new URLSearchParams(location.search);
  if (Qearly.get("tab") === "paper") {
    location.replace("paper.html");
    return;
  }
  const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const Q = new URLSearchParams(location.search);
  const $ = (s) => document.querySelector(s);
  const $$ = (s) => [...document.querySelectorAll(s)];
  const fmt = (n) => Math.round(n).toLocaleString("en-US");
  const ARC = ["#16171b", "#1e6fe0", "#e5484d", "#2ea44f", "#f5c518", "#9aa0a6", "#d63ac6", "#f08a24", "#68c2f0", "#8b1e2b"];
  const NAMES = ["geo", "colour", "object", "mixed", "noisy"];
  const COL = { geo: "#e2ded5", colour: "#b3ada1", object: "#8a857b", mixed: "#5b8ef5", noisy: "#65615a" };
  const NICE = { geo: "Geo", colour: "Colour", object: "Object", mixed: "Mixed", noisy: "Noisy" };
  const FAM_EASY = { geo: "shapes", colour: "colours", object: "things", cross: "mixed", trap: "a tricky one" };
  function plain() { return document.documentElement.classList.contains("simple"); }
  function lightTheme() { return document.documentElement.classList.contains("light"); }
  function palette() {
    return lightTheme()
      ? { txt: "#141413", mut: "#5c5954", line: "#14141314", line2: "#14141330", card: "#fffefb", heat: ["#ebe8df", "#c9d7f7", "#7fa2ef", "#2f6bed"], tt: "#fffefbf5", axis: "#5c5954" }
      : { txt: "#ecebe8", mut: "#9b9993", line: "#f5f0e614", line2: "#f5f0e626", card: "#201f1c", heat: ["#24231f", "#1d3366", "#2a58c4", "#5b8ef5"], tt: "#201f1cf5", axis: "#8b8983" };
  }
  function axis() {
    const C = palette();
    return { axisLine: { lineStyle: { color: C.line2 } }, axisTick: { show: false }, axisLabel: { color: C.axis, fontFamily: "JetBrains Mono", fontSize: 11 }, splitLine: { lineStyle: { color: C.line } } };
  }
  function tip() {
    const C = palette();
    return { backgroundColor: C.tt, borderColor: C.line2, textStyle: { color: C.txt, fontFamily: "Mona Sans", fontSize: 12 }, extraCssText: "border-radius:10px;box-shadow:0 10px 30px #0003", confine: true, triggerOn: "mousemove|click" };
  }
  const BASE = { backgroundColor: "transparent", textStyle: { fontFamily: "Mona Sans" }, animationDuration: RM ? 0 : 900, animationDurationUpdate: RM ? 0 : 350 };
  const engine = window.LightEngine;
  const UP = window.UPBRINGING;
  const AB = window.ABLATION;
  const SW = window.SWARM_DATA;
  const charts = {};

  function chart(id) {
    const el = document.getElementById(id);
    if (!el || !window.echarts) return null;
    const existing = echarts.getInstanceByDom(el);
    if (existing) return existing;
    const c = echarts.init(el, null, { renderer: "canvas" });
    addEventListener("resize", () => c.resize());
    charts[id] = c;
    return c;
  }

  const rv = $$(".rv");
  if (RM || !("IntersectionObserver" in window)) rv.forEach((e) => e.classList.add("in"));
  else {
    const io = new IntersectionObserver((es) => es.forEach((e, i) => {
      if (e.isIntersecting) { setTimeout(() => e.target.classList.add("in"), i * 70); io.unobserve(e.target); }
    }), { threshold: 0.08 });
    rv.forEach((e) => io.observe(e));
  }
  if (RM) { const a = $("#heroart"); a && a.pauseAnimations && a.pauseAnimations(); }

  function countUp(el, to, dur, dec) {
    dur = dur || 1100;
    dec = dec || 0;
    if (RM) { el.textContent = dec ? Number(to).toFixed(dec) : fmt(to); return; }
    const t0 = performance.now();
    (function f(t) {
      const k = Math.min(1, (t - t0) / dur);
      const e = 1 - Math.pow(1 - k, 3);
      const v = to * e;
      el.textContent = dec ? v.toFixed(dec) : fmt(v);
      if (k < 1) requestAnimationFrame(f);
    })(t0);
  }
  $$("[data-count]").forEach((el) => {
    const io = new IntersectionObserver((es) => {
      if (es[0].isIntersecting) { countUp(el, +el.dataset.count); io.disconnect(); }
    });
    io.observe(el);
  });

  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  function toTop() {
    window.scrollTo(0, 0);
  }
  function showTab(name, mode) {
    if (!document.querySelector('[data-view="' + name + '"]')) name = "overview";
    $$("[data-view]").forEach((view) => { view.hidden = view.getAttribute("data-view") !== name; });
    $$(".tabs [data-tab]").forEach((tab) => tab.classList.toggle("on", tab.getAttribute("data-tab") === name));
    const focused = document.activeElement;
    if (focused && focused.closest && focused.closest("[data-view][hidden]")) focused.blur();
    const url = new URL(location.href);
    url.searchParams.set("tab", name);
    url.hash = "";
    if (mode === "push") {
      const current = new URLSearchParams(location.search).get("tab") || "overview";
      if (current !== name) history.pushState({ tab: name }, "", url);
      else history.replaceState({ tab: name }, "", url);
    } else if (mode !== "none") {
      history.replaceState({ tab: name }, "", url);
    }
    toTop();
    requestAnimationFrame(() => {
      Object.values(charts).forEach((c) => c.resize());
      toTop();
    });
  }
  $$("[data-tab]").forEach((el) => el.addEventListener("click", (event) => {
    if (el.id === "nav-run") return;
    event.preventDefault();
    closeMenu();
    showTab(el.getAttribute("data-tab"), "push");
  }));
  addEventListener("popstate", () => {
    showTab(new URLSearchParams(location.search).get("tab") || "overview", "none");
  });
  addEventListener("pageshow", () => toTop());
  $("#nav-run").addEventListener("click", (event) => {
    event.preventDefault();
    closeMenu();
    showTab("playground", "push");
    $("#run").click();
  });
  const menuBtn = $("#menubtn");
  const siteNav = $("#sitenav");
  function closeMenu() {
    if (!siteNav) return;
    siteNav.classList.remove("open");
    if (menuBtn) menuBtn.setAttribute("aria-expanded", "false");
  }
  const themeButton = $("#theme");
  function applyTheme(next, persist) {
    document.documentElement.classList.remove("dark", "light");
    document.documentElement.classList.add(next);
    if (themeButton) {
      const light = next === "light";
      themeButton.setAttribute("aria-pressed", light ? "true" : "false");
      themeButton.setAttribute("aria-label", light ? "Switch to dark theme" : "Switch to light theme");
    }
    if (persist) {
      try { localStorage.setItem("light-agents-theme", next); } catch (e) { /* private mode */ }
    }
  }
  if (themeButton) {
    applyTheme(document.documentElement.classList.contains("light") ? "light" : (document.documentElement.classList.contains("dark") ? "dark" : "dark"), false);
    themeButton.addEventListener("click", () => {
      const next = document.documentElement.classList.contains("light") ? "dark" : "light";
      applyTheme(next, true);
      dispatchEvent(new Event("themechange"));
    });
  }
  if (menuBtn && siteNav) {
    menuBtn.addEventListener("click", () => {
      const open = siteNav.classList.toggle("open");
      menuBtn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    siteNav.addEventListener("click", (event) => {
      if (event.target.closest("a")) closeMenu();
    });
    document.addEventListener("click", (event) => {
      if (!event.target.closest(".nav")) closeMenu();
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeMenu();
    });
  }

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
  const PLAIN_NAME = {
    depth2_learned_minus_untrained: "Practised vs never practised",
    depth2_learned_minus_shuffled: "Practised vs scrambled puzzles",
    depth2_curiosity_on_minus_off: "Extra curiosity on vs off",
    society_minus_single_curious: "The team vs one robot",
    depth1_learned_minus_untrained: "A little practice vs none",
    depth1_learned_minus_shuffled: "A little practice vs scrambled",
    geo_tasks_geo_minus_colour: "Shape puzzles · Geo vs Colour",
    geo_tasks_geo_minus_object: "Shape puzzles · Geo vs Object",
    colour_tasks_colour_minus_geo: "Colour puzzles · Colour vs Geo",
    colour_tasks_colour_minus_object: "Colour puzzles · Colour vs Object",
    object_tasks_object_minus_geo: "Thing puzzles · Object vs Geo",
    object_tasks_object_minus_colour: "Thing puzzles · Object vs Colour",
    society_minus_best_single: "The team vs best robot (Mixed)",
    society_minus_generalist: "The team vs one all-round robot",
  };
  const subs = NAMES;
  const fams = ["geo", "colour", "object", "cross"];

  function narrow() { return innerWidth < 760; }
  function heatOption() {
    const d = [];
    const n = narrow();
    const C = palette();
    const xLabels = plain() ? fams.map((f) => FAM_EASY[f] || f) : fams;
    const yLabels = plain() ? subs.map((s) => NICE[s]) : subs;
    subs.forEach((s, y) => fams.forEach((f, x) => d.push([x, y, UP.matrix[s][f].solved])));
    return Object.assign({}, BASE, {
      tooltip: Object.assign({}, tip(), { formatter: (p) => plain()
        ? "<b>" + NICE[subs[p.value[1]]] + "</b> on <b>" + (FAM_EASY[fams[p.value[0]]] || fams[p.value[0]]) + "</b> puzzles<br><span style=\"font-family:JetBrains Mono\">" + p.value[2] + " of 16 solved</span>"
        : "<b>" + subs[p.value[1]] + "</b> learner on <b>" + fams[p.value[0]] + "</b> tasks<br><span style=\"font-family:JetBrains Mono\">" + p.value[2] + " / 16 solved</span>" }),
      grid: { left: n ? 58 : 72, right: 12, top: 8, bottom: n ? 48 : 56 },
      xAxis: Object.assign({ type: "category", data: xLabels, splitArea: { show: false } }, axis(), { splitLine: { show: false } }),
      yAxis: Object.assign({ type: "category", data: yLabels, inverse: true }, axis(), { splitLine: { show: false } }),
      visualMap: { min: 0, max: 16, calculable: false, orient: "horizontal", left: "center", bottom: 4, itemWidth: 10, itemHeight: n ? 110 : 180, text: ["16", "0"], textStyle: { color: C.axis, fontFamily: "JetBrains Mono", fontSize: 10 }, inRange: { color: C.heat } },
      series: [{ type: "heatmap", data: d, label: { show: true, formatter: (p) => (p.value[2] >= 10 ? "{d|" : "{l|") + p.value[2] + "}", rich: { d: { color: "#ffffff", fontFamily: "JetBrains Mono", fontSize: 12, fontWeight: 600 }, l: { color: C.txt, fontFamily: "JetBrains Mono", fontSize: 12 } } }, itemStyle: { borderColor: C.card, borderWidth: 3, borderRadius: 6 }, emphasis: { itemStyle: { borderColor: C.txt, borderWidth: 2 } } }],
    });
  }
  function bindHeat(id) {
    const h = chart(id);
    if (!h) return;
    h.setOption(heatOption());
    h.on("click", (p) => {
      const family = fams[p.value[0]];
      $$("#fam span").forEach((s) => s.classList.toggle("on", s.dataset.f === family));
      const example = (UP.examples || []).find((item) => item.family === family);
      if (example) setTask(example);
      showTab("playground", "push");
    });
  }
  function drawCI(id, toggle, k) {
    const ci = chart(id);
    if (!ci) return;
    const n = narrow();
    const rows = (k === "ablation" ? AB.contrasts : UP.contrasts).slice().reverse();
    const cats = rows.map((r) => (plain() ? PLAIN_NAME[r.name] : NAME[r.name]) || r.name);
    const freeze = k === "ablation" ? AB.freeze_commit : UP.freeze_commit;
    const C = palette();
    ci.setOption(Object.assign({}, BASE, {
      tooltip: Object.assign({}, tip(), { trigger: "item", formatter: (p) => { const r = rows[p.value[0]]; const verdict = plain() ? (r.clears ? "a real win" : "not a sure win") : (r.clears ? "clears" : "does not clear"); const extra = plain() ? "" : "<br>" + freeze; return "<b>" + cats[p.value[0]] + "</b><br><span style=\"font-family:JetBrains Mono\">" + r.left_solved + "/" + r.n + " vs " + r.right_solved + "/" + r.n + "<br>Δ " + (+r.diff_pp).toFixed(2) + " pp · CI [" + (+r.ci_low_pp).toFixed(2) + ", " + (+r.ci_high_pp).toFixed(2) + "]<br>" + verdict + extra + "</span>"; } }),
      grid: { left: n ? 128 : 220, right: 16, top: 8, bottom: 28 },
      xAxis: Object.assign({ type: "value", min: -20, max: 110 }, axis()),
      yAxis: Object.assign({ type: "category", data: cats }, axis(), { splitLine: { show: false }, axisLabel: Object.assign({}, axis().axisLabel, { color: C.txt, fontFamily: "Mona Sans", fontSize: n ? 10.5 : 12, width: n ? 118 : 200, overflow: "truncate" }) }),
      series: [{
        type: "custom",
        data: rows.map((r, i) => [i, +r.ci_low_pp, +r.ci_high_pp, +r.diff_pp, r.clears ? 1 : 0]),
        encode: { y: 0, x: [1, 2] },
        renderItem: (p, api) => {
          const y = api.value(0);
          const lo = api.coord([api.value(1), y]);
          const hi = api.coord([api.value(2), y]);
          const pt = api.coord([api.value(3), y]);
          const c = api.value(4) ? "#5b8ef5" : "#8b8983";
          const hh = api.size([0, 1])[1] * 0.32;
          return { type: "group", children: [
            { type: "rect", shape: { x: lo[0], y: lo[1] - hh / 2, width: Math.max(2, hi[0] - lo[0]), height: hh, r: 4 }, style: { fill: api.value(4) ? "#2f6bed40" : "#f5f0e614" } },
            { type: "line", shape: { x1: lo[0], y1: lo[1] - hh / 2, x2: lo[0], y2: lo[1] + hh / 2 }, style: { stroke: c, lineWidth: 1.5 } },
            { type: "line", shape: { x1: hi[0], y1: hi[1] - hh / 2, x2: hi[0], y2: hi[1] + hh / 2 }, style: { stroke: c, lineWidth: 1.5 } },
            { type: "circle", shape: { cx: pt[0], cy: pt[1], r: 5 }, style: { fill: "#201f1c", stroke: c, lineWidth: 2 } },
          ] };
        },
        markLine: { silent: true, symbol: "none", lineStyle: { color: "#f5f0e640", type: "dashed" }, data: [{ xAxis: 0 }], label: { show: false } },
      }],
    }), true);
    $$(toggle + " span").forEach((s) => {
      s.onclick = () => {
        $$(toggle + " span").forEach((o) => o.classList.remove("on"));
        s.classList.add("on");
        drawCI(id, toggle, s.dataset.k);
      };
    });
  }

  const NOTES = {
    geo: "1,600 geometry programs. Curiosity 0.",
    colour: "1,600 recolour programs. Curiosity 0.",
    object: "1,600 object programs. Curiosity 0.",
    mixed: "1,600 programs from the whole catalogue. Curiosity 1.5.",
    noisy: "200 mixed programs. A quarter of the labels are moved. Curiosity 0.",
  };
  const NOTES_EASY = {
    geo: "Loves shapes. Tries flips and turns first.",
    colour: "Loves colours. Tries repainting first.",
    object: "Loves things. Looks for the blobs on the grid.",
    mixed: "A bit of everything, and extra curious about new moves.",
    noisy: "Grew up in a noisy house, learning from messy examples.",
  };
  const host = $("#subjects");
  if (host && UP) {
    NAMES.forEach((name) => {
      const card = document.createElement("article");
      card.className = "card";
      card.tabIndex = 0;
      const bars = fams.map((family) => {
        const cell = UP.matrix[name][family];
        const pct = Math.round(100 * cell.solved / cell.n);
        return "<div style=\"display:grid;grid-template-columns:72px 1fr 42px;gap:8px;align-items:center;margin-top:6px;font:400 12px var(--mono);color:var(--muted)\"><span><span class=\"tech\">" + family + "</span><span class=\"easy\">" + (FAM_EASY[family] || family) + "</span></span><span style=\"height:4px;background:var(--surface3);border-radius:4px;overflow:hidden\"><i style=\"display:block;height:100%;width:" + pct + "%;background:#5b8ef5\"></i></span><span>" + cell.solved + "/" + cell.n + "</span></div>";
      }).join("");
      card.innerHTML = "<div class=\"hd\" style=\"display:flex;gap:10px;align-items:flex-start\"><span data-bot=\"" + name + "\" data-size=\"40\" data-k=\"" + NAMES.indexOf(name) + "\"></span><div><h3><span class=\"tech\">" + name + "</span><span class=\"easy\">" + NICE[name] + "</span></h3><p><span class=\"tech\">" + NOTES[name] + "</span><span class=\"easy\">" + NOTES_EASY[name] + "</span></p></div></div><div class=\"bd\"><div style=\"font:500 28px/1 var(--display);letter-spacing:-.03em\">" + UP.params_per_subject.toLocaleString("en-US") + "</div><div class=\"muted\" style=\"font-size:12px;margin:6px 0 10px\"><span class=\"tech\">parameters</span><span class=\"easy\">brain knobs</span></div>" + bars + "</div>" + '<div class="try"><span class="k">Try it</span><span><span class="tech">Click for the training curve.</span><span class="easy">Tap to see how it practised.</span></span></div>';
      const open = () => showCurve(name);
      card.addEventListener("click", open);
      card.addEventListener("keydown", (event) => { if (event.key === "Enter") open(); });
      host.appendChild(card);
    });
  }
  async function showCurve(name) {
    const win = $("#curve-win");
    win.hidden = false;
    $("#curve-name").textContent = name;
    const meta = await fetch("weights/meta.json").then((res) => res.json());
    const series = meta.subjects.find((item) => item.name === name).epoch_loss;
    const c = chart("curve");
    c.setOption(Object.assign({}, BASE, {
      tooltip: tip(),
      grid: { left: 44, right: 12, top: 16, bottom: 28 },
      xAxis: Object.assign({ type: "category", data: series.map((_, i) => "e" + (i + 1)) }, axis()),
      yAxis: Object.assign({ type: "value" }, axis()),
      series: [{ type: "line", smooth: 0.2, data: series, lineStyle: { color: "#5b8ef5", width: 2 }, itemStyle: { color: "#5b8ef5" }, areaStyle: { color: "#2f6bed33" } }],
    }), true);
    c.resize();
  }

  function gridHTML(text, cell) {
    cell = cell || 15;
    const rows = String(text || "").split(";");
    const w = rows[0] ? rows[0].length : 1;
    const cells = rows.join("").split("").map((ch) => '<i style="background:' + (ARC[+ch] || "#333") + ";width:" + cell + "px;height:" + cell + 'px"></i>').join("");
    return '<span class="gr" style="grid-template-columns:repeat(' + w + "," + cell + 'px)">' + cells + "</span>";
  }
  function pair(text, caption) {
    return '<div class="pair">' + gridHTML(text) + "<span>" + caption + "</span></div>";
  }
  let current = null;
  let models = null;
  let modelPromise = null;
  let runPhase = "idle";
  let runHits = 0;
  let runCuriosity = 1.5;
  let runNote = "";
  let lastFlags = null;
  let stageName = "Upbringing";
  function paintRun() {
    const log = $("#runlog");
    const st = $("#runst");
    if (!log || !st) return;
    if (runPhase === "error") {
      log.innerHTML = '<span class="no">' + runNote + "</span>";
      return;
    }
    if (runPhase === "ready") {
      log.innerHTML = plain()
        ? '<span class="p">›</span> a ' + (FAM_EASY[runNote] || runNote) + " puzzle is ready"
        : '<span class="p">›</span> ' + runNote + " task ready";
      st.innerHTML = '<span class="dot g"></span><span>ready</span>';
      return;
    }
    if (runPhase === "loading" || runPhase === "search") {
      log.innerHTML = plain()
        ? '<span class="p">›</span> five robots are guessing · keeping the best 6 · curiosity ' + runCuriosity.toFixed(1)
        : '<span class="p">›</span> five learners search · beam 6 · curiosity ' + runCuriosity.toFixed(1);
      const word = runPhase === "loading" ? (plain() ? "waking up" : "loading") : (plain() ? "guessing" : "searching");
      st.innerHTML = '<span class="dot" style="background:#8fb2f9"></span><span style="color:#8fb2f9">' + word + "</span>";
      return;
    }
    if (runPhase === "done") {
      log.innerHTML = plain()
        ? '<span class="p">›</span> <span class="t">' + runHits + " of 5 robots drew the right answer!</span>"
        : '<span class="p">›</span> <span class="t">' + runHits + " of 5 predictions match the hidden grid.</span> <span class=\"m\">answer revealed</span>";
      st.innerHTML = '<span class="dot"></span><span>' + runHits + (plain() ? " of 5 right" : " of 5 match") + "</span>";
    }
  }
  function paintBadges() {
    if (runPhase !== "done" || !lastFlags) return;
    NAMES.forEach((name, i) => {
      const ok = lastFlags[i];
      const label = ok ? (plain() ? "right" : "✓ match") : (plain() ? "miss" : "✕ miss");
      $("#R-" + name).innerHTML = '<span class="pill ' + (ok ? "a" : "r") + '">' + label + "</span>";
    });
  }
  function loadModels() {
    if (modelPromise) return modelPromise;
    modelPromise = Promise.all(NAMES.map((name) => fetch("weights/" + name + ".json").then((res) => {
      if (!res.ok) throw new Error(name + " " + res.status);
      return res.json();
    }))).then((packed) => {
      models = {};
      packed.forEach((item) => { models[item.name] = engine.decodeWeights(item); });
      return models;
    });
    return modelPromise;
  }
  function setTask(task) {
    current = task;
    const row = $("#demo-row");
    row.innerHTML = task.demos.map((demo, i) => pair(demo.in, "demo " + (i + 1) + " in") + pair(demo.out, "demo " + (i + 1) + " out")).join("")
      + pair(task.test_input, "test in")
      + '<div class="pair" id="ansbox" style="opacity:.35">' + gridHTML(task.test_output) + '<span style="color:#6f9bf7">hidden answer</span></div>';
    NAMES.forEach((name) => {
      $("#B-" + name).innerHTML = "<span>waiting…</span>";
      $("#P-" + name).style.width = "0";
      $("#Gwrap-" + name).innerHTML = "";
      $("#R-" + name).innerHTML = '<span class="pill">idle</span>';
    });
    runPhase = "ready";
    runNote = task.family;
    lastFlags = null;
    paintRun();
  }
  function family() { return $("#fam span.on").dataset.f; }
  $("#fam").addEventListener("click", (event) => {
    const span = event.target.closest("span");
    if (!span) return;
    $$("#fam span").forEach((s) => s.classList.remove("on"));
    span.classList.add("on");
  });
  $("#cur").addEventListener("input", () => { $("#curv").textContent = (+$("#cur").value).toFixed(1); });
  $("#gen").addEventListener("click", () => {
    try {
      const rng = new engine.PythonRandom(Number($("#seed").value) || 1);
      setTask(engine.packTask(engine.generateTask(family(), rng)));
    } catch (error) {
      runPhase = "error";
      runNote = error.message;
      paintRun();
    }
  });
  $("#frozen").addEventListener("click", () => {
    const example = (UP.examples || []).find((item) => item.family === family()) || UP.examples[0];
    if (example) setTask(example);
  });
  const STXT = {
    "Random init": "Seed 20261117. One Gaussian draw, shared by all five. 326,800 parameters each.",
    Upbringing: "geometry, colour, objects, mixed with curiosity, and a small noisy set.",
    Prior: "326,800 parameters. Three hidden layers. Ranks the 16 operations.",
    "Beam search": "beam of 6 over 16 operations; first program that fits the demos wins.",
    Answer: "the accepted program is applied to the test grid. Exact match or a miss.",
  };
  const STAGE_EASY = {
    "Random init": ["start", "All five robots start with the same brain, before any practice."],
    Upbringing: ["practice", "shapes, colours, things, a bit of everything with extra curiosity, and a few messy examples."],
    Prior: ["brain", "Each robot’s brain has 326,800 knobs, in three layers, and uses them to rank 16 moves."],
    "Beam search": ["guesses", "It tries a handful of moves, keeps its 6 best guesses, and stops at the first one that turns the examples into the right pictures."],
    Answer: ["answer", "That guess is drawn on the new picture. It matches the hidden answer, or it misses."],
  };
  function paintStage() {
    const box = $("#stagetxt");
    if (!box) return;
    if (plain()) {
      const pair = STAGE_EASY[stageName] || ["practice", ""];
      box.innerHTML = '<span class="p">' + pair[0] + "</span> · " + pair[1];
    } else {
      box.innerHTML = '<span class="p">' + stageName.toLowerCase() + "</span> · " + STXT[stageName];
    }
  }
  $$("#stages .stage").forEach((s) => s.addEventListener("click", () => {
    $$("#stages .stage").forEach((o) => o.classList.remove("on"));
    s.classList.add("on");
    stageName = s.textContent.trim();
    paintStage();
  }));
  const wait = (ms) => new Promise((resolve) => setTimeout(resolve, RM ? 0 : ms));
  let running = false;
  async function animateOne(name, found, delay) {
    await wait(delay);
    const beam = found.ranking.slice(0, 6);
    const B = $("#B-" + name);
    const P = $("#P-" + name);
    const R = $("#R-" + name);
    R.innerHTML = '<span class="pill c">searching</span>';
    B.innerHTML = "";
    for (let i = 0; i < beam.length; i += 1) {
      const chip = document.createElement("span");
      chip.textContent = beam[i].name;
      chip.className = "try";
      chip.title = "prior " + beam[i].logit.toFixed(2) + " bonus " + beam[i].bonus.toFixed(1);
      B.appendChild(chip);
      P.style.width = ((i + 1) / beam.length * 70) + "%";
      await wait(220);
      if (i < beam.length - 1) chip.className = "";
    }
    if (found.program) {
      B.querySelectorAll("span").forEach((chip) => {
        if (found.program.indexOf(chip.textContent) >= 0) chip.className = "hit";
      });
    }
    const text = found.predicted || current.test_input;
    const wrap = $("#Gwrap-" + name);
    wrap.innerHTML = gridHTML(text, 12);
    const cells = [...wrap.querySelectorAll("i")];
    cells.forEach((cell) => { cell.style.background = "#1f1e1b"; });
    const digits = text.replace(/;/g, "");
    for (let i = 0; i < cells.length; i += 1) {
      cells[i].style.background = ARC[+digits[i]] || "#333";
      cells[i].classList.add("pop");
      setTimeout(() => cells[i].classList.remove("pop"), 160);
      P.style.width = (70 + 30 * (i + 1) / cells.length) + "%";
      await wait(28);
    }
    const label = found.correct ? (plain() ? "right" : "✓ match") : (plain() ? "miss" : "✕ miss");
    R.innerHTML = '<span class="pill ' + (found.correct ? "a" : "r") + '">' + label + "</span>";
    return found.correct;
  }
  async function run() {
    if (running || !current) return;
    running = true;
    const button = $("#run");
    button.disabled = true;
    const ans = $("#ansbox");
    if (ans) ans.style.opacity = 0.35;
    runPhase = "loading";
    paintRun();
    try {
      await loadModels();
    } catch (error) {
      runPhase = "error";
      runNote = error.message;
      paintRun();
      button.disabled = false;
      running = false;
      return;
    }
    const curiosity = +$("#cur").value;
    const seen = $("#seen").checked;
    runCuriosity = curiosity;
    runPhase = "search";
    paintRun();
    const results = NAMES.map((name) => {
      const model = models[name];
      const archive = new Set();
      if (seen && name === "mixed") {
        const preview = engine.searchTrace(model, current.demos.map((d) => [engine.parseGrid(d.in), engine.parseGrid(d.out)]), { curiosity: 0, beam: 1, budget: 1, archive: new Set() });
        const first = preview.ranking[0];
        if (first) {
          const behavior = current.demos.map((d) => {
            const produced = engine.applyProgram(engine.parseGrid(d.in), [first.name]);
            return produced ? produced.map((row) => row.join("")).join(";") : "none";
          }).join("|");
          archive.add(behavior);
        }
      }
      return engine.predict(model, current, { curiosity: name === "mixed" ? curiosity : model.curiosity, beam: 6, budget: 48, archive });
    });
    const flags = await Promise.all(results.map((found, i) => animateOne(NAMES[i], found, i * 180)));
    const hits = flags.filter(Boolean).length;
    if (ans) ans.style.opacity = 1;
    runHits = hits;
    lastFlags = flags;
    runPhase = "done";
    paintRun();
    button.disabled = false;
    running = false;
  }
  $("#run").addEventListener("click", run);
  if (UP.examples && UP.examples[0]) setTask(UP.examples[0]);

  const T = SW.tasks;
  const A = SW.agents;
  const steps = [];
  T.forEach((t) => {
    const pay = t.payout;
    const fam = FAM_EASY[t.family] || t.family;
    [["post", "Post round " + t.round + " (" + t.family + "). Escrow locks the bounty.", "Puzzle " + t.round + " (" + fam + ") is posted. The reward goes in the jar."],
      ["bid", "Bid. " + (t.bids.length ? t.bids.map((b) => b.bidder + " " + b.score).join(", ") : "No bid."), t.bids.length ? "Robots put pocket money down: " + t.bids.map((b) => b.bidder + " " + b.score).join(", ") + "." : "Nobody bids."],
      ["assign", t.winner ? "Assign " + t.winner + "." : "No assignment. The bounty stays in escrow.", t.winner ? "The referee picks " + t.winner + "." : "Nobody is picked. The reward stays in the jar."],
      ["commit", t.winner ? "Commit. The solution hash is stored. Reveal waits for a later block." : "No commit.", t.winner ? "The answer goes in a sealed envelope." : "Nothing is sealed."],
      ["reveal", t.attempts.length ? "Reveal. " + t.attempts.map((a) => a.assignee + (a.correct ? " matches" : " slashed")).join(", ") + "." : "Nothing to reveal.", t.attempts.length ? "The envelope opens. " + t.attempts.map((a) => a.assignee + (a.correct ? " is right" : " is wrong")).join(", ") + "." : "Nothing to open."],
      ["settle", "Settle. Solver " + (pay.solver || 0) + ", helper " + (pay.helper || 0) + ", slashed " + (pay.slashed || 0) + ", refund " + (pay.requester_refund || 0) + ".", "Pay the winner " + (pay.solver || 0) + ", a friend " + (pay.helper || 0) + ", lost " + (pay.slashed || 0) + ", returned " + (pay.requester_refund || 0) + "."],
    ].forEach(([k, x, easy]) => steps.push({ k, t, x, easy }));
  });
  function state(idx) {
    let esc = 0, stk = 0, sl = 0, paid = 0, done = 0;
    const per = {};
    A.forEach((a) => { per[a.id] = { s: 0, h: 0 }; });
    steps.slice(0, idx + 1).forEach(({ k, t }) => {
      if (k === "post") esc += t.bounty;
      if (k === "bid") stk = t.bids.length * t.stake;
      if (k === "assign") stk = t.winner ? t.stake : 0;
      if (k === "settle") {
        paid += (t.payout.solver || 0) + (t.payout.helper || 0);
        sl += t.payout.slashed || 0;
        esc -= t.bounty;
        if (!t.winner) esc += t.bounty;
        stk = 0;
        done = t.round;
        if (t.winner && per[t.winner]) per[t.winner].s += t.payout.solver || 0;
        if (t.payout.helper_account) {
          const id = t.payout.helper_account.split(".")[0];
          if (per[id]) per[id].h += t.payout.helper || 0;
        }
      }
    });
    return { esc, stk, sl, paid, done, per };
  }
  const rep = chart("rep");
  const pay = chart("pay");
  if (rep) {
    rep.setOption(Object.assign({}, BASE, {
      color: A.map((a) => COL[a.id]),
      tooltip: Object.assign({}, tip(), { trigger: "axis", formatter: (ps) => (plain() ? "Trust score" : "Reputation") + "<br>" + ps.map((p) => p.marker + " " + p.seriesName + " " + fmt(p.value == null ? p.data : p.value)).join("<br>") }),
      legend: { top: 0, right: 0, icon: "roundRect", itemWidth: 12, itemHeight: 4, textStyle: { color: palette().mut, fontFamily: "JetBrains Mono", fontSize: 11 }, inactiveColor: "#45433e" },
      grid: { left: 44, right: 14, top: 34, bottom: 58 },
      xAxis: Object.assign({ type: "category", boundaryGap: false, data: [...Array(25).keys()].map((i) => "r" + i) }, axis()),
      yAxis: Object.assign({ type: "value", min: 900, max: 3100 }, axis()),
      dataZoom: [{ type: "inside" }, { type: "slider", height: 16, bottom: 8, borderColor: "#f5f0e614", backgroundColor: "#f5f0e605", fillerColor: "#2f6bed26", handleStyle: { color: "#5b8ef5", borderColor: "#5b8ef5" }, textStyle: { color: "#74726c", fontSize: 10 } }],
      series: A.map((a) => ({ id: a.id, name: plain() ? NICE[a.id] : a.id, type: "line", smooth: 0.25, symbol: "circle", showSymbol: false, lineStyle: { width: a.id === "mixed" ? 2.6 : 1.6 }, data: [] })),
    }));
  }
  if (pay) {
    pay.setOption(Object.assign({}, BASE, {
      tooltip: Object.assign({}, tip(), { trigger: "axis" }),
      legend: { top: 0, left: 0, icon: "roundRect", itemWidth: 10, itemHeight: 10, textStyle: { color: palette().mut, fontFamily: "JetBrains Mono", fontSize: 11 }, data: plain() ? [{ name: "winner", itemStyle: { color: "#5b8ef5" } }, "friend"] : [{ name: "solver", itemStyle: { color: "#5b8ef5" } }, "helper"] },
      grid: { left: 56, right: 10, top: 34, bottom: 24 },
      xAxis: Object.assign({ type: "category", data: A.map((a) => plain() ? NICE[a.id] : a.id) }, axis(), { splitLine: { show: false } }),
      yAxis: Object.assign({}, axis(), { type: "value" }),
      series: [
        { id: "solver", name: plain() ? "winner" : "solver", type: "bar", stack: "p", barWidth: "46%", itemStyle: { color: "#5b8ef5" }, data: [] },
        { id: "helper", name: plain() ? "friend" : "helper", type: "bar", stack: "p", itemStyle: { color: "#c9b89a", borderRadius: [5, 5, 0, 0] }, data: [] },
      ],
    }));
  }
  const range = $("#step");
  let idx = 0;
  let timer = null;
  function show(i) {
    idx = i;
    const s = steps[i];
    const st = state(i);
    range.value = i;
    const stepWord = plain() ? ({ post: "post", bid: "bid", assign: "pick", commit: "seal", reveal: "open", settle: "pay" }[s.k] || s.k) : s.k;
    $("#slabel").innerHTML = (i + 1) + " / " + steps.length + ' · <span style="color:#8fb2f9">' + stepWord + "</span>";
    $("#s-esc").textContent = fmt(st.esc);
    $("#s-stk").textContent = fmt(st.stk);
    $("#s-sl").textContent = fmt(st.sl);
    $("#s-paid").textContent = fmt(st.paid);
    $("#steptxt").innerHTML = plain()
      ? '<span class="p">puzzle ' + s.t.round + " · " + stepWord + "</span>  " + s.easy
      : '<span class="p">r' + s.t.round + " · " + s.k + "</span>  " + s.x;
    if (rep) rep.setOption({ series: A.map((a) => ({ data: a.reputation.slice(0, st.done + 1) })) });
    if (pay) pay.setOption({ series: [{ data: A.map((a) => st.per[a.id].s) }, { data: A.map((a) => st.per[a.id].h) }] });
    $$(".tbl tr").forEach((r) => r.classList.remove("sel"));
    const tr = $("#tr-" + s.t.round);
    if (tr) tr.classList.add("sel");
  }
  function stop() { clearInterval(timer); timer = null; $("#play").innerHTML = "▶ Play"; }
  $("#play").addEventListener("click", () => {
    if (timer) return stop();
    $("#play").innerHTML = "❚❚ Pause";
    timer = setInterval(() => { if (idx >= steps.length - 1) return stop(); show(idx + 1); }, RM ? 20 : 110);
  });
  $("#stepb").addEventListener("click", () => { stop(); show(Math.min(steps.length - 1, idx + 1)); });
  range.addEventListener("input", () => { stop(); show(+range.value); });
  show(0);

  async function nearView(method, args) {
    const res = await fetch("https://rpc.testnet.near.org", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        jsonrpc: "2.0",
        id: "light",
        method: "query",
        params: { request_type: "call_function", finality: "final", account_id: "lightswarm16771.testnet", method_name: method, args_base64: btoa(JSON.stringify(args)) },
      }),
    });
    const data = await res.json();
    if (!data.result || !data.result.result) throw new Error((data.error && data.error.message) || "RPC error");
    return JSON.parse(new TextDecoder().decode(new Uint8Array(data.result.result)));
  }
  async function readChain(target) {
    target.textContent = "Reading lightswarm16771.testnet…";
    try {
      const stats = await nearView("get_stats", {});
      const task = await nearView("get_task", { task_id: 1 });
      const bounty = task.bounty && (task.bounty.amount || task.bounty);
      target.textContent = "get_stats tasks_posted " + stats.tasks_posted + ", tasks_solved " + stats.tasks_solved + ", agents " + stats.agents + ".\nget_task 1 status " + task.status + ", bounty " + bounty + ".";
    } catch (error) {
      target.textContent = "Live read failed. " + error.message;
    }
  }
  $("#live").addEventListener("click", async () => {
    const on = $("#live").getAttribute("aria-pressed") !== "true";
    $("#live").setAttribute("aria-pressed", on ? "true" : "false");
    $("#live").classList.toggle("on", on);
    if (on) await readChain($("#liveout"));
  });
  $("#readchain").addEventListener("click", () => readChain($("#chainout")));

  const QUOTE = {
    dry: true,
    swapType: "EXACT_INPUT",
    slippageTolerance: 100,
    originAsset: "nep141:wrap.near",
    depositType: "INTENTS",
    destinationAsset: "nep141:arb-0xaf88d065e77c8cc2239327c5edb3a432268e5831.omft.near",
    amount: "100000000000000000000000",
    recipient: "0x2527D02599Ba641c19FEa793cD0F167589a0f10D",
    recipientType: "DESTINATION_CHAIN",
    refundTo: "lightswarm16771.testnet",
    refundType: "INTENTS",
  };
  const RECORDED = { out: "0.337044", min: "333673", t: "11" };
  function paintQuote(out, min, t, live) {
    $("#qout").textContent = out;
    $("#qmin").textContent = min;
    $("#qt").textContent = "~" + t + " s";
    $("#qdep").innerHTML = '<span class="ok">absent</span>';
    $("#qf").innerHTML = '<span class="ok">none</span>';
    $("#qnote").textContent = live ? "live dry quote" : "recorded dry quote · 13 Nov 2026 · API unavailable";
    $("#qst").innerHTML = '<span class="dot"></span><span>' + (live ? "dry run · live" : "dry run · recorded") + "</span>";
  }
  async function requestQuote() {
    $("#qst").innerHTML = '<span class="dot" style="background:#8fb2f9"></span><span style="color:#8fb2f9">requesting…</span>';
    const body = Object.assign({ deadline: new Date(Date.now() + 30 * 60 * 1000).toISOString() }, QUOTE);
    try {
      const res = await fetch("https://1click.chaindefuser.com/v0/quote", {
        method: "POST",
        headers: { "content-type": "application/json", accept: "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok || !data.quote) throw new Error((data && data.message) || ("HTTP " + res.status));
      const q = data.quote;
      if (q.depositAddress) throw new Error("dry quote returned a deposit address");
      paintQuote(q.amountOutFormatted, q.minAmountOut, q.timeEstimate, true);
    } catch (error) {
      paintQuote(RECORDED.out, RECORDED.min, RECORDED.t, false);
      $("#qnote").textContent = "recorded dry quote · 13 Nov 2026 · " + error.message;
    }
  }
  $("#quote").addEventListener("click", requestQuote);
  $("#mquote").addEventListener("click", () => { showTab("intents", "push"); requestQuote(); });
  $("#qcopy").addEventListener("click", () => {
    const body = Object.assign({ deadline: new Date(Date.now() + 30 * 60 * 1000).toISOString() }, QUOTE);
    navigator.clipboard && navigator.clipboard.writeText(JSON.stringify(body, null, 2));
  });

  const cards = $$(".fstep");
  const track = $("#ftrack");
  const dot = $("#fdot");
  let seq = null;
  function sel(i) {
    cards.forEach((c, j) => { c.classList.toggle("on", j === i); c.classList.toggle("done", j < i); });
    const pct = (i / 3) * 100;
    track.style.width = pct + "%";
    dot.style.left = pct + "%";
  }
  function playFlow() {
    clearTimeout(seq);
    let i = 0;
    sel(0);
    (function next() { seq = setTimeout(() => { i += 1; if (i <= 3) { sel(i); next(); } }, RM ? 0 : 1500); })();
  }
  cards.forEach((c, i) => c.addEventListener("click", () => { clearTimeout(seq); sel(i); }));
  $("#replayflow").addEventListener("click", playFlow);
  const flow = $(".flow");
  if (flow && "IntersectionObserver" in window) {
    const io = new IntersectionObserver((es) => { if (es[0].isIntersecting) { playFlow(); io.disconnect(); } });
    io.observe(flow);
  }

  bindHeat("heat");
  bindHeat("heat-s");
  drawCI("ci", "#ctoggle", "ablation");
  drawCI("ci-s", "#ctoggle-s", "ablation");
  let wasNarrow = narrow();
  addEventListener("resize", () => {
    const now = narrow();
    if (now === wasNarrow) return;
    wasNarrow = now;
    if (charts.heat) charts.heat.setOption(heatOption(), true);
    if (charts["heat-s"]) charts["heat-s"].setOption(heatOption(), true);
    const spec = [["ci", "#ctoggle"], ["ci-s", "#ctoggle-s"]];
    spec.forEach(([id, sel]) => {
      if (!charts[id]) return;
      const on = $(sel + " span.on");
      drawCI(id, sel, on ? on.dataset.k : "ablation");
    });
  });
  function redrawPlain() {
    if (charts.heat) charts.heat.setOption(heatOption(), true);
    if (charts["heat-s"]) charts["heat-s"].setOption(heatOption(), true);
    [["ci", "#ctoggle"], ["ci-s", "#ctoggle-s"]].forEach(([id, sel]) => {
      if (!charts[id]) return;
      const on = $(sel + " span.on");
      drawCI(id, sel, on ? on.dataset.k : "ablation");
    });
    if (rep) {
      rep.setOption({
        tooltip: Object.assign({}, tip(), { trigger: "axis", formatter: (ps) => (plain() ? "Trust score" : "Reputation") + "<br>" + ps.map((p) => p.marker + " " + p.seriesName + " " + fmt(p.value == null ? p.data : p.value)).join("<br>") }),
        legend: { textStyle: { color: palette().mut } },
        series: A.map((a) => ({ id: a.id, name: plain() ? NICE[a.id] : a.id })),
      });
    }
    if (pay) {
      pay.setOption({
        tooltip: Object.assign({}, tip(), { trigger: "axis", valueFormatter: (v) => fmt(v) }),
        legend: { data: plain() ? [{ name: "winner", itemStyle: { color: "#5b8ef5" } }, "friend"] : [{ name: "solver", itemStyle: { color: "#5b8ef5" } }, "helper"] },
        xAxis: { data: A.map((a) => plain() ? NICE[a.id] : a.id), axisLabel: { color: palette().axis } },
        series: [{ id: "solver", name: plain() ? "winner" : "solver" }, { id: "helper", name: plain() ? "friend" : "helper" }],
      });
    }
    if (typeof show === "function") show(idx);
    paintStage();
    paintRun();
    paintBadges();
  }
  addEventListener("simplechange", redrawPlain);
  addEventListener("themechange", redrawPlain);
  showTab(Q.get("tab") || "overview", "replace");
  toTop();
  if (Q.get("run") === "1" && (Q.get("tab") || "overview") === "playground") {
    const runBtn = $("#run");
    if (runBtn) runBtn.click();
  }
})();
