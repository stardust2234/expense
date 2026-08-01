<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import { api } from "../api/client";
import type {
  AllowanceType,
  Category,
  Commitment,
  CycleAllowance,
  PaymentCycle,
  PlanInferencePreview,
  SafeSpendingForecast,
  SpendingPriority,
} from "../types/api";
import { formatUkDate, inclusiveCycleEnd } from "../utils/date";
import { formatMoney, toMajorUnits, toMinorUnits } from "../utils/money";
import { formatCategoryName } from "../utils/category";
import { defaultCurrencyForLocale } from "../utils/currency";
import { addCalendarMonth, defaultPlanDates, inputDate } from "./plan/calendar";

const today = new Date();
const { locale, t } = useI18n();
const { calendarStart, benefitDate, firstBillDue } = defaultPlanDates(today);

const cycles = ref<PaymentCycle[]>([]);
const commitments = ref<Commitment[]>([]);
const allowances = ref<CycleAllowance[]>([]);
const forecast = ref<SafeSpendingForecast | null>(null);
const categories = ref<Category[]>([]);
const selectedCycleId = ref<number | null>(null);
const balanceInput = ref("");
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const inferencePreview = ref<PlanInferencePreview | null>(null);
const inferenceTargetMonth = ref(inputDate(calendarStart));
const selectedInferenceCommitments = ref<string[]>([]);
const selectedInferenceAllowances = ref<string[]>([]);
const creatingCycle = ref(false);
const editingCycle = ref(false);
const editingCommitmentId = ref<number | null>(null);
const editingAllowanceId = ref<number | null>(null);

const cycleForm = ref({
  name: t("plan.defaultCycleName"),
  nextPaymentDate: inputDate(benefitDate),
  expectedIncome: "",
  openingBalance: "",
  currentBalance: "",
  currency: defaultCurrencyForLocale(locale.value) as string,
});
const commitmentForm = ref({
  name: "",
  amount: "",
  dueDate: inputDate(firstBillDue),
  priority: "protected" as SpendingPriority,
  categoryId: "",
});
const allowanceForm = ref({
  name: "",
  amount: "",
  allowanceType: "food" as AllowanceType,
  priority: "essential" as SpendingPriority,
  categoryId: "",
});
const cycleEditForm = ref({
  name: "",
  nextPaymentDate: "",
  expectedIncome: "",
  openingBalance: "",
  currentBalance: "",
  currency: "GBP",
  status: "active" as PaymentCycle["status"],
});
const commitmentEditForm = ref({
  name: "",
  amount: "",
  dueDate: "",
  priority: "protected" as SpendingPriority,
  categoryId: "",
  status: "pending" as Commitment["status"],
  recurrence: "",
});
const allowanceEditForm = ref({
  name: "",
  amount: "",
  allowanceType: "food" as AllowanceType,
  priority: "essential" as SpendingPriority,
  categoryId: "",
});

watch(locale, (nextLocale, previousLocale) => {
  if (
    !inferencePreview.value &&
    !selectedCycle.value &&
    cycleForm.value.currency === defaultCurrencyForLocale(previousLocale)
  ) {
    cycleForm.value.currency = defaultCurrencyForLocale(nextLocale);
  }
});

const selectedCycle = computed(
  () => cycles.value.find((cycle) => cycle.id === selectedCycleId.value) ?? null,
);
const pendingCommitments = computed(() =>
  commitments.value.filter((item) => item.status === "pending"),
);
function allowanceForecast(id: number) {
  return forecast.value?.allowances.find((item) => item.id === id) ?? null;
}
function message(caught: unknown, fallback: string) {
  error.value = caught instanceof Error ? caught.message : fallback;
}

async function previewPlan() {
  saving.value = true;
  error.value = "";
  try {
    const preview = await api.previewPlan(
      inferenceTargetMonth.value,
      cycleForm.value.currency,
    );
    inferencePreview.value = preview;
    selectedInferenceCommitments.value = preview.commitments.map(
      (item) => item.proposal_id,
    );
    selectedInferenceAllowances.value = preview.allowances.map(
      (item) => item.proposal_id,
    );
    cycleForm.value.nextPaymentDate = preview.income.payment_date;
    cycleForm.value.expectedIncome = String(
      toMajorUnits(preview.income.expected_amount, preview.currency),
    );
    cycleForm.value.currency = preview.currency;
  } catch (caught) {
    message(caught, t("plan.errors.infer"));
  } finally {
    saving.value = false;
  }
}

