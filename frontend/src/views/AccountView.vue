<script setup lang="ts">
import { useI18n } from "vue-i18n";

import UserProfile from "../components/UserProfile.vue";

const { t } = useI18n();
</script>

<template>
  <section class="view-stack">
    <header class="view-heading">
      <div>
        <p class="eyebrow">{{ t("account.eyebrow") }}</p>
        <h2>{{ t("account.title") }}</h2>
      </div>
    </header>
    <article class="panel account-panel">
      <h3>{{ t("account.profile") }}</h3>
      <UserProfile />
      <p class="account-status">{{ t("account.auth0Managed") }}</p>
    </article>
  </section>
</template>

