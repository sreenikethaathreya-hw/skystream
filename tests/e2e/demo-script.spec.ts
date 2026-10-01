import { expect, test, type Page } from "@playwright/test";

const SHOTS = "screenshots";
const SENTENCE =
  "Two Almeria cooperatives are switching from Sur Seeds to Leontes because of T. parvispinus tolerance.";

async function actAs(page: Page, userId: string) {
  await page.getByLabel("Acting as").selectOption(userId);
}

async function openResolvedRow(page: Page) {
  const row = page
    .getByTestId("ledger-row")
    .filter({ has: page.getByTestId("claim-stamp").filter({ hasText: /confirmed|contradicted|inconclusive/ }) })
    .first();
  await row.getByRole("button", { expanded: false }).first().click();
  await expect(row.getByTestId("claim-receipt")).toContainText("Resolved against actuals");
}

test("demo script: capture, flag, structure, submit, consensus, advance, track record", async ({ page, request }) => {
  expect((await request.post("http://localhost:8000/api/demo/reset")).status()).toBe(204);
  await page.goto("/capture");
  await page.evaluate(() => localStorage.setItem("skystream.demoUser", "rep-a"));
  await page.reload();

  // 1. Baseline for the hero segment.
  await page.getByTestId("segment-2482").click();
  await expect(page.getByTestId("segment-title")).toContainText("2482");
  const baselineShare = await page.getByTestId("share-value").textContent();
  await page.screenshot({ path: `${SHOTS}/01-baseline.png`, fullPage: true });

  // 2. Typing a number recalculates instantly, no network round trip.
  const demand = page.getByTestId("demand-input");
  await demand.fill("16000");
  await expect(page.getByTestId("share-value")).not.toHaveText(baselineShare ?? "");

  // 3. An unrealistic number trips the critical flags and makes the justification required.
  await demand.fill("40000");
  await expect(page.getByTestId("flag-share_over_100")).toBeVisible();
  await expect(page.getByTestId("flag-implied_ha_over_market")).toBeVisible();
  await expect(page.getByTestId("submit-entry")).toBeDisabled();
  await page.screenshot({ path: `${SHOTS}/02-flags.png`, fullPage: true });

  // 4. A defensible number with a justification structured by Jev. Price still carries part of the
  //    revenue, so the price-carrying warning stays and the entry goes to consensus.
  await demand.fill("14500");
  await expect(page.getByTestId("flag-price_carrying")).toBeVisible();
  await page.getByTestId("justification-input").fill(SENTENCE);
  await page.getByTestId("structure-button").click();
  await expect(page.getByTestId("claim-tags")).toBeVisible();
  await expect(page.getByTestId("claim-tags")).toContainText("Sur Seeds");
  await expect(page.getByTestId("claim-tags")).toContainText("Leontes");
  await page.screenshot({ path: `${SHOTS}/03-structured-claim.png`, fullPage: true });
  await page.getByTestId("submit-entry").click();
  await expect(page.getByText(/Submitted 14,500 KS/)).toBeVisible();

  // A clean line at plan from a reliable rep is routine.
  await page.getByTestId("segment-2484").click();
  await expect(page.getByTestId("checks")).toContainText("No flags");
  await page.getByTestId("justification-input").fill("Hokkaido bookings confirmed by a Nijar cooperative.");
  await page.getByTestId("submit-entry").click();
  await expect(page.getByText(/Submitted .* for 2484/)).toBeVisible();

  // 5. Rep B submits without a strong record so consensus has an exception.
  await actAs(page, "rep-b");
  await page.getByTestId("segment-2432").click();
  await page.getByTestId("month-10").click();
  await page.getByTestId("demand-input").fill("2700");
  await page.getByTestId("justification-input").fill("Distributor expects more spring planting this year.");
  await page.getByTestId("submit-entry").click();
  await expect(page.getByText(/Submitted 2,700 KS/)).toBeVisible();

  // 6. Consensus lead sees exceptions only, gets Jev triage, drafts the RTB.
  await actAs(page, "lead");
  await page.goto("/consensus");
  await expect(page.getByTestId("exceptions").getByTestId("entry-card").first()).toBeVisible();
  await expect(page.getByTestId("triage").first()).toBeVisible();
  await page.getByTestId("draft-rtb").click();
  // Gemini drafts this when enabled (slower, free-form); the template fallback is instant.
  await expect(page.getByTestId("rtb-text")).toContainText("2482", { timeout: 60_000 });
  await page.screenshot({ path: `${SHOTS}/04-consensus.png`, fullPage: true });
  await expect(page.getByTestId("exceptions")).toContainText("2482");
  await expect(page.getByTestId("routine-entry").first()).toContainText("2484");
  await page.getByTestId("bulk-approve").click();
  await expect(page.getByText(/Approved \d+ routine entries/)).toBeVisible();
  const approveButtons = page.getByTestId("exceptions").getByRole("button", { name: "Approve" });
  while ((await approveButtons.count()) > 0) {
    await approveButtons.first().click();
    await page.waitForTimeout(300);
  }

  // 7. Advance the month: September claims resolve against synthetic actuals.
  await page.getByTestId("advance-month").click();
  await expect(page.getByText(/Sep closed, clock now Oct/)).toBeVisible();
  await page.goto("/ledger");
  await openResolvedRow(page);
  await page.screenshot({ path: `${SHOTS}/05-ledger.png`, fullPage: true });

  // 8. Track record and data quality.
  await page.goto("/reps");
  await expect(page.getByTestId("rep-rep-a")).toContainText("Reliable");
  await expect(page.getByTestId("rep-rep-b")).toContainText("Weak record");
  await page.screenshot({ path: `${SHOTS}/06-track-record.png`, fullPage: true });
  await page.goto("/data-quality");
  await expect(page.getByTestId("dq-market")).toContainText("821");
  await page.screenshot({ path: `${SHOTS}/07-data-quality.png`, fullPage: true });

  // 9. Supply handoff CSV contains the approved September line.
  const csv = await (await request.get("http://localhost:8000/api/export/supply.csv")).text();
  expect(csv).toContain("2482");
});

