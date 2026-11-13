const { test, expect } = require("@playwright/test");

async function scrollY(page) {
  return page.evaluate(() => window.scrollY);
}

async function visibleTab(page) {
  return page.locator("[data-view]:not([hidden])").getAttribute("data-view");
}

test.beforeEach(async ({ page }) => {
  await page.route("https://1click.chaindefuser.com/**", (route) => route.abort());
  await page.route("https://rpc.testnet.near.org/**", (route) => route.abort());
});

test("no paper file is offered anywhere in the dashboard", async ({ page }) => {
  await page.goto("/index.html");
  await expect(page.locator('a[href*="paper.pdf"], a[download]')).toHaveCount(0);
  await page.goto("/paper.html");
  await expect(page.locator('a[href*="paper.pdf"], a[download]')).toHaveCount(0);
  const missing = await page.request.get("/paper.pdf");
  expect(missing.status()).toBe(404);
});

test("every tab control opens that tab at the top", async ({ page }) => {
  await page.goto("/index.html");
  await page.evaluate(() => window.scrollTo(0, 1600));
  const controls = page.locator("[data-tab]");
  const count = await controls.count();
  const seen = new Set();
  for (let i = 0; i < count; i += 1) {
    const control = controls.nth(i);
    if (!(await control.isVisible())) continue;
    const tab = await control.getAttribute("data-tab");
    if (control === page.locator("#nav-run") || (await control.getAttribute("id")) === "nav-run") continue;
    seen.add(tab);
    await page.evaluate(() => window.scrollTo(0, 1400));
    await control.click();
    await expect(page.locator(`[data-view="${tab}"]`)).toBeVisible();
    expect(await scrollY(page)).toBe(0);
    expect(await visibleTab(page)).toBe(tab);
  }
  for (const tab of ["overview", "playground", "society", "market", "intents", "spec"]) {
    expect(seen.has(tab)).toBe(true);
  }
});

test("overview card buttons and links navigate", async ({ page }) => {
  await page.goto("/index.html");
  const cards = page.locator(".starts");
  await cards.getByRole("link", { name: "Society", exact: true }).click();
  expect(await visibleTab(page)).toBe("society");
  expect(await scrollY(page)).toBe(0);
  await page.goto("/index.html");
  await cards.getByRole("link", { name: "Market", exact: true }).click();
  expect(await visibleTab(page)).toBe("market");
  await page.goto("/index.html");
  await cards.getByRole("link", { name: "Intents", exact: true }).click();
  expect(await visibleTab(page)).toBe("intents");
  await page.goto("/index.html");
  await cards.getByRole("link", { name: "Spec", exact: true }).click();
  expect(await visibleTab(page)).toBe("spec");
  await page.goto("/index.html");
  await page.getByRole("link", { name: "Open Playground →" }).click();
  expect(await visibleTab(page)).toBe("playground");
  expect(await scrollY(page)).toBe(0);
  await page.goto("/index.html");
  await expect(page.getByRole("link", { name: "Contract" })).toHaveAttribute("href", /testnet\.nearblocks\.io/);
  const paper = page.getByRole("link", { name: "Read the paper" }).first();
  await expect(paper).toHaveAttribute("href", "paper.html");
  await paper.click();
  await expect(page).toHaveURL(/paper\.html$/);
  expect(await scrollY(page)).toBe(0);
});

test("back and forward restore the tab at the top", async ({ page }) => {
  await page.goto("/index.html?tab=overview");
  await page.evaluate(() => window.scrollTo(0, 1200));
  await page.locator(".tabs").getByRole("link", { name: "Society" }).click();
  expect(await visibleTab(page)).toBe("society");
  expect(await scrollY(page)).toBe(0);
  await page.evaluate(() => window.scrollTo(0, 600));
  await page.goBack();
  expect(await visibleTab(page)).toBe("overview");
  expect(await scrollY(page)).toBe(0);
  await page.goForward();
  expect(await visibleTab(page)).toBe("society");
  expect(await scrollY(page)).toBe(0);
});

test("a deep link opens at the top", async ({ page }) => {
  await page.goto("/index.html?tab=market");
  expect(await visibleTab(page)).toBe("market");
  expect(await scrollY(page)).toBe(0);
  await expect(page.locator('[data-view="market"] h2').first()).toContainText("checked");
});

