import os
import gzip
import requests
import xml.etree.ElementTree as ET
import re
from io import BytesIO

EPG_SOURCES_FILE = "epg_sources.txt"

OUTPUT_XML = "merged.xml"
OUTPUT_GZ = "merged.xml.gz"

OUTPUT_LOCAL_GZ = "local.xml.gz"
OUTPUT_ARABIC_GZ = "arabic2.xml.gz"


# -----------------------------
# FIX BROKEN XML (IMPORTANT)
# -----------------------------
def sanitize_xml_bytes(data):
    text = data.decode("utf-8", errors="ignore")

    # fix broken ampersands
    text = re.sub(r"&(?!(amp;|lt;|gt;|quot;|apos;))", "&amp;", text)

    # remove null bytes
    text = text.replace("\x00", "")

    return text.encode("utf-8")


# -----------------------------
# FETCH
# -----------------------------
def fetch(url):
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        return sanitize_xml_bytes(r.content)
    except:
        return None


# -----------------------------
# LOAD SOURCES
# -----------------------------
def load_sources():
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip().startswith("http")]


# -----------------------------
# SAFE PARSE XMLTV
# -----------------------------
def parse(content):
    try:
        f = gzip.open(BytesIO(content), "rb")
        f.peek(1)
    except:
        f = BytesIO(content)

    try:
        tree = ET.parse(f)
        root = tree.getroot()
    except:
        return {}, []

    channels = {}
    programmes = []

    for elem in root:

        if elem.tag == "channel":
            cid = elem.attrib.get("id")
            channels[cid] = elem

        elif elem.tag == "programme":
            programmes.append(elem)

    return channels, programmes


# -----------------------------
# BUILD XMLTV
# -----------------------------
def build(channels, programmes, filename, gz=False):

    tv = ET.Element("tv")

    # channels first (required for IPTV)
    for c in channels.values():
        tv.append(c)

    # programmes
    for p in programmes:
        tv.append(p)

    xml_data = ET.tostring(tv, encoding="utf-8", xml_declaration=True)

    if gz:
        with gzip.open(filename, "wb") as f:
            f.write(xml_data)
    else:
        with open(filename, "wb") as f:
            f.write(xml_data)


# -----------------------------
# MAIN
# -----------------------------
def main():

    sources = load_sources()

    all_channels = {}
    all_programmes = []

    for url in sources:
        content = fetch(url)
        if not content:
            continue

        channels, programmes = parse(content)

        # merge safely
        all_channels.update(channels)
        all_programmes.extend(programmes)

    # FULL OUTPUTS
    build(all_channels, all_programmes, OUTPUT_GZ, gz=True)
    build(all_channels, all_programmes, OUTPUT_LOCAL_GZ, gz=True)
    build(all_channels, all_programmes, OUTPUT_ARABIC_GZ, gz=True)

    print("DONE")


if __name__ == "__main__":
    main()