async function confirmPlan() {
  if (!inferencePreview.value) return;
  saving.value = true;
  error.value = "";
  try {
    const currency = inferencePreview.value.currency;
    const result = await api.confirmPlan({
      target_month: inferencePreview.value.target_month,
      currency,
      opening_balance: toMinorUnits(Number(cycleForm.value.openingBalance), currency),
      current_balance: cycleForm.value.currentBalance
        ? toMinorUnits(Number(cycleForm.value.currentBalance), currency)
        : null,
      commitment_proposal_ids: selectedInferenceCommitments.value,
      allowance_proposal_ids: selectedInferenceAllowances.value,
    });
    inferencePreview.value = null;
    await load();
    selectedCycleId.value = result.payment_cycle_id;
    await loadPlan();
  } catch (caught) {
    message(caught, t("plan.errors.confirm"));
  } finally {
    saving.value = false;
  }
}

async function loadPlan() {
  if (!selectedCycleId.value) {
    forecast.value = null;
    commitments.value = [];
    allowances.value = [];
    return;
  }
  error.value = "";
  try {
    const [forecastResult, commitmentResult, allowanceResult] = await Promise.all([
      api.safeSpendingForecast(selectedCycleId.value),
      api.cycleCommitments(selectedCycleId.value),
      api.cycleAllowances(selectedCycleId.value),
    ]);
    forecast.value = forecastResult;
    commitments.value = commitmentResult.items;
    allowances.value = allowanceResult.items;
    balanceInput.value = String(
      toMajorUnits(forecastResult.usable_balance, forecastResult.currency),
    );
    editingCommitmentId.value = null;
    editingAllowanceId.value = null;
  } catch (caught) {
    message(caught, t("plan.errors.loadSafe"));
  }
}

function startCycleEdit() {
  if (!selectedCycle.value) return;
  const cycle = selectedCycle.value;
  cycleEditForm.value = {
    name: cycle.name ?? "",
    nextPaymentDate: cycle.next_payment_date,
    expectedIncome: String(toMajorUnits(cycle.expected_income_amount, cycle.currency)),
    openingBalance: String(toMajorUnits(cycle.opening_balance, cycle.currency)),
    currentBalance:
      cycle.current_balance === null
        ? ""
        : String(toMajorUnits(cycle.current_balance, cycle.currency)),
    currency: cycle.currency,
    status: cycle.status,
  };
  editingCycle.value = true;
}

function startCycleCreate() {
  if (selectedCycle.value) {
    const payment = addCalendarMonth(
      new Date(`${selectedCycle.value.next_payment_date}T00:00:00`),
    );
    cycleForm.value = {
      name: selectedCycle.value.name ?? t("plan.defaultCycleName"),
      nextPaymentDate: inputDate(payment),
      expectedIncome: String(
        toMajorUnits(
          selectedCycle.value.expected_income_amount,
          selectedCycle.value.currency,
        ),
      ),
      openingBalance: "",
      currentBalance: "",
      currency: selectedCycle.value.currency,
    };
  }
  creatingCycle.value = true;
}

async function saveCycle() {
  if (!selectedCycle.value) return;
  saving.value = true;
  error.value = "";
  try {
    const currency = cycleEditForm.value.currency.toUpperCase();
    const updated = await api.updatePaymentCycle(selectedCycle.value.id, {
      name: cycleEditForm.value.name || null,
      next_payment_date: cycleEditForm.value.nextPaymentDate,
      expected_income_amount: toMinorUnits(
        Number(cycleEditForm.value.expectedIncome),
        currency,
      ),
      currency,
      opening_balance: toMinorUnits(Number(cycleEditForm.value.openingBalance), currency),
      current_balance: cycleEditForm.value.currentBalance
        ? toMinorUnits(Number(cycleEditForm.value.currentBalance), currency)
        : null,
      status: cycleEditForm.value.status,
    });
    cycles.value = cycles.value.map((cycle) => (cycle.id === updated.id ? updated : cycle));
    editingCycle.value = false;
    await loadPlan();
  } catch (caught) {
    message(caught, t("plan.errors.updateCycle"));
  } finally {
    saving.value = false;
  }
}

