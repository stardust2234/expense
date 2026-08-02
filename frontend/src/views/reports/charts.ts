import type { CategoryTotal, PaymentPeriod, PriorityTotal } from "../../types/api";
import { formatCategoryName } from "../../utils/category";
import { formatUkDate, inclusiveCycleEnd } from "../../utils/date";
import { formatMoney, toMajorUnits } from "../../utils/money";

type Translate = (key: string) => string;

const colours = ["#22D3EE", "#818CF8", "#E879F9", "#34D399"];
const priorityColours: Record<string, string> = {
  protected: "#FB7185",
  essential: "#34D399",
  adjustable: "#22D3EE",
  irregular_essential: "#A78BFA",
  optional: "#FBBF24",
};

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

export function priorityDistributionChart(items: PriorityTotal[], t: Translate) {
  const distributableItems = items.filter((item) => item.total_amount > 0);
  const currencies = [...new Set(distributableItems.map((item) => item.currency))];

  return currencies.map((currency, index) => {
    const currencyItems = distributableItems.filter((item) => item.currency === currency);
    const domainWidth = 1 / currencies.length;
    const domainPadding = Math.min(0.055, domainWidth / 8);

    return {
      type: "pie",
      name: currency,
      labels: currencyItems.map((item) => t(`common.priorities.${item.priority}`)),
      values: currencyItems.map((item) => toMajorUnits(item.total_amount, item.currency)),
      customdata: currencyItems.map((item) => formatMoney(item.total_amount, item.currency)),
      hole: 0.58,
      sort: false,
      textinfo: "percent",
      textposition: "inside",
      marker: {
        colors: currencyItems.map((item) => priorityColours[item.priority] ?? "#818CF8"),
        line: { color: "rgba(15,23,42,0.65)", width: 1 },
      },
      domain: {
        x: [index * domainWidth + domainPadding, (index + 1) * domainWidth - domainPadding],
        y: [0.04, 0.78],
      },
      title: { text: currency },
      hovertemplate: `%{label}<br>%{customdata}<br>%{percent}<extra>${currency}</extra>`,
    };
  });
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

