<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

type HealthResponse = {
  status: string;
  service: string;
  environment: string;
  database: string;
};

const health = ref<HealthResponse | null>(null);
const loading = ref(true);
const error = ref("");

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL ?? "/api";

const apiStatus = computed(() => {
  if (loading.value) {
    return "Checking API";
  }

  if (error.value) {
    return "API unavailable";
  }

  return `${health.value?.service} is ${health.value?.status}`;
});

onMounted(async () => {
  try {
    const response = await fetch(`${apiBaseUrl}/health`);
    if (!response.ok) {
      throw new Error(`Unexpected status: ${response.status}`);
    }

    health.value = (await response.json()) as HealthResponse;
  } catch (caughtError) {
    error.value = caughtError instanceof Error ? caughtError.message : "Unknown error";
  } finally {
    loading.value = false;
  }
});
</script>

<template>
  <main class="min-h-screen bg-[radial-gradient(circle_at_top,#f8fafc,#dbeafe_45%,#e0f2fe_100%)] text-slate-900">
    <section class="mx-auto flex min-h-screen max-w-6xl flex-col justify-center gap-10 px-6 py-16">
      <div class="space-y-4">
        <p class="inline-flex rounded-full border border-white/60 bg-white/70 px-3 py-1 text-xs font-semibold uppercase tracking-[0.3em] text-sky-700 shadow-sm backdrop-blur">
          Standard Full-Stack Template
        </p>
        <h1 class="max-w-4xl text-5xl font-black tracking-tight text-slate-950 sm:text-6xl">
          Vue, FastAPI, PostgreSQL, Docker Compose, and Caddy in one reusable baseline.
        </h1>
        <p class="max-w-2xl text-lg text-slate-700">
          Start projects with a frontend and API that already agree on build tooling, container
          orchestration, reverse proxying, and a health-checked database.
        </p>
      </div>

      <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <article class="rounded-3xl border border-slate-200/80 bg-white/80 p-6 shadow-lg shadow-sky-100 backdrop-blur">
          <p class="text-sm font-semibold uppercase tracking-[0.25em] text-sky-700">Frontend</p>
          <h2 class="mt-4 text-2xl font-bold text-slate-950">Vue 3 + Vite + TypeScript</h2>
          <p class="mt-2 text-sm leading-6 text-slate-600">
            Single-file components, fast HMR, and a typed client ready for app-specific features.
          </p>
        </article>

        <article class="rounded-3xl border border-slate-200/80 bg-white/80 p-6 shadow-lg shadow-cyan-100 backdrop-blur">
          <p class="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-700">Styling</p>
          <h2 class="mt-4 text-2xl font-bold text-slate-950">Tailwind CSS</h2>
          <p class="mt-2 text-sm leading-6 text-slate-600">
            Utility-first styling with the Vite plugin, ready for design tokens and shared patterns.
          </p>
        </article>

        <article class="rounded-3xl border border-slate-200/80 bg-white/80 p-6 shadow-lg shadow-emerald-100 backdrop-blur">
          <p class="text-sm font-semibold uppercase tracking-[0.25em] text-emerald-700">Backend</p>
          <h2 class="mt-4 text-2xl font-bold text-slate-950">FastAPI + PostgreSQL</h2>
          <p class="mt-2 text-sm leading-6 text-slate-600">
            A Python API with database-aware health checks and configuration that fits containerized
            deployments.
          </p>
        </article>

        <article class="rounded-3xl border border-slate-200/80 bg-white/80 p-6 shadow-lg shadow-amber-100 backdrop-blur">
          <p class="text-sm font-semibold uppercase tracking-[0.25em] text-amber-700">Deployment</p>
          <h2 class="mt-4 text-2xl font-bold text-slate-950">Docker + Compose + Caddy</h2>
          <p class="mt-2 text-sm leading-6 text-slate-600">
            A single entrypoint fronts the SPA and proxies API traffic while Compose wires services
            together.
          </p>
        </article>
      </div>

      <div class="grid gap-6 rounded-4xl border border-slate-200/80 bg-slate-950 p-8 text-white shadow-2xl shadow-slate-300/50 lg:grid-cols-[1.3fr_1fr]">
        <div class="space-y-3">
          <p class="text-sm font-semibold uppercase tracking-[0.3em] text-sky-300">Live status</p>
          <h2 class="text-3xl font-bold">{{ apiStatus }}</h2>
          <p class="text-sm text-slate-300">
            The frontend calls the backend through Caddy using the same `/api` path you will keep in
            production.
          </p>
        </div>

        <dl class="grid gap-4 rounded-3xl bg-white/10 p-6 text-sm text-slate-100">
          <div class="flex items-center justify-between gap-4">
            <dt class="text-slate-300">Environment</dt>
            <dd>{{ health?.environment ?? "Pending" }}</dd>
          </div>
          <div class="flex items-center justify-between gap-4">
            <dt class="text-slate-300">Database</dt>
            <dd>{{ health?.database ?? (error || "Pending") }}</dd>
          </div>
          <div class="flex items-center justify-between gap-4">
            <dt class="text-slate-300">API route</dt>
            <dd>{{ apiBaseUrl }}/health</dd>
          </div>
        </dl>
      </div>
    </section>
  </main>
</template>
