import gzip
import shutil
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime

# ---------------- Configuration ----------------
merged_file = Path("merged.xml.gz")

# EPG sources
epg_sources = [
    # US feeds
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz",
    
    # Foreign feeds
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://iptv-epg.org/files/epg-lb.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/egypt1.xml.gz",
    "https://www.open-epg.com/files/egypt2.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz"
]

# Channels to specifically pull from Indian sources
indian_channels = [
    # ---------------- Indian ----------------
    # Star Network
    "star plus",
    "star bharat",
    "star gold",
    "star sports",

    # Zee Network
    "zee tv",
    "zee cinema",
    "zee news",

    # Sony Network
    "sony entertainment",
    "sony sab",
    "sony max",

    # Colors / Viacom
    "colors",
    "colors cineplex"
]

# ---------------- Helper Functions ----------------
def download_and_extract_gz(url: str) -> Path:
    local_gz = Path(url.split("/")[-1])
    r = requests.get(url, stream=True)
    with open(local_gz, "wb") as f:
        shutil.copyfileobj(r.raw, f)
    xml_file = local_gz.with_suffix("")
    with gzip.open(local_gz, "rb") as f_in, open(xml_file, "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)
    return xml_file

def parse_xml(file_path: Path):
    tree = ET.parse(file_path)
    return tree.getroot()

# ---------------- Merge Logic ----------------
merged_channels = set()
merged_programs = []

for source in epg_sources:
    xml_file = download_and_extract_gz(source)
    root = parse_xml(xml_file)
    
    for channel in root.findall("channel"):
        channel_id = channel.get("id").lower()
        name = channel.findtext("display-name", default="").lower()
        
        # US feed filtering: keep East + neutral, skip West
        if "us2" in source or "unitedstates10" in source:
            if "west" in name:
                continue
            # East channels + neutral are allowed

        # US locals: keep all
        if "US_LOCALS" in source:
            pass  # keep everything

        # Foreign channels: check if Indian or Egyptian/Lebanese
        if any(ind_ch in name for ind_ch in indian_channels):
            pass  # keep Indian channels
        else:
            # keep all others for foreign feeds
            pass

        # Avoid duplicates
        if channel_id in merged_channels:
            continue
        merged_channels.add(channel_id)
        
        merged_programs.append(channel)

# ---------------- Write merged file ----------------
root_out = ET.Element("tv")
for ch in merged_programs:
    root_out.append(ch)

tree_out = ET.ElementTree(root_out)
with gzip.open(merged_file, "wb") as f:
    tree_out.write(f, encoding="utf-8", xml_declaration=True)

# ---------------- Report ----------------
num_channels = len(merged_channels)
num_programs = len(merged_programs)
file_size_mb = merged_file.stat().st_size / (1024 * 1024)

print(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print(f"Channels kept: {num_channels}")
print(f"Programs kept: {num_programs}")
print(f"Final merged file size: {file_size_mb:.2f} MB")

