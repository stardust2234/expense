import { computed, ref, type Ref } from "vue";

import { api } from "../../api/client";
import type { AllowanceType, Category, Commitment, CycleAllowance, PaymentCycle, SafeSpendingForecast, SpendingPriority } from "../../types/api";
import { toMajorUnits, toMinorUnits } from "../../utils/money";

type Translate = (key: string) => string;

export function usePlanItems(options: {
  cycles: Ref<PaymentCycle[]>;
  selectedCycleId: Ref<number | null>;
  saving: Ref<boolean>;
  setError: (caught: unknown, fallback: string) => void;
  clearError: () => void;
  t: Translate;
}) {
  const { cycles, selectedCycleId, saving, setError, clearError, t } = options;
  const commitments = ref<Commitment[]>([]);
  const allowances = ref<CycleAllowance[]>([]);
  const forecast = ref<SafeSpendingForecast | null>(null);
  const categories = ref<Category[]>([]);
  const balanceInput = ref("");
  const editingCommitmentId = ref<number | null>(null);
  const editingAllowanceId = ref<number | null>(null);
  const selectedCycle = computed(() =>
    cycles.value.find((cycle) => cycle.id === selectedCycleId.value) ?? null,
  );
  const pendingCommitments = computed(() =>
    commitments.value.filter((item) => item.status === "pending"),
  );
  const commitmentForm = ref({
    name: "", amount: "", dueDate: "", priority: "protected" as SpendingPriority, categoryId: "",
  });
  const allowanceForm = ref({
    name: "", amount: "", allowanceType: "food" as AllowanceType,
    priority: "essential" as SpendingPriority, categoryId: "",
  });
  const commitmentEditForm = ref({
    name: "", amount: "", dueDate: "", priority: "protected" as SpendingPriority,
    categoryId: "", status: "pending" as Commitment["status"], recurrence: "",
  });
  const allowanceEditForm = ref({
    name: "", amount: "", allowanceType: "food" as AllowanceType,
    priority: "essential" as SpendingPriority, categoryId: "",
  });

  const categoryId = (value: string) => value ? Number(value) : null;

  async function loadCategories() {
    categories.value = await api.categories();
  }

  async function loadPlan() {
    const cycleId = selectedCycleId.value;
    forecast.value = null;
    commitments.value = [];
    allowances.value = [];
    editingCommitmentId.value = null;
    editingAllowanceId.value = null;
    if (!cycleId) return;
    clearError();
    try {
      const [forecastResult, commitmentResult, allowanceResult] = await Promise.all([
        api.safeSpendingForecast(cycleId),
        api.cycleCommitments(cycleId),
        api.cycleAllowances(cycleId),
      ]);
      if (selectedCycleId.value !== cycleId) return;
      forecast.value = forecastResult;
      commitments.value = commitmentResult.items;
      allowances.value = allowanceResult.items;
      balanceInput.value = String(toMajorUnits(forecastResult.usable_balance, forecastResult.currency));
    } catch (caught) {
      if (selectedCycleId.value === cycleId) setError(caught, t("plan.errors.loadSafe"));
    }
  }

  function setDefaultDueDate(value: string) {
    commitmentForm.value.dueDate = value;
  }

  async function updateBalance() {
    const cycle = selectedCycle.value;
    if (!cycle) return;
    saving.value = true;
    clearError();
    try {
      const updated = await api.updatePaymentCycle(cycle.id, {
        current_balance: toMinorUnits(Number(balanceInput.value), cycle.currency),
      });
      cycles.value = cycles.value.map((item) => item.id === updated.id ? updated : item);
      await loadPlan();
    } catch (caught) {
      setError(caught, t("plan.errors.balance"));
    } finally {
      saving.value = false;
    }
  }

  async function addCommitment() {
    const cycle = selectedCycle.value;
    if (!cycle) return;
    saving.value = true;
    clearError();
    try {
      const created = await api.createCommitment(cycle.id, {
        name: commitmentForm.value.name,
        amount: toMinorUnits(Number(commitmentForm.value.amount), cycle.currency),
        due_date: commitmentForm.value.dueDate,
        priority: commitmentForm.value.priority,
        category_id: categoryId(commitmentForm.value.categoryId),
      });
      selectedCycleId.value = created.payment_cycle_id;
      commitmentForm.value.name = "";
      commitmentForm.value.amount = "";
      await loadPlan();
    } catch (caught) {
      setError(caught, t("plan.errors.addBill"));
    } finally {
      saving.value = false;
    }
  }

  async function removeCommitment(id: number) {
    try {
      await api.deleteCommitment(id);
      await loadPlan();
    } catch (caught) {
      setError(caught, t("plan.errors.removeBill"));
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
    clearError();
    try {
      const updated = await api.updateCommitment(item.id, {
        name: commitmentEditForm.value.name,
        amount: toMinorUnits(Number(commitmentEditForm.value.amount), item.currency),
        due_date: commitmentEditForm.value.dueDate,
        priority: commitmentEditForm.value.priority,
        category_id: categoryId(commitmentEditForm.value.categoryId),
        status: commitmentEditForm.value.status,
        recurrence: commitmentEditForm.value.recurrence || null,
      });
      selectedCycleId.value = updated.payment_cycle_id;
      await loadPlan();
    } catch (caught) {
      setError(caught, t("plan.errors.updateBill"));
    } finally {
      saving.value = false;
    }
  }

  async function addAllowance() {
    const cycle = selectedCycle.value;
    if (!cycle) return;
    saving.value = true;
    clearError();
    try {
      await api.createAllowance(cycle.id, {
        name: allowanceForm.value.name,
        allowance_type: allowanceForm.value.allowanceType,
        amount: toMinorUnits(Number(allowanceForm.value.amount), cycle.currency),
        priority: allowanceForm.value.priority,
        category_id: categoryId(allowanceForm.value.categoryId),
      });
      allowanceForm.value.name = "";
      allowanceForm.value.amount = "";
      await loadPlan();
    } catch (caught) {
      setError(caught, t("plan.errors.addAllowance"));
    } finally {
      saving.value = false;
    }
  }

  async function removeAllowance(id: number) {
    try {
      await api.deleteAllowance(id);
      await loadPlan();
    } catch (caught) {
      setError(caught, t("plan.errors.removeAllowance"));
    }
  }

  function startAllowanceEdit(item: CycleAllowance) {
    editingAllowanceId.value = item.id;
    allowanceEditForm.value = {
      name: item.name,
      amount: String(toMajorUnits(item.amount, selectedCycle.value?.currency ?? "GBP")),
      allowanceType: item.allowance_type,
      priority: item.priority,
      categoryId: item.category_id === null ? "" : String(item.category_id),
    };
  }

  async function saveAllowance(item: CycleAllowance) {
    const cycle = selectedCycle.value;
    if (!cycle) return;
    saving.value = true;
    clearError();
    try {
      await api.updateAllowance(item.id, {
        name: allowanceEditForm.value.name,
        allowance_type: allowanceEditForm.value.allowanceType,
        amount: toMinorUnits(Number(allowanceEditForm.value.amount), cycle.currency),
        priority: allowanceEditForm.value.priority,
        category_id: categoryId(allowanceEditForm.value.categoryId),
      });
      await loadPlan();
    } catch (caught) {
      setError(caught, t("plan.errors.updateAllowance"));
    } finally {
      saving.value = false;
    }
  }

  return {
    commitments, allowances, forecast, categories, balanceInput, selectedCycle,
    pendingCommitments, commitmentForm, allowanceForm, commitmentEditForm,
    allowanceEditForm, editingCommitmentId, editingAllowanceId, loadCategories,
    loadPlan, setDefaultDueDate, updateBalance, addCommitment, removeCommitment,
    startCommitmentEdit, saveCommitment, addAllowance, removeAllowance,
    startAllowanceEdit, saveAllowance,
  };
}

