<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { PlanInferencePreview } from "../../types/api";
import { formatUkDate } from "../../utils/date";
import { formatMoney } from "../../utils/money";

type InferenceForm = {
  currency: string;
  openingBalance: string;
  currentBalance: string;
};

type InferenceImpact = {
  income: number;
  bills: number;
  essentials: number;
  projected: number;
  safeWeekly: number;
};

const props = defineProps<{
  preview: PlanInferencePreview | null;
  impact: InferenceImpact | null;
  targetMonth: string;
  selectedIncomes: string[];
  selectedCommitments: string[];
  selectedAllowances: string[];
  form: InferenceForm;
  saving: boolean;
}>();

const emit = defineEmits<{
  previewPlan: [];
  confirm: [];
  cancel: [];
  "update:targetMonth": [value: string];
  "update:selectedIncomes": [value: string[]];
  "update:selectedCommitments": [value: string[]];
  "update:selectedAllowances": [value: string[]];
}>();

const { t } = useI18n();
const targetMonthModel = computed({
  get: () => props.targetMonth,
  set: (value: string) => emit("update:targetMonth", value),
});
const incomeSelection = computed({
  get: () => props.selectedIncomes,
  set: (value: string[]) => emit("update:selectedIncomes", value),
});
const commitmentSelection = computed({
  get: () => props.selectedCommitments,
  set: (value: string[]) => emit("update:selectedCommitments", value),
});
const allowanceSelection = computed({
  get: () => props.selectedAllowances,
  set: (value: string[]) => emit("update:selectedAllowances", value),
});
</script>

<template>
  <article class="panel setup-panel">
    <div class="panel-title"><div><h3>{{ t("plan.inferTitle") }}</h3><span>{{ t("plan.inferNote") }}</span></div></div>
    <form class="cycle-setup-form" @submit.prevent="emit('previewPlan')">
      <label class="field"><span>{{ t("plan.planMonth") }}</span><input v-model="targetMonthModel" type="date" required /></label>
      <label class="field compact-field"><span>{{ t("common.currency") }}</span><input v-model="form.currency" minlength="3" maxlength="3" required /></label>
      <button class="secondary-button" :disabled="saving">{{ t("plan.preview") }}</button>
    </form>
    <div v-if="preview" class="plan-list inference-preview">
      <label v-for="item in preview.incomes" :key="item.proposal_id" class="plan-row">
        <span><input v-model="incomeSelection" type="checkbox" :value="item.proposal_id" /> <strong>{{ item.description }}</strong><br /><small>{{ formatUkDate(item.payment_date) }} · {{ Math.round(item.confidence * 100) }}% · {{ t(`plan.proposalStates.${item.state}`) }}<template v-if="item.date_adjusted"> · {{ t("plan.bankingDayAdjusted", { date: formatUkDate(item.nominal_payment_date) }) }}</template></small></span>
        <strong>{{ formatMoney(item.expected_amount, preview.currency) }}</strong>
      </label>
      <label v-for="item in preview.commitments" :key="item.proposal_id" class="plan-row">
        <span><input v-model="commitmentSelection" type="checkbox" :value="item.proposal_id" /> <strong>{{ item.name }}</strong><br /><small>{{ item.category_name }} · {{ formatUkDate(item.due_date) }} · {{ Math.round(item.confidence * 100) }}% · {{ t(`plan.proposalStates.${item.state}`) }}</small></span>
        <strong>{{ formatMoney(item.amount, preview.currency) }}</strong>
      </label>
      <label v-for="item in preview.allowances" :key="item.proposal_id" class="plan-row">
        <span><input v-model="allowanceSelection" type="checkbox" :value="item.proposal_id" /> <strong>{{ t("plan.allowanceSuffix", { name: item.name }) }}</strong><br /><small>{{ t("plan.evidenceMonths", { count: item.months_observed }) }} · {{ t(`plan.proposalStates.${item.state}`) }}</small></span>
        <strong>{{ formatMoney(item.amount, preview.currency) }}</strong>
      </label>
      <div class="cycle-setup-form inference-balances">
        <label class="field"><span>{{ t("plan.openingBalance") }}</span><input v-model="form.openingBalance" type="number" step="0.01" required /></label>
        <label class="field"><span>{{ t("plan.currentBalance") }}</span><input v-model="form.currentBalance" type="number" step="0.01" /></label>
      </div>
      <div v-if="impact" class="forecast-grid inference-impact">
        <article><span>{{ t("plan.impactIncome") }}</span><strong>{{ formatMoney(impact.income, preview.currency) }}</strong></article>
        <article><span>{{ t("plan.impactBills") }}</span><strong>{{ formatMoney(impact.bills, preview.currency) }}</strong></article>
        <article><span>{{ t("plan.impactEssentials") }}</span><strong>{{ formatMoney(impact.essentials, preview.currency) }}</strong></article>
        <article><span>{{ t("plan.predictedEnd") }}</span><strong>{{ formatMoney(impact.projected, preview.currency) }}</strong></article>
        <article><span>{{ t("plan.safeWeekly") }}</span><strong>{{ formatMoney(Math.round(impact.safeWeekly), preview.currency) }}</strong></article>
      </div>
      <div class="form-actions"><button class="primary-button" type="button" :disabled="saving || !form.openingBalance || !selectedIncomes.length" @click="emit('confirm')">{{ t("plan.confirmPlan") }}</button><button class="secondary-button" type="button" @click="emit('cancel')">{{ t("plan.cancelPreview") }}</button></div>
    </div>
  </article>
</template>

