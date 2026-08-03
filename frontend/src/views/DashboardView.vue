<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { CirclePoundSterling, WalletCards } from "@lucide/vue";
import { useI18n } from "vue-i18n";

import { api } from "../api/client";
import type {
  Commitment,
  PaymentCycle,
  RecurringOpportunity,
  SafeSpendingForecast,
} from "../types/api";
import { formatUkDate } from "../utils/date";
import { formatMoney } from "../utils/money";

const cycles = ref<PaymentCycle[]>([]);
const { t } = useI18n();
const selectedCycleId = ref<number | null>(null);
const forecast = ref<SafeSpendingForecast | null>(null);
const commitments = ref<Commitment[]>([]);
const opportunities = ref<RecurringOpportunity[]>([]);
const loading = ref(true);
const error = ref("");
const today = new Date();
const todayIso =
  `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-` +
  String(today.getDate()).padStart(2, "0");

const selectedCycle = computed(
  () => cycles.value.find((cycle) => cycle.id === selectedCycleId.value) ?? null,
);
const pendingCommitments = computed(() =>
  commitments.value.filter((item) => item.status === "pending"),
);
const cycleTiming = computed(() => {
  const paymentDate = forecast.value?.next_payment_date;
  if (!paymentDate) return "future";
  if (paymentDate < todayIso) return "past";
  if (paymentDate === todayIso) return "today";
  return "future";
});
const daysSinceCycleEnded = computed(() => {
  if (!selectedCycle.value || cycleTiming.value !== "past") return 0;
  const paymentDate = new Date(`${forecast.value!.next_payment_date}T00:00:00`);
  const currentDate = new Date(`${todayIso}T00:00:00`);
  return Math.round((currentDate.getTime() - paymentDate.getTime()) / 86_400_000);
});
const essentialRemaining = computed(
  () =>
    forecast.value?.allowances
      .filter((item) =>
        ["protected", "essential", "adjustable", "irregular_essential"].includes(
          item.priority,
        ),
      )
      .reduce((total, item) => total + item.remaining_amount, 0) ?? 0,
);
const realisticOpportunities = computed(() =>
  opportunities.value
    .filter(
      (item) =>
        item.monthly_saving !== null &&
        item.monthly_saving > 0 &&
        item.decision !== "rejected",
    )
    .slice(0, 3),
);

function setError(caught: unknown) {
  error.value =
    caught instanceof Error ? caught.message : t("dashboard.loadError");
}

