import type { CategoryTotal, MonthlyTotal, PaymentPeriod } from "../../types/api";
import { formatCategoryName } from "../../utils/category";
import { formatUkDate, inclusiveCycleEnd } from "../../utils/date";
import { formatMoney, toMajorUnits } from "../../utils/money";

type Translate = (key: string) => string;

const colours = ["#22D3EE", "#818CF8", "#E879F9", "#34D399"];

export function categoryChart(items: CategoryTotal[]) {
  return [{
    type: "bar",
    orientation: "h",
    x: items.map((item) => toMajorUnits(item.total_amount, item.currency)),
    y: items.map((item) => `${formatCategoryName({ code: item.category_code, name: item.category_name })} · ${item.currency}`),
    text: items.map((item) => formatMoney(item.total_amount, item.currency)),
    hovertemplate: "%{y}<br>%{text}<extra></extra>",
    marker: { color: items.map((_, index) => colours[index % colours.length]), opacity: 0.82, borderRadius: 6 },
  }];
}

export function monthlyChart(items: MonthlyTotal[]) {
  const currencies = [...new Set(items.map((item) => item.currency))];
  return currencies.map((currency, index) => ({
    type: "scatter",
    mode: "lines+markers",
    name: currency,
    x: items.filter((item) => item.currency === currency).map((item) => item.month),
    y: items.filter((item) => item.currency === currency).map((item) => toMajorUnits(item.total_amount, item.currency)),
    line: { width: 2, color: colours[index % 3] },
    marker: { size: 7, color: colours[index % 3] },
    fill: "tozeroy",
    fillcolor: "rgba(129,140,248,0.10)",
    hovertemplate: `%{x}<br>%{y:.2f} ${currency}<extra></extra>`,
  }));
}

export function paymentPeriodChart(items: PaymentPeriod[], t: Translate) {
  const definitions = [
    [t("common.priorities.protected"), "protected_spending", "#FB7185"],
    [t("common.priorities.essential"), "essential_spending", "#34D399"],
    [t("common.priorities.adjustable"), "adjustable_spending", "#22D3EE"],
    [t("common.priorities.optional"), "optional_spending", "#FBBF24"],
    [t("common.priorities.irregular_essential"), "irregular_essential_spending", "#A78BFA"],
  ] as const;
  return definitions.map(([name, field, color]) => ({
    type: "bar",
    name,
    x: items.map((period) => `${formatUkDate(period.start_date)}–${formatUkDate(inclusiveCycleEnd(period.end_date))}`),
    y: items.map((period) => toMajorUnits(period[field], period.currency)),
    marker: { color },
    hovertemplate: `%{x}<br>%{y:.2f}<extra>${name}</extra>`,
  }));
}

export const reportChartLayout = {
  autosize: true,
  height: 330,
  margin: { l: 115, r: 24, t: 18, b: 45 },
  paper_bgcolor: "transparent",
  plot_bgcolor: "transparent",
  font: { family: "Inter, sans-serif", color: "rgba(255,255,255,0.40)", size: 11 },
  xaxis: { gridcolor: "rgba(255,255,255,0.05)", zeroline: false },
  yaxis: { gridcolor: "rgba(255,255,255,0.05)", zeroline: false, automargin: true },
  showlegend: true,
  legend: { orientation: "h", y: 1.1 },
};

