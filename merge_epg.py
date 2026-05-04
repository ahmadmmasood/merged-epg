import os
import gzip
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta
from io import BytesIO
import pytz
from difflib import SequenceMatcher

MASTER_LIST_FILE = "master_channels.txt"
EPG_SOURCES_FILE = "epg_sources.txt"

OUTPUT_XML = "merged.xml"
OUTPUT_XML_GZ = "merged.xml.gz"

OUTPUT_LOCAL_XML = "local.xml"
OUTPUT_LOCAL_XML_GZ = "local.xml.gz"

INDEX_HTML = "index.html"

LOCAL_FEED_URL = "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz"
MUAZT_URL = "https://raw.githubusercontent.com/MuazT/EPG-Guide/master/ArabicEPG.xml"

remove_words = ["hd", "hdtv", "tv", "channel", "network", "east", "west", "us", "us2"]
regex_remove = re.compile(r"[^\w\s]")

def clean_text(name):
    if not name:
        return ""
    name = name.lower()
    name = name.replace("×", "x").replace("/", " ").replace("(", " ").replace(")", " ").replace("&", " and ").replace("-", " ")
    for word in remove_words:
        name = re.sub(r"\b" + word + r"\b", " ", name)
    name = regex_remove.sub(" ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()

def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

def fix_muazt_epg(content_bytes):
    try:
        f = BytesIO(content_bytes)
        tree = ET.parse(f)
        root = tree.getroot()

        for prog in root.findall("programme"):
            titles = prog.findall("title")
            if titles:
                clean = titles[0].text or ""
                clean = re.sub(r"\s+", " ", clean).strip()

                for t in titles:
                    prog.remove(t)

                new_title = ET.Element("title")
                new_title.text = clean
                prog.insert(0, new_title)

        return ET.tostring(root, encoding="utf-8")

    except:
        return content_bytes

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

def split_master(master_display):
    local = set()
    non_local = set()

    for ch in master_display:
        if re.match(r"^[WK][A-Z]{2,4}-DT$", ch):
            local.add(ch)
        else:
            non_local.add(ch)
    return local, non_local

def load_epg_sources():
    sources = []
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and line.startswith("http"):
                sources.append(line)
    return sources

def fetch_content(url):
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        return r.content
    except:
        return None

def parse_xml_stream(content_bytes, master_cleaned, local_channels):
    channel_matches = {}
    programmes = []

    cutoff = datetime.utcnow() + timedelta(days=7)

    try:
        f = gzip.open(BytesIO(content_bytes), "rb")
        f.peek(1)
    except:
        f = BytesIO(content_bytes)

    context = ET.iterparse(f, events=("end",))

    for event, elem in context:

        if elem.tag == "channel":
            raw_id = elem.attrib.get("id", "")
            display = elem.findtext("display-name") or raw_id

            if display in local_channels:
                channel_matches[raw_id] = display
                programmes.append((raw_id, ET.tostring(elem, encoding="utf-8")))
                elem.clear()
                continue

            cleaned_display = clean_text(display)
            matched_display = None

            if cleaned_display in master_cleaned:
                matched_display = master_cleaned[cleaned_display]

            if not matched_display:
                for mc, md in master_cleaned.items():
                    if similar(cleaned_display, mc) >= 0.7:
                        matched_display = md
                        break

            if matched_display:
                channel_matches[raw_id] = matched_display
                programmes.append((raw_id, ET.tostring(elem, encoding="utf-8")))

            elem.clear()

        elif elem.tag == "programme":
            raw_channel = elem.attrib.get("channel")
            start_str = elem.attrib.get("start")

            if raw_channel not in channel_matches:
                elem.clear()
                continue

            try:
                start_dt = datetime.strptime(start_str.strip(), "%Y%m%d%H%M%S %z")
                start_dt = start_dt.astimezone(pytz.utc).replace(tzinfo=None)
            except:
                elem.clear()
                continue

            programmes.append((raw_channel, ET.tostring(elem, encoding="utf-8")))
            elem.clear()

    return channel_matches, programmes

def save_xml(channel_map, programmes, xml_file, gz_file=None):

    def write(f):
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(b"<tv>\n")

        written = set()

        for cid, data in programmes:
            if data.startswith(b"<channel") and cid not in written:
                f.write(data)
                written.add(cid)

        for cid, data in programmes:
            if not data.startswith(b"<channel"):
                f.write(data)

        f.write(b"</tv>")

    with open(xml_file, "wb") as f:
        write(f)

    if gz_file:
        with gzip.open(gz_file, "wb") as f:
            write(f)

def create_local(all_map, all_prog, local_channels):
    local_map = {k: v for k, v in all_map.items() if v in local_channels}
    local_prog = [(k, p) for k, p in all_prog if k in local_map]
    save_xml(local_map, local_prog, OUTPUT_LOCAL_XML, OUTPUT_LOCAL_XML_GZ)

def create_arabic2():
    with open(OUTPUT_XML, "rb") as f:
        data = f.read()

    with open("arabic2.xml", "wb") as f:
        f.write(data)

    with gzip.open("arabic2.xml.gz", "wb") as f:
        f.write(data)

def main():
    master_cleaned, master_display = load_master_list()
    local_channels, non_local_channels = split_master(master_display)
    sources = load_epg_sources()

    all_map = {}
    all_prog = []

    for url in sources:
        content = fetch_content(url)
        if not content:
            continue

        if MUAZT_URL in url:
            content = fix_muazt_epg(content)

        channel_map, programmes = parse_xml_stream(content, master_cleaned, local_channels)

        all_map.update(channel_map)
        all_prog.extend(programmes)

    save_xml(all_map, all_prog, OUTPUT_XML, OUTPUT_XML_GZ)
    create_local(all_map, all_prog, local_channels)
    create_arabic2()

    print("Done")

if __name__ == "__main__":
    main()
