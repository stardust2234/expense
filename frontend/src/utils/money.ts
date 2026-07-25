const zeroDecimalCurrencies = new Set(["JPY", "KRW"]);
const threeDecimalCurrencies = new Set(["BHD", "KWD", "OMR", "TND"]);

export function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
  }).format(toMajorUnits(amount, currency));
}

export function toMajorUnits(amount: number, currency: string): number {
  const exponent = zeroDecimalCurrencies.has(currency)
    ? 0
    : threeDecimalCurrencies.has(currency)
      ? 3
      : 2;
  return amount / 10 ** exponent;
}

