<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

import { api } from "../api/client";
import type { ImportBatch } from "../types/api";
import { formatUkDateTime } from "../utils/date";

const selectedFile = ref<File | null>(null);
const defaultCurrency = ref("GBP");
const importing = ref(false);
const error = ref("");
const result = ref<ImportBatch | null>(null);
const history = ref<ImportBatch[]>([]);
const historyTotal = ref(0);
const retryingBatchId = ref<number | null>(null);
let pollTimer: ReturnType<typeof setTimeout> | undefined;

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
    error.value = caught instanceof Error ? caught.message : "Could not load import history";
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
    error.value = caught instanceof Error ? caught.message : "Could not refresh import status";
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
    error.value = caught instanceof Error ? caught.message : "Import failed";
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
    error.value = caught instanceof Error ? caught.message : "Could not retry import";
  } finally {
    retryingBatchId.value = null;
  }
}

onMounted(loadHistory);
onBeforeUnmount(() => clearTimeout(pollTimer));
</script>

<template>
  <section class="view-stack">
    <header class="view-heading">
      <div>
        <p class="eyebrow">Start here</p>
        <h2>Import transactions</h2>
        <p>Upload CSV, Excel or a text-based PDF. Every source row is retained before cleaning.</p>
      </div>
    </header>

    <div class="panel import-panel">
      <form class="import-form" @submit.prevent="submitImport">
        <label class="drop-zone">
          <span class="drop-icon">↑</span>
          <strong>{{ selectedFile?.name ?? "Choose a bank statement" }}</strong>
          <small>CSV, XLSX or text-based PDF · Maximum 10 MiB</small>
          <input type="file" accept=".csv,.xlsx,.pdf,text/csv,application/pdf" @change="selectFile" />
        </label>

        <label class="field compact-field">
          <span>Fallback currency</span>
          <input v-model="defaultCurrency" maxlength="3" placeholder="GBP" />
        </label>

        <button class="primary-button" type="submit" :disabled="!selectedFile || importing || jobRunning">
          {{ importing ? "Queueing import…" : jobRunning ? "Pipeline running…" : "Import and categorise" }}
        </button>
      </form>

      <p v-if="error" class="message error-message">{{ error }}</p>
    </div>

    <div v-if="result" class="result-grid" aria-live="polite">
      <article class="metric-card accent-blue">
        <span>Imported</span>
        <strong>{{ result.total_rows }}</strong>
      </article>
      <article class="metric-card accent-violet">
        <span>Normalised</span>
        <strong>{{ result.normalised_rows }}</strong>
      </article>
      <article class="metric-card accent-green">
        <span>Categorised</span>
        <strong>{{ result.categorised_rows }}</strong>
      </article>
      <article class="metric-card accent-orange">
        <span>Needs review</span>
        <strong>{{ result.needs_review_rows }}</strong>
      </article>
      <p v-if="jobRunning" class="message result-warning">
        Batch {{ result.id }} is {{ result.status }}. This page will update automatically.
      </p>
      <p v-else-if="result.processing_error" class="message error-message result-warning">
        Pipeline failed: {{ result.processing_error }}
      </p>
      <p v-else-if="result.failed_rows" class="message error-message result-warning">
        {{ result.failed_rows }} row(s) could not be normalised.
      </p>
      <p v-if="result.duplicate_rows" class="message result-warning">
        {{ result.duplicate_rows }} row(s) matched transactions imported earlier and were skipped.
      </p>
    </div>

    <article class="panel report-panel">
      <div class="panel-title">
        <h3>Import history</h3>
        <span>{{ historyTotal }} batches</span>
      </div>
      <div v-if="!history.length" class="table-empty">No statements imported yet.</div>
      <div v-else class="table-wrap">
        <table>
          <thead>
            <tr><th>Imported</th><th>File</th><th>Rows</th><th>Outcome</th><th></th></tr>
          </thead>
          <tbody>
            <tr v-for="batch in history" :key="batch.id">
              <td>{{ formatUkDateTime(batch.imported_at) }}</td>
              <td><strong>{{ batch.source_filename }}</strong><br /><span class="muted">{{ batch.source_type.toUpperCase() }} · Batch {{ batch.id }}</span></td>
              <td>{{ batch.normalised_rows }}/{{ batch.total_rows }} normalised<span v-if="batch.duplicate_rows" class="muted"> · {{ batch.duplicate_rows }} duplicates skipped</span></td>
              <td>
                <span class="status-pill">{{ batch.status.replace(/_/g, " ") }}</span>
                <span v-if="batch.failed_rows" class="muted"> · {{ batch.failed_rows }} failed</span>
                <span v-else class="muted"> · {{ batch.categorised_rows }} categorised, {{ batch.needs_review_rows }} review</span>
              </td>
              <td>
                <button
                  v-if="batch.failed_rows || batch.status === 'failed'"
                  class="text-button"
                  :disabled="retryingBatchId === batch.id"
                  @click="retryImport(batch)"
                >
                  {{ retryingBatchId === batch.id ? "Retrying…" : "Retry failed rows" }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </article>
  </section>
</template>

