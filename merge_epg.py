import requests
import gzip
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime, timedelta
import pytz

# Configuration
EPG_SOURCES_FILE = "epg_sources.txt"
MASTER_CHANNELS_FILE = "master_channels.txt"
MERGED_OUTPUT = "merged.xml"
LOCAL_OUTPUT = "local.xml"
DAYS_TO_INCLUDE = 3  # Optional: only include N days of programming
LOCAL_SECTION_HEADER = "#LOCAL CHANNELS – DC / BALTIMORE OTA"

# Helper functions
def fetch_gz_xml(url):
    print(f"Fetching {url} ...")
    r = requests.get(url)
    r.raise_for_status()
    return ET.parse(BytesIO(gzip.decompress(r.content)))

def read_master_channels():
    master_channels = {"local": set(), "other": set()}
    current_section = None
    with open(MASTER_CHANNELS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("#"):
                if LOCAL_SECTION_HEADER in line:
                    current_section = "local"
                else:
                    current_section = None
                continue
            if not line or current_section is None:
                continue
            master_channels["local"].add(line.lower())
    return master_channels

def channel_matches_master(channel_name, master_list):
    # Partial contains match
    name = channel_name.lower()
    return any(m in name for m in master_list)

def filter_programs_for_days(programs, days):
    now = datetime.now(pytz.utc)
    cutoff = now + timedelta(days=days)
    filtered = []
    for prog in programs:
        start_str = prog.get("start")
        stop_str = prog.get("stop")
        try:
            start_dt = datetime.strptime(start_str, "%Y%m%d%H%M%S %z")
            stop_dt = datetime.strptime(stop_str, "%Y%m%d%H%M%S %z")
        except Exception:
            continue
        if start_dt <= cutoff:
            filtered.append(prog)
    return filtered

# Load EPG sources
print("Loading EPG sources...")
with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
    epg_sources = [line.strip() for line in f if line.strip()]

all_channels = {}
all_programs = []

for url in epg_sources:
    tree = fetch_gz_xml(url)
    root = tree.getroot()
    for ch in root.findall("channel"):
        ch_id = ch.get("id")
        all_channels[ch_id] = ET.tostring(ch, encoding="unicode")
    for prog in root.findall("programme"):
        all_programs.append(prog)

print(f"Total channels fetched: {len(all_channels)}")
print(f"Total programmes fetched: {len(all_programs)}")

# Save merged XML
merged_root = ET.Element("tv")
for ch_xml in all_channels.values():
    merged_root.append(ET.fromstring(ch_xml))
for prog in all_programs:
    merged_root.append(prog)

merged_tree = ET.ElementTree(merged_root)
merged_tree.write(MERGED_OUTPUT, encoding="utf-8", xml_declaration=True)
with gzip.open(MERGED_OUTPUT + ".gz", "wb") as f:
    f.write(ET.tostring(merged_root, encoding="utf-8"))
print("Saved merged XML.")

# Filter local channels
master_channels = read_master_channels()
local_channels = {}
for ch_id, ch_xml in all_channels.items():
    disp_name = ET.fromstring(ch_xml).findtext("display-name")
    if disp_name and channel_matches_master(disp_name, master_channels["local"]):
        local_channels[ch_id] = ch_xml

print(f"Local channels matched: {list(local_channels.keys())}")

local_programs = [prog for prog in all_programs if prog.get("channel") in local_channels]
if DAYS_TO_INCLUDE:
    local_programs = filter_programs_for_days(local_programs, DAYS_TO_INCLUDE)

# Save local XML
local_root = ET.Element("tv")
for ch_xml in local_channels.values():
    local_root.append(ET.fromstring(ch_xml))
for prog in local_programs:
    local_root.append(prog)

local_tree = ET.ElementTree(local_root)
local_tree.write(LOCAL_OUTPUT, encoding="utf-8", xml_declaration=True)
with gzip.open(LOCAL_OUTPUT + ".gz", "wb") as f:
    f.write(ET.tostring(local_root, encoding="utf-8"))

print(f"Local channels included: {len(local_channels)}")
print(f"Local programmes included: {len(local_programs)}")
print("Saved local XML.")
