import { createApp, nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  paymentCycles: vi.fn(),
  recurringOpportunities: vi.fn(),
  safeSpendingForecast: vi.fn(),
  cycleCommitments: vi.fn(),
}));

vi.mock("../api/client", () => ({ api: apiMock }));

import DashboardView from "./DashboardView.vue";

const currentCycle = {
  id: 1,
  name: "Benefit payment",
  start_date: "2026-07-01",
  end_date: "2026-08-01",
  next_payment_date: "2026-08-25",
  expected_income_amount: 92480,
  currency: "GBP",
  opening_balance: 50000,
  current_balance: 42000,
  status: "active" as const,
  created_at: "2026-07-25T00:00:00Z",
  updated_at: "2026-07-25T00:00:00Z",
};
const pastCycle = {
  ...currentCycle,
  id: 3,
  start_date: "2026-04-01",
  end_date: "2026-05-01",
  next_payment_date: "2026-05-25",
  expected_income_amount: 90014,
  status: "planned" as const,
};

function forecast(cycleId: number) {
  const past = cycleId === pastCycle.id;
  return {
    payment_cycle_id: cycleId,
    as_of_date: "2026-07-25",
    next_payment_date: past ? pastCycle.next_payment_date : currentCycle.next_payment_date,
    currency: "GBP",
    balance_source: "current",
    usable_balance: 42000,
    pending_commitments: 0,
    allowance_reserves: 0,
    safe_to_spend: 42000,
    shortfall: 0,
    projected_balance: 42000,
    days_remaining: past ? 0 : 31,
    safe_daily_amount: past ? 0 : 1354,
    safe_weekly_amount: past ? 0 : 9483,
    essential_cost_coverage: null,
    allowances: [],
    risks: past ? ["The next payment date has arrived or passed"] : [],
  };
}

async function settle() {
  for (let index = 0; index < 5; index += 1) {
    await Promise.resolve();
    await nextTick();
  }
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-07-25T12:00:00"));
  apiMock.paymentCycles.mockResolvedValue({
    items: [currentCycle, pastCycle],
    total: 2,
    limit: 100,
    offset: 0,
  });
  apiMock.recurringOpportunities.mockResolvedValue([]);
  apiMock.safeSpendingForecast.mockImplementation(async (id: number) => forecast(id));
  apiMock.cycleCommitments.mockResolvedValue({ items: [], total: 0 });
});

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("Dashboard cycle timing", () => {
  it("selects the date-current cycle instead of an old expected payment", async () => {
    const host = document.createElement("div");
    document.body.append(host);
    const app = createApp(DashboardView);
    app.component("RouterLink", { template: "<a><slot /></a>" });
    app.mount(host);
    await settle();

    expect(apiMock.safeSpendingForecast).toHaveBeenCalledWith(1);
    expect(host.textContent).toContain("Next income");
    expect(host.textContent).toContain("25/08/2026");
  });

  it("labels a selected previous cycle as historical rather than expected income", async () => {
    const host = document.createElement("div");
    document.body.append(host);
    const app = createApp(DashboardView);
    app.component("RouterLink", { template: "<a><slot /></a>" });
    app.mount(host);
    await settle();

    const select = host.querySelector("select") as HTMLSelectElement;
    select.value = String(pastCycle.id);
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();

    expect(host.textContent).toContain("Historical payment cycle");
    expect(host.textContent).toContain("Cycle ended");
    expect(host.textContent).toContain("25/05/2026");
    expect(host.textContent).not.toContain("£900.14 expected");
  });
});

