import csv
import os
from datetime import datetime

from dateutil import parser as date_parser
from result import Result, Ok, Err

CSV_PATH = os.path.join(os.path.dirname(__file__), 'MORTGAGE30US.csv')


def _load_rows():
    rows = []
    with open(CSV_PATH, newline='') as handle:
        for row in csv.DictReader(handle):
            try:
                date = datetime.strptime(row['observation_date'], '%Y-%m-%d').date()
                rate = float(row['MORTGAGE30US'])
            except (KeyError, ValueError):
                continue

            rows.append((date, rate))

    return rows


def get_all_rates():
    """Returns one observation per month/year as a JSON-ready list of {'date': 'MM-DD-YY', 'rate': float}."""
    seen_months = set()
    results = []

    for date, rate in _load_rows():
        month_year = (date.year, date.month)
        if month_year in seen_months:
            continue

        seen_months.add(month_year)
        results.append({'date': date.strftime('%m-%d-%y'), 'rate': rate})

    return results


def get_rate(date_str) -> Result[float, str]:
    """Parses date_str as loosely as possible and returns the rate for the closest observation date."""
    try:
        target = date_parser.parse(date_str, fuzzy=True).date()
    except (date_parser.ParserError, ValueError, OverflowError, TypeError):
        return Err(f"Couldn't find a month/day/year in: {date_str}")

    rows = _load_rows()
    if not rows:
        return Err("No rate data available")

    closest_date, closest_rate = min(rows, key=lambda row: abs((row[0] - target).days))
    return Ok(closest_rate)
