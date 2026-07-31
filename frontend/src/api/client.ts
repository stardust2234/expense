import type {
  AllowanceType,
  Category,
  CategoryTotal,
  Commitment,
  CycleAllowance,
  HealthResponse,
  ImportBatch,
  Merchant,
  MerchantAlias,
  MonthlyTotal,
  PaymentPeriod,
  PaymentCycle,
  PlanInferencePreview,
  RecurringExpense,
  RecurringOpportunity,
  ReviewQueueResponse,
  Rule,
  SafeSpendingForecast,
  SpendingPriority,
  Transaction,
} from "../types/api";

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, init);
  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = (await response.json()) as { detail?: string };
      message = payload.detail ?? message;
    } catch {
      // Keep the status-based fallback for non-JSON errors.
    }
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export const api = {
  health: () => request<HealthResponse>("/health"),

  importStatement: (file: File, defaultCurrency: string) => {
    const form = new FormData();
    form.append("file", file);
    if (defaultCurrency.trim()) {
      form.append("default_currency", defaultCurrency.trim().toUpperCase());
    }
    return request<ImportBatch>("/imports/file", { method: "POST", body: form });
  },
  importHistory: (limit = 25, offset = 0) =>
    request<{ items: ImportBatch[]; total: number; limit: number; offset: number }>(
      `/imports?limit=${limit}&offset=${offset}`,
    ),
  importBatch: (batchId: number) => request<ImportBatch>(`/imports/${batchId}`),
  retryImport: (batchId: number) =>
    request<ImportBatch>(`/imports/${batchId}/retry`, { method: "POST" }),

  categories: async () => (await request<{ items: Category[] }>("/categories")).items,
  createCategory: (
    name: string,
    parentCategoryId: number | null,
    defaultPriority: SpendingPriority,
  ) =>
    request<Category>("/categories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        parent_category_id: parentCategoryId,
        default_priority: defaultPriority,
      }),
    }),
  updateCategory: (
    id: number,
    name: string,
    parentCategoryId: number | null,
    defaultPriority: SpendingPriority,
  ) =>
    request<Category>(`/categories/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        parent_category_id: parentCategoryId,
        default_priority: defaultPriority,
      }),
    }),
  deleteCategory: (id: number) =>
    request<void>(`/categories/${id}`, { method: "DELETE" }),

  reviewQueue: (limit = 50, offset = 0) =>
    request<ReviewQueueResponse>(`/review-queue?limit=${limit}&offset=${offset}`),

  resolveReview: (
    expenseId: number,
    categoryId: number,
    matchPattern: string,
    priority = 0,
  ) =>
    request(`/review-queue/${expenseId}/resolve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        category_id: categoryId,
        save_rule: true,
        match_pattern: matchPattern || null,
        priority,
      }),
    }),

  categoryTotals: async (params: URLSearchParams) =>
    (
      await request<{ items: CategoryTotal[] }>(
        `/reports/category-totals?${params.toString()}`,
      )
    ).items,

  monthlyTotals: async (params: URLSearchParams) =>
    (await request<{ items: MonthlyTotal[] }>(`/reports/monthly?${params.toString()}`))
      .items,
  recurringExpenses: async (params: URLSearchParams) =>
    (await request<{ items: RecurringExpense[] }>(`/reports/recurring?${params}`)).items,
  paymentPeriodReports: async (currency = "") => {
    const params = new URLSearchParams();
    if (currency.trim()) params.set("currency", currency.trim().toUpperCase());
    return (
      await request<{ items: PaymentPeriod[] }>(
        `/reports/payment-periods?${params}`,
      )
    ).items;
  },
  recurringOpportunities: async (params: URLSearchParams) =>
    (
      await request<{ items: RecurringOpportunity[] }>(
        `/reports/recurring-opportunities?${params}`,
      )
    ).items,
  saveRecurringOpportunity: (payload: {
    identity_key: string;
    description: string;
    currency: string;
    current_monthly_cost: number;
    replacement_monthly_cost: number | null;
    one_off_switching_cost: number;
    difficulty: RecurringOpportunity["difficulty"];
    decision: RecurringOpportunity["decision"];
    notes: string | null;
  }) =>
    request("/reports/recurring-opportunities", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deleteRecurringOpportunity: (id: number) =>
    request<void>(`/reports/recurring-opportunities/${id}`, {
      method: "DELETE",
    }),
  exportUrl: (format: "csv" | "xlsx", filters = new URLSearchParams()) => {
    const params = new URLSearchParams(filters);
    params.set("format", format);
    return `${apiBaseUrl}/reports/export?${params}`;
  },

  paymentCycles: (limit = 100, offset = 0) =>
    request<{ items: PaymentCycle[]; total: number; limit: number; offset: number }>(
      `/payment-cycles?limit=${limit}&offset=${offset}`,
    ),
  createPaymentCycle: (payload: {
    name: string | null;
    next_payment_date: string;
    expected_income_amount: number;
    currency: string;
    opening_balance: number;
    current_balance: number | null;
    status: "planned" | "active";
  }) =>
    request<PaymentCycle>("/payment-cycles", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  updatePaymentCycle: (
    id: number,
    payload: Partial<
      Pick<
        PaymentCycle,
        | "name"
        | "next_payment_date"
        | "expected_income_amount"
        | "currency"
        | "opening_balance"
        | "current_balance"
        | "status"
      >
    >,
  ) =>
    request<PaymentCycle>(`/payment-cycles/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deletePaymentCycle: (id: number) =>
    request<void>(`/payment-cycles/${id}`, { method: "DELETE" }),
  cycleCommitments: (cycleId: number) =>
    request<{ items: Commitment[]; total: number }>(
      `/payment-cycles/${cycleId}/commitments`,
    ),
  createCommitment: (
    cycleId: number,
    payload: {
      name: string;
      amount: number;
      due_date: string;
      priority: SpendingPriority;
      category_id: number | null;
    },
  ) =>
    request<Commitment>(`/payment-cycles/${cycleId}/commitments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  updateCommitment: (
    id: number,
    payload: Partial<
      Pick<
        Commitment,
        | "name"
        | "amount"
        | "currency"
        | "due_date"
        | "priority"
        | "category_id"
        | "status"
        | "recurrence"
      >
    >,
  ) =>
    request<Commitment>(`/commitments/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deleteCommitment: (id: number) =>
    request<void>(`/commitments/${id}`, { method: "DELETE" }),
  cycleAllowances: (cycleId: number) =>
    request<{ items: CycleAllowance[]; total: number }>(
      `/payment-cycles/${cycleId}/allowances`,
    ),
  createAllowance: (
    cycleId: number,
    payload: {
      name: string;
      allowance_type: AllowanceType;
      amount: number;
      priority: SpendingPriority;
      category_id: number | null;
    },
  ) =>
    request<CycleAllowance>(`/payment-cycles/${cycleId}/allowances`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  updateAllowance: (
    id: number,
    payload: Partial<
      Pick<
        CycleAllowance,
        "name" | "allowance_type" | "amount" | "priority" | "category_id"
      >
    >,
  ) =>
    request<CycleAllowance>(`/allowances/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  deleteAllowance: (id: number) =>
    request<void>(`/allowances/${id}`, { method: "DELETE" }),
  safeSpendingForecast: (cycleId: number) =>
    request<SafeSpendingForecast>(`/payment-cycles/${cycleId}/forecast`),
  previewPlan: (targetMonth: string, currency: string) => {
    const params = new URLSearchParams({
      target_month: targetMonth,
      currency: currency.toUpperCase(),
    });
    return request<PlanInferencePreview>(`/plan-inference/preview?${params}`);
  },
  confirmPlan: (payload: {
    target_month: string;
    currency: string;
    opening_balance: number;
    current_balance: number | null;
    commitment_proposal_ids: string[];
    allowance_proposal_ids: string[];
  }) =>
    request<{
      payment_cycle_id: number;
      created_cycle: boolean;
      created_commitment_ids: number[];
      created_allowance_ids: number[];
    }>("/plan-inference/confirm", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  transactions: (params: URLSearchParams) =>
    request<{ items: Transaction[]; total: number }>(`/transactions?${params}`),
  bulkCategorise: (transactionIds: number[], categoryId: number) =>
    request<{ updated: number }>("/transactions/bulk", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ transaction_ids: transactionIds, category_id: categoryId }),
    }),

  rules: async () => (await request<{ items: Rule[] }>("/rules")).items,
  updateRule: (
    id: number,
    changes: Partial<Pick<Rule, "match_pattern" | "category_id" | "priority" | "enabled">>,
  ) =>
    request<Rule>(`/rules/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),
  deleteRule: (id: number) => request<void>(`/rules/${id}`, { method: "DELETE" }),

  merchants: async () => (await request<{ items: Merchant[] }>("/merchants")).items,

  createMerchant: (name: string, aliases: string[]) =>
    request<Merchant>("/merchants", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, aliases }),
    }),

  addMerchantAlias: (merchantId: number, pattern: string) =>
    request<MerchantAlias>(`/merchants/${merchantId}/aliases`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pattern }),
    }),

  deleteMerchantAlias: (merchantId: number, aliasId: number) =>
    request<void>(`/merchants/${merchantId}/aliases/${aliasId}`, { method: "DELETE" }),
  mergeMerchants: (targetMerchantId: number, sourceMerchantId: number) =>
    request<Merchant>(`/merchants/${targetMerchantId}/merge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_merchant_id: sourceMerchantId }),
    }),
};

