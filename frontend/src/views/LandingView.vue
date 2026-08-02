<script setup lang="ts">
import {
  ArrowRight,
  ChartNoAxesCombined,
  CircleCheck,
  Landmark,
  ScanSearch,
  ShieldCheck,
  Sparkles,
  Upload,
  WalletCards,
} from "@lucide/vue";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";

import { defaultCurrencyForLocale } from "../utils/currency";
import { formatMoney } from "../utils/money";

const { locale, t } = useI18n();
const route = useRoute();
const displayCurrency = computed(() => defaultCurrencyForLocale(locale.value));
const monthlyPrice = computed(() => formatMoney(599, displayCurrency.value));
const previewMoney = (amount: number) => formatMoney(amount, displayCurrency.value);

const features = [
  { key: "import", icon: Upload },
  { key: "categorise", icon: ScanSearch },
  { key: "plan", icon: WalletCards },
  { key: "reports", icon: ChartNoAxesCombined },
];
</script>

<template>
  <main class="landing-page">
    <header class="landing-nav">
      <RouterLink class="landing-brand" to="/" aria-label="Folio home">
        <span class="brand-mark"><Landmark :size="21" :stroke-width="1.5" /></span>
        <strong>Folio</strong>
      </RouterLink>
      <nav :aria-label="t('landing.navigation')">
        <a href="#about">{{ t("landing.nav.about") }}</a>
        <a href="#features">{{ t("landing.nav.features") }}</a>
        <a href="#pricing">{{ t("landing.nav.pricing") }}</a>
      </nav>
      <div class="landing-auth-actions">
        <RouterLink class="landing-button secondary" to="/login">{{ t("auth.login") }}</RouterLink>
        <RouterLink class="landing-button primary" to="/register">{{ t("landing.register") }}</RouterLink>
      </div>
    </header>

    <div v-if="route.query.trial === 'expired'" class="trial-expired-banner" role="alert">
      <span>{{ t("landing.expired") }}</span>
      <RouterLink to="/account">{{ t("landing.manageAccount") }}</RouterLink>
    </div>

    <section id="about" class="landing-hero">
      <div class="landing-hero-copy">
        <p class="landing-kicker"><Sparkles :size="16" /> {{ t("landing.kicker") }}</p>
        <h1>{{ t("landing.heroTitle") }}</h1>
        <p>{{ t("landing.heroCopy") }}</p>
        <div class="landing-hero-actions">
          <RouterLink class="landing-button primary large" to="/register">
            {{ t("landing.startTrial") }} <ArrowRight :size="18" />
          </RouterLink>
          <a class="landing-button secondary large" href="#features">{{ t("landing.explore") }}</a>
        </div>
        <p class="landing-trial-note"><CircleCheck :size="15" /> {{ t("landing.noCard") }}</p>
      </div>

      <div class="landing-preview" aria-hidden="true">
        <div class="preview-glow"></div>
        <div class="preview-card preview-balance">
          <span>{{ t("landing.preview.safe") }}</span>
          <strong>{{ previewMoney(14730) }}</strong>
          <small>{{ t("landing.preview.until") }}</small>
        </div>
        <div class="preview-grid">
          <div class="preview-card"><span>{{ t("landing.preview.essential") }}</span><strong>{{ previewMoney(38200) }}</strong></div>
          <div class="preview-card"><span>{{ t("landing.preview.outlook") }}</span><strong class="positive">+{{ previewMoney(9640) }}</strong></div>
        </div>
        <div class="preview-card preview-risk">
          <ShieldCheck :size="19" />
          <div><strong>{{ t("landing.preview.onTrack") }}</strong><span>{{ t("landing.preview.risk") }}</span></div>
        </div>
      </div>
    </section>

    <section id="features" class="landing-section">
      <div class="landing-section-heading">
        <p class="landing-kicker">{{ t("landing.featuresKicker") }}</p>
        <h2>{{ t("landing.featuresTitle") }}</h2>
        <p>{{ t("landing.featuresCopy") }}</p>
      </div>
      <div class="landing-feature-grid">
        <article v-for="feature in features" :key="feature.key" class="landing-feature-card">
          <span><component :is="feature.icon" :size="22" :stroke-width="1.5" /></span>
          <h3>{{ t(`landing.features.${feature.key}.title`) }}</h3>
          <p>{{ t(`landing.features.${feature.key}.copy`) }}</p>
        </article>
      </div>
    </section>

    <section id="pricing" class="landing-section pricing-section">
      <div class="landing-section-heading">
        <p class="landing-kicker">{{ t("landing.pricingKicker") }}</p>
        <h2>{{ t("landing.pricingTitle") }}</h2>
        <p>{{ t("landing.pricingCopy") }}</p>
      </div>
      <article class="pricing-card">
        <p>{{ t("landing.planName") }}</p>
        <div class="pricing-amount"><strong>{{ monthlyPrice }}</strong><span>/ {{ t("landing.month") }}</span></div>
        <p>{{ t("landing.trial") }}</p>
        <ul>
          <li><CircleCheck :size="17" /> {{ t("landing.benefits.imports") }}</li>
          <li><CircleCheck :size="17" /> {{ t("landing.benefits.plan") }}</li>
          <li><CircleCheck :size="17" /> {{ t("landing.benefits.reports") }}</li>
          <li><CircleCheck :size="17" /> {{ t("landing.benefits.workspace") }}</li>
        </ul>
        <RouterLink class="landing-button primary large" to="/register">
          {{ t("landing.startTrial") }} <ArrowRight :size="18" />
        </RouterLink>
        <small>{{ t("landing.afterTrial") }}</small>
      </article>
    </section>

    <footer class="landing-footer">
      <div class="landing-brand"><span class="brand-mark"><Landmark :size="18" /></span><strong>Folio</strong></div>
      <p>{{ t("landing.footer") }}</p>
    </footer>
  </main>
</template>

