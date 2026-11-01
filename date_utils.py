from datetime import date, timedelta

HOLIDAYS = {
    date(2026, 8, 15),
    date(2026, 10, 2),
    date(2026, 10, 19),
    date(2026, 11, 9),
}


def add_business_days(start_date, days):
    current = start_date
    count = 0

    while count < days:
        if current.weekday() < 6 and current not in HOLIDAYS:
            count += 1

        if count < days:
            current += timedelta(days=1)

    return current


def refund_window(initiated_date, minimum=5, maximum=7):
    start = add_business_days(initiated_date, minimum)
    end = add_business_days(initiated_date, maximum)
    return start, end


if __name__ == "__main__":
    start, end = refund_window(date(2026, 10, 17))
    print("Earliest:", start.strftime("%d %B %Y"))
    print("Latest:", end.strftime("%d %B %Y"))

