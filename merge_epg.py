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

remove_words = ["hd", "hdtv", "channel", "network", "west", "us", "us2"]
regex_remove = re.compile(r"[^\w\s]")

def clean_text(name, keep_direction=False):
    if not name:
        return ""
    name = name.lower()
    name = name.replace("×", "x").replace("/", " ").replace("(", " ").replace(")", " ").replace("&", " and ").replace("-", " ")
    for word in remove_words:
        if keep_direction and word == "east":
            continue
        name = re.sub(r"\b" + word + r"\b", " ", name)
    name = regex_remove.sub(" ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()

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
                keep_dir = "LOCAL CHANNELS" in line.upper() or re.match(r"^[WK][A-Z]{2,4}-DT$", line)
                master_cleaned[clean_text(line, keep_direction=keep_dir)] = line
                master_display.append(line)
    return master_cleaned, master_display

def split_master(master_display):
    local = set()
    non_local = set()
    local_section_started = False
    for line in master_display:
        line = line.strip()
        if not line or line.startswith("#"):
            if "LOCAL CHANNELS" in line.upper():
                local_section_started = True
            continue
        if re.match(r"^[WK][A-Z]{2,4}-DT$", line):
            local.add(line)
            continue
        if local_section_started:
            local.add(line)
        else:
            non_local.add(line)
    return local, non_local

def load_epg_sources():
    sources = []
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("http"):
                sources.append(line)
    return sources

def filter_local_channels(all_channels, all_programmes, local_channels):
    local_ch_map = {ch_id: xml for ch_id, xml in all_channels.items() if xml.decode().lower() in map(str.lower, local_channels)}
    local_progs = [(ch_id, prog) for ch_id, prog in all_programmes if ch_id in local_ch_map]
    if not local_ch_map:
        # Ensure at least one channel to prevent broken XML
        dummy = b'<channel id="DUMMY"><display-name>DUMMY</display-name></channel>'
        local_ch_map["DUMMY"] = dummy
    return local_ch_map, local_progs

def main():
    master_cleaned, master_display = load_master_list()
    local_channels, non_local_channels = split_master(master_display)
    sources = load_epg_sources()

    all_channels = {}
    all_programmes = []

    for url in sources:
        content = fetch_content(url)
        chs, progs = parse_xml(content)
        all_channels.update(chs)
        all_programmes.extend(progs)

    # Save merged full XML
    if not all_channels:
        # Ensure at least one channel to prevent broken XML
        dummy = b'<channel id="DUMMY"><display-name>DUMMY</display-name></channel>'
        all_channels["DUMMY"] = dummy
    save_xml(all_channels, all_programmes, OUTPUT_XML, OUTPUT_XML_GZ)

    # Save local-only XML
    local_ch_map, local_progs = filter_local_channels(all_channels, all_programmes, local_channels)
    save_xml(local_ch_map, local_progs, OUTPUT_LOCAL_XML, OUTPUT_LOCAL_XML_GZ)

    print(f"Done. {OUTPUT_XML_GZ} and {OUTPUT_LOCAL_XML_GZ} ready.")

if __name__ == "__main__":
    main()
