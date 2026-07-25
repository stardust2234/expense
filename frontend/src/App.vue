<script setup lang="ts">
import { onMounted, ref } from "vue";

import { api } from "./api/client";

const apiOnline = ref(false);
const healthLabel = ref("Connecting");

const views = [
  { path: "/dashboard", label: "Dashboard", symbol: "⌂" },
  { path: "/imports", label: "Import", symbol: "↑" },
  { path: "/plan", label: "Plan", symbol: "£" },
  { path: "/review", label: "Review", symbol: "✓" },
  { path: "/transactions", label: "Transactions", symbol: "≡" },
  { path: "/rules", label: "Rules", symbol: "⚙" },
  { path: "/merchants", label: "Merchants", symbol: "◎" },
  { path: "/categories", label: "Categories", symbol: "◇" },
  { path: "/reports", label: "Reports", symbol: "▥" },
];

onMounted(async () => {
  try {
    const health = await api.health();
    apiOnline.value = health.status === "ok" && health.database === "ok";
    healthLabel.value = apiOnline.value ? "System ready" : "Service degraded";
  } catch {
    healthLabel.value = "API offline";
  }
});
</script>

<template>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark">F</span>
        <div><strong>Folio</strong><small>Expense desk</small></div>
      </div>

      <nav aria-label="Primary navigation">
        <RouterLink
          v-for="view in views"
          :key="view.path"
          :to="view.path"
        >
          <span>{{ view.symbol }}</span>{{ view.label }}
        </RouterLink>
      </nav>

      <div class="sidebar-status">
        <span :class="{ online: apiOnline }"></span>
        <div><strong>{{ healthLabel }}</strong><small>Local workspace</small></div>
      </div>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div>
          <p>Personal finance workspace</p>
          <h1>Make every transaction explainable.</h1>
        </div>
        <span class="date-label">{{ new Intl.DateTimeFormat("en-GB", { dateStyle: "medium" }).format(new Date()) }}</span>
      </header>

      <RouterView />
    </main>
  </div>
</template>

