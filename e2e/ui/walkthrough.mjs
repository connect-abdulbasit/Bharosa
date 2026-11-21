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
async function loginForm(user, pw) {
  await page.goto(FE + "/login"); await page.evaluate(() => { localStorage.clear(); });
  await page.goto(FE + "/login"); await page.waitForSelector("text=Try a demo user");
  await page.locator("input:not([type=password])").first().fill(user); await page.locator("input[type=password]").first().fill(pw);
  await page.getByRole("button", { name: /^Log in/ }).first().click();
  await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 15000 });
}
let lastClaimId = null;
page.on("response", async (r) => { if (r.request().method() === "POST" && r.url() === API + "/claims" && r.status() === 202) { try { lastClaimId = (await r.json()).claim_id; } catch {} } });
async function apiLogin(u, p) { return (await (await fetch(API + "/auth/login", { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ username: u, password: p }) })).json()).access_token; }
async function hasBanner() { return /PROTOTYPE - simulated data/i.test(await text()); }

await step("01-landing", "Landing page + prototype banner", async () => { await page.goto(FE + "/"); await page.waitForSelector("text=Check"); if (!(await hasBanner())) throw new Error("no banner"); });
for (const [i, role] of [["02a", "citizen"], ["02b", "helper"], ["02c", "officer"], ["02d", "admin"], ["02e", "auditor"]])
  await step(`${i}-login-${role}`, `Login as ${role}`, async () => { await loginAs(role); if (!(await hasBanner())) throw new Error("no banner"); return page.url().replace(FE, ""); });

