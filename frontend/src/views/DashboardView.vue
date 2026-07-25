<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api } from "../api/client";
import type { DashboardSummary } from "../types/api";
import { formatUkMonth } from "../utils/date";
import { formatMoney } from "../utils/money";

const summary = ref<DashboardSummary | null>(null);
const currency = ref("GBP");
const month = ref(new Date().toISOString().slice(0, 7));
const error = ref("");
const maxCategoryMagnitude = computed(() =>
  Math.max(1, ...(summary.value?.category_totals.map((item) => Math.abs(item.total_amount)) ?? [])),
);

async function load() {
  error.value = "";
  try {
    summary.value = await api.dashboard(currency.value.toUpperCase(), month.value);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Could not load dashboard";
  }
}

onMounted(load);
</script>

<template>
  <section class="view-stack">
    <header class="view-heading split-heading">
      <div><p class="eyebrow">At a glance</p><h2>Dashboard</h2><p>Monthly cash flow and the categories shaping your spending.</p></div>
      <form class="inline-filter" @submit.prevent="load">
        <input v-model="month" class="month-input" type="month" aria-label="Dashboard month" />
        <input v-model="currency" maxlength="3" aria-label="Currency" />
        <button class="secondary-button">Apply</button>
      </form>
    </header>
    <p v-if="error" class="message error-message">{{ error }}</p>
    <div v-if="summary" class="dashboard-metrics">
      <article class="metric-card accent-blue"><span>Monthly spending</span><strong>{{ formatMoney(summary.spending, summary.currency) }}</strong></article>
      <article class="metric-card accent-green"><span>Income</span><strong>{{ formatMoney(summary.income, summary.currency) }}</strong></article>
      <article class="metric-card accent-violet"><span>Net position</span><strong>{{ formatMoney(summary.net, summary.currency) }}</strong></article>
      <article class="metric-card accent-orange"><span>Needs review</span><strong>{{ summary.review_count }}</strong></article>
    </div>
    <article v-if="summary" class="panel report-panel">
      <div class="panel-title"><h3>Category totals · {{ formatUkMonth(summary.month) }}</h3><span>{{ summary.transaction_count }} transactions</span></div>
      <div v-if="!summary.category_totals.length" class="table-empty">No categorised activity this month.</div>
      <div v-else class="category-bars">
        <div v-for="item in summary.category_totals" :key="item.category_id" class="category-bar-row">
          <div><strong>{{ item.category_name }}</strong><span>{{ item.transaction_count }} transactions</span></div>
          <div class="bar-track"><span :style="{ width: `${Math.max(4, Math.abs(item.total_amount) / maxCategoryMagnitude * 100)}%` }"></span></div>
          <strong>{{ formatMoney(item.total_amount, item.currency) }}</strong>
        </div>
      </div>
    </article>
  </section>
</template>

