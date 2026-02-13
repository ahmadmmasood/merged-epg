#!/usr/bin/env python3
import gzip
from lxml import etree
from datetime import datetime
import pytz

# -----------------------------
# CONFIG: Only keep local + important channels
# -----------------------------
LOCAL_CHANNELS = {
    "HUT-TV", "WRC-TV", "WZDC-CD", "WTTG", "WHUT-TV", "WDCA",
    "WDCN-LD", "WJLA-TV", "WJAL", "WUSA", "WDCO-CD", "WFDC-DT",
    "WDCW", "WMPT", "WDDN-LD", "WDWA-LD", "WDVM-TV", "WETA-TV",
    "WRZB-LD", "W13DW-D", "W10DE-D", "WWTD-LD", "WMDO-CD",
    "WPXW-TV", "WIAV-CD", "WFPT"
}

INPUT_URLS = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz"
]

OUTPUT_XML = "merged.xml.gz"
INDEX_HTML = "index.html"

# -----------------------------
# Function to download and parse XML
# -----------------------------
import requests
def download_xml(url):
    print(f"Downloading {url} ...")
    r = requests.get(url, timeout=None)  # no timeout
    r.raise_for_status()
    return etree.fromstring(r.content)

# -----------------------------
# Merge XMLs
# -----------------------------
merged = etree.Element("tv")

channels_kept = 0
programs_kept = 0

for url in INPUT_URLS:
    try:
        root = download_xml(url)
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        continue

    for channel in root.findall("channel"):
        if channel.get("id") not in LOCAL_CHANNELS:
            continue
        merged.append(channel)
        channels_kept += 1

    for programme in root.findall("programme"):
        if programme.get("channel") in LOCAL_CHANNELS:
            merged.append(programme)
            programs_kept += 1

# -----------------------------
# Write gzipped XML
# -----------------------------
with gzip.open(OUTPUT_XML, "wb") as f:
    f.write(etree.tostring(merged, encoding="UTF-8", xml_declaration=True))

# -----------------------------
# Update index.html with local time
# -----------------------------
local_time = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z")
html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>EPG Merge Status</title>
</head>
<body>
    <h1>EPG merge completed</h1>
    <p>Last updated: {local_time}</p>
    <p>Channels kept: {channels_kept}</p>
    <p>Programs kept: {programs_kept}</p>
</body>
</html>"""

with open(INDEX_HTML, "w") as f:
    f.write(html_content)

print(f"EPG merge completed\nLast updated: {local_time}\nChannels kept: {channels_kept}\nPrograms kept: {programs_kept}")

