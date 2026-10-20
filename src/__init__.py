from datetime import date, datetime, timedelta
from typing import List, Dict, Any
import functools
import re
from csv_diff import load_csv, compare
import io
import openpyxl
import requests
import sys
import time
import csv

"""
Schemes are often badly capitalized
This is a list of words considered
exceptional and always follow the given
case
"""
CASE_EXCEPTIONS = [
    "AAA",
    "AI",
    "APR",
    "ASEAN",
    "AUG",
    "BEES",
    "BNP",
    "BSE",
    "CCF",
    "CPSE",
    "CRISIL",
    "DEC",
    "DSP",
    "EAFE",
    "ELSS",
    "EQ",
    "EQQQ",
    "ESG",
    "ETF",
    "FANG",
    "FEB",
    "FMCG",
    "GSF",
    "HDFC",
    "HSBC",
    "IBX",
    "ICICI",
    "IDBI",
    "IIFL",
    "IPO",
    "IT",
    "ITI",
    "JAN",
    "JM",
    "JUL",
    "JUN",
    "LIC",
    "MAR",
    "MAY",
    "MF",
    "MNC",
    "MSCI",
    "NASDAQ",
    "NJ",
    "NOV",
    "NSE",
    "NYSE",
    "OCT",
    "PE",
    "PGIM",
    "PSU",
    "REIT",
    "SBI",
    "SDL",
    "SEC",
    "SENSEX",
    "SEP",
    "TRUSTMF",
    "ULIS",
    "US",
    "UTI",
    # Non-CAPS exceptions
    "WhiteOak",
    "and",
    "of",
    "with",
    "as",
    "has",
    "to",
    "BeES",
    "30s",
    "40s",
    "50s",
    "60s",
    "70s",
    "FoF",
    "Off-shore",
    "Children's",
]

API_URL = "https://www.amfiindia.com/api/populate-te-rdata-revised"
MAX_ATTEMPTS = 6
MAX_ROW_DROP = 0.1

# Column headers used in the AMFI TER export since April 2026
FIELDS = [
    "Base Expense Ratio (BER) (%)",
    "Brokerage cost (%)",
    "Transaction Cost incurred for the purpose of execution of trade (%)",
    "Statutory Levies (including GST) (%)",
    "Total TER (%)",
]
PLANS = ["Regular Plan", "Direct Plan"]

CODE_HEADER = "NSDL Scheme Code"
FINAL_HEADERS = [CODE_HEADER, "Scheme Name"] + [f"{plan} - {field}" for plan in PLANS for field in FIELDS]
TOTAL_TER_HEADER = FINAL_HEADERS[-1]
EXPORT_HEADERS = [CODE_HEADER, "Scheme Name", "TER Date"] + FINAL_HEADERS[2:]

"""
Prints Diff between TER CSV files
using only the Direct Plans total pricing as change
identifier. Rows are matched by NSDL Scheme Code when
both files have it (v2), and by Scheme Name otherwise.
"""


def generate_diff(old_file, new_file, outf=sys.stdout):
    with open(old_file) as old, open(new_file) as new:
        headers = [next(csv.reader(f), []) for f in (old, new)]
        key = CODE_HEADER if all(CODE_HEADER in h for h in headers) else "Scheme Name"
        old.seek(0)
        new.seek(0)
        old_rows, new_rows = load_csv(old, key=key), load_csv(new, key=key)
    diff = compare(old_rows, new_rows)

    for row in diff["changed"]:
        if TOTAL_TER_HEADER in row["changes"]:
            name = new_rows[row["key"]]["Scheme Name"]
            old, new = row["changes"][TOTAL_TER_HEADER]
            verb = "lowered" if float(new) <= float(old) else "increased"
            print(f"- \"{name}\" {verb} its TER from {old} to {new}", file=outf)


"""
Reads the TER rows from an AMFI Excel export.
Yields [NSDL Scheme Code, Scheme Name, TER Date] followed by
- 5 values for the Regular plan pricing breakdown
- 5 values for the Direct plan pricing breakdown
The sheet ends with disclaimer rows, which are skipped.
"""


def read_ter_rows(xlsx, headers=EXPORT_HEADERS):
    book = openpyxl.load_workbook(io.BytesIO(xlsx), read_only=True, data_only=True)
    rows = book.worksheets[0].iter_rows(values_only=True)
    header = [str(h or "").strip() for h in next(rows, ())]
    missing = [h for h in headers if h not in header]
    if missing:
        raise ValueError(f"Columns missing from AMFI export: {missing}")
    columns = [header.index(h) for h in headers]
    for row in rows:
        if len(row) >= len(header) and isinstance(row[columns[headers.index("TER Date")]], datetime):
            yield [row[i] for i in columns]


