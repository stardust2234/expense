<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";

import type { AllowanceType, Category, CycleAllowance, SafeSpendingForecast, SpendingPriority } from "../../types/api";
import { formatCategoryName } from "../../utils/category";
import { formatMoney } from "../../utils/money";

type AllowanceForm = {
  name: string;
  amount: string;
  allowanceType: AllowanceType;
  priority: SpendingPriority;
  categoryId: string;
};

const props = defineProps<{
  allowances: CycleAllowance[];
  categories: Category[];
  forecast: SafeSpendingForecast;
  editingId: number | null;
  saving: boolean;
  form: AllowanceForm;
  editForm: AllowanceForm;
}>();

const emit = defineEmits<{
  add: [];
  edit: [item: CycleAllowance];
  save: [item: CycleAllowance];
  remove: [id: number];
  cancelEdit: [];
}>();

const { t } = useI18n();
const priorities: SpendingPriority[] = ["protected", "essential", "adjustable", "irregular_essential", "optional"];
const types: AllowanceType[] = ["food", "transport", "irregular_cost", "emergency", "custom"];
const rows = computed(() => {
  const usageById = new Map(props.forecast.allowances.map((item) => [item.id, item]));
  return props.allowances.map((item) => {
    const usage = usageById.get(item.id) ?? null;
    const percentage = usage && item.amount
      ? Math.min(100, usage.spent_amount / item.amount * 100)
      : 0;
    return { item, usage, percentage };
  });
});
</script>

<template>
  <article class="panel">
    <div class="panel-title"><h3>{{ t("plan.allowancesTitle") }}</h3><span>{{ t("plan.plannedCount", { count: allowances.length }) }}</span></div>
    <div v-if="!allowances.length" class="table-empty">{{ t("plan.noAllowances") }}</div>
    <div v-else class="plan-list">
      <div v-for="{ item, usage, percentage } in rows" :key="item.id" class="allowance-row">
        <form v-if="editingId === item.id" class="plan-edit-form" @submit.prevent="emit('save', item)">
          <label class="field"><span>{{ t("plan.allowance") }}</span><input v-model="editForm.name" required /></label>
          <label class="field"><span>{{ t("common.amount") }}</span><input v-model="editForm.amount" type="number" min="0" step="0.01" required /></label>
          <label class="field"><span>{{ t("plan.type") }}</span><select v-model="editForm.allowanceType"><option v-for="value in types" :key="value" :value="value">{{ t(`common.allowanceTypes.${value}`) }}</option></select></label>
          <label class="field"><span>{{ t("common.priority") }}</span><select v-model="editForm.priority"><option v-for="value in priorities" :key="value" :value="value">{{ t(`common.priorities.${value}`) }}</option></select></label>
          <label class="field"><span>{{ t("common.category") }}</span><select v-model="editForm.categoryId"><option value="">{{ t("plan.reserveOnly") }}</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ formatCategoryName(category) }}</option></select></label>
          <div class="form-actions"><button class="primary-button" :disabled="saving">{{ t("common.save") }}</button><button class="secondary-button" type="button" @click="emit('cancelEdit')">{{ t("common.cancel") }}</button></div>
        </form>
        <template v-else>
          <div class="allowance-heading"><div><strong>{{ item.name }}</strong><span>{{ t(`common.allowanceTypes.${item.allowance_type}`) }} · {{ t(`common.priorities.${item.priority}`) }}</span></div><strong>{{ formatMoney(item.amount, forecast.currency) }}</strong></div>
          <template v-if="usage">
            <div class="allowance-track"><span :style="{ width: `${percentage}%` }"></span></div>
            <div class="allowance-foot"><span>{{ t("plan.spentLeft", { spent: formatMoney(usage.spent_amount, forecast.currency), left: formatMoney(usage.remaining_amount, forecast.currency) }) }}</span><div class="row-actions"><button class="text-button" @click="emit('edit', item)">{{ t("common.edit") }}</button><button class="text-button danger" @click="emit('remove', item.id)">{{ t("common.remove") }}</button></div></div>
          </template>
          <div v-else class="allowance-foot"><span>{{ item.category_id ? t("plan.linkedCategory") : t("plan.reserveOnly") }}</span><div class="row-actions"><button class="text-button" @click="emit('edit', item)">{{ t("common.edit") }}</button><button class="text-button danger" @click="emit('remove', item.id)">{{ t("common.remove") }}</button></div></div>
        </template>
      </div>
    </div>
    <form class="plan-form" @submit.prevent="emit('add')">
      <label class="field"><span>{{ t("plan.allowance") }}</span><input v-model="form.name" required /></label>
      <label class="field"><span>{{ t("common.amount") }}</span><input v-model="form.amount" type="number" min="0" step="0.01" required /></label>
      <label class="field"><span>{{ t("plan.type") }}</span><select v-model="form.allowanceType"><option v-for="value in types" :key="value" :value="value">{{ t(`common.allowanceTypes.${value}`) }}</option></select></label>
      <label class="field"><span>{{ t("common.priority") }}</span><select v-model="form.priority"><option v-for="value in priorities" :key="value" :value="value">{{ t(`common.priorities.${value}`) }}</option></select></label>
      <label class="field"><span>{{ t("common.category") }}</span><select v-model="form.categoryId"><option value="">{{ t("plan.reserveOnly") }}</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ formatCategoryName(category) }}</option></select></label>
      <button class="primary-button" :disabled="saving">{{ t("plan.addAllowance") }}</button>
    </form>
  </article>
</template>

