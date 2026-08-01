<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import { api } from "../api/client";
import type { Category, SpendingPriority } from "../types/api";
import { formatCategoryName } from "../utils/category";

const categories = ref<Category[]>([]);
const { t } = useI18n();
const name = ref("");
const parentId = ref("");
const defaultPriority = ref<SpendingPriority>("adjustable");
const error = ref("");
const roots = computed(() => categories.value.filter((category) => !category.parent_category_id));

async function load() {
  try { categories.value = await api.categories(); }
  catch (caught) { error.value = caught instanceof Error ? caught.message : t("views.categoryManager.errors.load"); }
}
async function create() {
  try {
    await api.createCategory(
      name.value,
      parentId.value ? Number(parentId.value) : null,
      defaultPriority.value,
    );
    name.value = ""; parentId.value = ""; await load();
  } catch (caught) { error.value = caught instanceof Error ? caught.message : t("views.categoryManager.errors.create"); }
}
async function save(category: Category) {
  try {
    await api.updateCategory(
      category.id,
      category.name,
      category.parent_category_id,
      category.default_priority,
    );
    await load();
  }
  catch (caught) { error.value = caught instanceof Error ? caught.message : t("views.categoryManager.errors.update"); }
}
async function remove(category: Category) {
  if (!window.confirm(t("views.categoryManager.deleteConfirm", { name: formatCategoryName(category) }))) return;
  try { await api.deleteCategory(category.id); await load(); }
  catch (caught) { error.value = caught instanceof Error ? caught.message : t("views.categoryManager.errors.delete"); }
}
function children(parent: Category) { return categories.value.filter((item) => item.parent_category_id === parent.id); }
onMounted(load);
</script>

<template>
  <section class="view-stack">
    <header class="view-heading"><div><p class="eyebrow">{{ t("views.categoryManager.eyebrow") }}</p><h2>{{ t("views.categoryManager.title") }}</h2><p>{{ t("views.categoryManager.subtitle") }}</p></div></header>
    <form class="panel merchant-form category-create-form" @submit.prevent="create">
      <label class="field"><span>{{ t("common.name") }}</span><input v-model="name" maxlength="100" /></label>
      <label class="field"><span>{{ t("views.categoryManager.parent") }}</span><select v-model="parentId"><option value="">{{ t("views.categoryManager.topLevel") }}</option><option v-for="root in roots" :key="root.id" :value="String(root.id)">{{ formatCategoryName(root) }}</option></select></label>
      <label class="field"><span>{{ t("common.priority") }}</span><select v-model="defaultPriority"><option v-for="priority in ['protected','essential','adjustable','optional','irregular_essential','transfer']" :key="priority" :value="priority">{{ t(`common.priorities.${priority}`) }}</option></select></label>
      <button class="primary-button" :disabled="!name.trim()">{{ t("views.categoryManager.add") }}</button>
    </form>
    <p v-if="error" class="message error-message">{{ error }}</p>
    <div class="category-tree">
      <article v-for="root in roots" :key="root.id" class="panel category-group">
        <div class="category-edit"><input v-if="!root.code" v-model="root.name" /><input v-else :value="formatCategoryName(root)" readonly /><select v-model="root.default_priority" class="table-input"><option v-for="priority in ['protected','essential','adjustable','optional','irregular_essential','transfer']" :key="priority" :value="priority">{{ t(`common.priorities.${priority}`) }}</option></select><button class="text-button" @click="save(root)">{{ t("common.save") }}</button><button class="text-button danger" @click="remove(root)">{{ t("views.categoryManager.delete") }}</button></div>
        <div class="child-list">
          <div v-for="child in children(root)" :key="child.id" class="category-edit child-category"><span>↳</span><input v-if="!child.code" v-model="child.name" /><input v-else :value="formatCategoryName(child)" readonly /><select v-model="child.default_priority" class="table-input"><option v-for="priority in ['protected','essential','adjustable','optional','irregular_essential','transfer']" :key="priority" :value="priority">{{ t(`common.priorities.${priority}`) }}</option></select><button class="text-button" @click="save(child)">{{ t("common.save") }}</button><button class="text-button danger" @click="remove(child)">{{ t("views.categoryManager.delete") }}</button></div>
        </div>
      </article>
    </div>
  </section>
</template>

