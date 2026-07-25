<script setup lang="ts">
import { onMounted, ref } from "vue";

import { api } from "../api/client";
import type { Category, Rule } from "../types/api";

const rules = ref<Rule[]>([]);
const categories = ref<Category[]>([]);
const error = ref("");

async function load() {
  try {
    [rules.value, categories.value] = await Promise.all([api.rules(), api.categories()]);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : "Could not load rules";
  }
}

async function save(rule: Rule) {
  await api.updateRule(rule.id, {
    match_pattern: rule.match_pattern,
    category_id: rule.category_id,
    priority: Number(rule.priority),
    enabled: rule.enabled,
  });
  await load();
}

async function remove(rule: Rule) {
  if (!window.confirm(`Delete rule “${rule.match_pattern}”?`)) return;
  await api.deleteRule(rule.id);
  await load();
}

onMounted(load);
</script>

<template>
  <section class="view-stack">
    <header class="view-heading"><div><p class="eyebrow">Automation</p><h2>Rules</h2><p>Higher-priority patterns are evaluated first.</p></div></header>
    <p v-if="error" class="message error-message">{{ error }}</p>
    <div class="panel table-wrap">
      <table>
        <thead><tr><th>Pattern</th><th>Category</th><th>Priority</th><th>Matches</th><th>Enabled</th><th></th></tr></thead>
        <tbody>
          <tr v-for="rule in rules" :key="rule.id">
            <td><input v-model="rule.match_pattern" class="table-input" /></td>
            <td><select v-model="rule.category_id" class="table-input"><option v-for="category in categories" :key="category.id" :value="category.id">{{ category.name }}</option></select></td>
            <td><input v-model.number="rule.priority" class="table-input priority-input" type="number" /></td>
            <td>{{ rule.match_count }}</td><td><input v-model="rule.enabled" type="checkbox" /></td>
            <td class="row-actions"><button class="text-button" @click="save(rule)">Save</button><button class="text-button danger" @click="remove(rule)">Delete</button></td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

