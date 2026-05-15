import requests
import gzip
import xml.etree.ElementTree as ET
from io import BytesIO
import re

# =========================
# LOAD CONFIG FILES
# =========================

with open("epg_sources.txt", "r") as f:
    SOURCES = [x.strip() for x in f if x.strip()]

with open("master_channels.txt", "r") as f:
    MASTER_LIST = [x.strip() for x in f if x.strip()]

# =========================
# NORMALIZE (MATCH ONLY)
# =========================

def norm(text):
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text.strip()

MASTER_SET = set(norm(x) for x in MASTER_LIST)

# =========================
# FETCH XML
# =========================

def fetch(url):
    print(f"Fetching {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()

    if url.endswith(".gz"):
        return ET.parse(BytesIO(gzip.decompress(r.content)))

    return ET.ElementTree(ET.fromstring(r.content))

# =========================
# LOAD ALL SOURCES
# =========================

trees = []
for url in SOURCES:
    try:
        trees.append(fetch(url))
    except Exception as e:
        print(f"Failed {url}: {e}")

# =========================
# INDEX CHANNELS + PROGRAMMES
# =========================

channels = {}
programmes = {}

for tree in trees:
    root = tree.getroot()

    for ch in root.findall("channel"):
        cid = ch.get("id")
        if cid:
            channels[cid] = ch

    for p in root.findall("programme"):
        cid = p.get("channel")
        if cid:
            programmes.setdefault(cid, []).append(p)

# =========================
# MATCH FUNCTION
# =========================

def is_master(ch):
    cid = ch.get("id", "")
    name = "".join(ch.itertext())
    return norm(cid) in MASTER_SET or norm(name) in MASTER_SET

# =========================
# BUILD OUTPUT XML
# =========================

merged_root = ET.Element("tv")
local_root = ET.Element("tv")

for cid, ch in channels.items():
    merged_root.append(ch)

    if is_master(ch):
        local_root.append(ch)

        for p in programmes.get(cid, []):
            local_root.append(p)

# =========================
# SAVE OUTPUTS (XML + GZ)
# =========================

merged_xml = ET.tostring(merged_root, encoding="utf-8", xml_declaration=True)
local_xml = ET.tostring(local_root, encoding="utf-8", xml_declaration=True)

with open("merged.xml", "wb") as f:
    f.write(merged_xml)

with open("local.xml", "wb") as f:
    f.write(local_xml)

with gzip.open("merged.xml.gz", "wb") as f:
    f.write(merged_xml)

with gzip.open("local.xml.gz", "wb") as f:
    f.write(local_xml)

print("Done")
print(f"Merged channels: {len(channels)}")
print(f"Local channels: {sum(1 for c in channels.values() if is_master(c))}")
