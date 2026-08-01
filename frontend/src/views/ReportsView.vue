<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import { api } from "../api/client";
import PlotlyChart from "../components/PlotlyChart.vue";
import type {
  CategoryTotal,
  MonthlyTotal,
  PaymentPeriod,
  RecurringExpense,
  RecurringOpportunity,
} from "../types/api";
import { formatUkDate, formatUkMonth, inclusiveCycleEnd } from "../utils/date";
import { formatMoney, toMajorUnits, toMinorUnits } from "../utils/money";
import { formatCategoryName } from "../utils/category";
import { categoryChart, monthlyChart, paymentPeriodChart, reportChartLayout } from "./reports/charts";

const categoryTotals = ref<CategoryTotal[]>([]);
const { t } = useI18n();
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

const categoryChartData = computed(() => categoryChart(categoryTotals.value));
const monthlyChartData = computed(() => monthlyChart(monthlyTotals.value));
const paymentPeriodChartData = computed(() => paymentPeriodChart(paymentPeriods.value, t));
const chartLayout = reportChartLayout;

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
    error.value = caught instanceof Error ? caught.message : t("views.reports.errors.load");
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
    error.value = caught instanceof Error ? caught.message : t("views.reports.errors.save");
  }
}

async function resetOpportunity(item: RecurringOpportunity) {
  if (item.opportunity_id === null) return;
  if (!window.confirm(t("importDetail.resetConfirm", { description: item.description }))) return;
  error.value = "";
  try {
    await api.deleteRecurringOpportunity(item.opportunity_id);
    await loadReports();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.reports.errors.reset");
  }
}

onMounted(loadReports);
</script>