test("storyboard: baseline benchmarks and the share-jump copilot message", async ({ page, request }) => {
  expect((await request.post("http://localhost:8000/api/demo/reset")).status()).toBe(204);
  await page.goto("/capture");
  await page.evaluate(() => localStorage.setItem("skystream.demoUser", "rep-b"));
  await page.reload();

  await page.getByTestId("segment-2432").click();
  await page.getByRole("button", { name: "Oct", exact: true }).click();
  await expect(page.getByTestId("baseline-panel")).toContainText("Syngenta volume share by year");
  await expect(page.getByTestId("baseline-grower-potential")).toContainText("CRM grower potential");
  await page.getByTestId("demand-input").fill("7090");
  await expect(page.getByTestId("share-value")).toHaveText("35.0%");
  await expect(page.getByTestId("ytg-gap")).toContainText("+");
  await expect(page.getByTestId("flag-share_jump")).toContainText(/above the historical October average/);
  await expect(page.getByTestId("flag-share_jump")).toContainText("lifts share from 20.2% to 35.0%");
  await page.screenshot({ path: `${SHOTS}/09-storyboard-share-jump.png`, fullPage: true });
});

test("lead turns a missed claim into a rule that reps meet on the next keystroke", async ({ page, request }) => {
  expect((await request.post("http://localhost:8000/api/demo/reset")).status()).toBe(204);
  await page.goto("/ledger");
  await page.evaluate(() => localStorage.setItem("skystream.demoUser", "lead"));
  await page.reload();

  await page.getByLabel("Missed claims only").check();
  await page.getByTestId("ledger-row").first().getByRole("button", { expanded: false }).click();
  await page.getByTestId("add-rule-from-miss").first().click();
  await page
    .getByLabel("Rule in plain language")
    .fill("Do not accept any month more than 15% above last year in every segment unless the rep names a confirmed customer order.");
  await page.getByTestId("check-rule").click();
  await expect(page.getByTestId("rule-description")).toContainText("above +15%");
  await expect(page.getByTestId("rule-description")).toContainText("must cite a customer win or loss");
  await expect(page.getByTestId("rule-preview")).toContainText("Backtest");
  await page.screenshot({ path: `${SHOTS}/10-lead-rule-draft.png`, fullPage: true });
  await page.getByTestId("activate-rule").click();
  await expect(page.getByText("Rule is live")).toBeVisible();

  await page.goto("/rules");
  await expect(page.getByTestId("rule-card")).toContainText("Written after the miss on");

  await actAs(page, "rep-a");
  await page.goto("/capture");
  await page.getByTestId("segment-2482").click();
  await page.getByTestId("demand-input").fill("17500");
  const ruleFlag = page.locator('[data-testid^="flag-lead_rule_"]');
  await expect(ruleFlag).toContainText("Lead rule (Consensus lead)");
  await page.getByTestId("justification-input").fill("Our price is lower this season so growers will buy more.");
  await page.getByTestId("structure-button").click();
  await expect(page.getByText(/needs a justification citing a customer win or loss/)).toBeVisible();
  await page.screenshot({ path: `${SHOTS}/11-lead-rule-in-capture.png`, fullPage: true });

  await actAs(page, "lead");
  await page.goto("/rules");
  await page.getByRole("button", { name: "Retire" }).click();
  await page.getByRole("button", { name: "Confirm retire" }).click();
  await expect(page.getByTestId("rule-card")).toContainText("retired");
});

