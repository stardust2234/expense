<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api } from "../api/client";
import type { Category, ReviewQueueItem } from "../types/api";
import { formatUkDate } from "../utils/date";
import { formatMoney } from "../utils/money";

const items = ref<ReviewQueueItem[]>([]);
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
  () => new Map(categories.value.map((category) => [category.id, category.name])),
);

function categoryLabel(category: Category) {
  if (!category.parent_category_id) return category.name;
  return `${categoryNames.value.get(category.parent_category_id) ?? "Other"} / ${category.name}`;
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
    error.value = caught instanceof Error ? caught.message : "Could not load review queue";
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
    error.value = caught instanceof Error ? caught.message : "Could not save correction";
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
        <p class="eyebrow">Human in the loop</p>
        <h2>Review queue</h2>
        <p>Choose a category and save a reusable matching rule in one step.</p>
      </div>
      <div class="queue-count"><strong>{{ total }}</strong><span>waiting</span></div>
    </header>

    <p v-if="error" class="message error-message">{{ error }}</p>
    <div v-if="loading" class="panel empty-state">Loading review queue…</div>
    <div v-else-if="!items.length" class="panel empty-state">
      <span class="empty-icon">✓</span>
      <h3>All caught up</h3>
      <p>No transactions need manual review.</p>
    </div>

    <div v-else class="review-list">
      <article v-for="item in items" :key="item.id" class="panel review-card">
        <div class="transaction-summary">
          <div>
            <span class="date-chip">{{ formatUkDate(item.transaction_date) }}</span>
            <h3>{{ item.description }}</h3>
            <p>
              {{ item.merchant_name ?? "Merchant not identified" }}
              <span v-if="item.source_filename">· {{ item.source_filename }}:{{ item.source_row_number }}</span>
            </p>
          </div>
          <strong class="money">{{ formatMoney(item.amount, item.currency) }}</strong>
        </div>

        <div class="review-controls">
          <label class="field">
            <span>Category</span>
            <select v-model="selectedCategories[item.id]">
              <option value="" disabled>Select a category</option>
              <option v-for="category in categories" :key="category.id" :value="String(category.id)">
                {{ categoryLabel(category) }}
              </option>
            </select>
          </label>
          <label class="field">
            <span>Save matching rule</span>
            <input v-model="patterns[item.id]" maxlength="500" />
          </label>
          <button
            class="primary-button resolve-button"
            :disabled="!selectedCategories[item.id] || savingId === item.id"
            @click="resolve(item)"
          >
            {{ savingId === item.id ? "Saving…" : "Assign & save rule" }}
          </button>
        </div>
      </article>
    </div>
    <nav v-if="total" class="pagination" aria-label="Review queue pages">
      <button class="secondary-button" :disabled="offset === 0 || loading" @click="changePage(-1)">Previous</button>
      <span>Page {{ currentPage }} of {{ totalPages }} · {{ total }} waiting</span>
      <button class="secondary-button" :disabled="offset + pageSize >= total || loading" @click="changePage(1)">Next</button>
    </nav>
  </section>
</template>

