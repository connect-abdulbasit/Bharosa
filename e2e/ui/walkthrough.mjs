import { open, FE } from "./lib.mjs";
import fs from "fs";
const OUT = "/Users/abdulbasit/Personal/Bharosa/docs/screenshots";
fs.mkdirSync(OUT, { recursive: true });
const API = "http://localhost:8000";
const results = [];
const { browser, ctx, page } = await open();
await page.addInitScript(() => { try { delete window.SpeechRecognition; delete window.webkitSpeechRecognition; } catch (e) {} });
const apiRequests = [];
page.on("response", (r) => { if (r.url().startsWith(API)) apiRequests.push(r.request().method() + " " + r.url().replace(API, "").split("?")[0] + " " + r.status()); });
async function step(id, name, fn) {
  const t0 = Date.now();
  try { const note = await fn(); results.push({ id, name, ok: true, note: note || "" }); console.log("PASS", id, name, note || ""); }
  catch (e) { results.push({ id, name, ok: false, note: String(e.message).split("\n")[0].slice(0, 250) }); console.log("FAIL", id, name, String(e.message).split("\n")[0].slice(0, 250)); }
  try { await page.screenshot({ path: `${OUT}/${id}.png`, fullPage: true }); } catch {}
}
const text = async () => (await page.locator("body").innerText());
async function loginAs(role) {
  await page.goto(FE + "/login"); await page.evaluate(() => { localStorage.clear(); });
  await page.goto(FE + "/login"); await page.waitForSelector("text=Try a demo user");
  await page.getByRole("button", { name: new RegExp("^" + role, "i") }).click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 15000 });
}
async function hasBanner() { return /PROTOTYPE - simulated data/i.test(await text()); }

await step("01-landing", "Landing page + prototype banner", async () => { await page.goto(FE + "/"); await page.waitForSelector("text=Check"); if (!(await hasBanner())) throw new Error("no banner"); });
for (const [i, role] of [["02a", "citizen"], ["02b", "helper"], ["02c", "officer"], ["02d", "admin"], ["02e", "auditor"]])
  await step(`${i}-login-${role}`, `Login as ${role}`, async () => { await loginAs(role); if (!(await hasBanner())) throw new Error("no banner"); return page.url().replace(FE, ""); });

