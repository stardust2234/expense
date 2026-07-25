<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api } from "../api/client";
import type {
  AllowanceType,
  Category,
  Commitment,
  CycleAllowance,
  PaymentCycle,
  SafeSpendingForecast,
  SpendingPriority,
} from "../types/api";
import { formatUkDate } from "../utils/date";
import { formatMoney, toMajorUnits, toMinorUnits } from "../utils/money";

const today = new Date();
function addCalendarMonth(value: Date) {
  const targetMonth = value.getMonth() + 1;
  const lastTargetDay = new Date(value.getFullYear(), targetMonth + 1, 0).getDate();
  return new Date(
    value.getFullYear(),
    targetMonth,
    Math.min(value.getDate(), lastTargetDay),
  );
}
const nextPayment = addCalendarMonth(today);
const firstBillDue = new Date(nextPayment);
firstBillDue.setDate(nextPayment.getDate() - 1);
const inputDate = (value: Date) =>
  `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;

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
const creatingCycle = ref(false);
const editingCycle = ref(false);
const editingCommitmentId = ref<number | null>(null);
const editingAllowanceId = ref<number | null>(null);

const cycleForm = ref({
  name: "Benefit payment",
  startDate: inputDate(today),
  nextPaymentDate: inputDate(nextPayment),
  expectedIncome: "",
  openingBalance: "",
  currentBalance: "",
  currency: "GBP",
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
  startDate: "",
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
    message(caught, "Could not load the safe-spending plan");
  }
}

function startCycleEdit() {
  if (!selectedCycle.value) return;
  const cycle = selectedCycle.value;
  cycleEditForm.value = {
    name: cycle.name ?? "",
    startDate: cycle.start_date,
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
    const start = new Date(`${selectedCycle.value.next_payment_date}T00:00:00`);
    const end = addCalendarMonth(start);
    cycleForm.value = {
      name: selectedCycle.value.name ?? "Benefit payment",
      startDate: inputDate(start),
      nextPaymentDate: inputDate(end),
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
      start_date: cycleEditForm.value.startDate,
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
    message(caught, "Could not update the payment cycle");
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
    message(caught, "Could not load the financial plan");
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
      start_date: cycleForm.value.startDate,
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
    const cycleEnd = new Date(`${cycle.next_payment_date}T00:00:00`);
    cycleEnd.setDate(cycleEnd.getDate() - 1);
    commitmentForm.value.dueDate = inputDate(cycleEnd);
    await loadPlan();
  } catch (caught) {
    message(caught, "Could not create the payment cycle");
  } finally {
    saving.value = false;
  }
}

async function removeCycle() {
  if (!selectedCycle.value) return;
  if (!window.confirm("Delete this payment cycle, its bills, and its allowances?")) return;
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
    message(caught, "Could not delete the payment cycle");
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
    message(caught, "Could not update the usable balance");
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
    message(caught, "Could not add the bill");
  } finally {
    saving.value = false;
  }
}

async function removeCommitment(id: number) {
  try {
    await api.deleteCommitment(id);
    await loadPlan();
  } catch (caught) {
    message(caught, "Could not remove the bill");
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
    message(caught, "Could not update the bill");
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
    message(caught, "Could not add the allowance");
  } finally {
    saving.value = false;
  }
}

async function removeAllowance(id: number) {
  try {
    await api.deleteAllowance(id);
    await loadPlan();
  } catch (caught) {
    message(caught, "Could not remove the allowance");
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
    message(caught, "Could not update the allowance");
  } finally {
    saving.value = false;
  }
}

function priorityLabel(value: SpendingPriority) {
  return value.replace("_", " ");
}

onMounted(load);
</script>

<template>
  <section class="view-stack">
    <header class="view-heading split-heading">
      <div>
        <p class="eyebrow">Until your next payment</p>
        <h2>Financial plan</h2>
        <p>Protect bills and essential allowances before treating the rest as available.</p>
      </div>
      <div v-if="cycles.length" class="cycle-actions">
        <label class="field cycle-picker">
          <span>Payment cycle</span>
          <select v-model="selectedCycleId" @change="creatingCycle = false; loadPlan()">
            <option v-for="cycle in cycles" :key="cycle.id" :value="cycle.id">
              {{ cycle.name || "Payment cycle" }} · {{ formatUkDate(cycle.start_date) }}
            </option>
          </select>
        </label>
        <button class="secondary-button" @click="startCycleCreate">Add cycle</button>
      </div>
    </header>

    <p v-if="error" class="message error-message">{{ error }}</p>
    <p v-if="loading" class="panel empty-state">Loading your financial position…</p>

    <article v-else-if="!selectedCycle || creatingCycle" class="panel setup-panel">
      <div class="panel-title">
        <div><h3>{{ selectedCycle ? "Add payment cycle" : "Set up your first payment cycle" }}</h3><span>Amounts are entered in pounds.</span></div>
        <button v-if="selectedCycle" class="text-button" @click="creatingCycle = false">Cancel</button>
      </div>
      <form class="cycle-setup-form" @submit.prevent="createCycle">
        <label class="field"><span>Name</span><input v-model="cycleForm.name" required /></label>
        <label class="field"><span>Payment received</span><input v-model="cycleForm.startDate" type="date" required /></label>
        <label class="field"><span>Next payment</span><input v-model="cycleForm.nextPaymentDate" type="date" required /></label>
        <label class="field"><span>Expected income</span><input v-model="cycleForm.expectedIncome" type="number" min="0" step="0.01" required /></label>
        <label class="field"><span>Opening balance</span><input v-model="cycleForm.openingBalance" type="number" step="0.01" required /></label>
        <label class="field"><span>Current usable balance</span><input v-model="cycleForm.currentBalance" type="number" step="0.01" placeholder="Same as opening" /></label>
        <label class="field compact-field"><span>Currency</span><input v-model="cycleForm.currency" minlength="3" maxlength="3" required /></label>
        <button class="primary-button" :disabled="saving">Create payment cycle</button>
      </form>
    </article>

    <template v-if="selectedCycle && forecast">
      <article class="panel cycle-details">
        <div class="panel-title">
          <div><h3>Payment-cycle details</h3><span>{{ formatUkDate(selectedCycle.start_date) }} to {{ formatUkDate(selectedCycle.next_payment_date) }}</span></div>
          <div v-if="!editingCycle" class="row-actions"><button class="text-button" @click="startCycleEdit">Edit cycle</button><button class="text-button danger" @click="removeCycle">Delete cycle</button></div>
        </div>
        <form v-if="editingCycle" class="cycle-setup-form" @submit.prevent="saveCycle">
          <label class="field"><span>Name</span><input v-model="cycleEditForm.name" /></label>
          <label class="field"><span>Payment received</span><input v-model="cycleEditForm.startDate" type="date" required /></label>
          <label class="field"><span>Next payment</span><input v-model="cycleEditForm.nextPaymentDate" type="date" required /></label>
          <label class="field"><span>Expected income</span><input v-model="cycleEditForm.expectedIncome" type="number" min="0" step="0.01" required /></label>
          <label class="field"><span>Opening balance</span><input v-model="cycleEditForm.openingBalance" type="number" step="0.01" required /></label>
          <label class="field"><span>Current usable balance</span><input v-model="cycleEditForm.currentBalance" type="number" step="0.01" /></label>
          <label class="field"><span>Currency</span><input v-model="cycleEditForm.currency" minlength="3" maxlength="3" required /></label>
          <label class="field"><span>Status</span><select v-model="cycleEditForm.status"><option value="planned">Planned</option><option value="active">Active</option><option value="closed">Closed</option></select></label>
          <div class="form-actions"><button class="primary-button" :disabled="saving">Save cycle</button><button class="secondary-button" type="button" @click="editingCycle = false">Cancel</button></div>
        </form>
      </article>

      <article class="panel balance-panel">
        <div><strong>Keep the forecast current</strong><span>The calculation uses your {{ forecast.balance_source }} balance.</span></div>
        <form class="inline-filter" @submit.prevent="updateBalance">
          <label class="field"><span>Usable balance</span><input v-model="balanceInput" type="number" step="0.01" required /></label>
          <button class="secondary-button" :disabled="saving">Update</button>
        </form>
      </article>

      <div class="plan-grid">
        <article class="panel">
          <div class="panel-title"><h3>Bills due before payment</h3><span>{{ pendingCommitments.length }} pending</span></div>
          <div v-if="!commitments.length" class="table-empty">No commitments recorded.</div>
          <div v-else class="plan-list">
            <div v-for="item in commitments" :key="item.id" class="plan-row-wrap">
              <form v-if="editingCommitmentId === item.id" class="plan-edit-form" @submit.prevent="saveCommitment(item)">
                <label class="field"><span>Bill</span><input v-model="commitmentEditForm.name" required /></label>
                <label class="field"><span>Amount</span><input v-model="commitmentEditForm.amount" type="number" min="0" step="0.01" required /></label>
                <label class="field"><span>Due</span><input v-model="commitmentEditForm.dueDate" type="date" required /></label>
                <label class="field"><span>Priority</span><select v-model="commitmentEditForm.priority"><option value="protected">Protected</option><option value="essential">Essential</option><option value="adjustable">Adjustable</option><option value="optional">Optional</option></select></label>
                <label class="field"><span>Status</span><select v-model="commitmentEditForm.status"><option value="pending">Pending</option><option value="paid">Paid</option><option value="skipped">Skipped</option></select></label>
                <label class="field"><span>Recurrence</span><input v-model="commitmentEditForm.recurrence" placeholder="e.g. monthly" /></label>
                <label class="field"><span>Category</span><select v-model="commitmentEditForm.categoryId"><option value="">None</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ category.name }}</option></select></label>
                <div class="form-actions"><button class="primary-button" :disabled="saving">Save</button><button class="secondary-button" type="button" @click="editingCommitmentId = null">Cancel</button></div>
              </form>
              <div v-else class="plan-row">
                <div><strong>{{ item.name }}</strong><span>{{ formatUkDate(item.due_date) }} · {{ priorityLabel(item.priority) }} · {{ item.status }}</span><span>Funded by payment received {{ formatUkDate(item.funding_payment_date) }}</span></div>
                <strong>{{ formatMoney(item.amount, item.currency) }}</strong>
                <div class="row-actions"><button class="text-button" @click="startCommitmentEdit(item)">Edit</button><button class="text-button danger" aria-label="Delete bill" @click="removeCommitment(item.id)">Remove</button></div>
              </div>
            </div>
          </div>
          <form class="plan-form" @submit.prevent="addCommitment">
            <label class="field"><span>Bill</span><input v-model="commitmentForm.name" required /></label>
            <label class="field"><span>Amount</span><input v-model="commitmentForm.amount" type="number" min="0" step="0.01" required /></label>
            <label class="field"><span>Due</span><input v-model="commitmentForm.dueDate" type="date" required /></label>
            <label class="field"><span>Priority</span><select v-model="commitmentForm.priority"><option value="protected">Protected</option><option value="essential">Essential</option><option value="adjustable">Adjustable</option><option value="optional">Optional</option></select></label>
            <label class="field"><span>Category</span><select v-model="commitmentForm.categoryId"><option value="">None</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ category.name }}</option></select></label>
            <button class="primary-button" :disabled="saving">Add bill</button>
          </form>
        </article>

        <article class="panel">
          <div class="panel-title"><h3>Allowances and reserves</h3><span>{{ allowances.length }} planned</span></div>
          <div v-if="!allowances.length" class="table-empty">No essential allowances recorded.</div>
          <div v-else class="plan-list">
            <div v-for="item in allowances" :key="item.id" class="allowance-row">
              <form v-if="editingAllowanceId === item.id" class="plan-edit-form" @submit.prevent="saveAllowance(item)">
                <label class="field"><span>Allowance</span><input v-model="allowanceEditForm.name" required /></label>
                <label class="field"><span>Amount</span><input v-model="allowanceEditForm.amount" type="number" min="0" step="0.01" required /></label>
                <label class="field"><span>Type</span><select v-model="allowanceEditForm.allowanceType"><option value="food">Food</option><option value="transport">Transport</option><option value="irregular_cost">Irregular cost</option><option value="emergency">Emergency</option><option value="custom">Custom</option></select></label>
                <label class="field"><span>Priority</span><select v-model="allowanceEditForm.priority"><option value="protected">Protected</option><option value="essential">Essential</option><option value="adjustable">Adjustable</option><option value="irregular_essential">Irregular essential</option><option value="optional">Optional</option></select></label>
                <label class="field"><span>Category</span><select v-model="allowanceEditForm.categoryId"><option value="">Reserve only</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ category.name }}</option></select></label>
                <div class="form-actions"><button class="primary-button" :disabled="saving">Save</button><button class="secondary-button" type="button" @click="editingAllowanceId = null">Cancel</button></div>
              </form>
              <template v-else>
                <div class="allowance-heading"><div><strong>{{ item.name }}</strong><span>{{ item.allowance_type.replace("_", " ") }} · {{ priorityLabel(item.priority) }}</span></div><strong>{{ formatMoney(item.amount, forecast.currency) }}</strong></div>
                <template v-if="allowanceForecast(item.id)">
                  <div class="allowance-track"><span :style="{ width: `${Math.min(100, item.amount ? (allowanceForecast(item.id)?.spent_amount ?? 0) / item.amount * 100 : 0)}%` }"></span></div>
                  <div class="allowance-foot"><span>{{ formatMoney(allowanceForecast(item.id)?.spent_amount ?? 0, forecast.currency) }} spent · {{ formatMoney(allowanceForecast(item.id)?.remaining_amount ?? item.amount, forecast.currency) }} left</span><div class="row-actions"><button class="text-button" @click="startAllowanceEdit(item)">Edit</button><button class="text-button danger" @click="removeAllowance(item.id)">Remove</button></div></div>
                </template>
                <div v-else class="allowance-foot"><span>{{ item.category_id ? "Linked to a spending category" : "Reserve only" }}</span><div class="row-actions"><button class="text-button" @click="startAllowanceEdit(item)">Edit</button><button class="text-button danger" @click="removeAllowance(item.id)">Remove</button></div></div>
              </template>
            </div>
          </div>
          <form class="plan-form" @submit.prevent="addAllowance">
            <label class="field"><span>Allowance</span><input v-model="allowanceForm.name" required /></label>
            <label class="field"><span>Amount</span><input v-model="allowanceForm.amount" type="number" min="0" step="0.01" required /></label>
            <label class="field"><span>Type</span><select v-model="allowanceForm.allowanceType"><option value="food">Food</option><option value="transport">Transport</option><option value="irregular_cost">Irregular cost</option><option value="emergency">Emergency</option><option value="custom">Custom</option></select></label>
            <label class="field"><span>Priority</span><select v-model="allowanceForm.priority"><option value="protected">Protected</option><option value="essential">Essential</option><option value="adjustable">Adjustable</option><option value="irregular_essential">Irregular essential</option><option value="optional">Optional</option></select></label>
            <label class="field"><span>Category</span><select v-model="allowanceForm.categoryId"><option value="">Reserve only</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ category.name }}</option></select></label>
            <button class="primary-button" :disabled="saving">Add allowance</button>
          </form>
        </article>
      </div>
    </template>
  </section>
</template>

