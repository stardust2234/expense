<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import { api } from "../api/client";
import type { Category, ImportBatch, Merchant, Transaction } from "../types/api";
import { formatUkDate } from "../utils/date";
import { formatMoney } from "../utils/money";
import { formatCategoryName } from "../utils/category";

const items = ref<Transaction[]>([]);
const { t } = useI18n();
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
    error.value = caught instanceof Error ? caught.message : t("views.transactions.errors.load");
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
    error.value = caught instanceof Error ? caught.message : t("views.transactions.errors.update");
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
    error.value = caught instanceof Error ? caught.message : t("views.transactions.errors.filters");
  }
  await load();
});
</script>

<template>
  <section class="view-stack">
    <header class="view-heading"><div><p class="eyebrow">{{ t("views.transactions.eyebrow") }}</p><h2>{{ t("views.transactions.title") }}</h2><p>{{ t("views.transactions.subtitle") }}</p></div></header>
    <form class="panel filter-bar transaction-filters" @submit.prevent="applyFilters">
      <label class="field grow-field"><span>{{ t("views.transactions.search") }}</span><input v-model="search" :placeholder="t('views.transactions.searchPlaceholder')" /></label>
      <label class="field"><span>{{ t("common.status") }}</span><select v-model="status"><option value="">{{ t("views.transactions.all") }}</option><option value="categorised">{{ t("views.transactions.statuses.categorised") }}</option><option value="needs_review">{{ t("views.transactions.statuses.needs_review") }}</option><option value="normalised">{{ t("views.transactions.statuses.normalised") }}</option></select></label>
      <label class="field"><span>{{ t("common.category") }}</span><select v-model="categoryId"><option value="">{{ t("views.transactions.all") }}</option><option v-for="category in categories" :key="category.id" :value="String(category.id)">{{ formatCategoryName(category) }}</option></select></label>
      <label class="field"><span>{{ t("views.transactions.merchant") }}</span><select v-model="merchantId"><option value="">{{ t("views.transactions.all") }}</option><option v-for="merchant in merchants" :key="merchant.id" :value="String(merchant.id)">{{ merchant.name }}</option></select></label>
      <label class="field"><span>{{ t("common.currency") }}</span><input v-model="currency" maxlength="3" :placeholder="t('views.transactions.all')" /></label>
      <label class="field"><span>{{ t("views.transactions.from") }}</span><input v-model="dateFrom" type="date" /></label>
      <label class="field"><span>{{ t("views.transactions.to") }}</span><input v-model="dateTo" type="date" /></label>
      <label class="field batch-filter"><span>{{ t("views.transactions.batch") }}</span><select v-model="importBatchId"><option value="">{{ t("views.transactions.all") }}</option><option v-for="batch in importBatches" :key="batch.id" :value="String(batch.id)">#{{ batch.id }} · {{ batch.source_filename }}</option></select></label>
      <button class="secondary-button">{{ t("views.transactions.applyFilters") }}</button>
    </form>
    <p v-if="error" class="message error-message">{{ error }}</p>
    <div class="bulk-bar">
      <span>{{ t("views.transactions.selected", { selected: selected.length, total }) }}</span>
      <select v-model="bulkCategory"><option value="">{{ t("views.transactions.chooseCategory") }}</option><option v-for="category in categories" :key="category.id" :value="String(category.id)">{{ formatCategoryName(category) }}</option></select>
      <button class="primary-button" :disabled="!selected.length || !bulkCategory" @click="bulkUpdate">{{ t("views.transactions.applyCategory") }}</button>
    </div>
    <div class="panel table-wrap">
      <table>
        <thead><tr><th><input type="checkbox" @change="toggleAll" /></th><th>{{ t("views.transactions.date") }}</th><th>{{ t("views.transactions.description") }}</th><th>{{ t("views.transactions.merchant") }}</th><th>{{ t("common.category") }}</th><th>{{ t("common.status") }}</th><th>{{ t("views.transactions.total") }}</th></tr></thead>
        <tbody>
          <tr v-for="item in items" :key="item.id">
            <td><input v-model="selected" type="checkbox" :value="item.id" /></td><td>{{ formatUkDate(item.transaction_date) }}</td><td><strong>{{ item.description }}</strong></td><td>{{ item.merchant_name ?? "—" }}</td><td>{{ item.category_name ? formatCategoryName({ code: item.category_code, name: item.category_name }) : "—" }}</td><td><span class="status-pill" :class="item.status">{{ t(`views.transactions.statuses.${item.status}`) }}</span></td><td class="numeric">{{ formatMoney(item.amount, item.currency) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="loading" class="table-empty">{{ t("views.transactions.loading") }}</div><div v-else-if="!items.length" class="table-empty">{{ t("views.transactions.empty") }}</div>
    </div>
    <nav class="pagination" :aria-label="t('views.transactions.pages')"><button class="secondary-button" :disabled="offset === 0 || loading" @click="changePage(-1)">{{ t("views.transactions.previous") }}</button><span>{{ t("views.transactions.page", { page: currentPage, pages: totalPages, count: total }) }}</span><button class="secondary-button" :disabled="offset + pageSize >= total || loading" @click="changePage(1)">{{ t("views.transactions.next") }}</button>
    </nav>
  </section>
</template>