await loginAs("citizen");
await step("03-citizen-scam-check", "Citizen scam check", async () => {
  await page.goto(FE + "/citizen/check"); await page.waitForSelector("text=Check it");
  await page.getByRole("button", { name: /^0300-5550199/ }).click();
  await page.getByRole("button", { name: /Check it/ }).click();
  await page.waitForFunction(() => /scam|safe|official|not sure|suspicious/i.test(document.body.innerText) && /confidence|%|sure/i.test(document.body.innerText), null, { timeout: 15000 });
  const t = await text(); return (t.match(/(scam|looks safe|official|suspicious|not sure)[^\n]*/i) || [""])[0].slice(0, 90);
});
await step("04-citizen-claim-polling", "Citizen claim: 202 + poll until progress.active=false", async () => {
  await page.goto(FE + "/citizen/claim"); await page.waitForSelector("text=Tell us the problem");
  const ta = page.locator("textarea"); await ta.first().fill("mujhe is mahine ke paisay nahi mile");
  await page.getByRole("button", { name: /Yes/ }).first().click();
  await page.locator("input[type=file]").first().setInputFiles("id.jpg");
  await page.waitForSelector("text=Photo looks clear", { timeout: 20000 });
  const before = apiRequests.length;
  await page.getByRole("button", { name: /Send my claim/ }).click();
  await page.waitForSelector("text=How sure we are", { timeout: 60000 });
  const mine = apiRequests.slice(before);
  const post = mine.find((r) => r.startsWith("POST /claims "));
  const polls = mine.filter((r) => /GET \/claims\/[^/]+\/progress/.test(r)).length;
  if (!post || !post.endsWith("202")) throw new Error("POST /claims was not 202: " + post);
  if (polls < 1) throw new Error("no progress polling seen");
  return `${post}; ${polls} progress polls; ` + (await text()).match(/\d+%/)?.[0];
});
await step("05-citizen-status", "Citizen status timeline", async () => { await page.goto(FE + "/citizen/status"); await page.waitForTimeout(2500); const t = await text(); if (!/needs more proof|With an officer|Submitted|with officer/i.test(t)) throw new Error("no status text"); });
await step("06-payment-check", "Did my payment arrive? (payment_check)", async () => {
  await page.goto(FE + "/citizen"); await page.getByRole("button", { name: /Check this month/ }).click();
  await page.waitForSelector("text=Ask again", { timeout: 60000 });
  const post = apiRequests.filter((r) => r.startsWith("POST /claims ")).pop();
  return post + " | " + (await text()).split("\n").find((l) => /We found|Good news|payment/i.test(l) && l.length > 25)?.slice(0, 110);
});
await step("07-consent-withdraw", "Consent withdraw (two-step confirm)", async () => {
  await page.goto(FE + "/citizen/data"); await page.waitForSelector("text=Take it back");
  const n = await page.getByRole("button", { name: /^Take it back/ }).count();
  await page.getByRole("button", { name: /^Take it back/ }).first().click();
  await page.getByRole("button", { name: /Yes, take back/ }).click(); await page.waitForTimeout(2500);
  const w = apiRequests.filter((r) => /POST \/consent\/[^/]+\/withdraw/.test(r)).pop();
  if (!w || !w.endsWith("200")) throw new Error("withdraw call: " + w);
  return w + ` (${n} scopes shared before)`;
});
await step("08-consent-correct", "Consent correction (extra)", async () => {
  await page.goto(FE + "/citizen/data"); await page.waitForSelector("text=Save correction");
  await page.locator("input.input").last().fill("Fatima Noor");
  await page.getByRole("button", { name: /Save correction/ }).click(); await page.waitForTimeout(2000);
  const w = apiRequests.filter((r) => /POST \/consent\/[^/]+\/correct/.test(r)).pop(); if (!w) throw new Error("no correct call"); return w;
});

await loginAs("helper");
await step("09-helper-switch-pin", "Helper family switch + PIN consent grant", async () => {
  await page.goto(FE + "/helper"); await page.waitForSelector("a:has-text('Fatima')");
  await page.locator("a", { hasText: "Fatima" }).first().click(); await page.waitForTimeout(3000);
  await page.screenshot({ path: `${OUT}/09a-helper-fatima-before-pin.png`, fullPage: true });
  const pin = page.locator("input[inputmode=numeric]");
  let note = "no PIN needed";
  if (await pin.count()) { await pin.first().fill("1234"); await page.getByRole("button", { name: /Save their consent/ }).click(); await page.waitForTimeout(2500);
    const c = apiRequests.filter((r) => r.startsWith("POST /consent ")).pop(); if (!c || !/ 20\d$/.test(c)) throw new Error("consent grant " + c); note = c; }
  await page.screenshot({ path: `${OUT}/09b-helper-fatima-after-pin.png`, fullPage: true });
  await page.getByRole("button", { name: /Switch person/ }).click(); await page.waitForURL(/\/helper$/);
  await page.locator("a", { hasText: "Zubaida" }).first().click(); await page.waitForSelector("text=You are now helping");
  if (!/Zubaida/.test(await text())) throw new Error("second person not shown");
  return "Fatima (" + note + ") -> switch -> Zubaida";
});

