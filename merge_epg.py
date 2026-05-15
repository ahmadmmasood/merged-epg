import requests
import gzip
import xml.etree.ElementTree as ET
import re

# =========================
# LOAD SOURCES (FROM TXT)
# =========================
def load_sources(file="epg_sources.txt"):
    with open(file, "r", encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]

SOURCES = load_sources()

# =========================
# LOAD MASTER CHANNELS
# =========================
def load_master(file="master_channels.txt"):
    with open(file, "r", encoding="utf-8") as f:
        return [
            line.strip()
            for line in f
            if line.strip() and not line.startswith("#")
        ]

LOCAL_MASTER = load_master()

# =========================
# NORMALIZATION
# =========================
def words(s):
    return set(re.findall(r"[a-z0-9]+", s.lower()))

LOCAL_WORDS = [(x, words(x)) for x in LOCAL_MASTER]

# =========================
# FETCH XML
# =========================
def fetch_xml(url):
    print(f"Fetching {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()

    if url.endswith(".gz"):
        return ET.fromstring(gzip.decompress(r.content))
    return ET.fromstring(r.content)

# =========================
# MATCHING (SAFE + FLEXIBLE)
# =========================
def match_score(text):
    ch_words = words(text)
    score = 0

    for _, lw in LOCAL_WORDS:
        overlap = ch_words & lw

        if len(overlap) >= 2:
            score += 3
        elif len(overlap) == 1:
            score += 1

    return score

def is_local(text):
    return match_score(text) >= 2

# =========================
# MERGE ALL DATA
# =========================
all_channels = {}
all_programmes = []

for url in SOURCES:
    root = fetch_xml(url)

    for ch in root.findall("channel"):
        cid = ch.attrib.get("id")
        all_channels[cid] = ch

    for p in root.findall("programme"):
        all_programmes.append(p)

print(f"Total channels: {len(all_channels)}")
print(f"Total programmes: {len(all_programmes)}")

# =========================
# FILTER LOCAL
# =========================
local_channels = {}

for ch in all_channels.values():
    dn = ch.find("display-name")
    name = dn.text if dn is not None else ""
    cid = ch.attrib.get("id", "")

    if is_local(f"{name} {cid}"):
        local_channels[cid] = ch

local_ids = set(local_channels.keys())

local_programmes = [
    p for p in all_programmes
    if p.attrib.get("channel") in local_ids
]

# =========================
# DEBUG
# =========================
print("\n--- LOCAL DEBUG ---")
print("LOCAL MASTER:", len(LOCAL_MASTER))
print("LOCAL CHANNELS:", len(local_channels))
print("LOCAL PROGRAMMES:", len(local_programmes))

# =========================
# WRITE OUTPUT
# =========================
def write_xml(name, channels, programmes):
    tv = ET.Element("tv")

    for ch in channels.values():
        tv.append(ch)

    for p in programmes:
        tv.append(p)

    ET.ElementTree(tv).write(name, encoding="utf-8", xml_declaration=True)

write_xml("merged.xml", all_channels, all_programmes)
write_xml("local.xml", local_channels, local_programmes)

print("Done")
