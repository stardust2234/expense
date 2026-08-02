import {
  createRouter,
  createWebHistory,
  type Router,
  type RouterHistory,
  type RouteRecordRaw,
} from "vue-router";

import { auth } from "./auth";

export const routes: RouteRecordRaw[] = [
  {
    path: "/",
    name: "landing",
    component: () => import("./views/LandingView.vue"),
    meta: { public: true, authLayout: true },
  },
  {
    path: "/login",
    name: "login",
    component: () => import("./views/LoginView.vue"),
    meta: { public: true, authLayout: true },
  },
  {
    path: "/register",
    name: "register",
    component: () => import("./views/LoginView.vue"),
    meta: { public: true, authLayout: true },
  },
  { path: "/verify-email", name: "verify-email", component: () => import("./views/VerifyEmailView.vue"), meta: { public: true, authLayout: true } },
  { path: "/reset-password", name: "reset-password", component: () => import("./views/ResetPasswordView.vue"), meta: { public: true, authLayout: true } },
  {
    path: "/dashboard",
    name: "dashboard",
    component: () => import("./views/DashboardView.vue"),
  },
  { path: "/account", name: "account", component: () => import("./views/AccountView.vue") },
  {
    path: "/imports",
    name: "imports",
    component: () => import("./views/ImportView.vue"),
  },
  {
    path: "/plan",
    name: "plan",
    component: () => import("./views/PlanView.vue"),
  },
  {
    path: "/review",
    name: "review",
    component: () => import("./views/ReviewView.vue"),
  },
  {
    path: "/transactions",
    name: "transactions",
    component: () => import("./views/TransactionsView.vue"),
  },
  {
    path: "/rules",
    name: "rules",
    component: () => import("./views/RulesView.vue"),
  },
  {
    path: "/merchants",
    name: "merchants",
    component: () => import("./views/MerchantsView.vue"),
  },
  {
    path: "/categories",
    name: "categories",
    component: () => import("./views/CategoriesView.vue"),
  },
  {
    path: "/reports",
    name: "reports",
    component: () => import("./views/ReportsView.vue"),
  },
  { path: "/:pathMatch(.*)*", redirect: "/dashboard" },
];

export function createAppRouter(
  history: RouterHistory = createWebHistory(),
  sessionGuard: () => Promise<boolean> = () => auth.ensureSession(),
): Router {
  const router = createRouter({ history, routes });
  router.onError((error, to) => {
    console.error(`Route navigation to ${to.fullPath} failed`, error);
  });
  router.beforeEach(async (to) => {
    const authenticated = await sessionGuard();
    if (!to.meta.public && !authenticated) {
      return { name: "login", query: { redirect: to.fullPath } };
    }
    if (!to.meta.public && authenticated && auth.user.value?.email_verified === false) {
      return { name: "verify-email" };
    }
    if (
      !to.meta.public
      && to.name !== "account"
      && authenticated
      && auth.user.value?.access_active === false
    ) {
      return { name: "landing", hash: "#pricing", query: { trial: "expired" } };
    }
    if ((to.name === "login" || to.name === "register") && authenticated) {
      return { name: "dashboard" };
    }
    return true;
  });
  return router;
}

