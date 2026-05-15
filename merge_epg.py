import requests
import gzip
import xml.etree.ElementTree as ET
from io import BytesIO
import re

# =========================
# SOURCES
# =========================
SOURCES = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz",
    "https://raw.githubusercontent.com/MuazT/EPG-Guide/master/ArabicEPG.xml",
    "https://www.open-epg.com/files/egypt2.xml.gz",
]

# =========================
# YOUR MASTER LIST (LOCAL ONLY USED FOR LOCAL.XML FILTER)
# =========================
LOCAL_MASTER = [
    "WRC-DT","COZI TV","CRIMES","Oxygen",
    "WTTG-DT","BUZZR","Start TV",
    "WJLA-DT","Charge!","Comet","ROAR",
    "WUSA-DT","Crime TV","Quest","The Nest","QVC",
    "WBAL-DT","MeTV","Story Television","GetTV",
    "WFDC-DT","GRIT","UniMas",
    "WDCA-DT","Movies!","Heroes & Icons","Fox Weather",
    "MPT-DT","MPT-2","MPT Kids","NHK World Japan",
    "WDVM-SD",
    "WETA-HD","WETA UK","WETA Kids","WORLD Channel","Metro",
    "WHUT","PBS Kids",
    "WZDC","XITOS",
    "WDCW-DT","Antenna TV",
    "Bounce","Court TV","Laff","Busted","HSN","AltaVsn","DEFY",
    "WNUV-DT","Telexitos",
]

# =========================
# HELPERS (IMPORTANT FIX: FLEX MATCHING)
# =========================
def norm(text):
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text.strip()

def download_xml(url):
    print(f"Fetching {url}")
    r = requests.get(url, timeout=60)
    r.raise_for_status()

    if url.endswith(".gz"):
        return ET.parse(BytesIO(gzip.decompress(r.content)))
    return ET.ElementTree(ET.fromstring(r.content))

# =========================
# LOAD ALL DATA
# =========================
trees = []
for url in SOURCES:
    try:
        trees.append(download_xml(url))
    except Exception as e:
        print(f"Failed {url}: {e}")

# =========================
# INDEX ALL CHANNELS
# =========================
channel_map = {}
programme_map = {}

for tree in trees:
    root = tree.getroot()

    for ch in root.findall("channel"):
        cid = ch.get("id")
        if cid:
            channel_map[cid] = ch

    for p in root.findall("programme"):
        cid = p.get("channel")
        if cid:
            programme_map.setdefault(cid, []).append(p)

# =========================
# BUILD MASTER LOOKUP (LOCAL MATCHING ONLY)
# =========================
local_set = set(norm(x) for x in LOCAL_MASTER)

def is_local(channel_obj):
    if channel_obj is None:
        return False

    cid = channel_obj.get("id", "")
    display = "".join(channel_obj.itertext())

    return norm(cid) in local_set or norm(display) in local_set

# =========================
# BUILD OUTPUT ROOTS
# =========================
merged_root = ET.Element("tv")
local_root = ET.Element("tv")

merged_count = 0
local_count = 0

used_channels = set()

# =========================
# BUILD MERGED (ONLY MASTER LIST FILTER)
# =========================
for cid, ch in channel_map.items():
    display = "".join(ch.itertext())

    # MERGED: keep ALL channels but only from sources (you already do this)
    merged_root.append(ch)
    merged_count += 1

    # LOCAL FILTER
    if is_local(ch):
        local_root.append(ch)
        local_count += 1
        used_channels.add(cid)

        for prog in programme_map.get(cid, []):
            local_root.append(prog)

# =========================
# SAVE OUTPUT
# =========================
ET.ElementTree(merged_root).write("merged.xml", encoding="utf-8", xml_declaration=True)
ET.ElementTree(local_root).write("local.xml", encoding="utf-8", xml_declaration=True)

print("\nDone.")
print(f"Merged channels: {merged_count}")
print(f"Local channels: {local_count}")
