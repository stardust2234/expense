<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";

import { api, ApiError } from "../api/client";
import { auth } from "../auth";

const { t } = useI18n();
const router = useRouter();
const currentUser = computed(() => auth.user.value);
const currentPassword = ref("");
const newPassword = ref("");
const message = ref("");
const error = ref("");
const busy = ref(false);
const email = ref("");
const emailPassword = ref("");
const emailBusy = ref(false);
const showDeleteAccount = ref(false);
const deletePassword = ref("");
const deleteConfirmation = ref("");
const deleteBusy = ref(false);
type AuditEvent = Awaited<ReturnType<typeof api.accountAudit>>[number];
const auditEvents = ref<AuditEvent[]>([]);

function errorMessage(caught: unknown): string {
  return caught instanceof ApiError ? caught.message : t("account.error");
}

async function changePassword() {
  busy.value = true;
  message.value = "";
  error.value = "";
  try {
    await api.changePassword(currentPassword.value, newPassword.value);
    message.value = t("account.passwordChanged");
    currentPassword.value = "";
    newPassword.value = "";
  } catch (caught) {
    error.value = errorMessage(caught);
  } finally {
    busy.value = false;
  }
}

async function changeEmail() {
  emailBusy.value = true;
  error.value = "";
  message.value = "";
  try {
    const result = await api.changeEmail(email.value, emailPassword.value);
    await router.push({
      name: "verify-email",
      query: result.development_token ? { token: result.development_token } : undefined,
    });
  } catch (caught) {
    error.value = errorMessage(caught);
  } finally {
    emailBusy.value = false;
  }
}

async function deleteAccount() {
  deleteBusy.value = true;
  error.value = "";
  try {
    await auth.deleteAccount(deletePassword.value, deleteConfirmation.value);
    await router.replace("/login");
  } catch (caught) {
    error.value = errorMessage(caught);
  } finally {
    deleteBusy.value = false;
  }
}

async function loadAuditEvents() {
  try {
    auditEvents.value = await api.accountAudit();
  } catch (caught) {
    error.value = errorMessage(caught);
  }
}

onMounted(() => {
  email.value = currentUser.value?.email ?? "";
  void loadAuditEvents();
});
</script>

<template>
  <section class="view-stack">
    <header class="view-heading">
      <div>
        <p class="eyebrow">{{ t("account.eyebrow") }}</p>
        <h2>{{ t("account.title") }}</h2>
        <p>{{ currentUser?.display_name }} · {{ currentUser?.email }}</p>
      </div>
    </header>

    <p v-if="error" class="message error-message">{{ error }}</p>

    <article class="panel account-panel">
      <h3>{{ t("account.security") }}</h3>
      <p class="account-status">
        {{ currentUser?.email_verified ? t("account.verified") : t("account.unverified") }}
      </p>
      <form class="account-form" @submit.prevent="changePassword">
        <label class="field">
          <span>{{ t("account.currentPassword") }}</span>
          <input v-model="currentPassword" type="password" required autocomplete="current-password" />
        </label>
        <label class="field">
          <span>{{ t("account.newPassword") }}</span>
          <input v-model="newPassword" type="password" minlength="12" required autocomplete="new-password" />
        </label>
        <button class="primary-button" :disabled="busy">
          {{ busy ? t("auth.working") : t("account.changePassword") }}
        </button>
      </form>
      <p v-if="message" class="message">{{ message }}</p>
    </article>

    <article class="panel account-panel">
      <h3>{{ t("account.emailTitle") }}</h3>
      <p class="account-status">{{ t("account.emailHelp") }}</p>
      <form class="account-form" @submit.prevent="changeEmail">
        <label class="field">
          <span>{{ t("account.newEmail") }}</span>
          <input v-model="email" type="email" required autocomplete="email" />
        </label>
        <label class="field">
          <span>{{ t("account.currentPassword") }}</span>
          <input v-model="emailPassword" type="password" required autocomplete="current-password" />
        </label>
        <button class="primary-button" :disabled="emailBusy">
          {{ emailBusy ? t("auth.working") : t("account.changeEmail") }}
        </button>
      </form>
    </article>

    <article class="panel account-panel danger-zone">
      <h3>{{ t("account.deleteTitle") }}</h3>
      <p class="account-status">{{ t("account.deleteWarning") }}</p>
      <button
        v-if="!showDeleteAccount"
        class="text-button danger delete-account-link"
        type="button"
        @click="showDeleteAccount = true"
      >
        {{ t("account.deleteLink") }}
      </button>
      <form v-else class="account-form" @submit.prevent="deleteAccount">
        <label class="field">
          <span>{{ t("account.currentPassword") }}</span>
          <input v-model="deletePassword" type="password" required autocomplete="current-password" />
        </label>
        <label class="field">
          <span>{{ t("account.deleteConfirmation") }}</span>
          <input v-model="deleteConfirmation" required autocomplete="off" placeholder="DELETE" />
        </label>
        <div class="danger-actions">
          <button class="danger-button" :disabled="deleteBusy || deleteConfirmation !== 'DELETE'">
            {{ deleteBusy ? t("auth.working") : t("account.deleteButton") }}
          </button>
          <button class="secondary-button" type="button" @click="showDeleteAccount = false">
            {{ t("common.cancel") }}
          </button>
        </div>
      </form>
    </article>

    <article class="panel account-panel admin-panel">
      <h3>{{ t("account.auditTitle") }}</h3>
      <p v-if="!auditEvents.length" class="table-empty">{{ t("account.noAuditEvents") }}</p>
      <ul v-else class="audit-list">
        <li v-for="event in auditEvents.slice(0, 25)" :key="event.id">
          <strong>{{ event.event_type }}</strong><span>{{ new Date(event.created_at).toLocaleString() }}</span>
        </li>
      </ul>
    </article>
  </section>
</template>

