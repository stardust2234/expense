<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { CircleCheck } from "@lucide/vue";
import { useI18n } from "vue-i18n";

import { api } from "../api/client";
import type { Category, ReviewQueueItem } from "../types/api";
import { formatUkDate } from "../utils/date";
import { formatMoney } from "../utils/money";
import { formatCategoryName } from "../utils/category";

const items = ref<ReviewQueueItem[]>([]);
const { t } = useI18n();
const categories = ref<Category[]>([]);
const total = ref(0);
const pageSize = 20;
const offset = ref(0);
const loading = ref(true);
const error = ref("");
const savingId = ref<number | null>(null);
const selectedCategories = ref<Record<number, string>>({});
const patterns = ref<Record<number, string>>({});
const currentPage = computed(() => Math.floor(offset.value / pageSize) + 1);
const totalPages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)));

const categoryNames = computed(
  () => new Map(categories.value.map((category) => [category.id, formatCategoryName(category)])),
);

function categoryLabel(category: Category) {
  if (!category.parent_category_id) return formatCategoryName(category);
  return `${categoryNames.value.get(category.parent_category_id) ?? t("views.review.other")} / ${formatCategoryName(category)}`;
}

async function loadQueue() {
  loading.value = true;
  error.value = "";
  try {
    const [queue, categoryItems] = await Promise.all([
      api.reviewQueue(pageSize, offset.value),
      api.categories(),
    ]);
    items.value = queue.items;
    total.value = queue.total;
    categories.value = categoryItems;
    for (const item of queue.items) {
      patterns.value[item.id] = item.merchant_name ?? item.normalised_description;
    }
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.review.errors.load");
  } finally {
    loading.value = false;
  }
}

async function resolve(item: ReviewQueueItem) {
  const categoryId = Number(selectedCategories.value[item.id]);
  if (!categoryId) return;
  savingId.value = item.id;
  error.value = "";
  try {
    await api.resolveReview(item.id, categoryId, patterns.value[item.id] ?? "");
    if (items.value.length === 1 && offset.value > 0) {
      offset.value = Math.max(0, offset.value - pageSize);
    }
    await loadQueue();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.review.errors.save");
  } finally {
    savingId.value = null;
  }
}

async function changePage(direction: -1 | 1) {
  offset.value += direction * pageSize;
  await loadQueue();
}

onMounted(loadQueue);
</script>

<template>
  <section class="view-stack">
    <header class="view-heading split-heading">
      <div>
        <p class="eyebrow">{{ t("views.review.eyebrow") }}</p><h2>{{ t("views.review.title") }}</h2><p>{{ t("views.review.subtitle") }}</p>
      </div>
      <div class="queue-count"><strong>{{ total }}</strong><span>{{ t("views.review.waiting") }}</span></div>
    </header>

    <p v-if="error" class="message error-message">{{ error }}</p>
    <div v-if="loading" class="panel empty-state">{{ t("views.review.loading") }}</div>
    <div v-else-if="!items.length" class="panel empty-state">
      <span class="empty-icon"><CircleCheck :size="22" :stroke-width="1.5" /></span>
      <h3>{{ t("views.review.caughtUp") }}</h3><p>{{ t("views.review.empty") }}</p>
    </div>

    <div v-else class="review-list">
      <article v-for="item in items" :key="item.id" class="panel review-card">
        <div class="transaction-summary">
          <div>
            <span class="date-chip">{{ formatUkDate(item.transaction_date) }}</span>
            <h3>{{ item.description }}</h3>
            <p>
              {{ item.merchant_name ?? t("views.review.merchantUnknown") }}
              <span v-if="item.source_filename">· {{ item.source_filename }}:{{ item.source_row_number }}</span>
            </p>
          </div>
          <strong class="money">{{ formatMoney(item.amount, item.currency) }}</strong>
        </div>

        <div class="review-controls">
          <label class="field">
            <span>{{ t("common.category") }}</span>
            <select v-model="selectedCategories[item.id]">
              <option value="" disabled>{{ t("views.review.selectCategory") }}</option>
              <option v-for="category in categories" :key="category.id" :value="String(category.id)">
                {{ categoryLabel(category) }}
              </option>
            </select>
          </label>
          <label class="field">
            <span>{{ t("views.review.saveRule") }}</span>
            <input v-model="patterns[item.id]" maxlength="500" />
          </label>
          <button
            class="primary-button resolve-button"
            :disabled="!selectedCategories[item.id] || savingId === item.id"
            @click="resolve(item)"
          >
            {{ savingId === item.id ? t("views.review.saving") : t("views.review.assign") }}
          </button>
        </div>
      </article>
    </div>
    <nav v-if="total" class="pagination" :aria-label="t('views.review.pages')">
      <button class="secondary-button" :disabled="offset === 0 || loading" @click="changePage(-1)">{{ t("views.review.previous") }}</button>
      <span>{{ t("views.review.page", { page: currentPage, pages: totalPages, count: total }) }}</span>
      <button class="secondary-button" :disabled="offset + pageSize >= total || loading" @click="changePage(1)">{{ t("views.review.next") }}</button>
    </nav>
  </section>
</template>

