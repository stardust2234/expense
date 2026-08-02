import { computed, ref, type Ref } from "vue";

import { api } from "../../api/client";
import type { PlanInferencePreview } from "../../types/api";
import { toMajorUnits, toMinorUnits } from "../../utils/money";

type Translate = (key: string) => string;

export function usePlanInference(options: {
  cycleForm: Ref<{
    nextPaymentDate: string; expectedIncome: string; openingBalance: string;
    currentBalance: string; currency: string;
  }>;
  selectedCycleId: Ref<number | null>;
  saving: Ref<boolean>;
  initialTargetMonth: string;
  reloadCycles: () => Promise<void>;
  reloadPlan: () => Promise<void>;
  setError: (caught: unknown, fallback: string) => void;
  clearError: () => void;
  t: Translate;
}) {
  const { cycleForm, selectedCycleId, saving, reloadCycles, reloadPlan, setError, clearError, t } = options;
  const inferencePreview = ref<PlanInferencePreview | null>(null);
  const inferenceTargetMonth = ref(options.initialTargetMonth);
  const selectedInferenceIncomes = ref<string[]>([]);
  const selectedInferenceCommitments = ref<string[]>([]);
  const selectedInferenceAllowances = ref<string[]>([]);

  const inferenceImpact = computed(() => {
    const preview = inferencePreview.value;
    if (!preview) return null;
    const income = preview.incomes
      .filter((item) => selectedInferenceIncomes.value.includes(item.proposal_id))
      .reduce((total, item) => total + item.expected_amount, 0);
    const bills = preview.commitments
      .filter((item) => selectedInferenceCommitments.value.includes(item.proposal_id))
      .reduce((total, item) => total + item.amount, 0);
    const essentials = preview.allowances
      .filter((item) => selectedInferenceAllowances.value.includes(item.proposal_id))
      .reduce((total, item) => total + item.amount, 0);
    const balanceText = cycleForm.value.currentBalance || cycleForm.value.openingBalance;
    const balance = balanceText ? toMinorUnits(Number(balanceText), preview.currency) : 0;
    const selectedIncomeRows = preview.incomes.filter((item) =>
      selectedInferenceIncomes.value.includes(item.proposal_id),
    );
    const firstIncomeDate = selectedIncomeRows.map((item) => item.payment_date).sort()[0] ?? preview.end_date;
    const billsBeforeIncome = preview.commitments
      .filter((item) => selectedInferenceCommitments.value.includes(item.proposal_id) && item.due_date < firstIncomeDate)
      .reduce((total, item) => total + item.amount, 0);
    const daysBeforeIncome = Math.max(1, Math.round(
      (new Date(firstIncomeDate).getTime() - new Date(preview.target_month).getTime()) / 86_400_000,
    ));
    const safeBeforeIncome = Math.max(balance - billsBeforeIncome - essentials, 0);
    return {
      income,
      bills,
      essentials,
      projected: balance + income - bills - essentials,
      safeWeekly: safeBeforeIncome * 7 / daysBeforeIncome,
    };
  });

  async function previewPlan() {
    saving.value = true;
    clearError();
    try {
      const preview = await api.previewPlan(inferenceTargetMonth.value, cycleForm.value.currency);
      inferencePreview.value = preview;
      const selected = <T extends { proposal_id: string; confidence: number; state: string }>(items: T[]) =>
        items.filter((item) => item.confidence >= 0.8 && item.state !== "changed").map((item) => item.proposal_id);
      selectedInferenceIncomes.value = selected(preview.incomes);
      selectedInferenceCommitments.value = selected(preview.commitments);
      selectedInferenceAllowances.value = selected(preview.allowances);
      const primaryIncome = preview.incomes.find((item) =>
        selectedInferenceIncomes.value.includes(item.proposal_id),
      ) ?? preview.incomes[0];
      cycleForm.value.nextPaymentDate = primaryIncome?.payment_date ?? preview.target_month;
      cycleForm.value.expectedIncome = primaryIncome
        ? String(toMajorUnits(preview.impact.expected_income, preview.currency)) : "";
      cycleForm.value.currency = preview.currency;
    } catch (caught) {
      setError(caught, t("plan.errors.infer"));
    } finally {
      saving.value = false;
    }
  }

  async function confirmPlan() {
    const preview = inferencePreview.value;
    if (!preview) return;
    saving.value = true;
    clearError();
    try {
      const result = await api.confirmPlan({
        target_month: preview.target_month,
        currency: preview.currency,
        opening_balance: toMinorUnits(Number(cycleForm.value.openingBalance), preview.currency),
        current_balance: cycleForm.value.currentBalance
          ? toMinorUnits(Number(cycleForm.value.currentBalance), preview.currency) : null,
        income_proposal_ids: selectedInferenceIncomes.value,
        commitment_proposal_ids: selectedInferenceCommitments.value,
        allowance_proposal_ids: selectedInferenceAllowances.value,
      });
      inferencePreview.value = null;
      await reloadCycles();
      selectedCycleId.value = result.payment_cycle_id;
      await reloadPlan();
    } catch (caught) {
      setError(caught, t("plan.errors.confirm"));
    } finally {
      saving.value = false;
    }
  }

  return {
    inferencePreview, inferenceTargetMonth, selectedInferenceIncomes,
    selectedInferenceCommitments, selectedInferenceAllowances, inferenceImpact,
    previewPlan, confirmPlan,
  };
}

