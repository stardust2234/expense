<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";

import { api } from "../api/client";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const password = ref("");
const message = ref("");
const busy = ref(false);

async function submit() {
  busy.value = true;
  try {
    await api.resetPassword(String(route.query.token || ""), password.value);
    message.value = t("passwordReset.changed");
  } catch {
    message.value = t("passwordReset.invalid");
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <main class="login-page">
    <section class="login-card">
      <h1>{{ t("passwordReset.title") }}</h1>
      <form @submit.prevent="submit">
        <label>
          {{ t("passwordReset.newPassword") }}
          <input v-model="password" type="password" minlength="12" maxlength="128" required autocomplete="new-password" />
        </label>
        <button class="primary-action" :disabled="busy">
          {{ busy ? t("auth.working") : t("passwordReset.change") }}
        </button>
      </form>
      <p v-if="message">{{ message }}</p>
      <button class="text-action" type="button" @click="router.push('/login')">
        {{ t("passwordReset.back") }}
      </button>
    </section>
  </main>
</template>

