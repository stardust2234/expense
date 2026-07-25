<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { api } from "../api/client";
import type { Category } from "../types/api";

const categories = ref<Category[]>([]);
const name = ref("");
const parentId = ref("");
const error = ref("");
const roots = computed(() => categories.value.filter((category) => !category.parent_category_id));

async function load() {
  categories.value = await api.categories();
}
async function create() {
  try {
    await api.createCategory(name.value, parentId.value ? Number(parentId.value) : null);
    name.value = ""; parentId.value = ""; await load();
  } catch (caught) { error.value = caught instanceof Error ? caught.message : "Could not create category"; }
}
async function save(category: Category) {
  try { await api.updateCategory(category.id, category.name, category.parent_category_id); await load(); }
  catch (caught) { error.value = caught instanceof Error ? caught.message : "Could not update category"; }
}
async function remove(category: Category) {
  if (!window.confirm(`Delete category “${category.name}”?`)) return;
  try { await api.deleteCategory(category.id); await load(); }
  catch (caught) { error.value = caught instanceof Error ? caught.message : "Could not delete category"; }
}
function children(parent: Category) { return categories.value.filter((item) => item.parent_category_id === parent.id); }
onMounted(load);
</script>

<template>
  <section class="view-stack">
    <header class="view-heading"><div><p class="eyebrow">Taxonomy</p><h2>Categories</h2><p>Maintain the hierarchy used in review, rules and reports.</p></div></header>
    <form class="panel merchant-form" @submit.prevent="create">
      <label class="field"><span>Name</span><input v-model="name" maxlength="100" /></label>
      <label class="field"><span>Parent</span><select v-model="parentId"><option value="">Top level</option><option v-for="root in roots" :key="root.id" :value="String(root.id)">{{ root.name }}</option></select></label>
      <button class="primary-button" :disabled="!name.trim()">Add category</button>
    </form>
    <p v-if="error" class="message error-message">{{ error }}</p>
    <div class="category-tree">
      <article v-for="root in roots" :key="root.id" class="panel category-group">
        <div class="category-edit"><input v-model="root.name" /><button class="text-button" @click="save(root)">Save</button><button class="text-button danger" @click="remove(root)">Delete</button></div>
        <div class="child-list">
          <div v-for="child in children(root)" :key="child.id" class="category-edit child-category"><span>↳</span><input v-model="child.name" /><button class="text-button" @click="save(child)">Save</button><button class="text-button danger" @click="remove(child)">Delete</button></div>
        </div>
      </article>
    </div>
  </section>
</template>

