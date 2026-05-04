import os
import gzip
import requests
import xml.etree.ElementTree as ET
from io import BytesIO

MASTER_LIST_FILE = "master_channels.txt"
EPG_SOURCES_FILE = "epg_sources.txt"

OUTPUT_XML = "merged.xml"
OUTPUT_XML_GZ = "merged.xml.gz"

OUTPUT_LOCAL_XML = "local.xml"
OUTPUT_LOCAL_XML_GZ = "local.xml.gz"

LOCAL_FEED_URL = "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz"


# -----------------------------
# FETCH
# -----------------------------
def fetch_content(url):
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        return r.content
    except:
        return None


# -----------------------------
# LOAD SOURCES
# -----------------------------
def load_epg_sources():
    sources = []
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and line.startswith("http"):
                sources.append(line)
    return sources


# -----------------------------
# PARSE (FIXED: NO FILTERING)
# -----------------------------
def parse_xml_stream(content_bytes):
    channel_map = {}
    programmes = []

    # handle gz or xml
    try:
        f = gzip.open(BytesIO(content_bytes), "rb")
        f.peek(1)
    except:
        f = BytesIO(content_bytes)

    context = ET.iterparse(f, events=("end",))

    for event, elem in context:

        # ---------------- CHANNEL ----------------
        if elem.tag == "channel":
            raw_id = elem.attrib.get("id", "")
            display = elem.findtext("display-name") or raw_id

            # KEEP EVERYTHING (important fix)
            channel_map[raw_id] = display
            programmes.append((raw_id, ET.tostring(elem, encoding="utf-8")))
            elem.clear()

        # ---------------- PROGRAMME ----------------
        elif elem.tag == "programme":
            raw_channel = elem.attrib.get("channel")

            # KEEP EVERYTHING (important fix)
            programmes.append((raw_channel, ET.tostring(elem, encoding="utf-8")))
            elem.clear()

    return channel_map, programmes


# -----------------------------
# SAVE XML / GZ
# -----------------------------
def save_xml(channel_map, programmes, xml_file, gz_file=None):

    def write(f):
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(b"<tv>\n")

        for _, data in programmes:
            f.write(data)

        f.write(b"</tv>")

    with open(xml_file, "wb") as f:
        write(f)

    if gz_file:
        with gzip.open(gz_file, "wb") as f:
            write(f)


# -----------------------------
# LOCAL FILE
# -----------------------------
def create_local(all_map, all_prog):
    save_xml(all_map, all_prog, OUTPUT_LOCAL_XML, OUTPUT_LOCAL_XML_GZ)


# -----------------------------
# ARABIC2 (MAIN FIX FOR YOU)
# -----------------------------
def create_arabic2():
    with open(OUTPUT_XML, "rb") as f:
        data = f.read()

    # ONLY USE THIS FILE IN IPTV
    with gzip.open("arabic2.xml.gz", "wb") as f:
        f.write(data)


# -----------------------------
# MAIN
# -----------------------------
def main():
    sources = load_epg_sources()

    all_map = {}
    all_prog = []

    for url in sources:
        content = fetch_content(url)
        if not content:
            continue

        channel_map, programmes = parse_xml_stream(content)

        all_map.update(channel_map)
        all_prog.extend(programmes)

    # full merge
    save_xml(all_map, all_prog, OUTPUT_XML, OUTPUT_XML_GZ)

    # local file
    create_local(all_map, all_prog)

    # arabic file (gz ONLY)
    create_arabic2()

    print("Done")


if __name__ == "__main__":
    main()
