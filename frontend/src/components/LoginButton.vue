<script setup lang="ts">
import { useAuth0 } from "@auth0/auth0-vue";
import { useI18n } from "vue-i18n";

const props = withDefaults(
  defineProps<{
    redirectTo?: string;
    signup?: boolean;
  }>(),
  { redirectTo: "/dashboard", signup: false },
);

const { t } = useI18n();
const { error, loginWithRedirect, isLoading } = useAuth0();

async function handleLogin() {
  await loginWithRedirect({
    appState: { target: props.redirectTo },
    authorizationParams: props.signup ? { screen_hint: "signup" } : undefined,
  });
}
</script>

<template>
  <p v-if="error" class="error-banner" role="alert">{{ t("auth.errors.unavailable") }}</p>
  <button class="primary-action" type="button" :disabled="isLoading" @click="handleLogin">
    {{ isLoading ? t("auth.working") : signup ? t("auth.register") : t("auth.login") }}
  </button>
</template>