test("rep asks the data a question and gets a sourced answer", async ({ page, request }) => {
  expect((await request.post("http://localhost:8000/api/demo/reset")).status()).toBe(204);
  await page.goto("/capture");
  await page.evaluate(() => localStorage.setItem("skystream.demoUser", "rep-a"));
  await page.reload();

  await page.getByTestId("ask-the-data").click();
  const dialog = page.getByRole("dialog", { name: "Ask the data" });
  await dialog.getByRole("button", { name: "Which segments can I ask about?" }).click();
  // Gemini answers when enabled (slower); the template fallback is instant.
  await expect(dialog.getByTestId("chat-message-assistant")).toBeVisible({ timeout: 60_000 });
  await expect(dialog.getByTestId("chat-source").first()).toContainText("Segments in scope");
  await expect(dialog.getByTestId("chat-source").first()).toContainText("2482");

  await dialog.getByLabel("Ask a question about the data").fill("Can you forecast October demand for 2482?");
  await dialog.getByRole("button", { name: "Send" }).click();
  await expect(dialog.getByTestId("chat-message-assistant").last()).toContainText("can't forecast", {
    timeout: 60_000,
  });
  await page.screenshot({ path: `${SHOTS}/12-ask-the-data.png`, fullPage: true });
});

test("admin uploads monthly actuals and the rep's claim resolves", async ({ page, request }) => {
  expect((await request.post("http://localhost:8000/api/demo/reset")).status()).toBe(204);
  await page.goto("/capture");
  await page.evaluate(() => localStorage.setItem("skystream.demoUser", "rep-a"));
  await page.reload();

  await page.getByTestId("segment-2482").click();
  await page.getByTestId("demand-input").fill("14500");
  await page.getByTestId("justification-input").fill(SENTENCE);
  await page.getByTestId("submit-entry").click();
  await expect(page.getByText(/Submitted 14,500 KS/)).toBeVisible();

  await actAs(page, "admin");
  await page.goto("/admin/data");
  await page.getByLabel("Upload kind").selectOption("actuals");
  await page.getByTestId("upload-file").setInputFiles({
    name: "sep-actuals.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("country_code,micro_segment_id,year,month,sales_qty_ks\nES,2482,2026,9,13900\nXX,2482,2026,9,1\n"),
  });
  await page.getByTestId("upload-button").click();
  const preview = page.getByTestId("batch-preview");
  await expect(preview).toContainText("Unknown country 'XX'");
  await page.screenshot({ path: `${SHOTS}/08-admin-upload-preview.png`, fullPage: true });
  await page.getByTestId("commit-upload").click();
  await expect(page.getByTestId("commit-summary")).toContainText("Claims resolved 1");
  await expect(page.getByText(/1 claims resolved against the new actuals/)).toBeVisible();

  await page.goto("/ledger");
  await openResolvedRow(page);
  await expect(page.getByText(/Oct 2026/).first()).toBeVisible();
});
