from datetime import date, timedelta
from typing import List, Dict, Any
import functools
import re
from csv_diff import load_csv, compare
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
PAGE_SIZE = 5000
MAX_ATTEMPTS = 6
MAX_ROW_DROP = 0.1

# AMFI JSON fields mapped to the column headers used on the AMFI website
FIELDS = {
    "BER": "Base Expense Ratio (BER) (%)",
    "BrokerageCost": "Brokerage cost (%)",
    "TransactionCost": "Transaction Cost incurred for the purpose of execution of trade (%)",
    "StatutoryLevies": "Statutory Levies (including GST) (%)",
    "TER": "Total TER (%)",
}
PLANS = {"R": "Regular Plan", "D": "Direct Plan"}

FINAL_HEADERS = ["Scheme Name"] + [
    f"{plan} - {header}" for plan in PLANS.values() for header in FIELDS.values()
]
TOTAL_TER_HEADER = FINAL_HEADERS[-1]

"""
Prints Diff between TER CSV files
using only the Direct Plans total pricing as change
identifier.
"""


def generate_diff(old_file, new_file, outf=sys.stdout):
    with open(old_file) as old, open(new_file) as new:
        diff = compare(
            load_csv(old, key="Scheme Name"),
            load_csv(new, key="Scheme Name"),
        )

    for row in diff["changed"]:
        if TOTAL_TER_HEADER in row["changes"]:
            old, new = row["changes"][TOTAL_TER_HEADER]
            verb = "lowered" if float(new) <= float(old) else "increased"
            print(f"- \"{row['key']}\" {verb} its TER from {old} to {new}", file=outf)


"""
Parses TER records from the AMFI JSON API
to a dictionary. The dict contains:
[Date, Scheme Name(str)] followed by:
- 5 float values for the Regular plan pricing breakdown
- 5 float values for the Direct plan pricing breakdown

AMFI publishes one record per scheme per date,
so only the most recent record is kept.
The keys of the dict are the scheme name.
"""


def parse_ter(records) -> Dict[str, List[Any]]:
    ret_d = {}
    for record in records:
        scheme_name = record["Scheme_Name"].strip()
        scheme_date = date.fromisoformat(record["TER_Date"][:10])
        values = [
            float(record[f"{prefix}_{field}"] or 0)
            for prefix in PLANS
            for field in FIELDS
        ]
        if scheme_name in ret_d and scheme_date < ret_d[scheme_name][0]:
            continue
        ret_d[scheme_name] = [scheme_date, scheme_name] + values
    return ret_d


"""
Fetches a single page of TER records from AMFI.
AMFI rate-limits by returning invalid JSON with
a 200 status, so those responses are retried.
"""


def fetch_ter_page(session, month, page):
    params = {
        "MF_ID": "All",
        "Month": month.strftime("%m-%Y"),
        "strCat": "-1",
        "strType": "-1",
        "page": page,
        "pageSize": PAGE_SIZE,
    }
    for attempt in range(MAX_ATTEMPTS):
        try:
            response = session.get(API_URL, params=params, timeout=120)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as e:
            if attempt == MAX_ATTEMPTS - 1:
                raise
            print(f"Retrying {month:%m-%Y} page {page}: {e}", file=sys.stderr)
            time.sleep(2**attempt)


def fetch_ter_records(session, month):
    records, page, page_count = [], 1, 1
    while page <= page_count:
        payload = fetch_ter_page(session, month, page)
        records += payload.get("data") or []
        page_count = (payload.get("meta") or {}).get("pageCount") or 1
        page += 1
    return records


# This parses the TER based on the provided date
# as well as the previous month. This is because
# the TER is only published on the date it is changed,
# so the last known value for schemes without changes
# this month would be found in the previous month
def fetch_combined_ter(session, date):
    prev_month = date.replace(day=1) - timedelta(days=1)
    ter = parse_ter(
        fetch_ter_records(session, prev_month) + fetch_ter_records(session, date)
    )
    if not ter:
        raise ValueError("No TER records returned by AMFI")
    return [[canonical_name(row[1])] + row[2:] for row in ter.values()]


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


def write_csv(filename, data):
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        spamwriter = csv.writer(
            csvfile,
            delimiter=",",
            quotechar='"',
            quoting=csv.QUOTE_NONNUMERIC,
            lineterminator="\n",
        )
        spamwriter.writerow(FINAL_HEADERS)
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
