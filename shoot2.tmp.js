const { chromium } = require("@playwright/test");
const B = "https://light-swarm-near.pages.dev";
const OUT = "/workspace/lsn/post/";
(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 }, deviceScaleFactor: 2, colorScheme: "dark" });
  await ctx.addInitScript(() => { localStorage.setItem("light-agents-theme", "dark"); localStorage.setItem("light-agents-simple", "0"); localStorage.setItem("light-agents-tour-seen", "1"); });
  const errs = [];
  const page = await ctx.newPage();
  page.on("console", m => { if (m.type() === "error") errs.push(page.url() + " :: " + m.text()); });
  page.on("pageerror", e => errs.push(page.url() + " :: pageerror " + e.message));
  page.on("response", r => { if (r.status() >= 400) errs.push(r.status() + " " + r.url()); });
  const scrollTo = async (y) => { await page.evaluate((y) => window.scrollTo({ top: y, behavior: "instant" }), y); await page.waitForTimeout(400); };

  await page.goto(B + "/index.html?simple=0", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  const nav = await page.evaluate(() => { const n = document.querySelector(".nav"); const s = getComputedStyle(n); return { pos: s.position, h: n.getBoundingClientRect().height, bottom: n.getBoundingClientRect().bottom }; });
  console.log("nav", JSON.stringify(nav));
  await scrollTo(130);
  await page.waitForTimeout(2600);
  console.log("stats:", (await page.locator(".stats").first().innerText()).replace(/\n/g, " | "));
  await page.screenshot({ path: OUT + "01-overview.png" });

  await page.goto(B + "/index.html?tab=playground&simple=0", { waitUntil: "networkidle" });
  await page.locator("#frozen").click();
  await page.locator("#run").click();
  await page.waitForFunction(() => /of 5/.test(document.querySelector("#runst").textContent), null, { timeout: 60000 });
  await page.waitForTimeout(1500);
  const win = await page.locator("#runst").evaluate(e => { const w = e.closest(".win"); const r = w.getBoundingClientRect(); return { top: r.top + scrollY, h: r.height }; });
  console.log("win", JSON.stringify(win), "runst:", await page.locator("#runst").innerText());
  console.log("results:", JSON.stringify(await page.$$eval(".res", els => els.map(e => e.innerText))));
  await scrollTo(Math.max(0, win.top - nav.h - 16));
  await page.waitForTimeout(800);
  await page.screenshot({ path: OUT + "02-playground-run.png" });

  await page.goto(B + "/index.html?tab=market&simple=0", { waitUntil: "networkidle" });
  await page.locator("#step").evaluate(e => { e.value = 71; e.dispatchEvent(new Event("input", { bubbles: true })); e.dispatchEvent(new Event("change", { bubbles: true })); });
  await page.waitForTimeout(800);
  console.log("slabel:", await page.locator("#slabel").innerText(), "esc", await page.locator("#s-esc").innerText(), "stk", await page.locator("#s-stk").innerText());
  const rp = await page.locator("#play").evaluate(e => { const c = e.closest(".card"); return c.getBoundingClientRect().top + scrollY; });
  await scrollTo(Math.max(0, rp - nav.h - 16));
  await page.waitForTimeout(1500);
  await page.screenshot({ path: OUT + "03-market.png" });

  await page.goto(B + "/paper.html", { waitUntil: "networkidle" });
  await page.waitForTimeout(1200);
  console.log("paper theme:", await page.locator("html").getAttribute("class"));
  await page.screenshot({ path: OUT + "04-paper.png" });
  console.log("ERRORS:", JSON.stringify(errs, null, 1));
  await browser.close();
})();