<template>
  <section class="view-stack">
    <header class="view-heading">
      <div>
        <p class="eyebrow">{{ t("views.reports.eyebrow") }}</p><h2>{{ t("views.reports.title") }}</h2><p>{{ t("views.reports.subtitle") }}</p>
      </div>
    </header>

    <form class="panel filter-bar" @submit.prevent="loadReports">
      <label class="field"><span>{{ t("views.reports.from") }}</span><input v-model="dateFrom" type="date" /></label><label class="field"><span>{{ t("views.reports.to") }}</span><input v-model="dateTo" type="date" /></label><label class="field compact-field"><span>{{ t("common.currency") }}</span><input v-model="currency" maxlength="3" :placeholder="t('views.reports.all')" /></label><button class="secondary-button" type="submit">{{ t("views.reports.refresh") }}</button>
    </form>

    <p v-if="error" class="message error-message">{{ error }}</p>
    <div v-if="loading" class="panel empty-state">{{ t("views.reports.loading") }}</div>
    <div v-else class="report-grid chart-grid">
      <article class="panel report-panel">
        <div class="panel-title"><h3>{{ t("views.reports.categoryDistribution") }}</h3><span>{{ t("views.reports.interactive") }}</span></div>
        <PlotlyChart v-if="categoryTotals.length" :data="categoryChartData" :layout="{ ...chartLayout, showlegend: false }" />
        <div v-else class="table-empty">{{ t("views.reports.noCategoryPlot") }}</div>
      </article>
      <article class="panel report-panel">
        <div class="panel-title"><h3>{{ t("views.reports.monthlyTrend") }}</h3><span>{{ t("views.reports.interactive") }}</span></div>
        <PlotlyChart v-if="monthlyTotals.length" :data="monthlyChartData" :layout="chartLayout" />
        <div v-else class="table-empty">{{ t("views.reports.noMonthlyPlot") }}</div>
      </article>
    </div>
    <div v-if="!loading" class="report-grid">
      <article class="panel report-panel">
        <div class="panel-title"><h3>{{ t("views.reports.byCategory") }}</h3><span>{{ t("views.reports.totals", { count: categoryTotals.length }) }}</span></div><div v-if="!categoryTotals.length" class="table-empty">{{ t("views.reports.noCategories") }}</div>
        <div v-else class="table-wrap">
          <table>
            <thead><tr><th>{{ t("common.category") }}</th><th>{{ t("views.reports.transactions") }}</th><th>{{ t("views.reports.total") }}</th></tr></thead>
            <tbody>
              <tr v-for="row in categoryTotals" :key="`${row.category_id}-${row.currency}`">
                <td>{{ formatCategoryName({ code: row.category_code, name: row.category_name }) }}</td>
                <td>{{ row.transaction_count }}</td>
                <td class="numeric">{{ formatMoney(row.total_amount, row.currency) }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="panel report-panel">
        <div class="panel-title"><h3>{{ t("views.reports.byMonth") }}</h3><span>{{ t("views.reports.periods", { count: monthlyTotals.length }) }}</span></div><div v-if="!monthlyTotals.length" class="table-empty">{{ t("views.reports.noMonths") }}</div>
        <div v-else class="table-wrap">
          <table>
            <thead><tr><th>{{ t("views.reports.month") }}</th><th>{{ t("views.reports.transactions") }}</th><th>{{ t("views.reports.total") }}</th></tr></thead>
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
      <div class="panel-title"><h3>{{ t("views.reports.paymentSpending") }}</h3><span>{{ t("views.reports.cycles", { count: paymentPeriods.length }) }}</span></div>
      <PlotlyChart
        v-if="paymentPeriods.length"
        :data="paymentPeriodChartData"
        :layout="{ ...chartLayout, barmode: 'stack', height: 360, xaxis: { ...chartLayout.xaxis, tickangle: -20 } }"
      />
      <div v-else class="table-empty">{{ t("views.reports.createCycles") }}</div>
      <div v-if="paymentPeriods.length" class="table-wrap">
        <table>
          <thead><tr><th>{{ t("views.reports.paymentPeriod") }}</th><th>{{ t("views.reports.income") }}</th><th>{{ t("views.reports.spending") }}</th><th>{{ t("views.reports.optional") }}</th><th>{{ t("views.reports.net") }}</th></tr></thead>
          <tbody>
            <tr v-for="period in paymentPeriods" :key="period.payment_cycle_id">
              <td><strong>{{ period.name || t("common.paymentCycle") }}</strong><br><span class="muted">{{ formatUkDate(period.start_date) }}–{{ formatUkDate(inclusiveCycleEnd(period.end_date)) }}</span></td>
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
      <div class="panel-title"><div><h3>{{ t("views.reports.opportunities") }}</h3><span>{{ t("views.reports.opportunitiesNote") }}</span></div><span>{{ t("views.reports.candidates", { count: opportunities.length }) }}</span></div><div v-if="!opportunities.length" class="table-empty">{{ t("views.reports.noOpportunities") }}</div>
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
          <label class="field"><span>{{ t("views.reports.alternativeCost") }}</span><input v-model="opportunityDrafts[opportunityKey(item)].replacement" type="number" min="0" step="0.01" :placeholder="t('views.reports.notResearched')" /></label><label class="field"><span>{{ t("views.reports.switchingCost") }}</span><input v-model="opportunityDrafts[opportunityKey(item)].switchingCost" type="number" min="0" step="0.01" /></label><label class="field"><span>{{ t("views.reports.difficulty") }}</span><select v-model="opportunityDrafts[opportunityKey(item)].difficulty"><option v-for="value in ['easy','moderate','hard']" :key="value" :value="value">{{ t(`views.reports.difficulties.${value}`) }}</option></select></label><label class="field"><span>{{ t("views.reports.decision") }}</span><select v-model="opportunityDrafts[opportunityKey(item)].decision"><option v-for="value in ['review','planned','accepted','rejected']" :key="value" :value="value">{{ t(`views.reports.decisions.${value}`) }}</option></select></label>
          <div class="opportunity-saving">
            <span>{{ t("views.reports.potentialSaving") }}</span><strong>{{ item.monthly_saving === null ? t("views.reports.notAssessed") : t("views.reports.perMonth", { amount: formatMoney(item.monthly_saving, item.currency) }) }}</strong>
            <small v-if="item.first_year_saving !== null">{{ formatMoney(item.first_year_saving, item.currency) }} in year one</small>
          </div>
          <div class="row-actions">
            <button class="secondary-button">{{ t("views.reports.saveAssessment") }}</button><button v-if="item.opportunity_id !== null" class="text-button danger" type="button" @click="resetOpportunity(item)">{{ t("views.reports.reset") }}</button>
          </div>
        </form>
      </div>
    </article>

    <article v-if="!loading" class="panel report-panel">
      <div class="panel-title"><h3>{{ t("views.reports.recurring") }}</h3><span>{{ t("views.reports.patterns", { count: recurring.length }) }}</span></div><div v-if="!recurring.length" class="table-empty">{{ t("views.reports.noPatterns") }}</div><div v-else class="table-wrap"><table><thead><tr><th>{{ t("views.reports.description") }}</th><th>{{ t("views.reports.cadence") }}</th><th>{{ t("views.reports.occurrences") }}</th><th>{{ t("views.reports.lastSeen") }}</th><th>{{ t("views.reports.average") }}</th></tr></thead><tbody>
        <tr v-for="item in recurring" :key="`${item.description}-${item.currency}`"><td>{{ item.description }}</td><td><span class="status-pill">{{ t(`dynamic.cadences.${item.cadence}`) }}</span><span class="muted"> · {{ t("dynamic.approxDays", { count: item.typical_interval_days }) }}</span></td><td>{{ item.occurrence_count }}</td><td>{{ formatUkDate(item.last_seen) }}</td><td class="numeric">{{ formatMoney(item.average_amount, item.currency) }}</td></tr>
      </tbody></table></div>
    </article>

    <div class="export-actions">
      <div><strong>{{ t("views.reports.exportTitle") }}</strong><span>{{ t("views.reports.exportNote") }}</span></div><a class="secondary-button" :href="api.exportUrl('csv', reportParams)">{{ t("views.reports.exportCsv") }}</a><a class="primary-button" :href="api.exportUrl('xlsx', reportParams)">{{ t("views.reports.exportExcel") }}</a>
    </div>
  </section>
</template>

