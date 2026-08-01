import { i18n } from "../i18n";
import type { Category } from "../types/api";

export function formatCategoryName(category: Pick<Category, "code" | "name">): string {
  if (!category.code) return category.name;
  const key = `categories.${category.code}${category.code.includes(".") ? "" : "._name"}`;
  return i18n.global.te(key) ? i18n.global.t(key) : category.name;
}

