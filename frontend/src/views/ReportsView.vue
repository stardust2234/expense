<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api } from "../api/client";
import PlotlyChart from "../components/PlotlyChart.vue";
import type {
  CategoryTotal,
  MonthlyTotal,
  PaymentPeriod,
  RecurringExpense,
  RecurringOpportunity,
} from "../types/api";
import { formatUkDate, formatUkMonth } from "../utils/date";
import { formatMoney, toMajorUnits, toMinorUnits } from "../utils/money";

const categoryTotals = ref<CategoryTotal[]>([]);
const monthlyTotals = ref<MonthlyTotal[]>([]);
const recurring = ref<RecurringExpense[]>([]);
const paymentPeriods = ref<PaymentPeriod[]>([]);
const opportunities = ref<RecurringOpportunity[]>([]);
const opportunityDrafts = ref<Record<string, {
  replacement: string;
  switchingCost: string;
  difficulty: RecurringOpportunity["difficulty"];
  decision: RecurringOpportunity["decision"];
}>>({});
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

const paymentPeriodChartData = computed(() => {
  const definitions = [
    ["Protected", "protected_spending", "#8f5146"],
    ["Essential", "essential_spending", "#4f806b"],
    ["Adjustable", "adjustable_spending", "#5f83ad"],
    ["Optional", "optional_spending", "#b58a45"],
    ["Irregular essential", "irregular_essential_spending", "#8873a9"],
  ] as const;
  return definitions.map(([name, field, color]) => ({
    type: "bar",
    name,
    x: paymentPeriods.value.map((period) =>
      `${formatUkDate(period.start_date)}–${formatUkDate(period.next_payment_date)}`,
    ),
    y: paymentPeriods.value.map((period) =>
      toMajorUnits(period[field], period.currency),
    ),
    marker: { color },
    hovertemplate: `%{x}<br>%{y:.2f}<extra>${name}</extra>`,
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
    [categoryTotals.value, monthlyTotals.value, recurring.value, paymentPeriods.value, opportunities.value] = await Promise.all([
      api.categoryTotals(params),
      api.monthlyTotals(params),
      api.recurringExpenses(params),
      api.paymentPeriodReports(currency.value),
      api.recurringOpportunities(params),
    ]);
    opportunityDrafts.value = Object.fromEntries(
      opportunities.value.map((item) => [
        opportunityKey(item),
        {
          replacement: item.replacement_monthly_cost === null
            ? ""
            : String(toMajorUnits(item.replacement_monthly_cost, item.currency)),
          switchingCost: String(
            toMajorUnits(item.one_off_switching_cost, item.currency),
          ),
          difficulty: item.difficulty,
          decision: item.decision,
        },
      ]),
    );
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Could not load reports";
  } finally {
    loading.value = false;
  }
}

function opportunityKey(item: RecurringOpportunity) {
  return `${item.identity_key}-${item.currency}`;
}

async function saveOpportunity(item: RecurringOpportunity) {
  const draft = opportunityDrafts.value[opportunityKey(item)];
  if (!draft) return;
  error.value = "";
  try {
    await api.saveRecurringOpportunity({
      identity_key: item.identity_key,
      description: item.description,
      currency: item.currency,
      current_monthly_cost: item.current_monthly_cost,
      replacement_monthly_cost: draft.replacement
        ? toMinorUnits(Number(draft.replacement), item.currency)
        : null,
      one_off_switching_cost: draft.switchingCost
        ? toMinorUnits(Number(draft.switchingCost), item.currency)
        : 0,
      difficulty: draft.difficulty,
      decision: draft.decision,
      notes: item.notes,
    });
    await loadReports();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Could not save opportunity";
  }
}

async function resetOpportunity(item: RecurringOpportunity) {
  if (item.opportunity_id === null) return;
  if (!window.confirm(`Reset the saved assessment for ${item.description}?`)) return;
  error.value = "";
  try {
    await api.deleteRecurringOpportunity(item.opportunity_id);
    await loadReports();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Could not reset opportunity";
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
      <div class="panel-title"><h3>Spending by payment period</h3><span>{{ paymentPeriods.length }} benefit cycles</span></div>
      <PlotlyChart
        v-if="paymentPeriods.length"
        :data="paymentPeriodChartData"
        :layout="{ ...chartLayout, barmode: 'stack', height: 360, xaxis: { ...chartLayout.xaxis, tickangle: -20 } }"
      />
      <div v-else class="table-empty">Create payment cycles to compare benefit periods.</div>
      <div v-if="paymentPeriods.length" class="table-wrap">
        <table>
          <thead><tr><th>Payment period</th><th>Income</th><th>Spending</th><th>Optional</th><th>Net</th></tr></thead>
          <tbody>
            <tr v-for="period in paymentPeriods" :key="period.payment_cycle_id">
              <td><strong>{{ period.name || "Payment cycle" }}</strong><br><span class="muted">{{ formatUkDate(period.start_date) }}–{{ formatUkDate(period.next_payment_date) }}</span></td>
              <td class="numeric">{{ formatMoney(period.income, period.currency) }}</td>
              <td class="numeric">{{ formatMoney(period.spending, period.currency) }}</td>
              <td class="numeric">{{ formatMoney(period.optional_spending, period.currency) }}</td>
              <td class="numeric">{{ formatMoney(period.net, period.currency) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>

    <article v-if="!loading" class="panel report-panel">
      <div class="panel-title"><div><h3>Recurring-cost opportunities</h3><span>Alternatives are entered by you, not guessed by the app.</span></div><span>{{ opportunities.length }} candidates</span></div>
      <div v-if="!opportunities.length" class="table-empty">No stable recurring costs detected yet.</div>
      <div v-else class="opportunity-list">
        <form
          v-for="item in opportunities"
          :key="opportunityKey(item)"
          class="opportunity-row"
          @submit.prevent="saveOpportunity(item)"
        >
          <div class="opportunity-name">
            <strong>{{ item.description }}</strong>
            <span>{{ item.cadence }} · {{ item.occurrence_count }} payments · current monthly cost {{ formatMoney(item.current_monthly_cost, item.currency) }}</span>
          </div>
          <label class="field"><span>Alternative monthly cost</span><input v-model="opportunityDrafts[opportunityKey(item)].replacement" type="number" min="0" step="0.01" placeholder="Not researched" /></label>
          <label class="field"><span>One-off switching cost</span><input v-model="opportunityDrafts[opportunityKey(item)].switchingCost" type="number" min="0" step="0.01" /></label>
          <label class="field"><span>Difficulty</span><select v-model="opportunityDrafts[opportunityKey(item)].difficulty"><option value="easy">Easy</option><option value="moderate">Moderate</option><option value="hard">Hard</option></select></label>
          <label class="field"><span>Decision</span><select v-model="opportunityDrafts[opportunityKey(item)].decision"><option value="review">Review</option><option value="planned">Planned</option><option value="accepted">Accepted</option><option value="rejected">Rejected</option></select></label>
          <div class="opportunity-saving">
            <span>Potential saving</span>
            <strong>{{ item.monthly_saving === null ? "Not assessed" : `${formatMoney(item.monthly_saving, item.currency)}/month` }}</strong>
            <small v-if="item.first_year_saving !== null">{{ formatMoney(item.first_year_saving, item.currency) }} in year one</small>
          </div>
          <div class="row-actions">
            <button class="secondary-button">Save assessment</button>
            <button v-if="item.opportunity_id !== null" class="text-button danger" type="button" @click="resetOpportunity(item)">Reset</button>
          </div>
        </form>
      </div>
    </article>

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

