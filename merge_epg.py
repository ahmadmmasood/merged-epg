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
    master_cleaned = set()
    with open(MASTER_LIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                master_cleaned.add(clean_text(line))
    return master_cleaned

# -----------------------------
# LOAD SOURCES
# -----------------------------
def load_epg_sources():
    sources = []
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and line.startswith("http"):
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
# PARSE XML (KEEP ORIGINAL IDS)
# -----------------------------
def parse_xml_stream(content_bytes, master_cleaned, days_limit=3):
    allowed_channel_ids = set()
    programmes = []
    cutoff = datetime.utcnow() + timedelta(days=days_limit)

    try:
        f = gzip.open(BytesIO(content_bytes), "rb")
        f.peek(1)
    except:
        f = BytesIO(content_bytes)

    context = ET.iterparse(f, events=("end",))

    for event, elem in context:

        # CHANNEL
        if elem.tag == "channel":
            raw_id = elem.attrib.get("id", "")
            display = elem.findtext("display-name") or raw_id

            if clean_text(display) in master_cleaned:
                allowed_channel_ids.add(raw_id)

            elem.clear()

        # PROGRAMME
        elif elem.tag == "programme":
            raw_channel = elem.attrib.get("channel")
            start_str = elem.attrib.get("start")

            if not raw_channel or not start_str:
                elem.clear()
                continue

            if raw_channel not in allowed_channel_ids:
                elem.clear()
                continue

            try:
                start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
            except:
                elem.clear()
                continue

            if start_dt <= cutoff:
                programmes.append(
                    ET.tostring(elem, encoding="utf-8")
                )

            elem.clear()

    return allowed_channel_ids, programmes

# -----------------------------
# SAVE OUTPUT
# -----------------------------
def save_merged_xml(channel_ids, programmes):
    with gzip.open(OUTPUT_XML_GZ, "wb") as f_out:
        f_out.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f_out.write(b"<tv>\n")

        for cid in sorted(channel_ids):
            ch_elem = ET.Element("channel", id=cid)
            ET.SubElement(ch_elem, "display-name").text = cid
            f_out.write(ET.tostring(ch_elem, encoding="utf-8"))

        for prog in programmes:
            f_out.write(prog)

        f_out.write(b"\n</tv>")

# -----------------------------
# MAIN
# -----------------------------
def main():
    master_cleaned = load_master_list()
    sources = load_epg_sources()

    all_channel_ids = set()
    all_programmes = []

    print(f"Master channels loaded: {len(master_cleaned)}")
    print(f"EPG sources loaded: {len(sources)}")

    for url in sources:
        print(f"\nProcessing: {url}")
        content = fetch_content(url)
        if not content:
            continue

        try:
            channel_ids, programmes = parse_xml_stream(content, master_cleaned)
        except ET.ParseError as e:
            print(f"XML parse error in {url}: {e}")
            continue

        all_channel_ids.update(channel_ids)
        all_programmes.extend(programmes)

        print(f"  Channels kept: {len(channel_ids)}")
        print(f"  Programmes kept: {len(programmes)}")

    save_merged_xml(all_channel_ids, all_programmes)

    size_mb = os.path.getsize(OUTPUT_XML_GZ) / (1024 * 1024)

    print("\nFinished.")
    print(f"Final channels: {len(all_channel_ids)}")
    print(f"Final programmes: {len(all_programmes)}")
    print(f"Output size: {size_mb:.2f} MB")

if __name__ == "__main__":
    main()
