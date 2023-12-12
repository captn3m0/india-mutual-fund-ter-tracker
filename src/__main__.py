import http.client
from . import get_ters, write_csv, generate_diff
import sys

FILENAME = "data.csv"
conn = http.client.HTTPSConnection("www.amfiindia.com")

data = get_ters(conn)
data = sorted(data, key=lambda row: row[0].lower())
write_csv(FILENAME, data)
# Pass a second argument for the old file version
# to generate a diff to stdout
if len(sys.argv) >= 2:
    generate_diff(sys.argv[1], FILENAME)
