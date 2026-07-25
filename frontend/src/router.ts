import {
  createRouter,
  createWebHistory,
  type Router,
  type RouterHistory,
  type RouteRecordRaw,
} from "vue-router";

export const routes: RouteRecordRaw[] = [
  {
    path: "/dashboard",
    name: "dashboard",
    component: () => import("./views/DashboardView.vue"),
  },
  {
    path: "/imports",
    name: "imports",
    component: () => import("./views/ImportView.vue"),
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
  { path: "/", redirect: "/dashboard" },
  { path: "/:pathMatch(.*)*", redirect: "/dashboard" },
];

export function createAppRouter(
  history: RouterHistory = createWebHistory(),
): Router {
  return createRouter({ history, routes });
}

