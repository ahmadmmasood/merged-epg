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
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content


def parse_xml_stream(content_bytes, master_cleaned, local_channels, days_limit=7):

    channel_matches = {}
    programmes = []

    cutoff = datetime.utcnow() + timedelta(days=days_limit)

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

            if "pacific" in display.lower():
                elem.clear()
                continue

            icons = elem.findall("icon")
            for i, icon in enumerate(icons):
                if i > 0:
                    elem.remove(icon)

            cleaned_display = clean_text(display)

            matched_display = None

            if cleaned_display in master_cleaned:
                matched_display = master_cleaned[cleaned_display]

            if not matched_display:
                for master_clean, master_disp in master_cleaned.items():
                    if set(master_clean.split()).issubset(set(cleaned_display.split())):
                        matched_display = master_disp
                        break

            if not matched_display:
                for master_clean, master_disp in master_cleaned.items():
                    if similar(cleaned_display, master_clean) >= 0.7:
                        matched_display = master_disp
                        break

            if matched_display:
                channel_matches[raw_id] = matched_display

            elem.clear()

        elif elem.tag == "programme":

            raw_channel = elem.attrib.get("channel")
            start_str = elem.attrib.get("start")

            # 🔴 FIX: DO NOT DROP PROGRAMMES IF CHANNEL NOT YET REGISTERED
            # This was causing WUSA / WJLA / WTTG / WRC to disappear
            if raw_channel and raw_channel not in channel_matches:
                channel_matches.setdefault(raw_channel, raw_channel)

            try:
                start_dt = datetime.strptime(start_str.strip(), "%Y%m%d%H%M%S %z")
                start_dt = start_dt.astimezone(pytz.utc).replace(tzinfo=None)
            except:
                elem.clear()
                continue

            if start_dt <= cutoff:
                programmes.append((raw_channel, ET.tostring(elem, encoding="utf-8")))

            elem.clear()

    return channel_matches, programmes


def save_merged_xml(channel_id_map, programmes, xml_filename, gz_filename=None):

    def write_xml(f_out):
        f_out.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f_out.write(b"<tv generator-info-name=\"CustomEPG\">\n")

        written_channels = set()

        for raw_id, prog_xml in programmes:
            if prog_xml.startswith(b"<channel") and raw_id not in written_channels:
                f_out.write(prog_xml)
                written_channels.add(raw_id)

        for raw_id, prog_xml in programmes:
            if not prog_xml.startswith(b"<channel"):
                f_out.write(prog_xml)

        f_out.write(b"\n</tv>")

    with open(xml_filename, "wb") as f_xml:
        write_xml(f_xml)

    if gz_filename:
        with gzip.open(gz_filename, "wb") as f_gz:
            write_xml(f_gz)


def create_local_from_merged(all_channel_map, all_programmes, local_channels):

    local_channel_map = {
        raw_id: disp for raw_id, disp in all_channel_map.items()
        if disp in local_channels
    }

    local_programmes = [
        (raw_id, prog_xml)
        for raw_id, prog_xml in all_programmes
        if raw_id in local_channel_map
    ]

    save_merged_xml(local_channel_map, local_programmes, OUTPUT_LOCAL_XML, OUTPUT_LOCAL_XML_GZ)


def update_index(master_display, matched_display_names):

    size_xml = os.path.getsize(OUTPUT_XML) / (1024 * 1024)
    size_gz = os.path.getsize(OUTPUT_XML_GZ) / (1024 * 1024)

    html = f"""
    <html><body>
    <h2>EPG Output</h2>
    <p>XML: {size_xml:.2f} MB</p>
    <p>XML.GZ: {size_gz:.2f} MB</p>
    </body></html>
    """

    with open(INDEX_HTML, "w") as f:
        f.write(html)


def main():

    master_cleaned, master_display = load_master_list()
    local_channels, non_local_channels = split_master(master_display)
    sources = load_epg_sources()

    all_channel_map = {}
    all_programmes = []

    for url in sources:
        content = fetch_content(url)
        if not content:
            continue

        is_local_feed = (url == LOCAL_FEED_URL)

        channel_map, programmes = parse_xml_stream(content, master_cleaned, local_channels)

        if is_local_feed:
            channel_map = {k: v for k, v in channel_map.items() if v in local_channels}
        else:
            channel_map = {k: v for k, v in channel_map.items() if v in non_local_channels}

        all_channel_map.update(channel_map)
        all_programmes.extend(programmes)

    save_merged_xml(all_channel_map, all_programmes, OUTPUT_XML, OUTPUT_XML_GZ)
    create_local_from_merged(all_channel_map, all_programmes, local_channels)
    update_index(master_display, set(all_channel_map.values()))

    print("Done.")


if __name__ == "__main__":
    main()
