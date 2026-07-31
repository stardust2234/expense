<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

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
    caught instanceof Error ? caught.message : "Could not load the dashboard";
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
        <p class="eyebrow">Your position right now</p>
        <h2>Dashboard</h2>
        <p>What is safe before your next income payment, after protecting essentials.</p>
      </div>
      <label v-if="cycles.length > 1" class="field cycle-picker">
        <span>Payment cycle</span>
        <select v-model="selectedCycleId" @change="loadCycle">
          <option v-for="cycle in cycles" :key="cycle.id" :value="cycle.id">
            {{ cycle.name || "Payment cycle" }} · {{ formatUkDate(cycle.start_date) }}
          </option>
        </select>
      </label>
    </header>

    <p v-if="error" class="message error-message">{{ error }}</p>
    <div v-if="loading" class="panel empty-state">Calculating your safe position…</div>

    <article v-else-if="!selectedCycle || !forecast" class="panel dashboard-setup">
      <div class="empty-icon">£</div>
      <h3>Set up a payment cycle first</h3>
      <p>Add your next income date, usable balance, bills and essential allowances.</p>
      <RouterLink class="primary-button" to="/plan">Set up financial plan</RouterLink>
    </article>

    <template v-else>
      <p v-if="cycleTiming === 'past'" class="message historical-message">
        Historical payment cycle: these figures are the saved plan for an ended period, not your
        current safe-to-spend position.
      </p>

      <div v-if="forecast.risks.length" class="risk-list">
        <p v-for="risk in forecast.risks" :key="risk" class="message error-message">
          {{ risk }}
        </p>
      </div>

      <div class="dashboard-priority-grid">
        <article class="priority-card usable-balance">
          <span>Current usable balance</span>
          <strong>{{ formatMoney(forecast.usable_balance, forecast.currency) }}</strong>
          <small>{{ forecast.balance_source }} balance snapshot</small>
        </article>
        <article class="priority-card next-income">
          <span v-if="cycleTiming === 'past'">Cycle ended</span>
          <span v-else-if="cycleTiming === 'today'">Income due today</span>
          <span v-else>Next income</span>
          <strong>{{ formatUkDate(forecast.next_payment_date) }}</strong>
          <small v-if="cycleTiming === 'past'">Historical plan · ended {{ daysSinceCycleEnded }} day{{ daysSinceCycleEnded === 1 ? "" : "s" }} ago</small>
          <small v-else-if="cycleTiming === 'today'">{{ formatMoney(selectedCycle.expected_income_amount, selectedCycle.currency) }} expected today</small>
          <small v-else>{{ formatMoney(selectedCycle.expected_income_amount, selectedCycle.currency) }} expected · {{ forecast.days_remaining }} days</small>
        </article>
        <article class="priority-card bills-due">
          <span>Bills due before then</span>
          <strong>{{ formatMoney(forecast.pending_commitments, forecast.currency) }}</strong>
          <small>{{ pendingCommitments.length }} unpaid commitment{{ pendingCommitments.length === 1 ? "" : "s" }}</small>
        </article>
        <article class="priority-card weekly-safe" :class="{ danger: forecast.shortfall > 0 }">
          <span>Safe weekly spending</span>
          <strong>{{ formatMoney(forecast.safe_weekly_amount, forecast.currency) }}</strong>
          <small v-if="forecast.shortfall">{{ formatMoney(forecast.shortfall, forecast.currency) }} shortfall must be resolved first</small>
          <small v-else>{{ formatMoney(forecast.safe_to_spend, forecast.currency) }} total discretionary amount</small>
        </article>
        <article class="priority-card essential-left">
          <span>Essential spending remaining</span>
          <strong>{{ formatMoney(essentialRemaining, forecast.currency) }}</strong>
          <small>protected allowances and reserves</small>
        </article>
        <article class="priority-card predicted-balance" :class="{ danger: forecast.projected_balance < 0 }">
          <span>Predicted period-end balance</span>
          <strong>{{ formatMoney(forecast.projected_balance, forecast.currency) }}</strong>
          <small>after bills and remaining allowances</small>
        </article>
      </div>

      <article class="panel opportunity-summary">
        <div class="panel-title">
          <div><h3>Top realistic opportunities</h3><span>Only alternatives you have assessed are shown.</span></div>
          <RouterLink class="text-button" to="/reports">Review all</RouterLink>
        </div>
        <div v-if="!realisticOpportunities.length" class="table-empty">
          No assessed savings opportunities yet. Review recurring costs before assuming a saving.
        </div>
        <div v-else class="opportunity-summary-list">
          <div v-for="item in realisticOpportunities" :key="`${item.identity_key}-${item.currency}`">
            <div><strong>{{ item.description }}</strong><span>{{ item.difficulty }} · {{ item.decision }}</span></div>
            <strong>{{ formatMoney(item.monthly_saving!, item.currency) }}/month</strong>
          </div>
        </div>
      </article>

      <div class="dashboard-actions">
        <RouterLink class="secondary-button" to="/plan">Update balance, bills or allowances</RouterLink>
        <RouterLink class="text-button" to="/reports">View payment-period reports</RouterLink>
      </div>
    </template>
  </section>
</template>

