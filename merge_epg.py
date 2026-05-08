import os
import gzip
import requests
import xml.etree.ElementTree as ET
from io import BytesIO
from datetime import datetime, timedelta
import pytz
import re

MASTER_LIST_FILE = "master_channels.txt"
EPG_SOURCES_FILE = "epg_sources.txt"

OUTPUT_XML = "merged.xml"
OUTPUT_XML_GZ = "merged.xml.gz"

OUTPUT_LOCAL_XML = "local.xml"
OUTPUT_LOCAL_XML_GZ = "local.xml.gz"

INDEX_HTML = "index.html"

# Optional: number of days of programming to keep, None = keep all
DAYS_TO_KEEP = 3

def clean_text(name):
    if not name:
        return ""
    return re.sub(r"[^\w\s]", " ", name).lower().strip()

def fetch_content(url):
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return b""

def parse_xml(content_bytes):
    channels = {}
    programmes = []

    if not content_bytes:
        return channels, programmes

    # handle gzip
    try:
        f = gzip.open(BytesIO(content_bytes), "rb")
        f.peek(1)
    except:
        f = BytesIO(content_bytes)

    try:
        context = ET.iterparse(f, events=("end",))
    except:
        return channels, programmes

    for event, elem in context:
        if elem.tag == "channel":
            ch_id = elem.attrib.get("id", "").strip()
            if ch_id:
                channels[ch_id] = ET.tostring(elem, encoding="utf-8")
        elif elem.tag == "programme":
            prog_xml = ET.tostring(elem, encoding="utf-8")
            ch_id = elem.attrib.get("channel", "").strip()
            if ch_id:
                programmes.append((ch_id, prog_xml))
        elem.clear()

    return channels, programmes

def save_xml(channels, programmes, xml_filename, gz_filename=None):
    def write_xml(f_out):
        f_out.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="CustomEPG">\n')
        for ch_xml in channels.values():
            f_out.write(ch_xml)
        for _, prog_xml in programmes:
            f_out.write(prog_xml)
        f_out.write(b"\n</tv>")

    with open(xml_filename, "wb") as f:
        write_xml(f)
    if gz_filename:
        with gzip.open(gz_filename, "wb") as f:
            write_xml(f)

def load_master_list():
    master_cleaned = {}
    master_display = []

    with open(MASTER_LIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                master_cleaned[clean_text(line)] = line
                master_display.append(line)
    return master_cleaned, master_display

def load_epg_sources():
    sources = []
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("http"):
                sources.append(line)
    return sources

def filter_local_channels(all_channels, all_programmes, local_channels):
    matched_channels = {}
    matched_progs = []

    # lowercase for partial matching
    local_lc = [clean_text(ch) for ch in local_channels]

    for ch_id, ch_xml in all_channels.items():
        ch_tree = ET.fromstring(ch_xml)
        disp_name_elem = ch_tree.find("display-name")
        if disp_name_elem is None:
            continue
        disp_name = clean_text(disp_name_elem.text)
        # partial match anywhere in the display-name
        if any(loc in disp_name for loc in local_lc):
            matched_channels[ch_id] = ch_xml

    for ch_id, prog_xml in all_programmes:
        if ch_id in matched_channels:
            if DAYS_TO_KEEP:
                try:
                    start_str = ET.fromstring(prog_xml).attrib.get("start", "")[:14]
                    if start_str:
                        prog_start = datetime.strptime(start_str, "%Y%m%d%H%M%S")
                        if prog_start > datetime.utcnow() + timedelta(days=DAYS_TO_KEEP):
                            continue
                except:
                    pass
            matched_progs.append((ch_id, prog_xml))

    print(f"Local channels matched: {list(matched_channels.keys())}")
    print(f"Local programmes included: {len(matched_progs)}")
    return matched_channels, matched_progs

def main():
    print("Loading EPG sources...")
    sources = load_epg_sources()

    all_channels = {}
    all_programmes = []

    for url in sources:
        print(f"Fetching {url} ...")
        content = fetch_content(url)
        chs, progs = parse_xml(content)
        all_channels.update(chs)
        all_programmes.extend(progs)

    print(f"Total channels fetched: {len(all_channels)}")
    print(f"Total programmes fetched: {len(all_programmes)}")

    # Save merged full XML
    if not all_channels:
        all_channels["DUMMY"] = b'<channel id="DUMMY"><display-name>DUMMY</display-name></channel>'
    save_xml(all_channels, all_programmes, OUTPUT_XML, OUTPUT_XML_GZ)
    print("Saved merged XML.")

    # Load local channels from master
    _, master_display = load_master_list()
    local_channels_section = []
    in_local = False
    for line in master_display:
        if line.upper().startswith("LOCAL CHANNELS"):
            in_local = True
            continue
        if in_local:
            if not line or line.startswith("#"):
                continue
            local_channels_section.append(line)

    # Filter local channels
    local_ch_map, local_progs = filter_local_channels(all_channels, all_programmes, local_channels_section)
    if not local_ch_map:
        # Keep at least dummy to prevent broken XML
        local_ch_map["DUMMY"] = b'<channel id="DUMMY"><display-name>DUMMY</display-name></channel>'
    save_xml(local_ch_map, local_progs, OUTPUT_LOCAL_XML, OUTPUT_LOCAL_XML_GZ)
    print("Saved local XML.")

if __name__ == "__main__":
    main()
