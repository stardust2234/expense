<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { PaymentCycle, SafeSpendingForecast } from "../../types/api";
import { formatUkDate, inclusiveCycleEnd } from "../../utils/date";

type CycleForm = {
  name: string;
  nextPaymentDate: string;
  expectedIncome: string;
  openingBalance: string;
  currentBalance: string;
  currency: string;
};

type CycleEditForm = CycleForm & { status: PaymentCycle["status"] };

const props = defineProps<{
  loading: boolean;
  cycle: PaymentCycle | null;
  forecast: SafeSpendingForecast | null;
  creating: boolean;
  editing: boolean;
  saving: boolean;
  form: CycleForm;
  editForm: CycleEditForm;
  balance: string;
}>();

const emit = defineEmits<{
  create: [];
  cancelCreate: [];
  startEdit: [];
  save: [];
  remove: [];
  cancelEdit: [];
  updateBalance: [];
  "update:balance": [value: string];
}>();

const { t } = useI18n();
const balanceModel = computed({
  get: () => props.balance,
  set: (value: string) => emit("update:balance", value),
});
</script>

<template>
  <article v-if="!loading && (!cycle || creating)" class="panel setup-panel">
    <div class="panel-title">
      <div><h3>{{ cycle ? t("plan.addPaymentCycle") : t("plan.firstCycle") }}</h3><span>{{ t("plan.poundsNote") }}</span></div>
      <button v-if="cycle" class="text-button" @click="emit('cancelCreate')">{{ t("common.cancel") }}</button>
    </div>
    <form class="cycle-setup-form" @submit.prevent="emit('create')">
      <label class="field"><span>{{ t("common.name") }}</span><input v-model="form.name" required /></label>
      <label class="field"><span>{{ t("plan.benefitDate") }}</span><input v-model="form.nextPaymentDate" type="date" required /></label>
      <label class="field"><span>{{ t("plan.expectedIncome") }}</span><input v-model="form.expectedIncome" type="number" min="0" step="0.01" required /></label>
      <label class="field"><span>{{ t("plan.openingBalance") }}</span><input v-model="form.openingBalance" type="number" step="0.01" required /></label>
      <label class="field"><span>{{ t("plan.usableBalance") }}</span><input v-model="form.currentBalance" type="number" step="0.01" :placeholder="t('plan.sameAsOpening')" /></label>
      <label class="field compact-field"><span>{{ t("common.currency") }}</span><input v-model="form.currency" minlength="3" maxlength="3" required /></label>
      <button class="primary-button" :disabled="saving">{{ t("plan.createCycle") }}</button>
    </form>
  </article>

  <template v-if="cycle && forecast">
    <article class="panel cycle-details">
      <div class="panel-title">
        <div><h3>{{ t("plan.cycleDetails") }}</h3><span>{{ t("plan.cycleDates", { start: formatUkDate(cycle.start_date), end: formatUkDate(inclusiveCycleEnd(cycle.end_date)), payment: formatUkDate(cycle.next_payment_date) }) }}</span></div>
        <div v-if="!editing" class="row-actions"><button class="text-button" @click="emit('startEdit')">{{ t("plan.editCycle") }}</button><button class="text-button danger" @click="emit('remove')">{{ t("plan.deleteCycle") }}</button></div>
      </div>
      <form v-if="editing" class="cycle-setup-form" @submit.prevent="emit('save')">
        <label class="field"><span>{{ t("common.name") }}</span><input v-model="editForm.name" /></label>
        <label class="field"><span>{{ t("plan.benefitDate") }}</span><input v-model="editForm.nextPaymentDate" type="date" required /></label>
        <label class="field"><span>{{ t("plan.expectedIncome") }}</span><input v-model="editForm.expectedIncome" type="number" min="0" step="0.01" required /></label>
        <label class="field"><span>{{ t("plan.openingBalance") }}</span><input v-model="editForm.openingBalance" type="number" step="0.01" required /></label>
        <label class="field"><span>{{ t("plan.usableBalance") }}</span><input v-model="editForm.currentBalance" type="number" step="0.01" /></label>
        <label class="field"><span>{{ t("common.currency") }}</span><input v-model="editForm.currency" minlength="3" maxlength="3" required /></label>
        <label class="field"><span>{{ t("common.status") }}</span><select v-model="editForm.status"><option value="planned">{{ t("common.statuses.planned") }}</option><option value="active">{{ t("common.statuses.active") }}</option><option value="closed">{{ t("common.statuses.closed") }}</option></select></label>
        <div class="form-actions"><button class="primary-button" :disabled="saving">{{ t("plan.saveCycle") }}</button><button class="secondary-button" type="button" @click="emit('cancelEdit')">{{ t("common.cancel") }}</button></div>
      </form>
    </article>

    <article class="panel balance-panel">
      <div><strong>{{ t("plan.forecastTitle") }}</strong><span>{{ t("plan.forecastSource", { source: t(`dashboard.balanceSources.${forecast.balance_source}`) }) }}</span></div>
      <form class="inline-filter" @submit.prevent="emit('updateBalance')">
        <label class="field"><span>{{ t("plan.usableBalance") }}</span><input v-model="balanceModel" type="number" step="0.01" required /></label>
        <button class="secondary-button" :disabled="saving">{{ t("common.update") }}</button>
      </form>
    </article>
  </template>
</template>

