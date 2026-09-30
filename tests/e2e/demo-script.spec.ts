import { expect, test, type Page } from "@playwright/test";

const SHOTS = "screenshots";
const SENTENCE =
  "Two Almeria cooperatives are switching from Sur Seeds to Leontes because of T. parvispinus tolerance.";

async function actAs(page: Page, userId: string) {
  await page.getByLabel("Acting as").selectOption(userId);
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
  await expect(page.getByTestId("tile-flags")).toContainText("No flags");
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
  await expect(page.getByTestId("ledger-list")).toContainText("Resolved against actuals");
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
