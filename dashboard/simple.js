(function () {
  const RM = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => [...(r || document).querySelectorAll(s)];

  function ink() {
    const light = document.documentElement.classList.contains("light");
    return light
      ? { line: "#14141355", body: "#fffefb", face: "#ebe7dc", ear: "#d5d0c4", base: "#f3f1ea", phone: "#6b6862" }
      : { line: "#f5f0e64d", body: "#2a2926", face: "#121110", ear: "#34322d", base: "#24231f", phone: "#74726c" };
  }
  const ACC = { geo: "#5b8ef5", colour: "#e0b25c", object: "#c9b89a", mixed: "#5b8ef5", noisy: "#9b9993" };
  function robot(n, size, k) {
    size = size || 40;
    k = k || 0;
    const a = ACC[n] || "#5b8ef5";
    const C = ink();
    let tip = "";
    let eyes = "";
    let extra = "";
    if (n === "geo") tip = '<path d="M24 2.5l3.6 6h-7.2z" fill="' + a + '"/>';
    if (n === "colour") tip = '<circle cx="20" cy="6" r="2.2" fill="#5b8ef5"/><circle cx="24" cy="4.5" r="2.2" fill="#e0b25c"/><circle cx="28" cy="6" r="2.2" fill="#f07a7e"/>';
    if (n === "object") tip = '<rect x="21" y="2.5" width="6" height="6" rx="1.2" fill="' + a + '"/>';
    if (n === "mixed") tip = '<circle cx="24" cy="5.5" r="3.2" fill="#e0b25c"/><circle cx="24" cy="5.5" r="1.3" fill="#161513"/>';
    if (n === "noisy") tip = '<path d="M20 8l2-4 2 4 2-4 2 4" fill="none" stroke="' + a + '" stroke-width="1.6" stroke-linejoin="round"/>';
    if (n === "object") eyes = '<rect class="eye" x="16.5" y="21.5" width="5" height="5" rx="1" fill="' + a + '"/><rect class="eye" x="26.5" y="21.5" width="5" height="5" rx="1" fill="' + a + '"/>';
    else if (n === "mixed") eyes = '<g class="eye"><circle cx="19" cy="24" r="3.6" fill="' + a + '"/><circle cx="20.2" cy="22.8" r="1.1" fill="#fff"/></g><g class="eye"><circle cx="29" cy="24" r="3.6" fill="' + a + '"/><circle cx="30.2" cy="22.8" r="1.1" fill="#fff"/></g>';
    else eyes = '<circle class="eye" cx="19" cy="24" r="2.6" fill="' + a + '"/><circle class="eye" cx="29" cy="24" r="2.6" fill="' + a + '"/>';
    if (n === "colour") extra = '<circle cx="15.5" cy="28.5" r="1.4" fill="#f07a7e" opacity=".8"/><circle cx="32.5" cy="28.5" r="1.4" fill="#f07a7e" opacity=".8"/>';
    if (n === "geo") extra = '<path d="M24 38.2l3 1.7v3.4l-3 1.7-3-1.7v-3.4z" fill="none" stroke="' + a + '" stroke-width="1.2"/>';
    const ears = n === "noisy"
      ? '<path d="M7.5 24a16.5 16.5 0 0 1 33 0" fill="none" stroke="' + C.phone + '" stroke-width="2.4"/><rect x="3.5" y="19" width="6" height="12" rx="3" fill="' + C.phone + '"/><rect x="38.5" y="19" width="6" height="12" rx="3" fill="' + C.phone + '"/>'
      : '<rect x="5" y="20" width="3.5" height="9" rx="1.6" fill="' + C.ear + '" stroke="' + C.line + '"/><rect x="39.5" y="20" width="3.5" height="9" rx="1.6" fill="' + C.ear + '" stroke="' + C.line + '"/>';
    const badge = n === "geo" ? "" : '<circle cx="24" cy="41.5" r="1.8" fill="' + a + '"/>';
    return '<svg class="bot d' + k + '" width="' + size + '" height="' + size + '" viewBox="0 0 48 48" aria-hidden="true"><line x1="24" y1="8" x2="24" y2="12" stroke="' + C.line + '" stroke-width="1.5"/>' + tip + '<rect x="8" y="12" width="32" height="24" rx="8" fill="' + C.body + '" stroke="' + C.line + '"/>' + ears + '<rect x="12" y="17" width="24" height="14" rx="6" fill="' + C.face + '"/>' + eyes + '<path d="M21 28.6q3 2 6 0" fill="none" stroke="' + a + '" stroke-width="1.4" stroke-linecap="round"/>' + extra + '<rect x="15" y="36.5" width="18" height="10" rx="4" fill="' + C.base + '" stroke="' + C.line + '"/>' + badge + "</svg>";
  }

  function paintBots() {
    $$("[data-bot]").forEach((el) => {
      el.innerHTML = robot(el.dataset.bot, +el.dataset.size || 40, +el.dataset.k || 0);
    });
  }
  paintBots();
  addEventListener("themechange", paintBots);

  const KEY = "light-agents-simple";
  const TOUR_KEY = "light-agents-tour-seen";
  function seenTour() {
    try { return localStorage.getItem(TOUR_KEY) === "1"; } catch (e) { return true; }
  }
  function markTour() {
    try { localStorage.setItem(TOUR_KEY, "1"); } catch (e) { /* private mode */ }
  }
  function playgroundOn() {
    const view = $('[data-view="playground"]');
    return !!($("#run") && (!view || !view.hidden));
  }
  function syncSwitch(on) {
    $$(".smode").forEach((sw) => sw.setAttribute("aria-checked", on ? "true" : "false"));
  }
  function setSimple(on, offer) {
    document.documentElement.classList.toggle("simple", on);
    document.body.classList.toggle("simple", on);
    syncSwitch(on);
    try { localStorage.setItem(KEY, on ? "1" : "0"); } catch (e) { /* private mode */ }
    const url = new URL(location.href);
    if (on) url.searchParams.set("simple", "1");
    else url.searchParams.delete("simple");
    history.replaceState(history.state, "", url);
    if (!RM) {
      $$(".easy, .tech, .only-s").forEach((el) => {
        if (el.closest("[hidden]")) return;
        el.classList.remove("swapin");
        void el.offsetWidth;
        el.classList.add("swapin");
      });
    }
    dispatchEvent(new Event("simplechange"));
    if (!on) endTour();
    else if (offer) offerTour();
  }
  function offerTour() {
    if (!document.documentElement.classList.contains("simple") || seenTour() || !playgroundOn()) return;
    markTour();
    setTimeout(() => tour(0), RM ? 0 : 350);
  }

  $$(".smode").forEach((sw) => sw.addEventListener("click", () => {
    const next = !document.documentElement.classList.contains("simple");
    setSimple(next, true);
    if (sw.classList.contains("inmenu")) {
      const nav = $("#sitenav");
      if (nav) nav.classList.remove("open");
      const menu = $("#menubtn");
      if (menu) menu.setAttribute("aria-expanded", "false");
    }
  }));
  const showMe = $("#showme");
  if (showMe) showMe.addEventListener("click", () => tour(0));

  let hole = null;
  let bub = null;
  let cur = -1;
  const STEPS = [
    { t: () => [$("#run")], txt: "Tap here and watch the robots think!", pos: "below" },
    { t: () => [$("#L-geo"), $("#L-noisy")], txt: "Each robot tries a few moves like flip, turn and recolour, and keeps its best guesses.", pos: "right" },
    { t: () => [$("#ansbox")], txt: "The right answer stays hidden, like a sealed envelope, until everyone has guessed.", pos: "below" },
    { t: () => [$("#stages") && $("#stages").closest(".card")], txt: "All five started with the same brain. What they practised made them different.", pos: "left" },
    { t: () => [$('[data-view="playground"] details.more') || $("details.more")], txt: "Want the grown-up version? Switch Simple mode off any time.", pos: "left" },
  ];
  function targets() {
    if (cur < 0) return [];
    return STEPS[cur].t().filter(Boolean);
  }
  function unionRect(els) {
    const rs = els.map((el) => el.getBoundingClientRect());
    const left = Math.min(...rs.map((r) => r.left));
    const top = Math.min(...rs.map((r) => r.top));
    const right = Math.max(...rs.map((r) => r.right));
    const bottom = Math.max(...rs.map((r) => r.bottom));
    return { left, top, right, bottom, width: right - left, height: bottom - top };
  }
  function place() {
    const els = targets();
    if (!hole || !els.length) return;
    const pad = 8;
    const R = unionRect(els);
    hole.style.left = (R.left - pad) + "px";
    hole.style.top = (R.top - pad) + "px";
    hole.style.width = (R.width + pad * 2) + "px";
    hole.style.height = (R.height + pad * 2) + "px";
    const vw = Math.min(window.innerWidth, document.documentElement.clientWidth);
    const vh = Math.min(window.innerHeight, document.documentElement.clientHeight);
    const W = Math.min(330, vw - 24);
    bub.style.width = W + "px";
    const H = bub.offsetHeight || 150;
    const gap = 14;
    const pref = STEPS[cur].pos;
    const spots = {
      below: { x: R.left, y: R.bottom + gap },
      above: { x: R.left, y: R.top - H - gap },
      right: { x: R.right + gap, y: R.top },
      left: { x: R.left - W - gap, y: R.top },
    };
    let pos = pref;
    let spot = spots[pref];
    const fits = (s) => s.x >= 8 && s.y >= 8 && s.x + W <= vw - 8 && s.y + H <= vh - 8;
    if (!fits(spot)) {
      pos = ["below", "above", "right", "left"].find((name) => fits(spots[name])) || "below";
      spot = spots[pos];
    }
    const x = Math.max(12, Math.min(vw - W - 12, spot.x));
    const y = Math.max(12, Math.min(vh - H - 12, spot.y));
    bub.className = "tour-bub " + pos;
    bub.style.left = x + "px";
    bub.style.top = y + "px";
  }
  function tour(i) {
    const step = STEPS[i];
    if (!step) return endTour();
    const els = step.t().filter(Boolean);
    if (!els.length) return i + 1 < STEPS.length ? tour(i + 1) : endTour();
    if (!hole) {
      hole = document.createElement("div");
      hole.className = "tour-hole";
      bub = document.createElement("div");
      bub.className = "tour-bub";
      document.body.append(hole, bub);
    }
    cur = i;
    bub.innerHTML = '<div class="tt">' + robot("mixed", 40, 1) + "<p>" + step.txt + '</p></div><div class="tf"><span class="stp">' + (i + 1) + " of " + STEPS.length + '</span><span class="dots">' + STEPS.map((_, j) => '<i class="' + (j === i ? "on" : "") + '"></i>').join("") + '</span><button class="sk" type="button">Skip</button><button class="nx" type="button">' + (i === STEPS.length - 1 ? "Done" : "Next") + "</button></div>";
    $(".sk", bub).onclick = endTour;
    $(".nx", bub).onclick = () => (i + 1 < STEPS.length ? tour(i + 1) : endTour());
    const R = unionRect(els);
    if (R.top < 72 || R.bottom > innerHeight - 80) {
      const top = window.scrollY + R.top - innerHeight * 0.32;
      window.scrollTo({ top: Math.max(0, top), behavior: RM ? "auto" : "smooth" });
    }
    place();
    setTimeout(place, RM ? 0 : 450);
    setTimeout(place, RM ? 0 : 900);
  }
  function endTour() {
    cur = -1;
    if (hole) { hole.remove(); bub.remove(); hole = bub = null; }
  }
  addEventListener("resize", place);
  addEventListener("scroll", () => { if (cur >= 0) requestAnimationFrame(place); }, { passive: true });
  window.simpleTour = tour;

  const params = new URLSearchParams(location.search);
  let on = document.documentElement.classList.contains("simple");
  if (params.get("simple") === "1") on = true;
  else if (params.get("simple") === "0") on = false;
  document.body.classList.toggle("simple", on);
  document.documentElement.classList.toggle("simple", on);
  syncSwitch(on);
  try { localStorage.setItem(KEY, on ? "1" : "0"); } catch (e) { /* private mode */ }
  if (on) dispatchEvent(new Event("simplechange"));
  if (on && params.get("tour") != null) tour(+params.get("tour") || 0);
  else if (on) offerTour();
  addEventListener("popstate", () => setTimeout(offerTour, 0));
  document.addEventListener("click", (event) => {
    if (event.target.closest && event.target.closest("[data-tab]")) {
      endTour();
      setTimeout(offerTour, 40);
    }
  });
})();
