export function firstOfMonth(value: Date): Date {
  return new Date(value.getFullYear(), value.getMonth(), 1);
}

export function addCalendarMonth(value: Date): Date {
  const targetMonth = value.getMonth() + 1;
  const lastTargetDay = new Date(value.getFullYear(), targetMonth + 1, 0).getDate();
  return new Date(
    value.getFullYear(),
    targetMonth,
    Math.min(value.getDate(), lastTargetDay),
  );
}

export function inputDate(value: Date): string {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, "0")}-${String(value.getDate()).padStart(2, "0")}`;
}

export function defaultPlanDates(today: Date) {
  const calendarStart = firstOfMonth(today);
  const calendarEnd = addCalendarMonth(calendarStart);
  const benefitDate = new Date(today.getFullYear(), today.getMonth(), 29);
  const firstBillDue = new Date(calendarEnd);
  firstBillDue.setDate(calendarEnd.getDate() - 1);
  return { calendarStart, benefitDate, firstBillDue };
}