await loginAs("officer");
await step("10-officer-queue-approve", "Officer queue and approve", async () => {
  await page.goto(FE + "/officer"); await page.waitForSelector("a:has-text('case-')");
  await page.locator("a:has-text('case-')").first().click(); await page.waitForSelector("text=Your decision");
  await page.screenshot({ path: `${OUT}/10a-officer-case.png`, fullPage: true });
  await page.locator("textarea").first().fill("Integration walkthrough: ledger checked, approve.");
  await page.getByRole("button", { name: /^Approve/ }).click(); await page.waitForTimeout(3000);
  const d = apiRequests.filter((r) => /POST \/cases\/[^/]+\/decide/.test(r)).pop(); if (!d || !d.endsWith("200")) throw new Error("decide: " + d);
  return d;
});
await step("11-officer-photo-image-url", "Officer sees the ID photo (image_url -> blob)", async () => {
  const login = async (u, p) => (await (await fetch(API + "/auth/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ username: u, password: p }) })).json()).access_token;
  const ct = await login("s2-spelling", "citizen-demo-123");
  const form = new FormData(); form.append("file", new Blob([fs.readFileSync("id.jpg")], { type: "image/jpeg" }), "id.jpg");
  const doc = await (await fetch(API + "/documents", { method: "POST", headers: { authorization: "Bearer " + ct }, body: form })).json();
  const cl = await (await fetch(API + "/claims", { method: "POST", headers: { authorization: "Bearer " + ct, "content-type": "application/json" }, body: JSON.stringify({ transcript: "mujhe is mahine ke paisay nahi mile", document_id: doc.document_id }) })).json();
  await new Promise((r) => setTimeout(r, 4000));
  const d = await (await fetch(API + "/cases/" + cl.case_id, { headers: { authorization: "Bearer " + ct } })).json();
  if (!d.image_url) throw new Error("case detail has no image_url after an upload + claim");
  const withPhoto = [cl.case_id, d.image_url];
  await page.goto(FE + "/officer/case/" + withPhoto[0]); await page.waitForSelector("text=Your decision"); await page.waitForTimeout(2500);
  if (!(await page.locator("img[src^=blob]").count())) throw new Error("case " + withPhoto[0] + " has image_url " + withPhoto[1] + " but the page shows no photo");
  return withPhoto[0] + " " + withPhoto[1];
});

await loginAs("admin");
await step("12-admin-twin", "Digital Twin simulate", async () => {
  await page.goto(FE + "/admin/twin"); await page.waitForSelector("text=Run on past cases");
  await page.getByRole("button", { name: /Stricter: auto/ }).click(); await page.getByRole("button", { name: /Run on past cases/ }).click(); await page.waitForTimeout(3000);
  const s = apiRequests.filter((r) => /POST \/rules\/[^/]+\/simulate/.test(r)).pop(); if (!s || !s.endsWith("200")) throw new Error("simulate: " + s); return s;
});
await step("13-admin-rule-publish", "Admin rule publish", async () => {
  await page.goto(FE + "/admin/rules"); await page.waitForSelector("text=Publish new version");
  await page.locator("input[type=range]").first().fill("0.92");
  await page.locator("input.input").last().fill("walkthrough: slightly stricter auto-handle");
  await page.getByRole("button", { name: /Publish new version/ }).click({ timeout: 8000 });
  await page.getByRole("button", { name: /Yes, publish/ }).click({ timeout: 8000 }); await page.waitForTimeout(3000);
  const s = apiRequests.filter((r) => /POST \/rules\/[^/]+\/versions/.test(r)).pop(); if (!s || !/ 20\d$/.test(s)) throw new Error("publish: " + s); return s;
});
await step("14-chaos-claim-pauses-resume", "Chaos switch -> claim pauses -> switch off -> Try again (resume)", async () => {
  await page.goto(FE + "/admin/chaos"); await page.waitForSelector("text=Identity service down");
  await page.getByRole("switch", { name: /Identity service down/ }).click(); await page.waitForTimeout(2000);
  await page.screenshot({ path: `${OUT}/14a-chaos-on.png`, fullPage: true });
  const mocks = await (await fetch("http://localhost:8001/chaos")).json(); if (!mocks.error_500) throw new Error("real mocks chaos not switched: " + JSON.stringify(mocks));
  await loginAs("helper"); // a fresh citizen claim: helper files for Gulshan (clean person)
  await page.goto(FE + "/helper"); await page.waitForSelector("a:has-text('Gulshan')"); await page.locator("a", { hasText: "Gulshan" }).first().click(); await page.waitForSelector("text=You are now helping");
  await page.locator("textarea").first().fill("mera naam Gulshan Bibi hai. mujhe is mahine ke paisay nahi mile").catch(async () => {});
  await page.getByRole("button", { name: /^Use this|Yes/ }).first().click().catch(() => {});
  await page.getByRole("button", { name: /Send my claim/ }).click();
  await page.waitForSelector("text=How sure we are", { timeout: 60000 });
  await page.screenshot({ path: `${OUT}/14b-claim-paused.png`, fullPage: true });
  if (!(await page.getByRole("button", { name: /Try again/ }).count())) throw new Error("no Try again button on paused claim");
  await fetch("http://localhost:8001/chaos/reset", { method: "POST" });
  await page.getByRole("button", { name: /Try again/ }).click(); await page.waitForSelector("text=How sure we are", { timeout: 60000 });
  await page.waitForTimeout(1500);
  const r = apiRequests.filter((x) => /POST \/claims\/[^/]+\/resume/.test(x)).pop(); if (!r) throw new Error("resume not called");
  if (await page.getByRole("button", { name: /Try again/ }).count()) throw new Error("still paused after resume");
  return r + " -> completed";
});
await loginAs("admin");
await step("15-chaos-reset", "Admin chaos off + reset", async () => {
  await page.goto(FE + "/admin/chaos"); await page.waitForSelector("text=Identity service down"); await page.waitForTimeout(1500);
  const m = await (await fetch("http://localhost:8001/chaos")).json(); return "mocks chaos now " + JSON.stringify(m);
});
await loginAs("auditor");
await step("16-auditor-audit-log", "Auditor audit log (read-only)", async () => {
  await page.goto(FE + "/auditor"); await page.waitForSelector("button:has-text('auth.login')", { timeout: 15000 });
  const n = await page.locator("button:has-text(' · ')").count().catch(() => 0);
  const buttons = await page.getByRole("button", { name: /Approve|Reject|Publish/ }).count(); if (buttons) throw new Error("auditor sees write buttons");
  return "audit rows visible; no write actions";
});
await step("17-scam-map-eval", "Scam Map + /eval page (new shape)", async () => {
  await page.goto(FE + "/eval"); await page.waitForSelector("text=Scam Map", { timeout: 20000 });
  const t = await text(); const e = apiRequests.filter((r) => /GET \/eval /.test(r)).pop(); const m = apiRequests.filter((r) => /GET \/scam-map /.test(r)).pop();
  if (!/reports/.test(t)) throw new Error("scam map has no totals"); return `${e} ${m}`;
});
for (const [p, role] of [["/eval", "officer"]]) await step("18-eval-officer", "Officer can open /eval", async () => { await loginAs(role); await page.goto(FE + p); await page.waitForSelector("text=Scam Map", { timeout: 20000 }); });
await step("19-banner-all-pages", "Prototype banner on every page", async () => {
  await loginAs("admin"); const miss = [];
  for (const p of ["/", "/login", "/citizen", "/citizen/check", "/citizen/claim", "/citizen/status", "/citizen/data", "/helper", "/officer", "/admin", "/admin/rules", "/admin/twin", "/admin/chaos", "/auditor", "/eval", "/offline"]) { await page.goto(FE + p); await page.waitForTimeout(700); if (!/PROTOTYPE - simulated data/i.test(await text())) miss.push(p); }
  if (miss.length) throw new Error("banner missing on " + miss.join(", ")); return "16 pages";
});
fs.writeFileSync("results.json", JSON.stringify(results, null, 1));
await browser.close();