async function load() {
  loading.value = true;
  error.value = "";
  try {
    const [cycleResult, categoryResult] = await Promise.all([
      api.paymentCycles(),
      api.categories(),
    ]);
    cycles.value = cycleResult.items;
    categories.value = categoryResult;
    const preferred =
      cycles.value.find((cycle) => cycle.status === "active") ?? cycles.value[0];
    selectedCycleId.value = preferred?.id ?? null;
    await loadPlan();
  } catch (caught) {
    message(caught, t("plan.errors.load"));
  } finally {
    loading.value = false;
  }
}

async function createCycle() {
  saving.value = true;
  error.value = "";
  try {
    const cycleCurrency = cycleForm.value.currency.toUpperCase();
    const cycle = await api.createPaymentCycle({
      name: cycleForm.value.name || null,
      next_payment_date: cycleForm.value.nextPaymentDate,
      expected_income_amount: toMinorUnits(
        Number(cycleForm.value.expectedIncome),
        cycleCurrency,
      ),
      currency: cycleCurrency,
      opening_balance: toMinorUnits(
        Number(cycleForm.value.openingBalance),
        cycleCurrency,
      ),
      current_balance: cycleForm.value.currentBalance
        ? toMinorUnits(Number(cycleForm.value.currentBalance), cycleCurrency)
        : null,
      status: cycles.value.length ? "planned" : "active",
    });
    cycles.value.unshift(cycle);
    selectedCycleId.value = cycle.id;
    creatingCycle.value = false;
    const cycleEnd = new Date(`${cycle.end_date}T00:00:00`);
    cycleEnd.setDate(cycleEnd.getDate() - 1);
    commitmentForm.value.dueDate = inputDate(cycleEnd);
    await loadPlan();
  } catch (caught) {
    message(caught, t("plan.errors.createCycle"));
  } finally {
    saving.value = false;
  }
}

async function removeCycle() {
  if (!selectedCycle.value) return;
  if (!window.confirm(t("plan.deleteCycleConfirm"))) return;
  saving.value = true;
  error.value = "";
  try {
    const deletedId = selectedCycle.value.id;
    await api.deletePaymentCycle(deletedId);
    cycles.value = cycles.value.filter((cycle) => cycle.id !== deletedId);
    const preferred =
      cycles.value.find((cycle) => cycle.status === "active") ?? cycles.value[0];
    selectedCycleId.value = preferred?.id ?? null;
    editingCycle.value = false;
    await loadPlan();
  } catch (caught) {
    message(caught, t("plan.errors.deleteCycle"));
  } finally {
    saving.value = false;
  }
}

async function updateBalance() {
  if (!selectedCycle.value) return;
  saving.value = true;
  error.value = "";
  try {
    const updated = await api.updatePaymentCycle(selectedCycle.value.id, {
      current_balance: toMinorUnits(
        Number(balanceInput.value),
        selectedCycle.value.currency,
      ),
    });
    cycles.value = cycles.value.map((cycle) =>
      cycle.id === updated.id ? updated : cycle,
    );
    await loadPlan();
  } catch (caught) {
    message(caught, t("plan.errors.balance"));
  } finally {
    saving.value = false;
  }
}

async function addCommitment() {
  if (!selectedCycle.value) return;
  saving.value = true;
  error.value = "";
  try {
    const created = await api.createCommitment(selectedCycle.value.id, {
      name: commitmentForm.value.name,
      amount: toMinorUnits(
        Number(commitmentForm.value.amount),
        selectedCycle.value.currency,
      ),
      due_date: commitmentForm.value.dueDate,
      priority: commitmentForm.value.priority,
      category_id: commitmentForm.value.categoryId
        ? Number(commitmentForm.value.categoryId)
        : null,
    });
    selectedCycleId.value = created.payment_cycle_id;
    commitmentForm.value.name = "";
    commitmentForm.value.amount = "";
    await loadPlan();
  } catch (caught) {
    message(caught, t("plan.errors.addBill"));
  } finally {
    saving.value = false;
  }
}

async function removeCommitment(id: number) {
  try {
    await api.deleteCommitment(id);
    await loadPlan();
  } catch (caught) {
    message(caught, t("plan.errors.removeBill"));
  }
}

