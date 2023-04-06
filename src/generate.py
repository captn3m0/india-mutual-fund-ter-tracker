from datetime import date, datetime, timedelta
import http.client
import html2csv
import sys
import csv

conn = http.client.HTTPSConnection("www.amfiindia.com")

EXPECTED_HEADERS = [
    "Scheme Name",
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

FINAL_HEADERS = [EXPECTED_HEADERS[0]] + EXPECTED_HEADERS[2:]


def fetch_ter(date, scheme_category):
    d = date.strftime("%-m-%Y")
    payload = f"MonthTER={d}&MF_ID=-1&NAV_ID=1&SchemeCat_Desc={scheme_category}"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    conn.request("POST", "/modules/LoadTERData", payload, headers)
    res = conn.getresponse()
    convertor = html2csv.Converter()
    data = res.read().decode("utf-8")
    tables = convertor.convert_to_list(data)
    if len(tables) == 0 or len(tables[0]) == 0:
        return []
    if tables[0][0] != EXPECTED_HEADERS:
        return []
    d = date.strftime("%d-%b-%Y")
    # Drop the Date, and only keep rows with matching date
    return [
        [row[0]] + [float(ter) for ter in row[2:]]
        for row in tables[0][1:]
        if row[1] == date.strftime("%d-%b-%Y")
    ]


def get_ters(scheme_categories):
    data = []
    for scheme_category in scheme_categories:
        # the timedelta is to account for the delay in publishing.
        # so we check the TER for yesterday
        d = date.today() - timedelta(days=1)
        data += fetch_ter(d, scheme_category)
    return data


def write_csv(filename, data):
    with open(filename, "w") as csvfile:
        spamwriter = csv.writer(
            csvfile, delimiter=",", quotechar='"', quoting=csv.QUOTE_NONNUMERIC
        )
        spamwriter.writerow(FINAL_HEADERS)
        for row in data:
            spamwriter.writerow(row)


if __name__ == "__main__":
    data = get_ters(range(1, 70))
    data = sorted(data, key=lambda row: row[0].lower())
    write_csv("data.csv", data)
