<script setup lang="ts">
import { useAuth0 } from "@auth0/auth0-vue";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  ChartNoAxesCombined,
  CircleDollarSign,
  ClipboardCheck,
  FolderTree,
  Gauge,
  Landmark,
  ListFilter,
  UserRound,
  ReceiptText,
  Scale,
  Store,
  Upload,
  WalletCards,
} from "@lucide/vue";

import { api } from "./api/client";
import LogoutButton from "./components/LogoutButton.vue";
import { setAppLocale, type AppLocale } from "./i18n";
import { useRoute } from "vue-router";

const apiOnline = ref(false);
const healthState = ref<"connecting" | "ready" | "degraded" | "offline">("connecting");
const { d, locale, t } = useI18n();
const healthLabel = computed(() => t(`health.${healthState.value}`));
const route = useRoute();
const {
  isAuthenticated,
  isLoading: auth0Loading,
  user,
} = useAuth0();
const isAuthPage = computed(() => route.meta.authLayout === true);
const accountMenuOpen = ref(false);
const accountMenu = ref<HTMLElement | null>(null);

const views = computed(() => [
  { path: "/dashboard", label: t("navigation.dashboard"), icon: Gauge },
  { path: "/imports", label: t("navigation.import"), icon: Upload },
  { path: "/plan", label: t("navigation.plan"), icon: WalletCards },
  { path: "/review", label: t("navigation.review"), icon: ClipboardCheck },
  { path: "/transactions", label: t("navigation.transactions"), icon: ReceiptText },
  { path: "/rules", label: t("navigation.rules"), icon: ListFilter },
  { path: "/merchants", label: t("navigation.merchants"), icon: Store },
  { path: "/categories", label: t("navigation.categories"), icon: FolderTree },
  { path: "/reports", label: t("navigation.reports"), icon: ChartNoAxesCombined },
]);

function toggleLocale() {
  setAppLocale((locale.value === "en" ? "fr" : "en") as AppLocale);
}

function closeAccountMenu(event?: MouseEvent) {
  if (event && accountMenu.value?.contains(event.target as Node)) return;
  accountMenuOpen.value = false;
}

onMounted(async () => {
  document.addEventListener("click", closeAccountMenu);
  try {
    const health = await api.health();
    apiOnline.value = health.status === "ok" && health.database === "ok";
    healthState.value = apiOnline.value ? "ready" : "degraded";
  } catch {
    healthState.value = "offline";
  }
});

onBeforeUnmount(() => document.removeEventListener("click", closeAccountMenu));
</script>

<template>
  <RouterView v-if="isAuthPage" />

  <main v-else-if="auth0Loading" class="login-page" aria-live="polite">
    <section class="login-card"><p>{{ t("auth.loading") }}</p></section>
  </main>

  <div v-else-if="isAuthenticated && user" class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-mark"><Landmark :size="21" :stroke-width="1.5" /></span>
        <div><strong>Folio</strong><small>{{ t("app.brandSubtitle") }}</small></div>
      </div>

      <nav :aria-label="t('navigation.primary')">
        <RouterLink
          v-for="view in views"
          :key="view.path"
          :to="view.path"
        >
          <component :is="view.icon" :size="20" :stroke-width="1.5" />{{ view.label }}
        </RouterLink>
      </nav>

      <div class="sidebar-status">
        <span :class="{ online: apiOnline }"></span>
        <div><strong>{{ healthLabel }}</strong><small>{{ t("app.localWorkspace") }}</small></div>
      </div>
    </aside>

    <main class="workspace">
      <header class="topbar">
        <div>
          <p><CircleDollarSign :size="15" :stroke-width="1.5" /> {{ t("app.workspace") }}</p>
          <h1>{{ t("app.tagline") }}</h1>
        </div>
        <div class="topbar-tools">
          <span class="date-label"><Scale :size="15" :stroke-width="1.5" /> {{ d(new Date(), "medium") }}</span>
          <div ref="accountMenu" class="account-menu">
            <button
              class="icon-action account-trigger"
              type="button"
              :aria-label="t('auth.account')"
              :aria-expanded="accountMenuOpen"
              aria-haspopup="menu"
              @click.stop="accountMenuOpen = !accountMenuOpen"
            >
              <UserRound :size="19" :stroke-width="1.5" />
            </button>
            <div v-if="accountMenuOpen" class="account-dropdown" role="menu">
              <p class="account-identity">{{ user.email }}</p>
              <RouterLink to="/account" role="menuitem" @click="accountMenuOpen = false">
                <UserRound :size="17" :stroke-width="1.5" /> {{ t("account.profile") }}
              </RouterLink>
              <button type="button" role="menuitem" @click="toggleLocale">
                <span class="locale-switch">{{ locale === "en" ? "ENG" : "FR" }}</span>
                {{ locale === "en" ? "FR" : "ENG" }}
              </button>
              <LogoutButton
                class="logout-menu-item"
                role="menuitem"
                @logout-started="accountMenuOpen = false"
              />
            </div>
          </div>
        </div>
      </header>

      <RouterView />
    </main>
  </div>

  <main v-else class="login-page">
    <section class="login-card">
      <p>{{ t("auth.auth0Help") }}</p>
      <RouterLink class="primary-action" to="/login">{{ t("auth.login") }}</RouterLink>
    </section>
  </main>
</template>

