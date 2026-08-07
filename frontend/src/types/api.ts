export type HealthResponse = {
  status: string;
  service: string;
  environment: string;
  database: string;
};

export type ImportBatch = {
  id: number;
  source_filename: string;
  source_type: string;
  content_sha256: string | null;
  default_currency: string | null;
  total_rows: number;
  normalised_rows: number;
  failed_rows: number;
  duplicate_rows: number;
  categorised_rows: number;
  needs_review_rows: number;
  status: string;
  processing_error: string | null;
  imported_at: string;
  processing_started_at: string | null;
  processing_completed_at: string | null;
};

export type Category = {
  id: number;
  code: string | null;
  name: string;
  parent_category_id: number | null;
  default_priority: SpendingPriority;
};

export type ReviewQueueItem = {
  id: number;
  transaction_date: string;
  description: string;
  normalised_description: string;
  amount: number;
  currency: string;
  merchant_id: number | null;
  merchant_name: string | null;
  category_id: number | null;
  category_name: string | null;
  confidence_score: string | null;
  source_filename: string | null;
  source_row_number: number | null;
  raw_data: Record<string, string | null> | null;
  created_at: string;
};

export type ReviewQueueResponse = {
  items: ReviewQueueItem[];
  total: number;
  limit: number;
  offset: number;
};

export type CategoryTotal = {
  category_id: number;
  category_code: string | null;
  category_name: string;
  currency: string;
  total_amount: number;
  transaction_count: number;
};

export type PriorityTotal = {
  priority: SpendingPriority;
  currency: string;
  total_amount: number;
  transaction_count: number;
};

export type MerchantAlias = {
  id: number;
  pattern: string;
};

export type Merchant = {
  id: number;
  name: string;
  aliases: MerchantAlias[];
};

export type SpendingPriority =
  | "protected"
  | "essential"
  | "adjustable"
  | "optional"
  | "irregular_essential"
  | "transfer";

export type PaymentCycle = {
  id: number;
  name: string | null;
  start_date: string;
  end_date: string;
  next_payment_date: string;
  expected_income_amount: number;
  currency: string;
  opening_balance: number;
  current_balance: number | null;
  status: "planned" | "active" | "closed";
  created_at: string;
  updated_at: string;
};

export type Commitment = {
  id: number;
  payment_cycle_id: number;
  funding_payment_date: string;
  name: string;
  amount: number;
  currency: string;
  due_date: string;
  priority: SpendingPriority;
  category_id: number | null;
  status: "pending" | "paid" | "skipped";
  recurrence: string | null;
  matched_expense_id: number | null;
  created_at: string;
  updated_at: string;
};

export type AllowanceType =
  | "food"
  | "transport"
  | "irregular_cost"
  | "emergency"
  | "custom";

export type CycleAllowance = {
  id: number;
  payment_cycle_id: number;
  name: string;
  allowance_type: AllowanceType;
  amount: number;
  priority: SpendingPriority;
  category_id: number | null;
};

export type AllowanceForecast = {
  id: number;
  name: string;
  allowance_type: AllowanceType;
  priority: SpendingPriority;
  amount: number;
  spent_amount: number;
  remaining_amount: number;
};

export type SafeSpendingForecast = {
  payment_cycle_id: number;
  as_of_date: string;
  funding_start_date: string;
  funding_end_date: string;
  funding_income_amount: number;
  next_payment_date: string;
  next_income_amount: number;
  currency: string;
  balance_source: "current" | "funding_income";
  usable_balance: number;
  pending_commitments: number;
  allowance_reserves: number;
  safe_to_spend: number;
  shortfall: number;
  projected_balance: number;
  days_remaining: number;
  safe_daily_amount: number;
  safe_weekly_amount: number;
  essential_cost_coverage: number | null;
  allowances: AllowanceForecast[];
  risks: string[];
};

export type InferredIncome = {
  proposal_id: string;
  identity_key: string;
  description: string;
  expected_amount: number;
  nominal_payment_date: string;
  payment_date: string;
  date_adjusted: boolean;
  occurrence_count: number;
  confidence: number;
  evidence_transaction_ids: number[];
  state: "new" | "unchanged" | "changed";
};

export type InferredCommitment = {
  proposal_id: string;
  identity_key: string;
  name: string;
  amount: number;
  due_date: string;
  category_id: number;
  category_name: string;
  priority: SpendingPriority;
  recurrence: string;
  occurrence_count: number;
  confidence: number;
  evidence_transaction_ids: number[];
  state: "new" | "unchanged" | "changed";
  existing_id: number | null;
};

export type InferredAllowance = {
  proposal_id: string;
  identity_key: string;
  name: string;
  allowance_type: AllowanceType;
  amount: number;
  category_id: number;
  category_name: string;
  priority: SpendingPriority;
  months_observed: number;
  confidence: number;
  evidence_transaction_ids: number[];
  state: "new" | "unchanged" | "changed";
  existing_id: number | null;
};

export type PlanInferencePreview = {
  target_month: string;
  end_date: string;
  currency: string;
  incomes: InferredIncome[];
  commitments: InferredCommitment[];
  allowances: InferredAllowance[];
  impact: {
    expected_income: number;
    commitments: number;
    essential_allowances: number;
    net_before_balance: number;
    period_days: number;
  };
};

export type Transaction = {
  id: number;
  transaction_date: string;
  description: string;
  normalised_description: string;
  amount: number;
  currency: string;
  status: string;
  merchant_id: number | null;
  merchant_name: string | null;
  category_id: number | null;
  category_code: string | null;
  category_name: string | null;
  confidence_score: string | null;
};

export type Rule = {
  id: number;
  match_pattern: string;
  category_id: number;
  category_name: string;
  priority: number;
  enabled: boolean;
  match_count: number;
};

export type RecurringExpense = {
  description: string;
  currency: string;
  average_amount: number;
  occurrence_count: number;
  cadence: string;
  typical_interval_days: number;
  last_seen: string;
};

export type PaymentPeriod = {
  payment_cycle_id: number;
  name: string | null;
  start_date: string;
  end_date: string;
  next_payment_date: string;
  currency: string;
  status: string;
  income: number;
  spending: number;
  net: number;
  transaction_count: number;
  protected_spending: number;
  essential_spending: number;
  adjustable_spending: number;
  optional_spending: number;
  irregular_essential_spending: number;
};

export type RecurringOpportunity = {
  opportunity_id: number | null;
  identity_key: string;
  description: string;
  currency: string;
  cadence: string;
  occurrence_count: number;
  last_seen: string;
  current_monthly_cost: number;
  replacement_monthly_cost: number | null;
  one_off_switching_cost: number;
  monthly_saving: number | null;
  first_year_saving: number | null;
  difficulty: "easy" | "moderate" | "hard";
  decision: "review" | "planned" | "accepted" | "rejected";
  notes: string | null;
};
export interface AuthUser {
  id: number;
  email: string;
  display_name: string;
  workspace_id: number;
  trial_ends_at: string;
  access_expires_at: string | null;
  access_active: boolean;
}

