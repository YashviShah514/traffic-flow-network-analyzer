/** Audit of the buttons and interactions that the two workflows do not touch.  node e2e/buttons.mjs */
import { chromium } from "playwright-core";

const U = process.env.APP_URL ?? "http://127.0.0.1:5173";
const browser = await chromium.launch({ executablePath: process.env.BROWSER_PATH ?? "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe" });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
page.on("console", (m) => m.type() === "error" && errors.push(m.text().slice(0, 160)));
page.on("dialog", (d) => d.accept());
let failed = 0;
const check = (label, ok, extra = "") => { console.log(`${ok ? "PASS" : "FAIL"}  ${label}${extra ? `  (${extra})` : ""}`); if (!ok) failed++; };
const api = async (path, init) => { const r = await fetch(U + path, init); return r.status === 204 ? null : r.json(); };
const wait = (ms = 600) => page.waitForTimeout(ms);
const before = (await api("/api/dashboard")).networks.map((n) => n.id);

try {
  // a network to play with
  const body = { name: "Audit network", junctions: [{ key: "J1", name: "J1", x: 80, y: 100, net_demand: "-5" }, { key: "J2", name: "J2", x: 320, y: 100, net_demand: "5" }], roads: [{ key: "r1", source: "J1", target: "J2" }] };
  const made = await api("/api/networks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const row = () => page.getByTestId("network-row").filter({ hasText: "Audit network" });

  await page.goto(U); await row().waitFor();
  await row().getByRole("button", { name: "Open" }).click(); await page.waitForSelector(".react-flow__node");
  check("dashboard Open: read-only view", page.url().endsWith(`/network/${made.id}`) && (await page.getByText("Read-only view").count()) === 1);
  await page.getByRole("button", { name: "Edit", exact: true }).click();
  check("Edit button enables editing", (await page.getByRole("button", { name: "Add junction" }).count()) === 1);
  await page.getByRole("button", { name: "Done editing" }).click();
  check("Done editing returns to read-only", (await page.getByText("Read-only view").count()) === 1);
  await page.goto(U); await row().getByRole("button", { name: "Edit" }).click(); await page.waitForSelector(".react-flow__node");
  check("dashboard Edit: opens in edit mode", (await page.getByRole("button", { name: "Done editing" }).count()) === 1);

  const labels = page.getByTestId("flow-label");
  const selectRoad = async () => { await page.getByRole("button", { name: "Select", exact: true }).click(); await page.locator(".react-flow__node").first().click(); await page.getByTestId("properties").locator("button", { hasText: "→" }).first().click(); await wait(200); };
  await selectRoad();
  await page.getByRole("button", { name: "Make two-way" }).click(); await wait();
  check("Make two-way adds the opposite road", (await labels.count()) === 2);
  await page.getByRole("button", { name: "Make one-way" }).click(); await wait();
  check("Make one-way removes it", (await labels.count()) === 1);
  await page.getByRole("button", { name: "Reverse direction" }).click(); await wait();
  check("Reverse direction swaps the ends", (await page.getByTestId("properties").innerText()).includes("J2 → J1"));
  await page.getByRole("button", { name: "Reverse direction" }).click(); await wait();
  await page.getByRole("button", { name: "Connect roads" }).click();
  await page.getByLabel("parallel roads").check();
  await page.locator(".react-flow__node").nth(0).click(); await page.locator(".react-flow__node").nth(1).click(); await wait();
  check("parallel roads option allows a second road", (await labels.count()) === 2);
  await page.keyboard.press("Delete"); await wait();
  check("Delete key removes the selected road", (await labels.count()) === 1);
  await page.getByRole("button", { name: "Save", exact: true }).click(); await wait(1200);
  check("Save stores edits", (await api(`/api/networks/${made.id}`)).roads.length === 1);
  await page.getByRole("button", { name: "Delete", exact: true }).click(); await wait(1200);
  check("workspace Delete removes the network", new URL(page.url()).pathname === "/" && (await api("/api/dashboard")).networks.every((n) => n.id !== made.id));

  // dashboard Delete
  const second = await api("/api/networks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  await page.goto(U); await row().waitFor();
  const totalBefore = Number(await page.getByTestId("stat-Total Networks").innerText());
  await row().getByRole("button", { name: /Delete/ }).click(); await wait(1200);
  check("dashboard Delete updates list and statistics", Number(await page.getByTestId("stat-Total Networks").innerText()) === totalBefore - 1 && (await row().count()) === 0);
  void second;

  // demo: saving makes a copy
  const demo = (await api("/api/dashboard")).networks.find((n) => n.is_demo);
  await page.goto(`${U}/network/${demo.id}?edit=1`); await page.waitForSelector(".react-flow__node"); await wait();
  await page.getByRole("button", { name: "Save", exact: true }).click(); await wait(1500);
  const copy = (await api("/api/dashboard")).networks.find((n) => n.name === `${demo.name} (copy)`);
  check("saving a demo creates a copy and leaves the original", Boolean(copy) && (await api(`/api/networks/${demo.id}`)).name === demo.name);

  // sidebar button, dialog and Escape
  await page.getByRole("button", { name: "New network" }).click();
  check("sidebar New network opens the two choices", (await page.getByRole("dialog").getByRole("button", { name: /Network/ }).count()) >= 2);
  await page.keyboard.press("Escape"); await wait(200);
  check("Escape closes the dialog", (await page.getByRole("dialog").count()) === 0);

  // section navigation
  await page.getByRole("navigation", { name: "Analysis sections" }).getByRole("button", { name: /Row operation history/ }).click(); await wait(900);
  check("section chip opens and scrolls to its section", (await page.locator("h2 button", { hasText: "Row operation history" }).getAttribute("aria-expanded")) === "true");

  // choosing places on the map, dragging a marker, Change
  await page.goto(`${U}/create/map`); await page.waitForSelector(".leaflet-container"); await wait(1500);
  const map = await page.locator(".leaflet-container").boundingBox();
  await page.getByRole("button", { name: "or pick on the map" }).first().click();
  await page.mouse.click(map.x + map.width * 0.35, map.y + map.height * 0.5);
  await page.getByTestId("pickup-selected").waitFor({ timeout: 20000 }); await wait(2500);
  check("pick pickup by clicking the map", true, (await page.getByTestId("pickup-selected").innerText()).split("\n")[0]);
  const pin = page.locator(".fm-pin").first();
  const p = await pin.boundingBox();
  const textBefore = await page.getByTestId("pickup-selected").innerText();
  await page.mouse.move(p.x + p.width / 2, p.y + p.height / 2); await page.mouse.down(); await page.mouse.move(p.x + 160, p.y - 90, { steps: 12 }); await page.mouse.up(); await wait(3500);
  check("dragging the marker changes the location", (await page.getByTestId("pickup-selected").innerText()) !== textBefore);
  await page.getByRole("button", { name: "Change pickup location" }).click();
  check("Change clears the selection", (await page.getByTestId("pickup-selected").count()) === 0 && (await page.getByRole("button", { name: "Generate road network" }).isDisabled()));

  // settings
  await page.goto(`${U}/settings`);
  await page.getByRole("button", { name: /dark theme/ }).click();
  check("dark theme toggles", await page.evaluate(() => document.documentElement.classList.contains("dark")));
  await page.getByRole("button", { name: /light theme/ }).click();
  check("backend status shown", (await page.getByText("connected").count()) === 1);
} catch (e) {
  failed++;
  console.log("FAIL  script stopped:", e.message.split("\n").slice(0, 5).join("\n"));
}
for (const n of (await api("/api/dashboard")).networks) if (!before.includes(n.id)) await api(`/api/networks/${n.id}`, { method: "DELETE" });
check("no browser errors", errors.length === 0, errors.slice(0, 3).join(" || "));
console.log(failed ? `\n${failed} check(s) failed` : "\nALL CHECKS PASSED");
await browser.close();
process.exit(failed ? 1 : 0);
