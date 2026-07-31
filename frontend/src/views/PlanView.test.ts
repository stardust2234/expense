import { createApp, nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMock = vi.hoisted(() => ({
  paymentCycles: vi.fn(),
  categories: vi.fn(),
  safeSpendingForecast: vi.fn(),
  cycleCommitments: vi.fn(),
  cycleAllowances: vi.fn(),
  createPaymentCycle: vi.fn(),
  updatePaymentCycle: vi.fn(),
  deletePaymentCycle: vi.fn(),
  createCommitment: vi.fn(),
  updateCommitment: vi.fn(),
  deleteCommitment: vi.fn(),
  createAllowance: vi.fn(),
  updateAllowance: vi.fn(),
  deleteAllowance: vi.fn(),
  previewPlan: vi.fn(),
  confirmPlan: vi.fn(),
}));

vi.mock("../api/client", () => ({ api: apiMock }));

import PlanView from "./PlanView.vue";

const cycle = {
  id: 7,
  name: "Benefit payment",
  start_date: "2026-07-01",
  end_date: "2026-08-01",
  next_payment_date: "2026-07-29",
  expected_income_amount: 80000,
  currency: "GBP",
  opening_balance: 50000,
  current_balance: 42000,
  status: "active" as const,
  created_at: "2026-07-24T10:00:00Z",
  updated_at: "2026-07-24T10:00:00Z",
};
const commitment = {
  id: 12,
  payment_cycle_id: 7,
  funding_payment_date: "2026-07-29",
  name: "Rent",
  amount: 32000,
  currency: "GBP",
  due_date: "2026-08-01",
  priority: "protected" as const,
  category_id: 1,
  status: "pending" as const,
  recurrence: "monthly",
  matched_expense_id: null,
  created_at: "2026-07-24T10:00:00Z",
  updated_at: "2026-07-24T10:00:00Z",
};
const allowance = {
  id: 4,
  payment_cycle_id: 7,
  name: "Food",
  allowance_type: "food" as const,
  amount: 12000,
  priority: "essential" as const,
  category_id: 2,
};
const futureCycle = {
  ...cycle,
  id: 8,
  start_date: "2026-08-01",
  end_date: "2026-09-01",
  next_payment_date: "2026-08-29",
  status: "planned" as const,
};
const forecast = {
  payment_cycle_id: 7,
  as_of_date: "2026-07-25",
  next_payment_date: "2026-08-21",
  currency: "GBP",
  balance_source: "current" as const,
  usable_balance: 42000,
  pending_commitments: 32000,
  allowance_reserves: 12000,
  safe_to_spend: 0,
  shortfall: 2000,
  projected_balance: -2000,
  days_remaining: 27,
  safe_daily_amount: 0,
  safe_weekly_amount: 0,
  essential_cost_coverage: 0.95,
  allowances: [
    { ...allowance, spent_amount: 2500, remaining_amount: 9500 },
  ],
  risks: ["Essentials exceed the usable balance."],
};

let host: HTMLDivElement;

async function settle() {
  await Promise.resolve();
  await Promise.resolve();
  await nextTick();
}

function button(text: string, within: ParentNode = host) {
  const match = [...within.querySelectorAll("button")].find(
    (item) => item.textContent?.trim() === text,
  );
  if (!match) throw new Error(`Button ${text} was not found`);
  return match as HTMLButtonElement;
}

function inputValue(input: HTMLInputElement, value: string) {
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

beforeEach(async () => {
  vi.clearAllMocks();
  apiMock.paymentCycles.mockResolvedValue({
    items: [cycle],
    total: 1,
    limit: 100,
    offset: 0,
  });
  apiMock.categories.mockResolvedValue([
    { id: 1, name: "Housing", parent_category_id: null },
    { id: 2, name: "Groceries", parent_category_id: null },
  ]);
  apiMock.safeSpendingForecast.mockResolvedValue(forecast);
  apiMock.cycleCommitments.mockResolvedValue({ items: [commitment], total: 1 });
  apiMock.cycleAllowances.mockResolvedValue({ items: [allowance], total: 1 });
  apiMock.updatePaymentCycle.mockResolvedValue(cycle);
  apiMock.createPaymentCycle.mockResolvedValue(futureCycle);
  apiMock.updateCommitment.mockResolvedValue(commitment);
  apiMock.updateAllowance.mockResolvedValue(allowance);
  apiMock.previewPlan.mockResolvedValue({
    target_month: "2026-08-01",
    end_date: "2026-09-01",
    currency: "GBP",
    income: {
      proposal_id: "income:benefit",
      description: "Benefit",
      expected_amount: 80000,
      payment_date: "2026-08-29",
      occurrence_count: 3,
      confidence: 0.9,
      evidence_transaction_ids: [1, 2, 3],
    },
    commitments: [{
      proposal_id: "commitment:rent",
      name: "Rent",
      amount: 32000,
      due_date: "2026-08-01",
      category_id: 1,
      category_name: "Housing",
      priority: "protected",
      recurrence: "monthly",
      occurrence_count: 3,
      confidence: 0.9,
      evidence_transaction_ids: [4, 5, 6],
    }],
    allowances: [],
  });
  apiMock.confirmPlan.mockResolvedValue({
    payment_cycle_id: 8,
    created_cycle: true,
    created_commitment_ids: [13],
    created_allowance_ids: [],
  });

  host = document.createElement("div");
  document.body.append(host);
  createApp(PlanView).mount(host);
  await settle();
});

afterEach(() => {
  document.body.innerHTML = "";
});

describe("Plan page editing", () => {
  it("previews and confirms a transaction-inferred plan", async () => {
    const inferencePanel = [...host.querySelectorAll("article")].find((item) =>
      item.textContent?.includes("Build from imported transactions"),
    ) as HTMLElement;
    const balance = inferencePanel.querySelector('input[type="number"]') as HTMLInputElement;
    inputValue(balance, "400");
    button("Preview inferred plan", inferencePanel).click();
    await settle();

    expect(apiMock.previewPlan).toHaveBeenCalled();
    button("Confirm selected plan", inferencePanel).click();
    await settle();

    expect(apiMock.confirmPlan).toHaveBeenCalledWith(
      expect.objectContaining({
        target_month: "2026-08-01",
        opening_balance: 40000,
        commitment_proposal_ids: ["commitment:rent"],
      }),
    );
  });

  it("creates the next non-overlapping cycle as planned", async () => {
    button("Add cycle").click();
    await nextTick();

    const setupPanel = [...host.querySelectorAll(".setup-panel")].find((item) =>
      item.textContent?.includes("Add payment cycle"),
    ) as HTMLElement;
    const form = setupPanel.querySelector("form") as HTMLFormElement;
    const dates = form.querySelectorAll('input[type="date"]');
    expect((dates[0] as HTMLInputElement).value).toBe("2026-08-29");
    inputValue(
      form.querySelectorAll('input[type="number"]')[1] as HTMLInputElement,
      "400",
    );
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await settle();

    expect(apiMock.createPaymentCycle).toHaveBeenCalledWith(
      expect.objectContaining({
        next_payment_date: "2026-08-29",
        opening_balance: 40000,
        status: "planned",
      }),
    );
  });

  it("edits the selected payment cycle using minor currency units", async () => {
    button("Edit cycle").click();
    await nextTick();

    const form = host.querySelector(".cycle-details form") as HTMLFormElement;
    inputValue(form.querySelector("input") as HTMLInputElement, "Universal Credit");
    inputValue(
      form.querySelector('input[type="number"]') as HTMLInputElement,
      "845.50",
    );
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await settle();

    expect(apiMock.updatePaymentCycle).toHaveBeenCalledWith(
      7,
      expect.objectContaining({
        name: "Universal Credit",
        expected_income_amount: 84550,
        currency: "GBP",
      }),
    );
  });

  it("edits a commitment and can mark it paid", async () => {
    const row = host.querySelector(".plan-row-wrap") as HTMLElement;
    button("Edit", row).click();
    await nextTick();

    const form = row.querySelector("form") as HTMLFormElement;
    inputValue(form.querySelector('input[type="number"]') as HTMLInputElement, "325");
    const status = [...form.querySelectorAll("select")].find((select) =>
      [...select.options].some((option) => option.value === "paid"),
    ) as HTMLSelectElement;
    status.value = "paid";
    status.dispatchEvent(new Event("change", { bubbles: true }));
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await settle();

    expect(apiMock.updateCommitment).toHaveBeenCalledWith(
      12,
      expect.objectContaining({ amount: 32500, status: "paid" }),
    );
  });

  it("edits an allowance and preserves its category link", async () => {
    const row = host.querySelector(".allowance-row") as HTMLElement;
    button("Edit", row).click();
    await nextTick();

    const form = row.querySelector("form") as HTMLFormElement;
    inputValue(form.querySelector('input[type="number"]') as HTMLInputElement, "150");
    form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
    await settle();

    expect(apiMock.updateAllowance).toHaveBeenCalledWith(
      4,
      expect.objectContaining({
        amount: 15000,
        allowance_type: "food",
        category_id: 2,
      }),
    );
  });
});

