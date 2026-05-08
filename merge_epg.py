import os
import gzip
import requests
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime, timedelta

# ----------------------------
# CONFIGURATION
# ----------------------------
OUTPUT_MERGED = "merged.xml"
OUTPUT_MERGED_GZ = "merged.xml.gz"
OUTPUT_LOCAL = "local.xml"
OUTPUT_LOCAL_GZ = "local.xml.gz"

MASTER_LIST_FILE = "master_channels.txt"
EPG_SOURCES_FILE = "epg_sources.txt"

# Optional: limit to N days of programming (None = all)
MAX_DAYS = int(os.getenv("MAX_DAYS", 3))

# ----------------------------
# HELPER FUNCTIONS
# ----------------------------

def fetch_epg(url):
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        content = r.content
        try:
            with gzip.GzipFile(fileobj=BytesIO(content)) as f:
                xml_data = f.read()
        except OSError:
            xml_data = content
        return xml_data
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return b""

def parse_epg(xml_bytes):
    channels = {}
    programmes = []
    root = ET.fromstring(xml_bytes)
    for elem in root:
        if elem.tag == "channel":
            ch_id = elem.attrib.get("id")
            if ch_id:
                channels[ch_id] = ET.tostring(elem, encoding="utf-8")
        elif elem.tag == "programme":
            ch_id = elem.attrib.get("channel")
            if ch_id:
                programmes.append((ch_id, ET.tostring(elem, encoding="utf-8")))
    return channels, programmes

def deduplicate_icons(ch_xml):
    elem = ET.fromstring(ch_xml)
    seen = set()
    for icon in elem.findall("icon"):
        src = icon.attrib.get("src", "")
        if src in seen:
            elem.remove(icon)
        else:
            seen.add(src)
    return ET.tostring(elem, encoding="utf-8")

def load_epg_sources(file_path=EPG_SOURCES_FILE):
    sources = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                sources.append(line)
    return sources

def get_local_channel_ids(master_file=MASTER_LIST_FILE):
    local_ids = set()
    with open(master_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_local = False
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            if "LOCAL CHANNELS" in line.upper():
                in_local = True
            elif in_local and line.startswith("#"):
                break
            continue
        if in_local:
            local_ids.add(line)
    return local_ids

def filter_local_channels(all_channels, all_programmes, local_ids, max_days=None):
    # Partial contains: channel ID contains any of the local IDs
    filtered_ch = {ch_id: deduplicate_icons(ch_xml)
                   for ch_id, ch_xml in all_channels.items()
                   if any(lid in ch_id for lid in local_ids)}

    matched_ids = list(filtered_ch.keys())
    print(f"Local channels matched: {matched_ids}")

    now = datetime.utcnow()
    cutoff = now + timedelta(days=max_days) if max_days else None

    filtered_prog = []
    for ch_id, prog_xml in all_programmes:
        if ch_id in filtered_ch:
            if cutoff:
                elem = ET.fromstring(prog_xml)
                start = elem.attrib.get("start")
                if start:
                    dt = datetime.strptime(start[:14], "%Y%m%d%H%M%S")
                    if dt <= cutoff:
                        filtered_prog.append((ch_id, prog_xml))
            else:
                filtered_prog.append((ch_id, prog_xml))

    return filtered_ch, filtered_prog

def save_xml(channels, programmes, xml_file, gz_file=None):
    def write(f):
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="CustomEPG">\n')
        for ch_xml in channels.values():
            f.write(ch_xml)
        for _, prog_xml in programmes:
            f.write(prog_xml)
        f.write(b"\n</tv>")

    with open(xml_file, "wb") as f:
        write(f)
    if gz_file:
        with gzip.open(gz_file, "wb") as f:
            write(f)

# ----------------------------
# MAIN SCRIPT
# ----------------------------
def main(max_days=None):
    print("Loading EPG sources...")
    sources = load_epg_sources()
    all_channels = {}
    all_programmes = []

    for url in sources:
        print(f"Fetching {url} ...")
        xml_bytes = fetch_epg(url)
        if xml_bytes:
            chs, progs = parse_epg(xml_bytes)
            all_channels.update(chs)
            all_programmes.extend(progs)

    print(f"Total channels fetched: {len(all_channels)}")
    print(f"Total programmes fetched: {len(all_programmes)}")

    print("Saving merged XML...")
    save_xml(all_channels, all_programmes, OUTPUT_MERGED, OUTPUT_MERGED_GZ)

    print("Filtering local channels...")
    local_ids = get_local_channel_ids()
    local_ch_map, local_progs = filter_local_channels(all_channels, all_programmes, local_ids, max_days=max_days)
    print(f"Local channels included: {len(local_ch_map)}")
    print(f"Local programmes included: {len(local_progs)}")

    save_xml(local_ch_map, local_progs, OUTPUT_LOCAL, OUTPUT_LOCAL_GZ)
    print("Done. Files saved.")

if __name__ == "__main__":
    main(max_days=MAX_DAYS)
