import { createApp } from "vue";

import App from "./App.vue";
import { i18n } from "./i18n";
import { createAppRouter } from "./router";
import "./style.css";
import "./styles/account.css";
import "./styles/auth.css";

const router = createAppRouter();
window.addEventListener("folio:unauthorised", () => {
  if (router.currentRoute.value.name !== "login") {
    void router.replace({ name: "login", query: { redirect: router.currentRoute.value.fullPath } });
  }
});
createApp(App).use(router).use(i18n).mount("#app");

