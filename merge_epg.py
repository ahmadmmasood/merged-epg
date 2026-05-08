import os
import gzip
import requests
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime, timedelta

# Output files
OUTPUT_MERGED = "merged.xml"
OUTPUT_MERGED_GZ = "merged.xml.gz"
OUTPUT_LOCAL = "local.xml"
OUTPUT_LOCAL_GZ = "local.xml.gz"

# Configurable max_days
MAX_DAYS = int(os.getenv("MAX_DAYS", 3))  # Default 3 days, set None for all

# File paths
MASTER_LIST_FILE = "master_channels.txt"
EPG_SOURCES_FILE = "epg_sources.txt"

# ----------------------------
# Helper functions
# ----------------------------

def load_epg_sources(file_path=EPG_SOURCES_FILE):
    sources = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                sources.append(line)
    return sources

def fetch_epg(url):
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        content = r.content
        # Try gzip first
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
    """Remove duplicate icons in a channel"""
    elem = ET.fromstring(ch_xml)
    seen = set()
    for icon in elem.findall("icon"):
        src = icon.attrib.get("src", "")
        if src in seen:
            elem.remove(icon)
        else:
            seen.add(src)
    return ET.tostring(elem, encoding="utf-8")

def get_local_channels(master_file=MASTER_LIST_FILE):
    """Return set of local DC/Baltimore OTA channel names (lowercase)"""
    local_names = set()
    with open(master_file, "r", encoding="utf-8") as f:
        lines = f.readlines()

    in_local = False
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            if "LOCAL CHANNELS" in line.upper():
                in_local = True
            elif in_local and line.startswith("#"):
                break  # end of local section
            continue
        if in_local:
            local_names.add(line.lower())
    return local_names

def filter_channels(all_channels, all_programmes, name_set, max_days=None):
    """Filter channels and programmes by name set and optional max_days"""
    filtered_ch = {}
    for ch_id, ch_xml in all_channels.items():
        elem = ET.fromstring(ch_xml)
        disp_name = elem.findtext("display-name", "").strip().lower()
        if disp_name in name_set:
            filtered_ch[ch_id] = deduplicate_icons(ch_xml)

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

def save_xml(channels, programmes, xml_filename, gz_filename=None):
    def write_xml(f):
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="CustomEPG">\n')
        for ch_xml in channels.values():
            f.write(ch_xml)
        for _, prog_xml in programmes:
            f.write(prog_xml)
        f.write(b"\n</tv>")

    with open(xml_filename, "wb") as f:
        write_xml(f)
    if gz_filename:
        with gzip.open(gz_filename, "wb") as f:
            write_xml(f)

# ----------------------------
# Main workflow
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

    if not all_channels:
        print("No channels found in sources. Exiting.")
        return

    # --- Merged XML (all channels)
    print("Saving merged XML...")
    save_xml(all_channels, all_programmes, OUTPUT_MERGED, OUTPUT_MERGED_GZ)

    # --- Local XML (filtered channels)
    print("Filtering local channels...")
    local_names = get_local_channels()
    local_ch_map, local_progs = filter_channels(all_channels, all_programmes, local_names, max_days=max_days)
    print(f"{len(local_ch_map)} local channels found.")
    save_xml(local_ch_map, local_progs, OUTPUT_LOCAL, OUTPUT_LOCAL_GZ)

    print("Done. Files saved.")

# ----------------------------
# Entry point
# ----------------------------
if __name__ == "__main__":
    main(max_days=MAX_DAYS)
