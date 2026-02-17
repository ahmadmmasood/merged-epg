import os
import gzip
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta
from io import BytesIO

MASTER_LIST_FILE = "master_channels.txt"
EPG_SOURCES_FILE = "epg_sources.txt"
OUTPUT_XML_GZ = "merged.xml.gz"

# -----------------------------
# NORMALIZATION
# -----------------------------
remove_words = ["hd", "hdtv", "tv", "channel", "network", "east", "west"]
regex_remove = re.compile(r"[^\w\s]")

def clean_text(name):
    if not name:
        return ""
    name = name.lower()
    for word in remove_words:
        name = re.sub(r"\b" + word + r"\b", " ", name)
    name = name.replace("&", " and ").replace("-", " ")
    name = regex_remove.sub(" ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()

# -----------------------------
# LOAD MASTER
# -----------------------------
def load_master_list():
    master = {}
    with open(MASTER_LIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                master[clean_text(line)] = line
    return master

# -----------------------------
# LOAD SOURCES
# -----------------------------
def load_epg_sources():
    sources = []
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                sources.append(line)
    return sources

# -----------------------------
# FETCH
# -----------------------------
def fetch_content(url):
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

# -----------------------------
# SAFE STREAM PARSE
# -----------------------------
def parse_xml_stream(content_bytes, master_map, days_limit=3):
    raw_to_master = {}
    programmes = []
    channels_with_programmes = set()

    cutoff = datetime.utcnow() + timedelta(days=days_limit)

    # Handle gz and plain xml
    try:
        f = gzip.open(BytesIO(content_bytes), "rb")
        f.peek(1)
    except:
        f = BytesIO(content_bytes)

    context = ET.iterparse(f, events=("end",))

    for event, elem in context:

        # ------------------
        # CHANNEL BLOCK
        # ------------------
        if elem.tag == "channel":
            raw_id = elem.attrib.get("id", "")
            display_names = [dn.text for dn in elem.findall("display-name") if dn.text]

            possible_names = [raw_id] + display_names

            for name in possible_names:
                cleaned = clean_text(name)
                if cleaned in master_map:
                    raw_to_master[raw_id] = master_map[cleaned]
                    break

            elem.clear()

        # ------------------
        # PROGRAMME BLOCK
        # ------------------
        elif elem.tag == "programme":
            raw_channel = elem.attrib.get("channel")
            start_str = elem.attrib.get("start")

            if not raw_channel or not start_str:
                elem.clear()
                continue

            if raw_channel not in raw_to_master:
                elem.clear()
                continue

            try:
                start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
            except:
                elem.clear()
                continue

            if start_dt <= cutoff:
                master_name = raw_to_master[raw_channel]
                elem.attrib["channel"] = master_name
                programmes.append(
                    ET.tostring(elem, encoding="utf-8")
                )
                channels_with_programmes.add(master_name)

            elem.clear()

    return channels_with_programmes, programmes

# -----------------------------
# SAVE FINAL XML
# -----------------------------
def save_merged_xml(channels, programmes):
    with gzip.open(OUTPUT_XML_GZ, "wb") as f_out:
        f_out.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f_out.write(b"<tv>\n")

        for ch in sorted(channels):
            ch_elem = ET.Element("channel", id=ch)
            ET.SubElement(ch_elem, "display-name").text = ch
            f_out.write(ET.tostring(ch_elem, encoding="utf-8"))

        for prog in programmes:
            f_out.write(prog)

        f_out.write(b"\n</tv>")

# -----------------------------
# MAIN
# -----------------------------
def main():
    master_map = load_master_list()
    sources = load_epg_sources()

    all_channels = set()
    all_programmes = []

    print(f"Master channels loaded: {len(master_map)}")
    print(f"EPG sources loaded: {len(sources)}")

    for url in sources:
        print(f"\nProcessing: {url}")
        content = fetch_content(url)
        if not content:
            continue

        channels, programmes = parse_xml_stream(content, master_map)
        all_channels.update(channels)
        all_programmes.extend(programmes)

        print(f"  Channels matched: {len(channels)}")
        print(f"  Programmes kept: {len(programmes)}")

    save_merged_xml(all_channels, all_programmes)

    size_mb = os.path.getsize(OUTPUT_XML_GZ) / (1024 * 1024)

    print("\nFinished.")
    print(f"Final channels: {len(all_channels)}")
    print(f"Final programmes: {len(all_programmes)}")
    print(f"Output size: {size_mb:.2f} MB")

if __name__ == "__main__":
    main()
