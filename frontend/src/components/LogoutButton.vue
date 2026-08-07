<script setup lang="ts">
import { useAuth0 } from "@auth0/auth0-vue";
import { LogOut } from "@lucide/vue";
import { useI18n } from "vue-i18n";

const emit = defineEmits<{ logoutStarted: [] }>();
const { t } = useI18n();
const { logout, isLoading } = useAuth0();

async function handleLogout() {
  emit("logoutStarted");
  await logout({ logoutParams: { returnTo: window.location.origin } });
}
</script>

<template>
  <button type="button" :disabled="isLoading" @click="handleLogout">
    <LogOut :size="17" :stroke-width="1.5" />
    {{ isLoading ? t("auth.working") : t("auth.logout") }}
  </button>
</template>

