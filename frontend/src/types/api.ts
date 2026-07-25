export type HealthResponse = {
  status: string;
  service: string;
  environment: string;
  database: string;
};

export type CsvImportResult = {
  batch_id: number;
  imported: number;
  normalised: number;
  normalisation_failed: number;
  categorised: number;
  needs_review: number;
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
  name: string;
  parent_category_id: number | null;
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
  category_name: string;
  currency: string;
  total_amount: number;
  transaction_count: number;
};

export type MonthlyTotal = {
  month: string;
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

export type DashboardSummary = {
  month: string;
  spending: number;
  income: number;
  net: number;
  currency: string;
  review_count: number;
  transaction_count: number;
  category_totals: CategoryTotal[];
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