function startCommitmentEdit(item: Commitment) {
  editingCommitmentId.value = item.id;
  commitmentEditForm.value = {
    name: item.name,
    amount: String(toMajorUnits(item.amount, item.currency)),
    dueDate: item.due_date,
    priority: item.priority,
    categoryId: item.category_id === null ? "" : String(item.category_id),
    status: item.status,
    recurrence: item.recurrence ?? "",
  };
}

async function saveCommitment(item: Commitment) {
  saving.value = true;
  error.value = "";
  try {
    const updated = await api.updateCommitment(item.id, {
      name: commitmentEditForm.value.name,
      amount: toMinorUnits(Number(commitmentEditForm.value.amount), item.currency),
      due_date: commitmentEditForm.value.dueDate,
      priority: commitmentEditForm.value.priority,
      category_id: commitmentEditForm.value.categoryId
        ? Number(commitmentEditForm.value.categoryId)
        : null,
      status: commitmentEditForm.value.status,
      recurrence: commitmentEditForm.value.recurrence || null,
    });
    selectedCycleId.value = updated.payment_cycle_id;
    await loadPlan();
  } catch (caught) {
    message(caught, t("plan.errors.updateBill"));
  } finally {
    saving.value = false;
  }
}

async function addAllowance() {
  if (!selectedCycle.value) return;
  saving.value = true;
  error.value = "";
  try {
    await api.createAllowance(selectedCycle.value.id, {
      name: allowanceForm.value.name,
      allowance_type: allowanceForm.value.allowanceType,
      amount: toMinorUnits(
        Number(allowanceForm.value.amount),
        selectedCycle.value.currency,
      ),
      priority: allowanceForm.value.priority,
      category_id: allowanceForm.value.categoryId
        ? Number(allowanceForm.value.categoryId)
        : null,
    });
    allowanceForm.value.name = "";
    allowanceForm.value.amount = "";
    await loadPlan();
  } catch (caught) {
    message(caught, t("plan.errors.addAllowance"));
  } finally {
    saving.value = false;
  }
}

async function removeAllowance(id: number) {
  try {
    await api.deleteAllowance(id);
    await loadPlan();
  } catch (caught) {
    message(caught, t("plan.errors.removeAllowance"));
  }
}

function startAllowanceEdit(item: CycleAllowance) {
  editingAllowanceId.value = item.id;
  allowanceEditForm.value = {
    name: item.name,
    amount: String(
      toMajorUnits(item.amount, selectedCycle.value?.currency ?? "GBP"),
    ),
    allowanceType: item.allowance_type,
    priority: item.priority,
    categoryId: item.category_id === null ? "" : String(item.category_id),
  };
}

async function saveAllowance(item: CycleAllowance) {
  if (!selectedCycle.value) return;
  saving.value = true;
  error.value = "";
  try {
    await api.updateAllowance(item.id, {
      name: allowanceEditForm.value.name,
      allowance_type: allowanceEditForm.value.allowanceType,
      amount: toMinorUnits(
        Number(allowanceEditForm.value.amount),
        selectedCycle.value.currency,
      ),
      priority: allowanceEditForm.value.priority,
      category_id: allowanceEditForm.value.categoryId
        ? Number(allowanceEditForm.value.categoryId)
        : null,
    });
    await loadPlan();
  } catch (caught) {
    message(caught, t("plan.errors.updateAllowance"));
  } finally {
    saving.value = false;
  }
}

function priorityLabel(value: SpendingPriority) {
  return t(`common.priorities.${value}`);
}

function statusLabel(value: PaymentCycle["status"] | Commitment["status"]) {
  return t(`common.statuses.${value}`);
}

function allowanceTypeLabel(value: AllowanceType) {
  return t(`common.allowanceTypes.${value}`);
}

function balanceSourceLabel(value: string) {
  return t(`dashboard.balanceSources.${value}`);
}

onMounted(load);
</script>

