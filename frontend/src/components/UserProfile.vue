<script setup lang="ts">
import { useAuth0 } from "@auth0/auth0-vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();
const { user, isAuthenticated, isLoading } = useAuth0();
const placeholderImage = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='100' height='100' viewBox='0 0 100 100'%3E%3Ccircle cx='50' cy='50' r='50' fill='%2363b3ed'/%3E%3Cpath d='M50 45c7.5 0 13.64-6.14 13.64-13.64S57.5 17.72 50 17.72s-13.64 6.14-13.64 13.64S42.5 45 50 45zm0 6.82c-9.09 0-27.28 4.56-27.28 13.64v3.41c0 1.88 1.53 3.41 3.41 3.41h47.74c1.88 0 3.41-1.53 3.41-3.41v-3.41c0-9.08-18.19-13.64-27.28-13.64z' fill='%23fff'/%3E%3C/svg%3E`;

function handleImageError(event: Event) {
  const image = event.currentTarget as HTMLImageElement;
  if (image.src !== placeholderImage) image.src = placeholderImage;
}
</script>

<template>
  <p v-if="isLoading" class="account-status" aria-live="polite">
    {{ t("account.loading") }}
  </p>
  <div v-else-if="isAuthenticated && user" class="profile-container">
    <img
      :src="user.picture || placeholderImage"
      :alt="user.name || user.nickname || t('account.profileImage')"
      class="profile-picture"
      referrerpolicy="no-referrer"
      @error="handleImageError"
    />
    <div class="profile-info">
      <strong class="profile-name">{{ user.name || user.nickname || user.email }}</strong>
      <span class="profile-email">{{ user.email }}</span>
    </div>
  </div>
</template>

<style scoped>
.profile-container { display: flex; align-items: center; gap: 1rem; }
.profile-picture { width: 72px; height: 72px; flex: 0 0 auto; border: 2px solid var(--accent-cyan); border-radius: 50%; object-fit: cover; }
.profile-info { min-width: 0; display: grid; gap: .25rem; }
.profile-name { overflow: hidden; color: var(--text-primary); font-size: 1.1rem; text-overflow: ellipsis; white-space: nowrap; }
.profile-email { overflow: hidden; color: var(--text-muted); font-size: .9rem; text-overflow: ellipsis; white-space: nowrap; }
</style>