test("actions on each tab fire", async ({ page }) => {
  await page.goto("/index.html?tab=playground");
  await page.locator("#seed").fill("7");
  await page.locator("#gen").click();
  await expect(page.locator("#runlog")).toContainText("task ready");
  await page.locator("#frozen").click();
  await expect(page.locator("#runlog")).toContainText("task ready");
  await page.locator("#fam span", { hasText: "colour" }).click();
  await expect(page.locator("#fam span.on")).toHaveText("colour");
  await page.locator("#stages .stage", { hasText: "Prior" }).click();
  await expect(page.locator("#stagetxt")).toContainText("prior");
  await page.locator("#run").click();
  await expect(page.locator("#runst")).toContainText(/match|loading|searching/, { timeout: 20000 });

  await page.locator(".tabs").getByRole("link", { name: "Society" }).click();
  expect(await scrollY(page)).toBe(0);
  await page.locator("#subjects .card").first().click();
  await expect(page.locator("#curve-win")).toBeVisible();
  await page.locator("#ctoggle-s span[data-k='upbringing']").click();
  await expect(page.locator("#ctoggle-s span.on")).toContainText("Upbringing");

  await page.locator(".tabs").getByRole("link", { name: "Market" }).click();
  expect(await scrollY(page)).toBe(0);
  await page.locator("#stepb").click();
  await expect(page.locator("#slabel")).toContainText("2 /");
  await page.locator("#play").click();
  await expect(page.locator("#play")).toContainText("Pause");
  await page.locator("#play").click();
  await page.locator("#mquote").click();
  expect(await visibleTab(page)).toBe("intents");
  expect(await scrollY(page)).toBe(0);
  await expect(page.locator("#qout")).toHaveText("0.337044");

  await page.locator("#replayflow").click();
  await expect(page.locator(".fstep.on")).toBeVisible();
  await page.locator(".fstep").nth(2).click();
  await expect(page.locator(".fstep").nth(2)).toHaveClass(/on/);
  await page.locator("#qcopy").click();
  await page.locator("#quote").click();
  await expect(page.locator("#qst")).toContainText("dry run");
  await page.locator("#readchain").click();
  await expect(page.locator("#chainout")).toContainText(/Live read failed|tasks_posted/);

  await page.locator(".tabs").getByRole("link", { name: "Spec" }).click();
  expect(await scrollY(page)).toBe(0);
  await expect(page.locator('[data-view="spec"] table')).toContainText("Learned program prior");

  await page.context().grantPermissions(["clipboard-read", "clipboard-write"]);
  await page.getByRole("link", { name: "Paper" }).click();
  await expect(page).toHaveURL(/paper\.html/);
  expect(await scrollY(page)).toBe(0);
  const theme = await page.locator("html").getAttribute("class");
  await page.locator("#theme").click();
  await expect(page.locator("html")).not.toHaveClass(theme || "");
  await page.locator("#cite").click();
  await expect(page.locator("#cite")).toHaveText(/Copied|Copy failed/);
  await page.locator("#toc a").first().click();
  await page.locator("#runmini").click();
  await expect(page.locator("#ministat")).toContainText(/of 5|loading|searching/, { timeout: 20000 });
});

const SIMPLE = {
  overview: "Five little robots",
  playground: "five robots guess",
  society: "one starting brain",
  market: "pocket money",
  intents: "spend anything",
  spec: "still a plan",
};

async function noPageOverflow(page) {
  const overflow = await page.evaluate(() => {
    const w = document.documentElement.clientWidth;
    const nodes = [...document.body.querySelectorAll(".card, .win, .lrn, .crew, .game, .five, .tour-bub, .stats")];
    const bad = [];
    for (const el of nodes) {
      if (el.closest("[hidden]")) continue;
      const s = getComputedStyle(el);
      if (s.display === "none" || s.visibility === "hidden") continue;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) continue;
      if (r.right > w + 1 || r.left < -1) bad.push((el.id || el.className || el.tagName) + " " + Math.round(r.left) + ".." + Math.round(r.right));
    }
    return { scroll: document.documentElement.scrollWidth - w, bad: bad.slice(0, 6) };
  });
  expect(overflow.scroll, JSON.stringify(overflow.bad)).toBeLessThanOrEqual(1);
  expect(overflow.bad).toEqual([]);
}

