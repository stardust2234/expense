import { computed, ref, type Ref } from "vue";

import { api } from "../../api/client";
import type { PaymentCycle } from "../../types/api";
import { toMajorUnits, toMinorUnits } from "../../utils/money";
import { addCalendarMonth, inputDate } from "./calendar";

type Translate = (key: string) => string;

export function usePaymentCycles(options: {
  cycles: Ref<PaymentCycle[]>;
  selectedCycleId: Ref<number | null>;
  saving: Ref<boolean>;
  initialForm: {
    name: string; nextPaymentDate: string; expectedIncome: string;
    openingBalance: string; currentBalance: string; currency: string;
  };
  refreshPlan: () => Promise<void>;
  setDefaultDueDate: (value: string) => void;
  setError: (caught: unknown, fallback: string) => void;
  clearError: () => void;
  t: Translate;
}) {
  const { cycles, selectedCycleId, saving, refreshPlan, setDefaultDueDate, setError, clearError, t } = options;
  const creatingCycle = ref(false);
  const editingCycle = ref(false);
  const cycleForm = ref({ ...options.initialForm });
  const cycleEditForm = ref({
    name: "", nextPaymentDate: "", expectedIncome: "", openingBalance: "",
    currentBalance: "", currency: "GBP", status: "active" as PaymentCycle["status"],
  });
  const selectedCycle = computed(() =>
    cycles.value.find((cycle) => cycle.id === selectedCycleId.value) ?? null,
  );

  async function loadCycles() {
    const result = await api.paymentCycles();
    cycles.value = result.items;
    const preferred = cycles.value.find((cycle) => cycle.status === "active") ?? cycles.value[0];
    selectedCycleId.value = preferred?.id ?? null;
  }

  function selectCycle() {
    creatingCycle.value = false;
    editingCycle.value = false;
    void refreshPlan();
  }

  function startCycleEdit() {
    const cycle = selectedCycle.value;
    if (!cycle) return;
    cycleEditForm.value = {
      name: cycle.name ?? "",
      nextPaymentDate: cycle.next_payment_date,
      expectedIncome: String(toMajorUnits(cycle.expected_income_amount, cycle.currency)),
      openingBalance: String(toMajorUnits(cycle.opening_balance, cycle.currency)),
      currentBalance: cycle.current_balance === null ? "" : String(toMajorUnits(cycle.current_balance, cycle.currency)),
      currency: cycle.currency,
      status: cycle.status,
    };
    editingCycle.value = true;
  }

  function startCycleCreate() {
    const cycle = selectedCycle.value;
    if (cycle) {
      const payment = addCalendarMonth(new Date(`${cycle.next_payment_date}T00:00:00`));
      cycleForm.value = {
        name: cycle.name ?? t("plan.defaultCycleName"),
        nextPaymentDate: inputDate(payment),
        expectedIncome: String(toMajorUnits(cycle.expected_income_amount, cycle.currency)),
        openingBalance: "",
        currentBalance: "",
        currency: cycle.currency,
      };
    }
    creatingCycle.value = true;
  }

  async function saveCycle() {
    const cycle = selectedCycle.value;
    if (!cycle) return;
    saving.value = true;
    clearError();
    try {
      const currency = cycleEditForm.value.currency.toUpperCase();
      const updated = await api.updatePaymentCycle(cycle.id, {
        name: cycleEditForm.value.name || null,
        next_payment_date: cycleEditForm.value.nextPaymentDate,
        expected_income_amount: toMinorUnits(Number(cycleEditForm.value.expectedIncome), currency),
        currency,
        opening_balance: toMinorUnits(Number(cycleEditForm.value.openingBalance), currency),
        current_balance: cycleEditForm.value.currentBalance
          ? toMinorUnits(Number(cycleEditForm.value.currentBalance), currency) : null,
        status: cycleEditForm.value.status,
      });
      cycles.value = cycles.value.map((item) => item.id === updated.id ? updated : item);
      editingCycle.value = false;
      await refreshPlan();
    } catch (caught) {
      setError(caught, t("plan.errors.updateCycle"));
    } finally {
      saving.value = false;
    }
  }

  async function createCycle() {
    saving.value = true;
    clearError();
    try {
      const currency = cycleForm.value.currency.toUpperCase();
      const cycle = await api.createPaymentCycle({
        name: cycleForm.value.name || null,
        next_payment_date: cycleForm.value.nextPaymentDate,
        expected_income_amount: toMinorUnits(Number(cycleForm.value.expectedIncome), currency),
        currency,
        opening_balance: toMinorUnits(Number(cycleForm.value.openingBalance), currency),
        current_balance: cycleForm.value.currentBalance
          ? toMinorUnits(Number(cycleForm.value.currentBalance), currency) : null,
        status: cycles.value.length ? "planned" : "active",
      });
      cycles.value.unshift(cycle);
      selectedCycleId.value = cycle.id;
      creatingCycle.value = false;
      const cycleEnd = new Date(`${cycle.end_date}T00:00:00`);
      cycleEnd.setDate(cycleEnd.getDate() - 1);
      setDefaultDueDate(inputDate(cycleEnd));
      await refreshPlan();
    } catch (caught) {
      setError(caught, t("plan.errors.createCycle"));
    } finally {
      saving.value = false;
    }
  }

  async function removeCycle() {
    const cycle = selectedCycle.value;
    if (!cycle || !window.confirm(t("plan.deleteCycleConfirm"))) return;
    saving.value = true;
    clearError();
    try {
      await api.deletePaymentCycle(cycle.id);
      cycles.value = cycles.value.filter((item) => item.id !== cycle.id);
      const preferred = cycles.value.find((item) => item.status === "active") ?? cycles.value[0];
      selectedCycleId.value = preferred?.id ?? null;
      editingCycle.value = false;
      await refreshPlan();
    } catch (caught) {
      setError(caught, t("plan.errors.deleteCycle"));
    } finally {
      saving.value = false;
    }
  }

  return {
    selectedCycle, creatingCycle, editingCycle, cycleForm, cycleEditForm,
    loadCycles, selectCycle, startCycleEdit, startCycleCreate, saveCycle,
    createCycle, removeCycle,
  };
}