await loginForm("demo-live", "citizen-demo-123");
await step("03-citizen-scam-check", "Citizen scam check", async () => {
  await page.goto(FE + "/citizen/check"); await page.waitForSelector("text=Check it");
  await page.getByRole("button", { name: /^0300-5550199/ }).click();
  await page.getByRole("button", { name: /Check it/ }).click();
  await page.waitForFunction(() => /scam|safe|official|not sure|suspicious/i.test(document.body.innerText) && /confidence|%|sure/i.test(document.body.innerText), null, { timeout: 15000 });
  const t = await text(); return (t.match(/(scam|looks safe|official|suspicious|not sure)[^\n]*/i) || [""])[0].slice(0, 90);
});
await step("04-citizen-claim-polling", "Citizen claim: 202 + poll until progress.active=false", async () => {
  await page.goto(FE + "/citizen/claim"); await page.waitForSelector("text=Tell us the problem");
  const ta = page.locator("textarea"); await ta.first().fill("mera naam Samina Parveen hai. mujhe is mahine ke paisay nahi mile");
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
  const t = await text(); if (/Duplicate claim/i.test(t)) throw new Error("demo-live hit the duplicate rule");
  return `${post}; ${polls} progress polls; ` + t.match(/\d+%/)?.[0] + "; no duplicate warning";
});
await step("05-citizen-status", "Citizen status timeline", async () => { await page.goto(FE + "/citizen/status"); await page.waitForTimeout(2500); const t = await text(); if (!/needs more proof|With an officer|Submitted|with officer/i.test(t)) throw new Error("no status text"); });
await step("05b-my-messages", "Citizen home shows My messages (in-app notification, Urdu + English)", async () => {
  await page.goto(FE + "/citizen"); await page.waitForSelector("[data-testid=my-messages]");
  await page.waitForFunction(() => /was sent to an officer|ID card again|approved|closed/i.test(document.querySelector("[data-testid=my-messages]")?.innerText || ""), null, { timeout: 15000 });
  const t = await page.locator("[data-testid=my-messages]").innerText();
  if (!/[\u0600-\u06FF]/.test(t)) throw new Error("no Urdu text in the message");
  return t.split("\n").filter((l) => /officer|proof|approved/i.test(l))[0];
});
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
  const cl = await (await fetch(API + "/claims", { method: "POST", headers: { authorization: "Bearer " + ct, "content-type": "application/json" }, body: JSON.stringify({ transcript: "mera naam Muhammed Aslam hai. mujhe is mahine ke paisay nahi mile", document_id: doc.document_id }) })).json();
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
async function pauseResume(switchRe, mockKey, person, failedStep, shot) {
  await loginAs("admin");
  await page.goto(FE + "/admin/chaos"); await page.waitForSelector("text=Identity service down");
  await page.getByRole("switch", { name: switchRe }).click(); await page.waitForTimeout(2000);
  const summary = await page.locator("[data-testid=chaos-summary]").innerText(); if (!/1 switch ON/.test(summary)) throw new Error("summary does not show the switch: " + summary);
  await page.screenshot({ path: `${OUT}/${shot}a-chaos-on.png`, fullPage: true });
  const mocks = await (await fetch("http://localhost:8001/chaos")).json(); if (!mocks[mockKey]) throw new Error("real mocks chaos not switched: " + JSON.stringify(mocks));
  await loginAs("helper");
  await page.goto(FE + "/helper"); await page.waitForSelector(`a:has-text('${person}')`); await page.locator("a", { hasText: person }).first().click(); await page.waitForSelector("text=You are now helping");
  await page.locator("textarea").first().fill(`mera naam ${NAMES[person]} hai. mujhe is mahine ke paisay nahi mile`);
  await page.getByRole("button", { name: /Yes/ }).first().click();
  await page.getByRole("button", { name: /Send my claim/ }).click();
  await page.waitForSelector("text=How sure we are", { timeout: 60000 });
  await page.screenshot({ path: `${OUT}/${shot}b-claim-paused.png`, fullPage: true });
  const ht = await apiLogin("helper", "helper-demo-123");
  const c = await (await fetch(API + "/claims/" + lastClaimId, { headers: { authorization: "Bearer " + ht } })).json();
  const st = Object.fromEntries(c.pipeline_steps.map((x) => [x.step, x.status]));
  if (st[failedStep] !== "failed") throw new Error(`expected ${failedStep} failed, got ${JSON.stringify(st)}`);
  const before = failedStep === "ledger_lookup" ? "identity_lookup" : null; if (before && st[before] !== "done") throw new Error(before + " should still be done: " + JSON.stringify(st));
  if (!(await page.getByRole("button", { name: /Try again/ }).count())) throw new Error("no Try again button on paused claim");
  const at = await apiLogin("admin", "admin-demo-123"); // the same call the panel's "Reset all" makes
  await fetch(API + "/admin/demo/chaos", { method: "POST", headers: { authorization: "Bearer " + at, "content-type": "application/json" }, body: JSON.stringify({ identity_down: false, ledger_down: false, payments_down: false }) });
  await page.getByRole("button", { name: /Try again/ }).click(); await page.waitForSelector("text=How sure we are", { timeout: 60000 }); await page.waitForTimeout(1500);
  const r = apiRequests.filter((x) => /POST \/claims\/[^/]+\/resume/.test(x)).pop(); if (!r) throw new Error("resume not called");
  if (await page.getByRole("button", { name: /Try again/ }).count()) throw new Error("still paused after resume");
  return `paused at ${failedStep} -> ${r} -> completed`;
}
const NAMES = { "Gulshan Bibi": "Gulshan Bibi", "Parveen Akhtar": "Parveen Akhtar" };
await step("14-chaos-identity-pauses-resume", "Chaos: identity down -> claim pauses at identity_lookup -> Try again", () => pauseResume(/Identity service down/, "error_500", "Gulshan Bibi", "identity_lookup", "14"));
await step("14c-chaos-payment-record-pauses-resume", "Chaos: payment record down -> pauses at ledger_lookup (identity still done) -> Try again", () => pauseResume(/Payment record down/, "ledger_down", "Parveen Akhtar", "ledger_lookup", "14c"));
await loginAs("admin");
await step("15-chaos-reset-all", "Chaos page: switches on, Reset all", async () => {
  await page.goto(FE + "/admin/chaos"); await page.waitForSelector("text=Identity service down");
  await page.getByRole("switch", { name: /Payment record down/ }).click(); await page.getByRole("switch", { name: /Payments rail down/ }).click(); await page.waitForTimeout(2000);
  const on = await page.locator("[data-testid=chaos-summary]").innerText(); if (!/2 switches ON/.test(on)) throw new Error("summary: " + on);
  await page.screenshot({ path: `${OUT}/15a-two-switches-on.png`, fullPage: true });
  await page.getByRole("button", { name: /Reset all/ }).click(); await page.waitForFunction(() => /All services normal/.test(document.querySelector("[data-testid=chaos-summary]")?.innerText || ""), null, { timeout: 10000 });
  const m = await (await fetch("http://localhost:8001/chaos")).json(); if (m.error_500 || m.ledger_down) throw new Error("mocks still broken " + JSON.stringify(m));
  const t = await text(); if (!/extract_claim/.test(t)) throw new Error("AI function modes not shown on the page");
  return "2 on -> Reset all -> normal; AI modes listed";
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
