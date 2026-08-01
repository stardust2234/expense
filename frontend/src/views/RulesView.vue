<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import { api } from "../api/client";
import type { Category, Rule } from "../types/api";
import { formatCategoryName } from "../utils/category";

const rules = ref<Rule[]>([]);
const { t } = useI18n();
const categories = ref<Category[]>([]);
const error = ref("");

async function load() {
  try {
    [rules.value, categories.value] = await Promise.all([api.rules(), api.categories()]);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.rules.errors.load");
  }
}

async function save(rule: Rule) {
  try { await api.updateRule(rule.id, {
    match_pattern: rule.match_pattern,
    category_id: rule.category_id,
    priority: Number(rule.priority),
    enabled: rule.enabled,
  }); await load(); } catch (caught) { error.value = caught instanceof Error ? caught.message : t("views.rules.errors.save"); }
}

async function remove(rule: Rule) {
  if (!window.confirm(t("views.rules.deleteConfirm", { pattern: rule.match_pattern }))) return;
  try { await api.deleteRule(rule.id); await load(); } catch (caught) { error.value = caught instanceof Error ? caught.message : t("views.rules.errors.delete"); }
}

onMounted(load);
</script>

<template>
  <section class="view-stack">
    <header class="view-heading"><div><p class="eyebrow">{{ t("views.rules.eyebrow") }}</p><h2>{{ t("views.rules.title") }}</h2><p>{{ t("views.rules.subtitle") }}</p></div></header>
    <p v-if="error" class="message error-message">{{ error }}</p>
    <div class="panel table-wrap">
      <table>
        <thead><tr><th>{{ t("views.rules.pattern") }}</th><th>{{ t("common.category") }}</th><th>{{ t("common.priority") }}</th><th>{{ t("views.rules.matches") }}</th><th>{{ t("views.rules.enabled") }}</th><th></th></tr></thead>
        <tbody>
          <tr v-for="rule in rules" :key="rule.id">
            <td><input v-model="rule.match_pattern" class="table-input" /></td>
            <td><select v-model="rule.category_id" class="table-input"><option v-for="category in categories" :key="category.id" :value="category.id">{{ formatCategoryName(category) }}</option></select></td>
            <td><input v-model.number="rule.priority" class="table-input priority-input" type="number" /></td>
            <td>{{ rule.match_count }}</td><td><input v-model="rule.enabled" type="checkbox" /></td>
            <td class="row-actions"><button class="text-button" @click="save(rule)">{{ t("common.save") }}</button><button class="text-button danger" @click="remove(rule)">{{ t("views.rules.delete") }}</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

