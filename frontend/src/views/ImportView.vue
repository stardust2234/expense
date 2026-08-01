<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { UploadCloud } from "@lucide/vue";
import { useI18n } from "vue-i18n";

import { api } from "../api/client";
import type { ImportBatch } from "../types/api";
import { formatUkDateTime } from "../utils/date";
import { defaultCurrencyForLocale } from "../utils/currency";

const selectedFile = ref<File | null>(null);
const { locale, t } = useI18n();
const defaultCurrency = ref(defaultCurrencyForLocale(locale.value));
const importing = ref(false);
const error = ref("");
const result = ref<ImportBatch | null>(null);
const history = ref<ImportBatch[]>([]);
const historyTotal = ref(0);
const retryingBatchId = ref<number | null>(null);
const deletingBatchId = ref<number | null>(null);
let pollTimer: ReturnType<typeof setTimeout> | undefined;

watch(locale, (nextLocale, previousLocale) => {
  if (defaultCurrency.value === defaultCurrencyForLocale(previousLocale)) {
    defaultCurrency.value = defaultCurrencyForLocale(nextLocale);
  }
});

const jobRunning = computed(() =>
  result.value ? ["queued", "processing"].includes(result.value.status) : false,
);

function selectFile(event: Event) {
  selectedFile.value = (event.target as HTMLInputElement).files?.[0] ?? null;
  if (!jobRunning.value) result.value = null;
  error.value = "";
}

async function loadHistory() {
  try {
    const page = await api.importHistory();
    history.value = page.items;
    historyTotal.value = page.total;
    const active = page.items.find((batch) => ["queued", "processing"].includes(batch.status));
    if (active && !result.value) {
      result.value = active;
      schedulePoll(active.id);
    }
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.import.errors.history");
  }
}

function schedulePoll(batchId: number) {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(() => pollBatch(batchId), 750);
}

async function pollBatch(batchId: number) {
  try {
    result.value = await api.importBatch(batchId);
    await loadHistory();
    if (["queued", "processing"].includes(result.value.status)) {
      schedulePoll(batchId);
    }
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.import.errors.refresh");
  }
}

async function submitImport() {
  if (!selectedFile.value) return;
  importing.value = true;
  error.value = "";
  try {
    result.value = await api.importStatement(selectedFile.value, defaultCurrency.value);
    await loadHistory();
    schedulePoll(result.value.id);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.import.errors.upload");
  } finally {
    importing.value = false;
  }
}

async function retryImport(batch: ImportBatch) {
  retryingBatchId.value = batch.id;
  error.value = "";
  try {
    result.value = await api.retryImport(batch.id);
    await loadHistory();
    schedulePoll(batch.id);
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.import.errors.retry");
  } finally {
    retryingBatchId.value = null;
  }
}

async function deleteImport(batch: ImportBatch) {
  const confirmed = window.confirm(
    t("importDetail.deleteConfirm", { id: batch.id, file: batch.source_filename }),
  );
  if (!confirmed) return;

  deletingBatchId.value = batch.id;
  error.value = "";
  try {
    await api.deleteImport(batch.id);
    if (result.value?.id === batch.id) {
      clearTimeout(pollTimer);
      result.value = null;
    }
    await loadHistory();
  } catch (caught) {
    error.value = caught instanceof Error ? caught.message : t("views.import.errors.delete");
  } finally {
    deletingBatchId.value = null;
  }
}

onMounted(loadHistory);
onBeforeUnmount(() => clearTimeout(pollTimer));
</script>

