from datetime import date, datetime, timedelta
from typing import List, Dict, Any
import functools
import re
from csv_diff import load_csv, compare
import http.client
import html2csv
import sys
import time
import gzip
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

EXPECTED_HEADERS = [
    "Scheme Name",
    "Scheme Type",
    "Scheme Category",
    "TER Date",
    "Regular Plan - Base TER (%)",
    "Regular Plan - Additional expense as per Regulation 52(6A)(b) (%)",
    "Regular Plan - Additional expense as per Regulation 52(6A)(c) (%)",
    "Regular Plan - GST (%)",
    "Regular Plan - Total TER (%)",
    "Direct Plan - Base TER (%)",
    "Direct Plan - Additional expense as per Regulation 52(6A)(b) (%)",
    "Direct Plan - Additional expense as per Regulation 52(6A)(c) (%)",
    "Direct Plan - GST (%)",
    "Direct Plan - Total TER (%)",
]

# We can look at using Type/Category later
FINAL_HEADERS = [EXPECTED_HEADERS[0]] + EXPECTED_HEADERS[4:]

"""
Prints Diff between TER CSV files
using only the Direct Plans total pricing as change
identifier.
"""


def generate_diff(old_file, new_file, outf=sys.stdout):
    diff = compare(
        load_csv(open(old_file), key="Scheme Name"),
        load_csv(open(new_file), key="Scheme Name"),
    )

    total_ter_header = EXPECTED_HEADERS[-1]
    for row in diff["changed"]:
        if total_ter_header in row["changes"]:
            old = row["changes"][total_ter_header][0]
            new = row["changes"][total_ter_header][1]
            if new <= old:
                print(
                    f"- \"{row['key']}\" lowered its TER from {old} to {new}", file=outf
                )
            else:
                print(
                    f"- \"{row['key']}\" increased its TER from {old} to {new}",
                    file=outf,
                )


"""
Uses HTML response from the AMFI
website to parse the TER data from the
table to a dictionary. The dict contains:
[Datetime, Scheme Name(str)] followed by:
- 5 float values for the Regular plan pricing breakdown
- 5 float values for the Direct plan pricing breakdown

The keys of the dict are the scheme name.
"""


def parse_ter(html) -> Dict[str, List[Any]]:
    ret_d = {}
    convertor = html2csv.Converter()
    tables = convertor.convert_to_list(html)
    if len(tables) == 0 or len(tables[0]) == 0:
        raise BaseException("No tables found")
    if tables[0][0] != EXPECTED_HEADERS:
        raise BaseException("Headers don't match")
    for row in tables[0][1:]:
        scheme_name = row[0]
        scheme_date = datetime.strptime(row[3], "%d-%b-%Y").date()
        data = [scheme_date, scheme_name] + [float(ter) for ter in row[4:]]
        if scheme_name in ret_d and scheme_date >= ret_d[scheme_name][0]:
            ret_d[scheme_name] = data
        else:
            ret_d[scheme_name] = data
    return ret_d


"""
Makes a HTTP request to the AMFI website
to fetch the TER on a given date
Only uses the month and year as needed from the date
Returns the complete HTML response
"""


def fetch_ter_html(conn, date):
    # Month and Year
    d = date.strftime("%-m-%Y")
    payload = f"MonthTER={d}&MF_ID=-1&NAV_ID=1&SchemeCat_Desc=-1"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept-Encoding": "gzip",
    }
    conn.request("POST", "/modules/LoadTERData", payload, headers)
    return gzip.decompress(conn.getresponse().read()).decode("utf-8")


# This parses the TER based on the provided date
# as well as the last date of the previous month
# This is because the TER is only published
# on the date it is changed, and in case of no
# changes on a given date, the last known
# value would be found in the previous month
# so we fetch the previous month
# and update it with the latest values
def fetch_combined_ter(conn, date):
    d1 = date.replace(day=1)  # First date of current month
    prev_month = d1 - timedelta(days=1)  # Last date of previous month
    ter = parse_ter(fetch_ter_html(conn, prev_month))

    # Get TER for present month and update
    new_ter = parse_ter(fetch_ter_html(conn, date))
    ter.update(new_ter)

    return [[canonical_name(row[1])] + row[2:] for row in ter.values()]


def get_ters(conn):
    # the timedelta is to account for the delay in publishing.
    # so we always check the TER for yesterday
    # Since the website only allows Y-M (no day)
    # This is important on the first of the month, where
    # no data is available, except on the last date of previous month
    d = date.today() - timedelta(days=1)
    return fetch_combined_ter(conn, d)


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
