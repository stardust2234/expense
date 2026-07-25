import { afterEach, describe, expect, it, vi } from "vitest";

import { api } from "./client";

function jsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("financial-plan API contract", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it.each([
    {
      invoke: () =>
        api.updatePaymentCycle(7, {
          name: "Universal Credit",
          next_payment_date: "2026-08-21",
          expected_income_amount: 84500,
          status: "active",
        }),
      path: "/api/payment-cycles/7",
      body: {
        name: "Universal Credit",
        next_payment_date: "2026-08-21",
        expected_income_amount: 84500,
        status: "active",
      },
    },
    {
      invoke: () =>
        api.updateCommitment(12, {
          name: "Council tax",
          amount: 11450,
          category_id: null,
          status: "paid",
          recurrence: "monthly",
        }),
      path: "/api/commitments/12",
      body: {
        name: "Council tax",
        amount: 11450,
        category_id: null,
        status: "paid",
        recurrence: "monthly",
      },
    },
    {
      invoke: () =>
        api.updateAllowance(4, {
          name: "Food",
          allowance_type: "food",
          amount: 16000,
          priority: "essential",
          category_id: 3,
        }),
      path: "/api/allowances/4",
      body: {
        name: "Food",
        allowance_type: "food",
        amount: 16000,
        priority: "essential",
        category_id: 3,
      },
    },
  ])("PATCHes $path using the backend field names", async ({ invoke, path, body }) => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}));
    vi.stubGlobal("fetch", fetchMock);

    await invoke();

    expect(fetchMock).toHaveBeenCalledOnce();
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(path);
    expect(init).toMatchObject({
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
    });
    expect(JSON.parse(String(init.body))).toEqual(body);
  });

  it.each([
    {
      invoke: () => api.deletePaymentCycle(7),
      path: "/api/payment-cycles/7",
    },
    {
      invoke: () => api.deleteRecurringOpportunity(11),
      path: "/api/reports/recurring-opportunities/11",
    },
  ])("DELETEs $path", async ({ invoke, path }) => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await invoke();

    expect(fetchMock).toHaveBeenCalledWith(path, { method: "DELETE" });
  });
});