<template>
  <section class="view-stack">
    <header class="view-heading">
      <div>
        <p class="eyebrow">{{ t("views.import.eyebrow") }}</p>
        <h2>{{ t("views.import.title") }}</h2>
        <p>{{ t("views.import.subtitle") }}</p>
      </div>
    </header>

    <div class="panel import-panel">
      <form class="import-form" @submit.prevent="submitImport">
        <label class="drop-zone">
          <span class="drop-icon"><UploadCloud :size="19" :stroke-width="1.5" /></span>
          <strong>{{ selectedFile?.name ?? t("views.import.choose") }}</strong>
          <small>{{ t("views.import.types") }}</small>
          <input type="file" accept=".csv,.xlsx,.pdf,text/csv,application/pdf" @change="selectFile" />
        </label>

        <label class="field compact-field">
          <span>{{ t("views.import.fallbackCurrency") }}</span>
          <input v-model="defaultCurrency" maxlength="3" :placeholder="defaultCurrencyForLocale(locale)" />
        </label>

        <button class="primary-button" type="submit" :disabled="!selectedFile || importing || jobRunning">
          {{ importing ? t("views.import.queueing") : jobRunning ? t("views.import.running") : t("views.import.submit") }}
        </button>
      </form>

      <p v-if="error" class="message error-message">{{ error }}</p>
    </div>

    <div v-if="result" class="result-grid" aria-live="polite">
      <article class="metric-card accent-blue">
        <span>{{ t("views.import.imported") }}</span>
        <strong>{{ result.total_rows }}</strong>
      </article>
      <article class="metric-card accent-violet">
        <span>{{ t("views.import.normalised") }}</span>
        <strong>{{ result.normalised_rows }}</strong>
      </article>
      <article class="metric-card accent-green">
        <span>{{ t("views.import.categorised") }}</span>
        <strong>{{ result.categorised_rows }}</strong>
      </article>
      <article class="metric-card accent-orange">
        <span>{{ t("views.import.review") }}</span>
        <strong>{{ result.needs_review_rows }}</strong>
      </article>
      <p v-if="jobRunning" class="message result-warning">
        {{ t("importDetail.running", { id: result.id, status: result.status }) }}
      </p>
      <p v-else-if="result.processing_error" class="message error-message result-warning">
        {{ t("importDetail.failed", { error: result.processing_error }) }}
      </p>
      <p v-else-if="result.failed_rows" class="message error-message result-warning">
        {{ t("importDetail.normalisationFailed", { count: result.failed_rows }) }}
      </p>
      <p v-if="result.duplicate_rows" class="message result-warning">
        {{ t("importDetail.duplicates", { count: result.duplicate_rows }) }}
      </p>
    </div>

    <article class="panel report-panel">
      <div class="panel-title">
        <h3>{{ t("views.import.history") }}</h3>
        <span>{{ t("views.import.batches", { count: historyTotal }) }}</span>
      </div>
      <div v-if="!history.length" class="table-empty">{{ t("views.import.empty") }}</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr><th>{{ t("views.import.imported") }}</th><th>{{ t("views.import.file") }}</th><th>{{ t("views.import.rows") }}</th><th>{{ t("views.import.outcome") }}</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="batch in history" :key="batch.id">
              <td>{{ formatUkDateTime(batch.imported_at) }}</td>
              <td><strong>{{ batch.source_filename }}</strong><br /><span class="muted">{{ batch.source_type.toUpperCase() }} · {{ t("importDetail.batch", { id: batch.id }) }}</span></td>
              <td>{{ t("importDetail.rowSummary", { normalised: batch.normalised_rows, total: batch.total_rows }) }}<span v-if="batch.duplicate_rows" class="muted"> · {{ t("importDetail.duplicatesShort", { count: batch.duplicate_rows }) }}</span></td>
              <td>
                <span class="status-pill" :class="batch.status">{{ t(`dynamic.importStatuses.${batch.status}`) }}</span>
                <span v-if="batch.failed_rows" class="muted"> · {{ t("importDetail.failedShort", { count: batch.failed_rows }) }}</span><span v-else class="muted"> · {{ t("importDetail.outcome", { categorised: batch.categorised_rows, review: batch.needs_review_rows }) }}</span>
              </td>
              <td><div class="row-actions">
                <button
                  v-if="batch.failed_rows || batch.status === 'failed'"
                  class="text-button"
                  :disabled="retryingBatchId === batch.id"
                  @click="retryImport(batch)"
                >
                  {{ retryingBatchId === batch.id ? t("views.import.retrying") : t("views.import.retry") }}
                </button>
                <button
                  v-if="!['queued', 'processing'].includes(batch.status)"
                  class="text-button danger"
                  type="button"
                  :disabled="deletingBatchId === batch.id"
                  @click="deleteImport(batch)"
                >
                  {{ deletingBatchId === batch.id ? t("views.import.deleting") : t("views.import.delete") }}
                </button>
              </div></td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