<template>
  <section class="view-stack">
    <header class="view-heading split-heading">
      <div>
        <p class="eyebrow">{{ t("plan.eyebrow") }}</p>
        <h2>{{ t("plan.title") }}</h2>
        <p>{{ t("plan.subtitle") }}</p>
      </div>
      <div v-if="cycles.length" class="cycle-actions">
        <label class="field cycle-picker">
          <span>{{ t("common.paymentCycle") }}</span>
          <select v-model="selectedCycleId" @change="creatingCycle = false; loadPlan()">
            <option v-for="cycle in cycles" :key="cycle.id" :value="cycle.id">
              {{ cycle.name || t("common.paymentCycle") }} · {{ formatUkDate(cycle.start_date) }}
            </option>
          </select>
        </label>
        <button class="secondary-button" @click="startCycleCreate">{{ t("plan.addCycle") }}</button>
      </div>
    </header>

    <p v-if="error" class="message error-message">{{ error }}</p>
    <p v-if="loading" class="panel empty-state">{{ t("plan.loading") }}</p>

    <article v-if="!loading" class="panel setup-panel">
      <div class="panel-title">
        <div><h3>{{ t("plan.inferTitle") }}</h3><span>{{ t("plan.inferNote") }}</span></div>
      </div>
      <form class="cycle-setup-form" @submit.prevent="previewPlan">
        <label class="field"><span>{{ t("plan.planMonth") }}</span><input v-model="inferenceTargetMonth" type="date" required /></label>
        <label class="field"><span>{{ t("plan.openingBalance") }}</span><input v-model="cycleForm.openingBalance" type="number" step="0.01" required /></label>
        <label class="field"><span>{{ t("plan.currentBalance") }}</span><input v-model="cycleForm.currentBalance" type="number" step="0.01" /></label>
        <label class="field compact-field"><span>{{ t("common.currency") }}</span><input v-model="cycleForm.currency" minlength="3" maxlength="3" required /></label>
        <button class="secondary-button" :disabled="saving">{{ t("plan.preview") }}</button>
      </form>
      <div v-if="inferencePreview" class="plan-list inference-preview">
        <div class="plan-row"><div><strong>{{ t("plan.expectedIncome") }}</strong><span>{{ inferencePreview.income.description }} · {{ formatUkDate(inferencePreview.income.payment_date) }} · {{ t("plan.confidence", { value: Math.round(inferencePreview.income.confidence * 100) }) }}</span></div><strong>{{ formatMoney(inferencePreview.income.expected_amount, inferencePreview.currency) }}</strong></div>
        <label v-for="item in inferencePreview.commitments" :key="item.proposal_id" class="plan-row">
          <span><input v-model="selectedInferenceCommitments" type="checkbox" :value="item.proposal_id" /> <strong>{{ item.name }}</strong><br /><small>{{ item.category_name }} · {{ formatUkDate(item.due_date) }} · {{ Math.round(item.confidence * 100) }}%</small></span>
          <strong>{{ formatMoney(item.amount, inferencePreview.currency) }}</strong>
        </label>
        <label v-for="item in inferencePreview.allowances" :key="item.proposal_id" class="plan-row">
          <span><input v-model="selectedInferenceAllowances" type="checkbox" :value="item.proposal_id" /> <strong>{{ t("plan.allowanceSuffix", { name: item.name }) }}</strong><br /><small>{{ t("plan.evidenceMonths", { count: item.months_observed }) }}</small></span>
          <strong>{{ formatMoney(item.amount, inferencePreview.currency) }}</strong>
        </label>
        <div class="form-actions"><button class="primary-button" :disabled="saving" @click="confirmPlan">{{ t("plan.confirmPlan") }}</button><button class="secondary-button" @click="inferencePreview = null">{{ t("plan.cancelPreview") }}</button></div>
      </div>
    </article>

    <article v-if="!loading && (!selectedCycle || creatingCycle)" class="panel setup-panel">
      <div class="panel-title">
        <div><h3>{{ selectedCycle ? t("plan.addPaymentCycle") : t("plan.firstCycle") }}</h3><span>{{ t("plan.poundsNote") }}</span></div>
        <button v-if="selectedCycle" class="text-button" @click="creatingCycle = false">{{ t("common.cancel") }}</button>
      </div>
      <form class="cycle-setup-form" @submit.prevent="createCycle">
        <label class="field"><span>{{ t("common.name") }}</span><input v-model="cycleForm.name" required /></label>
        <label class="field"><span>{{ t("plan.benefitDate") }}</span><input v-model="cycleForm.nextPaymentDate" type="date" required /></label>
        <label class="field"><span>{{ t("plan.expectedIncome") }}</span><input v-model="cycleForm.expectedIncome" type="number" min="0" step="0.01" required /></label>
        <label class="field"><span>{{ t("plan.openingBalance") }}</span><input v-model="cycleForm.openingBalance" type="number" step="0.01" required /></label>
        <label class="field"><span>{{ t("plan.usableBalance") }}</span><input v-model="cycleForm.currentBalance" type="number" step="0.01" :placeholder="t('plan.sameAsOpening')" /></label>
        <label class="field compact-field"><span>{{ t("common.currency") }}</span><input v-model="cycleForm.currency" minlength="3" maxlength="3" required /></label>
        <button class="primary-button" :disabled="saving">{{ t("plan.createCycle") }}</button>
      </form>
    </article>

    <template v-if="selectedCycle && forecast">
      <article class="panel cycle-details">
        <div class="panel-title">
          <div><h3>{{ t("plan.cycleDetails") }}</h3><span>{{ t("plan.cycleDates", { start: formatUkDate(selectedCycle.start_date), end: formatUkDate(inclusiveCycleEnd(selectedCycle.end_date)), payment: formatUkDate(selectedCycle.next_payment_date) }) }}</span></div>
          <div v-if="!editingCycle" class="row-actions"><button class="text-button" @click="startCycleEdit">{{ t("plan.editCycle") }}</button><button class="text-button danger" @click="removeCycle">{{ t("plan.deleteCycle") }}</button></div>
        </div>
        <form v-if="editingCycle" class="cycle-setup-form" @submit.prevent="saveCycle">
          <label class="field"><span>{{ t("common.name") }}</span><input v-model="cycleEditForm.name" /></label>
          <label class="field"><span>{{ t("plan.benefitDate") }}</span><input v-model="cycleEditForm.nextPaymentDate" type="date" required /></label>
          <label class="field"><span>{{ t("plan.expectedIncome") }}</span><input v-model="cycleEditForm.expectedIncome" type="number" min="0" step="0.01" required /></label>
          <label class="field"><span>{{ t("plan.openingBalance") }}</span><input v-model="cycleEditForm.openingBalance" type="number" step="0.01" required /></label>
          <label class="field"><span>{{ t("plan.usableBalance") }}</span><input v-model="cycleEditForm.currentBalance" type="number" step="0.01" /></label>
          <label class="field"><span>{{ t("common.currency") }}</span><input v-model="cycleEditForm.currency" minlength="3" maxlength="3" required /></label>
          <label class="field"><span>{{ t("common.status") }}</span><select v-model="cycleEditForm.status"><option value="planned">{{ t("common.statuses.planned") }}</option><option value="active">{{ t("common.statuses.active") }}</option><option value="closed">{{ t("common.statuses.closed") }}</option></select></label>
          <div class="form-actions"><button class="primary-button" :disabled="saving">{{ t("plan.saveCycle") }}</button><button class="secondary-button" type="button" @click="editingCycle = false">{{ t("common.cancel") }}</button></div>
        </form>
      </article>

      <article class="panel balance-panel">
        <div><strong>{{ t("plan.forecastTitle") }}</strong><span>{{ t("plan.forecastSource", { source: balanceSourceLabel(forecast.balance_source) }) }}</span></div>
        <form class="inline-filter" @submit.prevent="updateBalance">
          <label class="field"><span>{{ t("plan.usableBalance") }}</span><input v-model="balanceInput" type="number" step="0.01" required /></label>
          <button class="secondary-button" :disabled="saving">{{ t("common.update") }}</button>
        </form>
      </article>

      <div class="plan-grid">
        <article class="panel">
          <div class="panel-title"><h3>{{ t("plan.billsTitle") }}</h3><span>{{ t("plan.pendingCount", { count: pendingCommitments.length }) }}</span></div>
          <div v-if="!commitments.length" class="table-empty">{{ t("plan.noBills") }}</div>
          <div v-else class="plan-list">
            <div v-for="item in commitments" :key="item.id" class="plan-row-wrap">
              <form v-if="editingCommitmentId === item.id" class="plan-edit-form" @submit.prevent="saveCommitment(item)">
                <label class="field"><span>{{ t("plan.bill") }}</span><input v-model="commitmentEditForm.name" required /></label>
                <label class="field"><span>{{ t("common.amount") }}</span><input v-model="commitmentEditForm.amount" type="number" min="0" step="0.01" required /></label>
                <label class="field"><span>{{ t("plan.due") }}</span><input v-model="commitmentEditForm.dueDate" type="date" required /></label>
                <label class="field"><span>{{ t("common.priority") }}</span><select v-model="commitmentEditForm.priority"><option value="protected">{{ t("common.priorities.protected") }}</option><option value="essential">{{ t("common.priorities.essential") }}</option><option value="adjustable">{{ t("common.priorities.adjustable") }}</option><option value="optional">{{ t("common.priorities.optional") }}</option></select></label>
                <label class="field"><span>{{ t("common.status") }}</span><select v-model="commitmentEditForm.status"><option value="pending">{{ t("common.statuses.pending") }}</option><option value="paid">{{ t("common.statuses.paid") }}</option><option value="skipped">{{ t("common.statuses.skipped") }}</option></select></label>
                <label class="field"><span>{{ t("plan.recurrence") }}</span><input v-model="commitmentEditForm.recurrence" :placeholder="t('plan.recurrencePlaceholder')" /></label>
                <label class="field"><span>{{ t("common.category") }}</span><select v-model="commitmentEditForm.categoryId"><option value="">{{ t("common.none") }}</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ formatCategoryName(category) }}</option></select></label>
                <div class="form-actions"><button class="primary-button" :disabled="saving">{{ t("common.save") }}</button><button class="secondary-button" type="button" @click="editingCommitmentId = null">{{ t("common.cancel") }}</button></div>
              </form>
              <div v-else class="plan-row">
                <div><strong>{{ item.name }}</strong><span>{{ formatUkDate(item.due_date) }} · {{ priorityLabel(item.priority) }} · {{ statusLabel(item.status) }}</span><span>{{ t("plan.fundedFrom", { date: formatUkDate(item.funding_payment_date) }) }}</span></div>
                <strong>{{ formatMoney(item.amount, item.currency) }}</strong>
                <div class="row-actions"><button class="text-button" @click="startCommitmentEdit(item)">{{ t("common.edit") }}</button><button class="text-button danger" :aria-label="t('plan.deleteBill')" @click="removeCommitment(item.id)">{{ t("common.remove") }}</button></div>
              </div>
            </div>
          </div>
          <form class="plan-form" @submit.prevent="addCommitment">
            <label class="field"><span>{{ t("plan.bill") }}</span><input v-model="commitmentForm.name" required /></label>
            <label class="field"><span>{{ t("common.amount") }}</span><input v-model="commitmentForm.amount" type="number" min="0" step="0.01" required /></label>
            <label class="field"><span>{{ t("plan.due") }}</span><input v-model="commitmentForm.dueDate" type="date" required /></label>
            <label class="field"><span>{{ t("common.priority") }}</span><select v-model="commitmentForm.priority"><option value="protected">{{ t("common.priorities.protected") }}</option><option value="essential">{{ t("common.priorities.essential") }}</option><option value="adjustable">{{ t("common.priorities.adjustable") }}</option><option value="optional">{{ t("common.priorities.optional") }}</option></select></label>
            <label class="field"><span>{{ t("common.category") }}</span><select v-model="commitmentForm.categoryId"><option value="">{{ t("common.none") }}</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ formatCategoryName(category) }}</option></select></label>
            <button class="primary-button" :disabled="saving">{{ t("plan.addBill") }}</button>
          </form>
        </article>

        <article class="panel">
          <div class="panel-title"><h3>{{ t("plan.allowancesTitle") }}</h3><span>{{ t("plan.plannedCount", { count: allowances.length }) }}</span></div>
          <div v-if="!allowances.length" class="table-empty">{{ t("plan.noAllowances") }}</div>
          <div v-else class="plan-list">
            <div v-for="item in allowances" :key="item.id" class="allowance-row">
              <form v-if="editingAllowanceId === item.id" class="plan-edit-form" @submit.prevent="saveAllowance(item)">
                <label class="field"><span>{{ t("plan.allowance") }}</span><input v-model="allowanceEditForm.name" required /></label>
                <label class="field"><span>{{ t("common.amount") }}</span><input v-model="allowanceEditForm.amount" type="number" min="0" step="0.01" required /></label>
                <label class="field"><span>{{ t("plan.type") }}</span><select v-model="allowanceEditForm.allowanceType"><option value="food">{{ t("common.allowanceTypes.food") }}</option><option value="transport">{{ t("common.allowanceTypes.transport") }}</option><option value="irregular_cost">{{ t("common.allowanceTypes.irregular_cost") }}</option><option value="emergency">{{ t("common.allowanceTypes.emergency") }}</option><option value="custom">{{ t("common.allowanceTypes.custom") }}</option></select></label>
                <label class="field"><span>{{ t("common.priority") }}</span><select v-model="allowanceEditForm.priority"><option value="protected">{{ t("common.priorities.protected") }}</option><option value="essential">{{ t("common.priorities.essential") }}</option><option value="adjustable">{{ t("common.priorities.adjustable") }}</option><option value="irregular_essential">{{ t("common.priorities.irregular_essential") }}</option><option value="optional">{{ t("common.priorities.optional") }}</option></select></label>
                <label class="field"><span>{{ t("common.category") }}</span><select v-model="allowanceEditForm.categoryId"><option value="">{{ t("plan.reserveOnly") }}</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ formatCategoryName(category) }}</option></select></label>
                <div class="form-actions"><button class="primary-button" :disabled="saving">{{ t("common.save") }}</button><button class="secondary-button" type="button" @click="editingAllowanceId = null">{{ t("common.cancel") }}</button></div>
              </form>
              <template v-else>
                <div class="allowance-heading"><div><strong>{{ item.name }}</strong><span>{{ allowanceTypeLabel(item.allowance_type) }} · {{ priorityLabel(item.priority) }}</span></div><strong>{{ formatMoney(item.amount, forecast.currency) }}</strong></div>
                <template v-if="allowanceForecast(item.id)">
                  <div class="allowance-track"><span :style="{ width: `${Math.min(100, item.amount ? (allowanceForecast(item.id)?.spent_amount ?? 0) / item.amount * 100 : 0)}%` }"></span></div>
                  <div class="allowance-foot"><span>{{ t("plan.spentLeft", { spent: formatMoney(allowanceForecast(item.id)?.spent_amount ?? 0, forecast.currency), left: formatMoney(allowanceForecast(item.id)?.remaining_amount ?? item.amount, forecast.currency) }) }}</span><div class="row-actions"><button class="text-button" @click="startAllowanceEdit(item)">{{ t("common.edit") }}</button><button class="text-button danger" @click="removeAllowance(item.id)">{{ t("common.remove") }}</button></div></div>
                </template>
                <div v-else class="allowance-foot"><span>{{ item.category_id ? t("plan.linkedCategory") : t("plan.reserveOnly") }}</span><div class="row-actions"><button class="text-button" @click="startAllowanceEdit(item)">{{ t("common.edit") }}</button><button class="text-button danger" @click="removeAllowance(item.id)">{{ t("common.remove") }}</button></div></div>
              </template>
            </div>
          </div>
          <form class="plan-form" @submit.prevent="addAllowance">
            <label class="field"><span>{{ t("plan.allowance") }}</span><input v-model="allowanceForm.name" required /></label>
            <label class="field"><span>{{ t("common.amount") }}</span><input v-model="allowanceForm.amount" type="number" min="0" step="0.01" required /></label>
            <label class="field"><span>{{ t("plan.type") }}</span><select v-model="allowanceForm.allowanceType"><option value="food">{{ t("common.allowanceTypes.food") }}</option><option value="transport">{{ t("common.allowanceTypes.transport") }}</option><option value="irregular_cost">{{ t("common.allowanceTypes.irregular_cost") }}</option><option value="emergency">{{ t("common.allowanceTypes.emergency") }}</option><option value="custom">{{ t("common.allowanceTypes.custom") }}</option></select></label>
            <label class="field"><span>{{ t("common.priority") }}</span><select v-model="allowanceForm.priority"><option value="protected">{{ t("common.priorities.protected") }}</option><option value="essential">{{ t("common.priorities.essential") }}</option><option value="adjustable">{{ t("common.priorities.adjustable") }}</option><option value="irregular_essential">{{ t("common.priorities.irregular_essential") }}</option><option value="optional">{{ t("common.priorities.optional") }}</option></select></label>
            <label class="field"><span>{{ t("common.category") }}</span><select v-model="allowanceForm.categoryId"><option value="">{{ t("plan.reserveOnly") }}</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ formatCategoryName(category) }}</option></select></label>
            <button class="primary-button" :disabled="saving">{{ t("plan.addAllowance") }}</button>
          </form>
        </article>
      </div>
    </template>
  </section>
</template>

