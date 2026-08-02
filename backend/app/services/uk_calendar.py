from datetime import date, timedelta


def _easter_sunday(year: int) -> date:
    """Return Gregorian Easter Sunday using the Meeus/Jones/Butcher algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    month_offset = (32 + 2 * e + 2 * i - h - k) // 7
    remainder = (a + 11 * h + 22 * month_offset) // 451
    month = (h + k - 7 * remainder + 114) // 31
    day = (h + k - 7 * remainder + 114) % 31 + 1
    return date(year, month, day)


def england_wales_bank_holidays(year: int) -> frozenset[date]:
    holidays: set[date] = set()
    new_year = date(year, 1, 1)
    holidays.add(
        new_year if new_year.weekday() < 5 else new_year + timedelta(days=7 - new_year.weekday())
    )

    easter = _easter_sunday(year)
    holidays.update({easter - timedelta(days=2), easter + timedelta(days=1)})

    may_first = date(year, 5, 1)
    holidays.add(may_first + timedelta(days=(7 - may_first.weekday()) % 7))
    may_end = date(year, 5, 31)
    holidays.add(may_end - timedelta(days=may_end.weekday()))
    august_end = date(year, 8, 31)
    holidays.add(august_end - timedelta(days=august_end.weekday()))

    christmas = date(year, 12, 25)
    boxing_day = date(year, 12, 26)
    if christmas.weekday() == 5:
        holidays.update({date(year, 12, 27), date(year, 12, 28)})
    elif christmas.weekday() == 6:
        holidays.update({date(year, 12, 27), boxing_day})
    else:
        holidays.add(christmas)
        holidays.add(boxing_day if boxing_day.weekday() < 5 else date(year, 12, 28))
    return frozenset(holidays)


def previous_uk_banking_day(value: date) -> date:
    holidays = england_wales_bank_holidays(value.year)
    adjusted = value
    while adjusted.weekday() >= 5 or adjusted in holidays:
        adjusted -= timedelta(days=1)
        if adjusted.year != value.year:
            holidays = england_wales_bank_holidays(adjusted.year)
    return adjusted
