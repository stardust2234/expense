import type {
  Category,
  CategoryTotal,
  DashboardSummary,
  HealthResponse,
  ImportBatch,
  Merchant,
  MerchantAlias,
  MonthlyTotal,
  RecurringExpense,
  ReviewQueueResponse,
  Rule,
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
  createCategory: (name: string, parentCategoryId: number | null) =>
    request<Category>("/categories", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, parent_category_id: parentCategoryId }),
    }),
  updateCategory: (id: number, name: string, parentCategoryId: number | null) =>
    request<Category>(`/categories/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, parent_category_id: parentCategoryId }),
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
  exportUrl: (format: "csv" | "xlsx", filters = new URLSearchParams()) => {
    const params = new URLSearchParams(filters);
    params.set("format", format);
    return `${apiBaseUrl}/reports/export?${params}`;
  },

  dashboard: (currency = "GBP", month = "") => {
    const params = new URLSearchParams({ currency });
    if (month) params.set("month", `${month}-01`);
    return request<DashboardSummary>(`/dashboard?${params}`);
  },

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

