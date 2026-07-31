export function formatUkDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  return `${match[3]}/${match[2]}/${match[1]}`;
}

export function formatUkMonth(value: string): string {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  if (!match) return value;
  return `${match[2]}/${match[1]}`;
}

export function inclusiveCycleEnd(exclusiveEnd: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(exclusiveEnd);
  if (!match) return exclusiveEnd;
  const value = new Date(
    Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])),
  );
  value.setUTCDate(value.getUTCDate() - 1);
  return [
    value.getUTCFullYear(),
    String(value.getUTCMonth() + 1).padStart(2, "0"),
    String(value.getUTCDate()).padStart(2, "0"),
  ].join("-");
}

export function formatUkDateTime(value: string): string {
  const hasTimezone = /(?:Z|[+-]\d{2}:\d{2})$/.test(value);
  const parsed = new Date(hasTimezone ? value : `${value}Z`);
  if (Number.isNaN(parsed.getTime())) return value;
  return new Intl.DateTimeFormat("en-GB", {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: "Europe/London",
  }).format(parsed);
}

