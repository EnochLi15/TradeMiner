import { expect, test, type Page } from "@playwright/test";
import path from "node:path";

const fixtureStrategyDir = path.resolve("tests/e2e/fixtures");
const browserErrors = new WeakMap<Page, string[]>();

test.beforeEach(({ page }) => {
  browserErrors.set(page, []);
  page.on("console", (message) => {
    if (message.type() === "error") {
      browserErrors.get(page)?.push(`Browser console error: ${message.text()}`);
    }
  });
  page.on("pageerror", (error) => {
    browserErrors.get(page)?.push(`Browser page error: ${error.message}`);
  });
});

test.afterEach(({ page }) => {
  expect(browserErrors.get(page) ?? []).toEqual([]);
});

async function fillMarketDataDates(page: Page) {
  const syncPanel = page.getByTestId("sync-panel");
  await syncPanel.getByLabel("Start Date").fill("2024-01-01");
  await syncPanel.getByLabel("End Date").fill("2024-01-05");
}

async function configureDailyMomentum(page: Page, topN: string) {
  const strategyPanel = page.getByTestId("strategy-panel");
  await strategyPanel.getByLabel("lookback_days").fill("2");
  await strategyPanel.getByLabel("top_n").fill(topN);
  await strategyPanel.getByLabel("include_etfs").uncheck();
  await strategyPanel.getByLabel("As-Of Date").fill("2024-01-05");
}

test("page supports the full research loop from source Strategy to compared snapshots", async ({
  page,
}) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "MVP Research Loop" })).toBeVisible();
  await expect(page.getByTestId("strategy-row-daily_momentum_v1")).toBeVisible();
  await expect(page.getByTestId("strategy-panel")).toContainText(
    "Source Strategy Directory",
  );
  await expect(page.getByTestId("strategy-panel")).toContainText("Daily Momentum");
  await page.getByTestId("sync-source-strategies").click();
  await expect(page.getByTestId("strategy-row-daily_momentum_v1")).toBeVisible();

  await page.getByLabel("Additional Strategy Path").fill(fixtureStrategyDir);
  await page.getByTestId("discover-strategies").click();
  await expect(page.getByTestId("strategy-row-e2e_close_ranker")).toBeVisible();
  await page.getByTestId("strategy-row-daily_momentum_v1").click();

  await fillMarketDataDates(page);
  await page.getByTestId("sync-market-data").click();
  await expect(page.getByTestId("sync-panel")).toContainText("succeeded");
  await expect(page.getByTestId("sync-panel")).toContainText("Last Success");
  await page.getByTestId("sync-panel").getByRole("button", { name: "Refresh" }).click();
  await expect(page.getByTestId("sync-panel")).toContainText("Recent Failures");

  const strategyPanel = page.getByTestId("strategy-panel");
  await strategyPanel.getByLabel("lookback_days").fill("3");
  await strategyPanel.getByRole("button", { name: "Reset" }).click();
  await expect(strategyPanel.getByLabel("lookback_days")).toHaveValue("20");
  await strategyPanel.getByText("Source Snapshot").click();
  await expect(strategyPanel.locator(".source-view")).toContainText("def select");
  await configureDailyMomentum(page, "2");
  await page.getByTestId("run-strategy").click();
  await expect(page.getByTestId("candidate-results")).toContainText("stock:000001");
  await expect(page.getByTestId("candidate-results")).toContainText("stock:000002");
  await expect(page.getByTestId("candidate-results")).toContainText(
    "adjusted_close_momentum",
  );

  await configureDailyMomentum(page, "1");
  await page.getByTestId("run-strategy").click();
  await expect(page.getByTestId("candidate-results")).toContainText("stock:000001");

  await page.getByTestId("strategy-run-snapshots-tab").click();
  const runSnapshotRows = page
    .getByTestId("snapshots-panel")
    .locator('[data-testid^="strategy-run-snapshot-"]');
  await expect(runSnapshotRows).toHaveCount(2);
  const runSnapshotIds = await runSnapshotRows.evaluateAll((rows) =>
    rows.map(
      (row) =>
        row.getAttribute("data-testid")?.replace("strategy-run-snapshot-", "") ?? "",
    ),
  );
  for (const id of runSnapshotIds) {
    expect(id).not.toBe("");
    await page.getByTestId(`compare-strategy-run-${id}`).check();
  }
  await page.getByTestId("compare-strategy-runs").click();
  await expect(page.getByTestId("snapshots-panel")).toContainText("Comparison");
  await expect(page.getByTestId("snapshots-panel")).toContainText("stock:000001");

  await configureDailyMomentum(page, "2");
  await strategyPanel.getByLabel("Start Date").fill("2024-01-02");
  await strategyPanel.getByLabel("End Date").fill("2024-01-04");
  await strategyPanel.getByLabel("Top N").fill("2");
  await strategyPanel.getByLabel("Horizons").fill("1");
  await page.getByTestId("run-backtest").click();
  await expect(page.getByTestId("backtest-results")).toContainText("Selection Dates");
  await expect(page.getByTestId("backtest-results")).toContainText("Avg Return");

  await strategyPanel.getByLabel("Top N").fill("1");
  await page.getByTestId("run-backtest").click();
  await expect(page.getByTestId("backtest-results")).toContainText("Selection Dates");

  await page.getByTestId("backtest-snapshots-tab").click();
  const backtestSnapshotRows = page
    .getByTestId("snapshots-panel")
    .locator('[data-testid^="backtest-snapshot-"]');
  await expect(backtestSnapshotRows).toHaveCount(2);
  const backtestSnapshotIds = await backtestSnapshotRows.evaluateAll((rows) =>
    rows.map(
      (row) =>
        row.getAttribute("data-testid")?.replace("backtest-snapshot-", "") ?? "",
    ),
  );
  for (const id of backtestSnapshotIds) {
    expect(id).not.toBe("");
    await page.getByTestId(`compare-backtest-${id}`).check();
  }
  await page.getByTestId("compare-backtests").click();
  await expect(page.getByTestId("snapshots-panel")).toContainText("Comparison");
  await expect(page.getByTestId("snapshots-panel")).toContainText("average_return");
});

test("strategy management remains usable on a mobile viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");

  await expect(page.getByTestId("strategy-row-daily_momentum_v1")).toBeVisible();
  await expect(page.getByLabel("lookback_days")).toBeVisible();

  const layout = await page.evaluate(() => {
    const offenders = Array.from(
      document.querySelectorAll(
        "button, input, select, dd, .strategy-row, .strategy-detail, .status-panel",
      ),
    )
      .map((element) => ({
        tag: element.tagName.toLowerCase(),
        className: element.getAttribute("class") ?? "",
        scrollWidth: element.scrollWidth,
        clientWidth: element.clientWidth,
      }))
      .filter((item) => item.scrollWidth > item.clientWidth + 2);
    return {
      bodyScrollWidth: document.body.scrollWidth,
      documentWidth: document.documentElement.clientWidth,
      offenders,
    };
  });

  expect(layout.bodyScrollWidth).toBe(layout.documentWidth);
  expect(layout.offenders).toEqual([]);
});
