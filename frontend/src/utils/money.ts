const zeroDecimalCurrencies = new Set(["JPY", "KRW"]);
const threeDecimalCurrencies = new Set(["BHD", "KWD", "OMR", "TND"]);

export function formatMoney(amount: number, currency: string): string {
  return new Intl.NumberFormat("en-GB", {
    style: "currency",
    currency,
  }).format(toMajorUnits(amount, currency));
}

export function toMajorUnits(amount: number, currency: string): number {
  const exponent = currencyExponent(currency);
  return amount / 10 ** exponent;
}

export function toMinorUnits(amount: number, currency: string): number {
  return Math.round(amount * 10 ** currencyExponent(currency.toUpperCase()));
}

function currencyExponent(currency: string): number {
  return zeroDecimalCurrencies.has(currency)
    ? 0
    : threeDecimalCurrencies.has(currency)
      ? 3
      : 2;
}

