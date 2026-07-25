<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api } from "../api/client";
import type { Category, ImportBatch, Merchant, Transaction } from "../types/api";
import { formatUkDate } from "../utils/date";
import { formatMoney } from "../utils/money";

const items = ref<Transaction[]>([]);
const categories = ref<Category[]>([]);
const merchants = ref<Merchant[]>([]);
const importBatches = ref<ImportBatch[]>([]);
const selected = ref<number[]>([]);
const bulkCategory = ref("");
const search = ref("");
const status = ref("");
const categoryId = ref("");
const merchantId = ref("");
const importBatchId = ref("");
const currency = ref("");
const dateFrom = ref("");
const dateTo = ref("");
const total = ref(0);
const pageSize = 50;
const offset = ref(0);
const loading = ref(true);
const error = ref("");
const currentPage = computed(() => Math.floor(offset.value / pageSize) + 1);
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

async function load() {
  loading.value = true;
  error.value = "";
  const params = new URLSearchParams({
    limit: String(pageSize),
    offset: String(offset.value),
  });
  if (search.value) params.set("search", search.value);
  if (status.value) params.set("status", status.value);
  if (categoryId.value) params.set("category_id", categoryId.value);
  if (merchantId.value) params.set("merchant_id", merchantId.value);
  if (importBatchId.value) params.set("import_batch_id", importBatchId.value);
  if (currency.value.trim()) params.set("currency", currency.value.trim().toUpperCase());
  if (dateFrom.value) params.set("date_from", dateFrom.value);
  if (dateTo.value) params.set("date_to", dateTo.value);
  try {
    const page = await api.transactions(params);
    items.value = page.items;
    total.value = page.total;
    selected.value = [];
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Could not load transactions";
  } finally {
    loading.value = false;
  }
}

async function applyFilters() {
  offset.value = 0;
  await load();
}

async function changePage(direction: -1 | 1) {
  offset.value += direction * pageSize;
  await load();
}

async function bulkUpdate() {
  if (!selected.value.length || !bulkCategory.value) return;
  error.value = "";
  try {
    await api.bulkCategorise(selected.value, Number(bulkCategory.value));
    await load();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Could not update transactions";
  }
}

function toggleAll(event: Event) {
  selected.value = (event.target as HTMLInputElement).checked ? items.value.map((item) => item.id) : [];
}

onMounted(async () => {
  try {
    const [categoryItems, merchantItems, batches] = await Promise.all([
      api.categories(),
      api.merchants(),
      api.importHistory(100),
    ]);
    categories.value = categoryItems;
    merchants.value = merchantItems;
    importBatches.value = batches.items;
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Could not load filters";
  }
  await load();
});
</script>

<template>
  <section class="view-stack">
    <header class="view-heading"><div><p class="eyebrow">Ledger</p><h2>Transactions</h2><p>Search, filter and assign a category to multiple transactions at once.</p></div></header>
    <form class="panel filter-bar transaction-filters" @submit.prevent="applyFilters">
      <label class="field grow-field"><span>Search</span><input v-model="search" placeholder="Merchant or description" /></label>
      <label class="field"><span>Status</span><select v-model="status"><option value="">All</option><option value="categorised">Categorised</option><option value="needs_review">Needs review</option><option value="normalised">Normalised</option></select></label>
      <label class="field"><span>Category</span><select v-model="categoryId"><option value="">All</option><option v-for="category in categories" :key="category.id" :value="String(category.id)">{{ category.name }}</option></select></label>
      <label class="field"><span>Merchant</span><select v-model="merchantId"><option value="">All</option><option v-for="merchant in merchants" :key="merchant.id" :value="String(merchant.id)">{{ merchant.name }}</option></select></label>
      <label class="field"><span>Currency</span><input v-model="currency" maxlength="3" placeholder="All" /></label>
      <label class="field"><span>From</span><input v-model="dateFrom" type="date" /></label>
      <label class="field"><span>To</span><input v-model="dateTo" type="date" /></label>
      <label class="field batch-filter"><span>Import batch</span><select v-model="importBatchId"><option value="">All</option><option v-for="batch in importBatches" :key="batch.id" :value="String(batch.id)">#{{ batch.id }} · {{ batch.source_filename }}</option></select></label>
      <button class="secondary-button">Apply filters</button>
    </form>
    <p v-if="error" class="message error-message">{{ error }}</p>
    <div class="bulk-bar">
      <span><strong>{{ selected.length }}</strong> selected · {{ total }} total</span>
      <select v-model="bulkCategory"><option value="">Choose category</option><option v-for="category in categories" :key="category.id" :value="String(category.id)">{{ category.name }}</option></select>
      <button class="primary-button" :disabled="!selected.length || !bulkCategory" @click="bulkUpdate">Apply category</button>
    </div>
    <div class="panel table-wrap">
      <table>
        <thead><tr><th><input type="checkbox" @change="toggleAll" /></th><th>Date</th><th>Description</th><th>Merchant</th><th>Category</th><th>Status</th><th>Total</th></tr></thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td><input v-model="selected" type="checkbox" :value="item.id" /></td><td>{{ formatUkDate(item.transaction_date) }}</td><td><strong>{{ item.description }}</strong></td><td>{{ item.merchant_name ?? "—" }}</td><td>{{ item.category_name ?? "—" }}</td><td><span class="status-pill">{{ item.status.replace("_", " ") }}</span></td><td class="numeric">{{ formatMoney(item.amount, item.currency) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="loading" class="table-empty">Loading transactions…</div>
      <div v-else-if="!items.length" class="table-empty">No transactions match these filters.</div>
    </div>
    <nav class="pagination" aria-label="Transaction pages">
      <button class="secondary-button" :disabled="offset === 0 || loading" @click="changePage(-1)">Previous</button>
      <span>Page {{ currentPage }} of {{ totalPages }} · {{ total }} transactions</span>
      <button class="secondary-button" :disabled="offset + pageSize >= total || loading" @click="changePage(1)">Next</button>
    </nav>
  </section>
</template>

