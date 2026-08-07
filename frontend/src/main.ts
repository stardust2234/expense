import { createAuth0 } from "@auth0/auth0-vue";
import { createApp, defineComponent, h } from "vue";
import { useI18n } from "vue-i18n";

import App from "./App.vue";
import { apiBaseUrl } from "./api/request";
import { configureAuth0 } from "./auth";
import { i18n } from "./i18n";
import { createAppRouter } from "./router";
import "./style.css";
import "./styles/account.css";
import "./styles/auth.css";
import "./styles/landing.css";

interface Auth0PublicConfig {
  domain: string;
  client_id: string;
  audience: string;
}

const BootstrapError = defineComponent({
  setup() {
    const { t } = useI18n();
    return () =>
      h("main", { class: "login-page" }, [
        h("section", { class: "login-card" }, [
          h("h1", t("auth.errors.configurationTitle")),
          h("p", { class: "error-banner", role: "alert" }, t("auth.errors.configuration")),
          h(
            "button",
            {
              class: "primary-action",
              type: "button",
              onClick: () => window.location.reload(),
            },
            t("auth.retry"),
          ),
        ]),
      ]);
  },
});

async function loadAuth0Config(): Promise<Auth0PublicConfig> {
  const response = await fetch(`${apiBaseUrl.replace(/\/+$/, "")}/auth/config`);
  if (!response.ok) throw new Error("Auth0 configuration request failed");
  const config = (await response.json()) as Partial<Auth0PublicConfig>;
  if (
    typeof config.domain !== "string"
    || typeof config.client_id !== "string"
    || typeof config.audience !== "string"
    || !config.domain
    || !config.client_id
    || !config.audience
  ) {
    throw new Error("Auth0 configuration response is incomplete");
  }
  return config as Auth0PublicConfig;
}

async function bootstrap(): Promise<void> {
  try {
    const auth0Config = await loadAuth0Config();
    const app = createApp(App);
    const router = createAppRouter();
    const auth0 = createAuth0({
      domain: auth0Config.domain,
      clientId: auth0Config.client_id,
      authorizationParams: {
        redirect_uri: window.location.origin,
        audience: auth0Config.audience,
      },
      cacheLocation: "memory",
      useRefreshTokens: true,
    });
    configureAuth0(auth0);

    let recoveringAuthentication = false;
    window.addEventListener("folio:unauthorised", () => {
      if (recoveringAuthentication) return;
      recoveringAuthentication = true;
      void auth0
        .logout({ logoutParams: { returnTo: window.location.origin } })
        .catch(() => {
          recoveringAuthentication = false;
          void router.replace({ name: "landing" });
        });
    });
    window.addEventListener("folio:access-expired", () => {
      void router.replace({ name: "landing", hash: "#pricing", query: { trial: "expired" } });
    });

    app.use(router);
    app.use(auth0);
    app.use(i18n);
    app.mount("#app");
  } catch {
    createApp(BootstrapError).use(i18n).mount("#app");
  }
}

void bootstrap();

