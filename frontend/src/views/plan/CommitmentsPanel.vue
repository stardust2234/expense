<script setup lang="ts">
import { useI18n } from "vue-i18n";

import type { Category, Commitment, SpendingPriority } from "../../types/api";
import { formatCategoryName } from "../../utils/category";
import { formatUkDate } from "../../utils/date";
import { formatMoney } from "../../utils/money";

type CommitmentForm = {
  name: string;
  amount: string;
  dueDate: string;
  priority: SpendingPriority;
  categoryId: string;
};

type CommitmentEditForm = CommitmentForm & {
  status: Commitment["status"];
  recurrence: string;
};

defineProps<{
  commitments: Commitment[];
  categories: Category[];
  pendingCount: number;
  editingId: number | null;
  saving: boolean;
  form: CommitmentForm;
  editForm: CommitmentEditForm;
}>();

const emit = defineEmits<{
  add: [];
  edit: [item: Commitment];
  save: [item: Commitment];
  remove: [id: number];
  cancelEdit: [];
}>();

const { t } = useI18n();
const priorities: SpendingPriority[] = ["protected", "essential", "adjustable", "optional"];
const statuses: Commitment["status"][] = ["pending", "paid", "skipped"];
</script>

<template>
  <article class="panel">
    <div class="panel-title"><h3>{{ t("plan.billsTitle") }}</h3><span>{{ t("plan.pendingCount", { count: pendingCount }) }}</span></div>
    <div v-if="!commitments.length" class="table-empty">{{ t("plan.noBills") }}</div>
    <div v-else class="plan-list">
      <div v-for="item in commitments" :key="item.id" class="plan-row-wrap">
        <form v-if="editingId === item.id" class="plan-edit-form" @submit.prevent="emit('save', item)">
          <label class="field"><span>{{ t("plan.bill") }}</span><input v-model="editForm.name" required /></label>
          <label class="field"><span>{{ t("common.amount") }}</span><input v-model="editForm.amount" type="number" min="0" step="0.01" required /></label>
          <label class="field"><span>{{ t("plan.due") }}</span><input v-model="editForm.dueDate" type="date" required /></label>
          <label class="field"><span>{{ t("common.priority") }}</span><select v-model="editForm.priority"><option v-for="value in priorities" :key="value" :value="value">{{ t(`common.priorities.${value}`) }}</option></select></label>
          <label class="field"><span>{{ t("common.status") }}</span><select v-model="editForm.status"><option v-for="value in statuses" :key="value" :value="value">{{ t(`common.statuses.${value}`) }}</option></select></label>
          <label class="field"><span>{{ t("plan.recurrence") }}</span><input v-model="editForm.recurrence" :placeholder="t('plan.recurrencePlaceholder')" /></label>
          <label class="field"><span>{{ t("common.category") }}</span><select v-model="editForm.categoryId"><option value="">{{ t("common.none") }}</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ formatCategoryName(category) }}</option></select></label>
          <div class="form-actions"><button class="primary-button" :disabled="saving">{{ t("common.save") }}</button><button class="secondary-button" type="button" @click="emit('cancelEdit')">{{ t("common.cancel") }}</button></div>
        </form>
        <div v-else class="plan-row">
          <div><strong>{{ item.name }}</strong><span>{{ formatUkDate(item.due_date) }} · {{ t(`common.priorities.${item.priority}`) }} · {{ t(`common.statuses.${item.status}`) }}</span><span>{{ t("plan.fundedFrom", { date: formatUkDate(item.funding_payment_date) }) }}</span></div>
          <strong>{{ formatMoney(item.amount, item.currency) }}</strong>
          <div class="row-actions"><button class="text-button" @click="emit('edit', item)">{{ t("common.edit") }}</button><button class="text-button danger" :aria-label="t('plan.deleteBill')" @click="emit('remove', item.id)">{{ t("common.remove") }}</button></div>
        </div>
      </div>
    </div>
    <form class="plan-form" @submit.prevent="emit('add')">
      <label class="field"><span>{{ t("plan.bill") }}</span><input v-model="form.name" required /></label>
      <label class="field"><span>{{ t("common.amount") }}</span><input v-model="form.amount" type="number" min="0" step="0.01" required /></label>
      <label class="field"><span>{{ t("plan.due") }}</span><input v-model="form.dueDate" type="date" required /></label>
      <label class="field"><span>{{ t("common.priority") }}</span><select v-model="form.priority"><option v-for="value in priorities" :key="value" :value="value">{{ t(`common.priorities.${value}`) }}</option></select></label>
      <label class="field"><span>{{ t("common.category") }}</span><select v-model="form.categoryId"><option value="">{{ t("common.none") }}</option><option v-for="category in categories" :key="category.id" :value="category.id">{{ formatCategoryName(category) }}</option></select></label>
      <button class="primary-button" :disabled="saving">{{ t("plan.addBill") }}</button>
    </form>
  </article>
</template>

