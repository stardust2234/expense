<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";

import type { PaymentCycle } from "../types/api";
import { defaultCurrencyForLocale } from "../utils/currency";
import { formatUkDate } from "../utils/date";
import AllowancesPanel from "./plan/AllowancesPanel.vue";
import { defaultPlanDates, inputDate } from "./plan/calendar";
import CommitmentsPanel from "./plan/CommitmentsPanel.vue";
import InferencePreviewPanel from "./plan/InferencePreviewPanel.vue";
import PaymentCycleSection from "./plan/PaymentCycleSection.vue";
import { usePaymentCycles } from "./plan/usePaymentCycles";
import { usePlanInference } from "./plan/usePlanInference";
import { usePlanItems } from "./plan/usePlanItems";

const { locale, t } = useI18n();
const { calendarStart, benefitDate, firstBillDue } = defaultPlanDates(new Date());
const cycles = ref<PaymentCycle[]>([]);
const selectedCycleId = ref<number | null>(null);
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const clearError = () => { error.value = ""; };
const setError = (caught: unknown, fallback: string) => {
  error.value = caught instanceof Error ? caught.message : fallback;
};

const items = usePlanItems({
  cycles, selectedCycleId, saving, setError, clearError, t,
});
items.setDefaultDueDate(inputDate(firstBillDue));

const paymentCycles = usePaymentCycles({
  cycles,
  selectedCycleId,
  saving,
  initialForm: {
    name: t("plan.defaultCycleName"),
    nextPaymentDate: inputDate(benefitDate),
    expectedIncome: "",
    openingBalance: "",
    currentBalance: "",
    currency: defaultCurrencyForLocale(locale.value),
  },
  refreshPlan: items.loadPlan,
  setDefaultDueDate: items.setDefaultDueDate,
  setError,
  clearError,
  t,
});

const inference = usePlanInference({
  cycleForm: paymentCycles.cycleForm,
  selectedCycleId,
  saving,
  initialTargetMonth: inputDate(calendarStart),
  reloadCycles: paymentCycles.loadCycles,
  reloadPlan: items.loadPlan,
  setError,
  clearError,
  t,
});

watch(locale, (nextLocale, previousLocale) => {
  if (
    !inference.inferencePreview.value
    && !paymentCycles.selectedCycle.value
    && paymentCycles.cycleForm.value.currency === defaultCurrencyForLocale(previousLocale)
  ) {
    paymentCycles.cycleForm.value.currency = defaultCurrencyForLocale(nextLocale);
  }
});

async function load() {
  loading.value = true;
  clearError();
  try {
    await Promise.all([paymentCycles.loadCycles(), items.loadCategories()]);
    await items.loadPlan();
  } catch (caught) {
    setError(caught, t("plan.errors.load"));
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
        <p class="eyebrow">{{ t("plan.eyebrow") }}</p>
        <h2>{{ t("plan.title") }}</h2>
        <p>{{ t("plan.subtitle") }}</p>
      </div>
      <div v-if="cycles.length" class="cycle-actions">
        <label class="field cycle-picker">
          <span>{{ t("common.paymentCycle") }}</span>
          <select v-model="selectedCycleId" @change="paymentCycles.selectCycle">
            <option v-for="cycle in cycles" :key="cycle.id" :value="cycle.id">
              {{ cycle.name || t("common.paymentCycle") }} · {{ formatUkDate(cycle.start_date) }}
            </option>
          </select>
        </label>
        <button class="secondary-button" @click="paymentCycles.startCycleCreate">{{ t("plan.addCycle") }}</button>
      </div>
    </header>

    <p v-if="error" class="message error-message">{{ error }}</p>
    <p v-if="loading" class="panel empty-state">{{ t("plan.loading") }}</p>

    <InferencePreviewPanel
      v-if="!loading"
      v-model:target-month="inference.inferenceTargetMonth.value"
      v-model:selected-incomes="inference.selectedInferenceIncomes.value"
      v-model:selected-commitments="inference.selectedInferenceCommitments.value"
      v-model:selected-allowances="inference.selectedInferenceAllowances.value"
      :preview="inference.inferencePreview.value"
      :impact="inference.inferenceImpact.value"
      :form="paymentCycles.cycleForm.value"
      :saving="saving"
      @preview-plan="inference.previewPlan"
      @confirm="inference.confirmPlan"
      @cancel="inference.inferencePreview.value = null"
    />

    <PaymentCycleSection
      v-model:balance="items.balanceInput.value"
      :loading="loading"
      :cycle="paymentCycles.selectedCycle.value"
      :forecast="items.forecast.value"
      :creating="paymentCycles.creatingCycle.value"
      :editing="paymentCycles.editingCycle.value"
      :saving="saving"
      :form="paymentCycles.cycleForm.value"
      :edit-form="paymentCycles.cycleEditForm.value"
      @create="paymentCycles.createCycle"
      @cancel-create="paymentCycles.creatingCycle.value = false"
      @start-edit="paymentCycles.startCycleEdit"
      @save="paymentCycles.saveCycle"
      @remove="paymentCycles.removeCycle"
      @cancel-edit="paymentCycles.editingCycle.value = false"
      @update-balance="items.updateBalance"
    />

    <div v-if="paymentCycles.selectedCycle.value && items.forecast.value" class="plan-grid">
      <CommitmentsPanel
        :commitments="items.commitments.value"
        :categories="items.categories.value"
        :pending-count="items.pendingCommitments.value.length"
        :editing-id="items.editingCommitmentId.value"
        :saving="saving"
        :form="items.commitmentForm.value"
        :edit-form="items.commitmentEditForm.value"
        @add="items.addCommitment"
        @edit="items.startCommitmentEdit"
        @save="items.saveCommitment"
        @remove="items.removeCommitment"
        @cancel-edit="items.editingCommitmentId.value = null"
      />
      <AllowancesPanel
        :allowances="items.allowances.value"
        :categories="items.categories.value"
        :forecast="items.forecast.value"
        :editing-id="items.editingAllowanceId.value"
        :saving="saving"
        :form="items.allowanceForm.value"
        :edit-form="items.allowanceEditForm.value"
        @add="items.addAllowance"
        @edit="items.startAllowanceEdit"
        @save="items.saveAllowance"
        @remove="items.removeAllowance"
        @cancel-edit="items.editingAllowanceId.value = null"
      />
    </div>
  </section>
</template>

