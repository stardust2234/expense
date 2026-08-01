<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { api } from "../api/client";
import { auth } from "../auth";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const state = ref(t("verification.instructions"));
const busy = ref(false);

async function verify(token: string) {
  busy.value = true;
  try {
    await api.verifyEmail(token);
    await auth.refreshSession();
    state.value = t("verification.verified");
    window.setTimeout(() => void router.replace("/dashboard"), 600);
  } catch {
    state.value = t("verification.invalid");
  } finally {
    busy.value = false;
  }
}

async function resend() {
  busy.value = true;
  try {
    const result = await api.resendVerification();
    if (result.development_token) {
      await verify(result.development_token);
    } else {
      state.value = t("verification.sent");
    }
  } catch {
    state.value = t("verification.sendError");
  } finally {
    busy.value = false;
  }
}

onMounted(() => {
  const token = String(route.query.token || "");
  if (token) void verify(token);
});
</script>

<template>
  <main class="login-page">
    <section class="login-card">
      <h1>{{ t("verification.title") }}</h1>
      <p>{{ state }}</p>
      <button class="primary-action" :disabled="busy" @click="resend">
        {{ busy ? t("auth.working") : t("verification.send") }}
      </button>
    </section>
  </main>
</template>

