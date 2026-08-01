<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";

import { api } from "../api/client";
import type { Merchant } from "../types/api";

const merchants = ref<Merchant[]>([]);
const { t } = useI18n();
const name = ref("");
const aliases = ref("");
const aliasDrafts = ref<Record<number, string>>({});
const loading = ref(true);
const saving = ref(false);
const error = ref("");
const mergeSources = ref<Record<number, string>>({});

async function loadMerchants() {
  loading.value = true;
  try {
    merchants.value = await api.merchants();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.merchants.errors.load");
  } finally {
    loading.value = false;
  }
}

async function createMerchant() {
  if (!name.value.trim()) return;
  saving.value = true;
  error.value = "";
  try {
    await api.createMerchant(
      name.value.trim(),
      aliases.value.split(",").map((value) => value.trim()).filter(Boolean),
    );
    name.value = "";
    aliases.value = "";
    await loadMerchants();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.merchants.errors.create");
  } finally {
    saving.value = false;
  }
}

async function addAlias(merchant: Merchant) {
  const pattern = aliasDrafts.value[merchant.id]?.trim();
  if (!pattern) return;
  try {
    await api.addMerchantAlias(merchant.id, pattern);
    aliasDrafts.value[merchant.id] = "";
    await loadMerchants();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.merchants.errors.addAlias");
  }
}

async function removeAlias(merchantId: number, aliasId: number) {
  try {
    await api.deleteMerchantAlias(merchantId, aliasId);
    await loadMerchants();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.merchants.errors.removeAlias");
  }
}

async function mergeInto(merchant: Merchant) {
  const sourceId = Number(mergeSources.value[merchant.id]);
  if (!sourceId || !window.confirm(t("views.merchants.mergeConfirm"))) return;
  try {
    await api.mergeMerchants(merchant.id, sourceId);
    mergeSources.value[merchant.id] = "";
    await loadMerchants();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.merchants.errors.merge");
  }
}

onMounted(loadMerchants);
</script>

<template>
  <section class="view-stack">
    <header class="view-heading">
      <div>
        <p class="eyebrow">{{ t("views.merchants.eyebrow") }}</p><h2>{{ t("views.merchants.title") }}</h2><p>{{ t("views.merchants.subtitle") }}</p>
      </div>
    </header>

    <form class="panel merchant-form" @submit.prevent="createMerchant">
      <label class="field"><span>{{ t("views.merchants.name") }}</span><input v-model="name" maxlength="200" placeholder="Tesco" /></label><label class="field"><span>{{ t("views.merchants.aliases") }}</span><input v-model="aliases" placeholder="TESCO STORES, TESCO EXPRESS" /></label>
      <button class="primary-button" type="submit" :disabled="!name.trim() || saving">
        {{ saving ? t("views.merchants.adding") : t("views.merchants.addMerchant") }}
      </button>
    </form>

    <p v-if="error" class="message error-message">{{ error }}</p>
    <div v-if="loading" class="panel empty-state">{{ t("views.merchants.loading") }}</div><div v-else-if="!merchants.length" class="panel empty-state">{{ t("views.merchants.empty") }}</div>
    <div v-else class="merchant-grid">
      <article v-for="merchant in merchants" :key="merchant.id" class="panel merchant-card">
        <h3>{{ merchant.name }}</h3>
        <div class="alias-list">
          <span v-for="alias in merchant.aliases" :key="alias.id" class="alias-chip">
            {{ alias.pattern }}
            <button :aria-label="t('views.merchants.removeAlias')" @click="removeAlias(merchant.id, alias.id)">×</button>
          </span>
          <span v-if="!merchant.aliases.length" class="muted">{{ t("views.merchants.noAliases") }}</span>
        </div>
        <form class="alias-form" @submit.prevent="addAlias(merchant)">
          <input v-model="aliasDrafts[merchant.id]" maxlength="200" :placeholder="t('views.merchants.aliasPlaceholder')" /><button class="secondary-button" type="submit">{{ t("views.merchants.add") }}</button>
        </form>
        <form class="merge-form" @submit.prevent="mergeInto(merchant)">
          <select v-model="mergeSources[merchant.id]">
            <option value="">{{ t("views.merchants.mergeInto", { name: merchant.name }) }}</option>
            <option v-for="candidate in merchants.filter((item) => item.id !== merchant.id)" :key="candidate.id" :value="String(candidate.id)">{{ candidate.name }}</option>
          </select>
          <button class="text-button" type="submit">{{ t("views.merchants.merge") }}</button>
        </form>
      </article>
    </div>
  </section>
</template>