async function loadCycle() {
  if (!selectedCycleId.value) return;
  try {
    const [forecastResult, commitmentResult] = await Promise.all([
      api.safeSpendingForecast(selectedCycleId.value),
      api.cycleCommitments(selectedCycleId.value),
    ]);
    forecast.value = forecastResult;
    commitments.value = commitmentResult.items;
  } catch (caught) {
    setError(caught);
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [cycleResult, opportunityResult] = await Promise.all([
      api.paymentCycles(),
      api.recurringOpportunities(new URLSearchParams()),
    ]);
    cycles.value = cycleResult.items;
    opportunities.value = opportunityResult;
    const currentCalendarCycle = cycles.value.find(
      (cycle) => cycle.start_date <= todayIso && cycle.end_date > todayIso,
    );
    selectedCycleId.value =
      currentCalendarCycle?.id ??
      cycles.value.find((cycle) => cycle.status === "active")?.id ??
      cycles.value[0]?.id ??
      null;
    await loadCycle();
  } catch (caught) {
    setError(caught);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section class="view-stack">
    <header class="view-heading split-heading">
      <div>
        <p class="eyebrow">{{ t("dashboard.eyebrow") }}</p>
        <h2>{{ t("dashboard.title") }}</h2>
        <p>{{ t("dashboard.subtitle") }}</p>
      </div>
      <label v-if="cycles.length > 1" class="field cycle-picker">
        <span>{{ t("dashboard.cycleLabel") }}</span>
        <select v-model="selectedCycleId" @change="loadCycle">
          <option v-for="cycle in cycles" :key="cycle.id" :value="cycle.id">
            {{ cycle.name || t("common.paymentCycle") }} · {{ formatUkDate(cycle.start_date) }}
          </option>
        </select>
      </label>
    </header>

    <p v-if="error" class="message error-message">{{ error }}</p>
    <div v-if="loading" class="panel empty-state">{{ t("dashboard.loading") }}</div>

    <article v-else-if="!selectedCycle || !forecast" class="panel dashboard-setup">
      <div class="empty-icon"><CirclePoundSterling :size="22" :stroke-width="1.5" /></div>
      <h3>{{ t("dashboard.setupTitle") }}</h3>
      <p>{{ t("dashboard.setupDescription") }}</p>
      <RouterLink class="primary-button" to="/plan">{{ t("dashboard.setupAction") }}</RouterLink>
    </article>

    <template v-else>
      <p v-if="cycleTiming === 'past'" class="message historical-message">
        {{ t("dashboard.historical") }}
      </p>

      <div v-if="forecast.risks.length" class="risk-list">
        <p v-for="risk in forecast.risks" :key="risk" class="message error-message">
          {{ risk }}
        </p>
      </div>

      <div class="dashboard-priority-grid">
        <article class="priority-card usable-balance">
          <div class="holographic-card-meta"><WalletCards :size="22" :stroke-width="1.5" /><span>{{ t("dashboard.liquidity") }}</span><i></i><i></i></div>
          <span>{{ t("dashboard.usableBalance") }}</span>
          <strong>{{ formatMoney(forecast.usable_balance, forecast.currency) }}</strong>
          <small v-if="forecast.balance_source === 'funding_income'">{{ t("dashboard.fundingSnapshot", { amount: formatMoney(forecast.funding_income_amount, forecast.currency), date: formatUkDate(forecast.funding_start_date) }) }}</small>
          <small v-else>{{ t("dashboard.balanceSnapshot", { source: t(`dashboard.balanceSources.${forecast.balance_source}`) }) }}</small>
        </article>
        <article class="priority-card next-income">
          <span v-if="cycleTiming === 'past'">{{ t("dashboard.cycleEnded") }}</span>
          <span v-else-if="cycleTiming === 'today'">{{ t("dashboard.incomeToday") }}</span>
          <span v-else>{{ t("dashboard.nextIncome") }}</span>
          <strong>{{ formatUkDate(forecast.next_payment_date) }}</strong>
          <small v-if="cycleTiming === 'past'">{{ t("dashboard.historicalEnded", { count: daysSinceCycleEnded }) }}</small>
          <small v-else-if="cycleTiming === 'today'">{{ t("dashboard.expectedToday", { amount: formatMoney(forecast.next_income_amount, forecast.currency) }) }}</small>
          <small v-else>{{ t("dashboard.expectedInDays", { count: forecast.days_remaining, amount: formatMoney(forecast.next_income_amount, forecast.currency) }) }}</small>
        </article>
        <article class="priority-card bills-due">
          <span>{{ t("dashboard.billsDue") }}</span>
          <strong>{{ formatMoney(forecast.pending_commitments, forecast.currency) }}</strong>
          <small>{{ t("dashboard.unpaidCommitments", { count: pendingCommitments.length }) }}</small>
        </article>
        <article class="priority-card weekly-safe" :class="{ danger: forecast.shortfall > 0 }">
          <span>{{ t("dashboard.safeWeekly") }}</span>
          <strong>{{ formatMoney(forecast.safe_weekly_amount, forecast.currency) }}</strong>
          <small v-if="forecast.shortfall">{{ t("dashboard.shortfall", { amount: formatMoney(forecast.shortfall, forecast.currency) }) }}</small>
          <small v-else>{{ t("dashboard.discretionary", { amount: formatMoney(forecast.safe_to_spend, forecast.currency) }) }}</small>
        </article>
        <article class="priority-card essential-left">
          <span>{{ t("dashboard.essentialRemaining") }}</span>
          <strong>{{ formatMoney(essentialRemaining, forecast.currency) }}</strong>
          <small>{{ t("dashboard.essentialNote") }}</small>
        </article>
        <article class="priority-card predicted-balance" :class="{ danger: forecast.projected_balance < 0 }">
          <span>{{ t("dashboard.predictedBalance") }}</span>
          <strong>{{ formatMoney(forecast.projected_balance, forecast.currency) }}</strong>
          <small>{{ t("dashboard.predictedNote") }}</small>
        </article>
      </div>

      <article class="panel opportunity-summary">
        <div class="panel-title">
          <div><h3>{{ t("dashboard.opportunities") }}</h3><span>{{ t("dashboard.opportunitiesNote") }}</span></div>
          <RouterLink class="text-button" to="/reports">{{ t("dashboard.reviewAll") }}</RouterLink>
        </div>
        <div v-if="!realisticOpportunities.length" class="table-empty">
          {{ t("dashboard.noOpportunities") }}
        </div>
        <div v-else class="opportunity-summary-list">
          <div v-for="item in realisticOpportunities" :key="`${item.identity_key}-${item.currency}`">
            <div><strong>{{ item.description }}</strong><span>{{ item.difficulty }} · {{ item.decision }}</span></div>
            <strong>{{ t("dashboard.perMonth", { amount: formatMoney(item.monthly_saving!, item.currency) }) }}</strong>
          </div>
        </div>
      </article>

      <div class="dashboard-actions">
        <RouterLink class="secondary-button" to="/plan">{{ t("dashboard.updatePlan") }}</RouterLink>
        <RouterLink class="text-button" to="/reports">{{ t("dashboard.viewReports") }}</RouterLink>
      </div>
    </template>
  </section>
</template>

