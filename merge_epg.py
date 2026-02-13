#!/usr/bin/env python3
import gzip
import datetime
import requests
from lxml import etree
from io import BytesIO

# =========================
# CONFIGURATION
# =========================
EPG_SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz"
]

OUTPUT_XML = "merged.xml"
OUTPUT_GZ = "merged.xml.gz"
INDEX_HTML = "index.html"

DAYS_AHEAD = 5  # Only keep 5 days of programs

# =========================
# HELPER FUNCTIONS
# =========================
def download_gz(url):
    print(f"Downloading {url} ...")
    r = requests.get(url, stream=True, timeout=None)
    r.raise_for_status()
    return gzip.decompress(r.content)

def parse_xml(content):
    return etree.parse(BytesIO(content))

def filter_programs(tv_element):
    now = datetime.datetime.utcnow()
    cutoff = now + datetime.timedelta(days=DAYS_AHEAD)
    for channel in tv_element.findall("channel"):
        programs = channel.xpath("./programme")
        for prog in programs:
            start = prog.get("start")
            if start:
                prog_time = datetime.datetime.strptime(start[:14], "%Y%m%d%H%M%S")
                if prog_time > cutoff:
                    channel.remove(prog)
    return tv_element

def deduplicate_channels(tv_element):
    seen_ids = set()
    for channel in tv_element.findall("channel"):
        cid = channel.get("id")
        if cid in seen_ids:
            tv_element.remove(channel)
        else:
            seen_ids.add(cid)
    return tv_element

# =========================
# MERGE XML SOURCES
# =========================
root = etree.Element("tv")
for url in EPG_SOURCES:
    try:
        content = download_gz(url)
        tree = parse_xml(content)
        tv = tree.getroot()
        # Merge channels
        for ch in tv.findall("channel"):
            root.append(ch)
        # Merge programs
        for prog in tv.findall("programme"):
            root.append(prog)
    except Exception as e:
        print(f"Failed {url}: {e}")

# Filter old programs
root = filter_programs(root)
# Deduplicate channels
root = deduplicate_channels(root)

# =========================
# WRITE MERGED XML AND GZ
# =========================
tree = etree.ElementTree(root)
tree.write(OUTPUT_XML, encoding="UTF-8", xml_declaration=True)
with open(OUTPUT_XML, "rb") as f_in, gzip.open(OUTPUT_GZ, "wb", compresslevel=9) as f_out:
    f_out.writelines(f_in)

# =========================
# UPDATE INDEX.HTML WITH STATUS
# =========================
local_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
channels_count = len(root.findall("channel"))
programs_count = len(root.findall("programme"))

html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>EPG Merge Status</title>
</head>
<body>
<h1>EPG Merge Status</h1>
<p>Last updated: {local_time}</p>
<p>Channels kept: {channels_count}</p>
<p>Programs kept: {programs_count}</p>
</body>
</html>
"""

with open(INDEX_HTML, "w", encoding="utf-8") as f:
    f.write(html_content)

print(f"EPG merge completed")
print(f"Last updated: {local_time}")
print(f"Channels kept: {channels_count}")
print(f"Programs kept: {programs_count}")