test("simple mode deep link, toggle, and tour", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("light-agents-tour-seen", "1"));
  await page.goto("/index.html?simple=1");
  await expect(page.locator("html")).toHaveClass(/simple/);
  await expect(page.locator("#smode")).toHaveAttribute("aria-checked", "true");
  expect(await page.locator('[data-view="overview"] h1').innerText()).toContain("Five little robots");
  await expect(page.locator("#crew")).toBeVisible();
  await page.locator("#smode").click();
  await expect(page.locator("html")).not.toHaveClass(/simple/);
  expect(await page.locator('[data-view="overview"] h1').innerText()).toContain("Five CPU learners");
  await page.locator("#smode").click();
  await page.reload();
  await expect(page.locator("html")).toHaveClass(/simple/);
  expect(await page.locator('[data-view="overview"] h1').innerText()).toContain("Five little robots");

  for (const tab of Object.keys(SIMPLE)) {
    await page.goto("/index.html?simple=1&tab=" + tab);
    const heading = page.locator(`[data-view="${tab}"] h1, [data-view="${tab}"] h2`).first();
    expect((await heading.innerText()).toLowerCase()).toContain(SIMPLE[tab].toLowerCase());
    await noPageOverflow(page);
    await page.locator("#smode").click();
    expect((await heading.innerText()).toLowerCase()).not.toContain(SIMPLE[tab].toLowerCase());
    await page.locator("#smode").click();
  }

  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto("/index.html?simple=1");
  await page.locator("#menubtn").click();
  await expect(page.locator("#smode-menu")).toBeVisible();
  await noPageOverflow(page);
  for (const width of [1024, 1280, 1440]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto("/index.html?simple=1&tab=playground");
    await noPageOverflow(page);
    await page.goto("/index.html?simple=1&tab=market");
    await noPageOverflow(page);
  }

  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/index.html?simple=1&tab=playground");
  await page.locator("#seed").fill("7");
  await page.locator("#gen").click();
  await expect(page.locator("#runlog")).toContainText("puzzle is ready");
  const seed = await page.locator("#seed").inputValue();
  await page.locator("#smode").click();
  await page.locator("#smode").click();
  expect(await page.locator("#seed").inputValue()).toBe(seed);
  await expect(page.locator("#runlog")).toContainText("puzzle is ready");
  await page.locator("#stages .stage", { hasText: "Prior" }).click();
  await expect(page.locator("#stagetxt")).toContainText("326,800");
  await page.locator("#run").click();
  await expect(page.locator("#runlog")).toContainText(/of 5 robots drew the right answer/, { timeout: 30000 });
  const hits = await page.locator("#runlog").innerText();
  await page.locator("#smode").click();
  await expect(page.locator("#runlog")).toContainText("predictions match the hidden grid");
  await page.locator("#smode").click();
  expect(await page.locator("#runlog").innerText()).toBe(hits);

  await page.goto("/index.html?simple=1&tab=market");
  await page.locator("#stepb").click();
  await expect(page.locator("#steptxt")).toContainText(/pocket money|reward goes in the jar|Puzzle/);
  await page.goto("/index.html?simple=1");
  await page.evaluate(() => window.scrollTo(0, 900));
  await page.locator(".starts").getByRole("link", { name: "Society", exact: true }).click();
  expect(await visibleTab(page)).toBe("society");
  expect(await scrollY(page)).toBe(0);

  const labels = await page.evaluate(() => echarts.getInstanceByDom(document.getElementById("heat-s")).getOption().yAxis[0].data);
  expect(labels).toEqual(["Geo", "Colour", "Object", "Mixed", "Noisy"]);

  await page.goto("/paper.html?simple=1");
  await expect(page.locator(".five")).toBeVisible();
  await expect(page.locator(".five")).toContainText("43 of 48");
  await expect(page.locator(".article")).toContainText("Abstract");
  await expect(page.locator('a[href*="paper.pdf"], a[download]')).toHaveCount(0);
  await page.locator("#smode").click();
  await expect(page.locator(".five")).toBeHidden();
});

test("the playground tour stays on screen", async ({ page }) => {
  await page.addInitScript(() => localStorage.removeItem("light-agents-tour-seen"));
  await page.setViewportSize({ width: 390, height: 800 });
  await page.goto("/index.html?tab=playground");
  await page.locator("#smode").click();
  const bub = page.locator(".tour-bub");
  await expect(bub).toContainText("Tap here and watch the robots think!");
  const inside = async () => {
    const box = await bub.boundingBox();
    const vp = page.viewportSize();
    expect(box.x).toBeGreaterThanOrEqual(-1);
    expect(box.y).toBeGreaterThanOrEqual(-1);
    expect(box.x + box.width).toBeLessThanOrEqual(vp.width + 1);
    expect(box.y + box.height).toBeLessThanOrEqual(vp.height + 1);
  };
  await inside();
  await bub.locator(".nx").click();
  await expect(bub).toContainText("flip, turn and recolour");
  await inside();
  await bub.locator(".nx").click();
  await expect(bub).toContainText("sealed envelope");
  await bub.locator(".sk").click();
  await expect(bub).toHaveCount(0);
  await page.locator("#showme").click();
  await expect(bub).toContainText("Tap here and watch the robots think!");
  await inside();
});

test("the playground seed field stays inside the puzzle card", async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem("light-agents-tour-seen", "1"));
  for (const simple of ["0", "1"]) {
    for (const width of [390, 1024]) {
      await page.setViewportSize({ width, height: 800 });
      await page.goto("/index.html?tab=playground&simple=" + simple);
      const card = page.locator("#seed").locator("xpath=ancestor::*[contains(@class,'card')]");
      const overflow = await card.evaluate((el) => el.scrollWidth - el.clientWidth);
      expect(overflow, "simple=" + simple + " width=" + width).toBeLessThanOrEqual(0);
      const seedBox = await page.locator("#seed").boundingBox();
      const cardBox = await card.boundingBox();
      expect(seedBox.x).toBeGreaterThanOrEqual(cardBox.x - 1);
      expect(seedBox.x + seedBox.width).toBeLessThanOrEqual(cardBox.x + cardBox.width + 1);
    }
  }
});