"""
Parses TER rows to a dict keyed by NSDL Scheme Code,
or by canonical name for rows without a code (v1).
The dict contains: [Date, Code, Scheme Name] followed
by the 10 float values. AMFI publishes one row per
scheme per date, so only the most recent row is kept.
AMFI has reused a code for different schemes on the
same date, so those ties keep the first name.
"""


def parse_ter(rows) -> Dict[str, List[Any]]:
    ret_d, collisions = {}, set()
    for code, scheme_name, scheme_date, *values in rows:
        code = str(code).strip() if code else None
        scheme_name = canonical_name(str(scheme_name).strip())
        scheme_date = scheme_date.date()
        key = code or scheme_name
        if key in ret_d:
            last_date, _, last_name = ret_d[key][:3]
            if scheme_date == last_date and scheme_name != last_name:
                collisions.add(key)
            if scheme_date < last_date or (scheme_date == last_date and scheme_name > last_name):
                continue
        ret_d[key] = [scheme_date, code, scheme_name] + [float(v or 0) for v in values]
    for key in sorted(collisions):
        print(f"Warning: {key} is used by several schemes, kept {ret_d[key][2]}", file=sys.stderr)
    return ret_d


"""
Downloads the Excel export of a month's TER data.
AMFI sometimes returns an error page with a 200
status, so anything that is not a workbook is retried.
"""


def fetch_ter_xlsx(session, month):
    params = {
        "MF_ID": "All",
        "Month": month.strftime("%m-%Y"),
        "strCat": "-1",
        "strType": "-1",
        "excel": "true",
    }
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = session.get(API_URL, params=params, timeout=300)
            response.raise_for_status()
            if not response.content.startswith(b"PK"):
                raise ValueError("response is not an Excel workbook")
            return response.content
        except (requests.RequestException, ValueError) as e:
            if attempt == MAX_ATTEMPTS - 1:
                raise
            print(f"Retrying {month:%m-%Y}: {e}", file=sys.stderr)
            time.sleep(2**attempt)


# This parses the TER based on the provided date
# as well as the previous month. This is because
# the TER is only published on the date it is changed,
# so the last known value for schemes without changes
# this month would be found in the previous month
def fetch_combined_ter(session, date):
    prev_month = date.replace(day=1) - timedelta(days=1)
    ter = parse_ter(
        list(read_ter_rows(fetch_ter_xlsx(session, prev_month)))
        + list(read_ter_rows(fetch_ter_xlsx(session, date)))
    )
    if not ter:
        raise ValueError("No TER records returned by AMFI")
    return [row[1:] for row in ter.values()]


def get_ters(session):
    # the timedelta is to account for the delay in publishing.
    # so we always check the TER for yesterday
    d = date.today() - timedelta(days=1)
    return fetch_combined_ter(session, d)


"""
Raises if the new dataset has lost more than
MAX_ROW_DROP of the rows in the existing CSV, which
usually means AMFI returned partial data.
"""


def check_row_count(old_file, data, max_drop=MAX_ROW_DROP):
    try:
        with open(old_file, newline="", encoding="utf-8") as f:
            old_count = sum(1 for _ in csv.reader(f)) - 1
    except FileNotFoundError:
        return
    if len(data) < old_count * (1 - max_drop):
        raise ValueError(
            f"Row count dropped from {old_count} to {len(data)}, more than {max_drop:.0%}"
        )


def write_csv(filename, data, headers=FINAL_HEADERS):
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        spamwriter = csv.writer(
            csvfile,
            delimiter=",",
            quotechar='"',
            quoting=csv.QUOTE_NONNUMERIC,
            lineterminator="\n",
        )
        spamwriter.writerow(headers)
        for row in data:
            spamwriter.writerow(row)


@functools.cache
def canonical_name(scheme_name):
    # Generate replacements
    replacements = {}
    for word in CASE_EXCEPTIONS:
        replacements[word.lower()] = word

    # custom replacement function
    def replace(m):
        return replacements[m.group(0).lower()]

    # Generate regex that replaces
    exceptions = "|".join(replacements.keys())
    regex = re.compile(f"\\b({exceptions})\\b", flags=re.IGNORECASE)
    final = re.sub(regex, replace, scheme_name.title())
    if scheme_name != final:
        print(f"Changed {scheme_name} to {final}", file=sys.stderr)
    return final
