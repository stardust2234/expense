<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { api, ApiError } from "../api/client";
import { auth } from "../auth";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const registering = ref(false);
const email = ref("");
const displayName = ref("");
const password = ref("");
const bootstrapRequired = ref(false);
const bootstrapToken = ref("");
const busy = ref(false);
const error = ref("");
const resetMessage = ref("");

async function submit() {
  busy.value = true;
  error.value = "";
  try {
    const session = registering.value
      ? await api.register(
          email.value,
          displayName.value,
          password.value,
          bootstrapRequired.value ? bootstrapToken.value : null,
        )
      : await api.login(email.value, password.value);
    auth.setSession(session.user);
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/dashboard";
    await router.replace(redirect);
  } catch (caught) {
    if (caught instanceof ApiError) {
      const key = caught.status === 401
        ? "invalid"
        : caught.status === 409
          ? "exists"
          : caught.status === 422
            ? "invalidInput"
            : caught.status === 429
              ? "throttled"
              : "unavailable";
      error.value = t(`auth.errors.${key}`);
    } else {
      error.value = t("auth.errors.unavailable");
    }
  } finally {
    busy.value = false;
  }
}

async function requestReset() {
  error.value = "";
  resetMessage.value = "";
  if (!email.value.trim()) {
    error.value = t("auth.errors.emailRequired");
    return;
  }
  busy.value = true;
  try {
    await api.requestPasswordReset(email.value);
    resetMessage.value = t("passwordReset.requested");
  } catch {
    error.value = t("auth.errors.unavailable");
  } finally {
    busy.value = false;
  }
}

onMounted(async () => {
  try {
    bootstrapRequired.value = (await api.bootstrapStatus()).required;
    if (bootstrapRequired.value) registering.value = true;
  } catch {
    // Submission still returns a safe server-side error if setup status is unavailable.
  }
});
</script>

<template>
  <main class="login-page">
    <section class="login-card">
      <p class="eyebrow">{{ t("auth.eyebrow") }}</p>
      <h1>{{ registering ? t("auth.registerTitle") : t("auth.loginTitle") }}</h1>
      <p>{{ t("auth.subtitle") }}</p>
      <form @submit.prevent="submit">
        <label v-if="registering">
          {{ t("auth.displayName") }}
          <input v-model="displayName" required minlength="1" maxlength="100" autocomplete="name" />
        </label>
        <label>
          {{ t("auth.email") }}
          <input v-model="email" required type="email" maxlength="320" autocomplete="email" />
        </label>
        <label v-if="registering && bootstrapRequired">
          {{ t("auth.bootstrapToken") }}
          <input
            v-model="bootstrapToken"
            required
            type="password"
            autocomplete="off"
          />
        </label>
        <p v-if="registering && bootstrapRequired" class="form-help">
          {{ t("auth.bootstrapHelp") }}
        </p>
        <label>
          {{ t("auth.password") }}
          <input
            v-model="password"
            required
            type="password"
            :minlength="registering ? 12 : 1"
            maxlength="128"
            :autocomplete="registering ? 'new-password' : 'current-password'"
          />
        </label>
        <p v-if="registering" class="form-help">{{ t("auth.passwordHelp") }}</p>
        <p v-if="error" class="error-banner" role="alert">{{ error }}</p>
        <p v-if="resetMessage" class="message">{{ resetMessage }}</p>
        <button class="primary-action" :disabled="busy">
          {{ busy ? t("auth.working") : registering ? t("auth.register") : t("auth.login") }}
        </button>
      </form>
      <button v-if="!registering" class="text-action" type="button" @click="requestReset">
        {{ t("passwordReset.forgot") }}
      </button>
      <button class="text-action" type="button" @click="registering = !registering; error = ''">
        {{ registering ? t("auth.haveAccount") : t("auth.needAccount") }}
      </button>
    </section>
  </main>
</template>

