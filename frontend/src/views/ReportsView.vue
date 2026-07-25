<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api } from "../api/client";
import PlotlyChart from "../components/PlotlyChart.vue";
import type { CategoryTotal, MonthlyTotal, RecurringExpense } from "../types/api";
import { formatUkDate, formatUkMonth } from "../utils/date";
import { formatMoney, toMajorUnits } from "../utils/money";

const categoryTotals = ref<CategoryTotal[]>([]);
const monthlyTotals = ref<MonthlyTotal[]>([]);
const recurring = ref<RecurringExpense[]>([]);
const dateFrom = ref("");
const dateTo = ref("");
const currency = ref("");
const loading = ref(true);
const error = ref("");
const reportParams = computed(() => {
  const params = new URLSearchParams();
  if (dateFrom.value) params.set("date_from", dateFrom.value);
  if (dateTo.value) params.set("date_to", dateTo.value);
  if (currency.value.trim()) params.set("currency", currency.value.trim().toUpperCase());
  return params;
});

const categoryChartData = computed(() => [{
  type: "bar",
  orientation: "h",
  x: categoryTotals.value.map((item) => toMajorUnits(item.total_amount, item.currency)),
  y: categoryTotals.value.map((item) => `${item.category_name} · ${item.currency}`),
  text: categoryTotals.value.map((item) => formatMoney(item.total_amount, item.currency)),
  hovertemplate: "%{y}<br>%{text}<extra></extra>",
  marker: { color: "#5f83ad", borderRadius: 4 },
}]);

const monthlyChartData = computed(() => {
  const currencies = [...new Set(monthlyTotals.value.map((item) => item.currency))];
  return currencies.map((rowCurrency) => ({
    type: "scatter",
    mode: "lines+markers",
    name: rowCurrency,
    x: monthlyTotals.value.filter((item) => item.currency === rowCurrency).map((item) => item.month),
    y: monthlyTotals.value.filter((item) => item.currency === rowCurrency).map((item) => toMajorUnits(item.total_amount, item.currency)),
    line: { width: 3 },
    marker: { size: 7 },
    hovertemplate: `%{x}<br>%{y:.2f} ${rowCurrency}<extra></extra>`,
  }));
});

const chartLayout = {
  autosize: true,
  height: 330,
  margin: { l: 115, r: 24, t: 18, b: 45 },
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  font: { family: "Inter, sans-serif", color: "#596273", size: 11 },
  xaxis: { gridcolor: "#ebe9e3", zeroline: false },
  yaxis: { gridcolor: "#ebe9e3", zeroline: false, automargin: true },
  showlegend: true,
  legend: { orientation: "h", y: 1.1 },
};

async function loadReports() {
  loading.value = true;
  error.value = "";
  const params = reportParams.value;

  try {
    [categoryTotals.value, monthlyTotals.value, recurring.value] = await Promise.all([
      api.categoryTotals(params),
      api.monthlyTotals(params),
      api.recurringExpenses(params),
    ]);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Could not load reports";
  } finally {
    loading.value = false;
  }
}

onMounted(loadReports);
</script>

<template>
  <section class="view-stack">
    <header class="view-heading">
      <div>
        <p class="eyebrow">Understand the pattern</p>
        <h2>Reports</h2>
        <p>Net spending excludes Income and Transfers. Refunds reduce spending, and currencies remain separate.</p>
      </div>
    </header>

    <form class="panel filter-bar" @submit.prevent="loadReports">
      <label class="field"><span>From</span><input v-model="dateFrom" type="date" /></label>
      <label class="field"><span>To</span><input v-model="dateTo" type="date" /></label>
      <label class="field compact-field"><span>Currency</span><input v-model="currency" maxlength="3" placeholder="All" /></label>
      <button class="secondary-button" type="submit">Refresh report</button>
    </form>

    <p v-if="error" class="message error-message">{{ error }}</p>
    <div v-if="loading" class="panel empty-state">Calculating totals…</div>
    <div v-else class="report-grid chart-grid">
      <article class="panel report-panel">
        <div class="panel-title"><h3>Category distribution</h3><span>Interactive</span></div>
        <PlotlyChart v-if="categoryTotals.length" :data="categoryChartData" :layout="{ ...chartLayout, showlegend: false }" />
        <div v-else class="table-empty">No category data to plot.</div>
      </article>
      <article class="panel report-panel">
        <div class="panel-title"><h3>Monthly trend</h3><span>Interactive</span></div>
        <PlotlyChart v-if="monthlyTotals.length" :data="monthlyChartData" :layout="chartLayout" />
        <div v-else class="table-empty">No monthly data to plot.</div>
      </article>
    </div>
    <div v-if="!loading" class="report-grid">
      <article class="panel report-panel">
        <div class="panel-title"><h3>By category</h3><span>{{ categoryTotals.length }} totals</span></div>
        <div v-if="!categoryTotals.length" class="table-empty">No categorised transactions yet.</div>
        <div v-else class="table-wrap">
          <table>
            <thead><tr><th>Category</th><th>Transactions</th><th>Total</th></tr></thead>
            <tbody>
              <tr v-for="row in categoryTotals" :key="`${row.category_id}-${row.currency}`">
                <td>{{ row.category_name }}</td>
                <td>{{ row.transaction_count }}</td>
                <td class="numeric">{{ formatMoney(row.total_amount, row.currency) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel report-panel">
        <div class="panel-title"><h3>By month</h3><span>{{ monthlyTotals.length }} periods</span></div>
        <div v-if="!monthlyTotals.length" class="table-empty">No monthly totals yet.</div>
        <div v-else class="table-wrap">
          <table>
            <thead><tr><th>Month</th><th>Transactions</th><th>Total</th></tr></thead>
            <tbody>
              <tr v-for="row in monthlyTotals" :key="`${row.month}-${row.currency}`">
                <td>{{ formatUkMonth(row.month) }}</td>
                <td>{{ row.transaction_count }}</td>
                <td class="numeric">{{ formatMoney(row.total_amount, row.currency) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>
    </div>

    <article v-if="!loading" class="panel report-panel">
      <div class="panel-title"><h3>Recurring expenses</h3><span>{{ recurring.length }} patterns</span></div>
      <div v-if="!recurring.length" class="table-empty">No recurring patterns detected yet.</div>
      <div v-else class="table-wrap"><table><thead><tr><th>Description</th><th>Cadence</th><th>Occurrences</th><th>Last seen</th><th>Average</th></tr></thead><tbody>
        <tr v-for="item in recurring" :key="`${item.description}-${item.currency}`"><td>{{ item.description }}</td><td><span class="status-pill">{{ item.cadence }}</span><span class="muted"> · ~{{ item.typical_interval_days }} days</span></td><td>{{ item.occurrence_count }}</td><td>{{ formatUkDate(item.last_seen) }}</td><td class="numeric">{{ formatMoney(item.average_amount, item.currency) }}</td></tr>
      </tbody></table></div>
    </article>

    <div class="export-actions">
      <div><strong>Take your data with you</strong><span>Exports use the active date and currency filters.</span></div>
      <a class="secondary-button" :href="api.exportUrl('csv', reportParams)">Export CSV</a>
      <a class="primary-button" :href="api.exportUrl('xlsx', reportParams)">Export Excel</a>
    </div>
  </section>
</template>

