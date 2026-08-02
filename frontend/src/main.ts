import { createApp } from "vue";

import App from "./App.vue";
import { i18n } from "./i18n";
import { createAppRouter } from "./router";
import "./style.css";
import "./styles/account.css";
import "./styles/auth.css";
import "./styles/landing.css";

const router = createAppRouter();
window.addEventListener("folio:unauthorised", () => {
  if (router.currentRoute.value.name !== "login") {
    void router.replace({ name: "login", query: { redirect: router.currentRoute.value.fullPath } });
  }
});
window.addEventListener("folio:access-expired", () => {
  void router.replace({ name: "landing", hash: "#pricing", query: { trial: "expired" } });
});
createApp(App).use(router).use(i18n).mount("#app");

