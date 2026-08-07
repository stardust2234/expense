<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";

import LoginButton from "../components/LoginButton.vue";

const { t } = useI18n();
const route = useRoute();
const registering = computed(() => route.name === "register");
const redirectTo = computed(() =>
  typeof route.query.redirect === "string" ? route.query.redirect : "/dashboard",
);
</script>

<template>
  <main class="login-page">
    <section class="login-card">
      <p class="eyebrow">{{ t("auth.eyebrow") }}</p>
      <h1>{{ registering ? t("auth.registerTitle") : t("auth.loginTitle") }}</h1>
      <p>{{ t("auth.auth0Help") }}</p>
      <LoginButton :redirect-to="redirectTo" :signup="registering" />
      <RouterLink class="text-action" :to="registering ? '/login' : '/register'">
        {{ registering ? t("auth.haveAccount") : t("auth.needAccount") }}
      </RouterLink>
    </section>
  </main>
</template>

