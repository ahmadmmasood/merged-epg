import os
import gzip
import requests
import xml.etree.ElementTree as ET
from io import BytesIO

EPG_SOURCES_FILE = "epg_sources.txt"

OUTPUT_XML = "merged.xml"
OUTPUT_XML_GZ = "merged.xml.gz"

OUTPUT_LOCAL_XML = "local.xml"
OUTPUT_LOCAL_XML_GZ = "local.xml.gz"


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
# PARSE XML (NO FILTERING)
# -----------------------------
def parse_xml_stream(content_bytes):
    channels = {}
    programmes = []

    try:
        f = gzip.open(BytesIO(content_bytes), "rb")
        f.peek(1)
    except:
        f = BytesIO(content_bytes)

    context = ET.iterparse(f, events=("end",))

    for event, elem in context:

        # ---------------- CHANNEL ----------------
        if elem.tag == "channel":
            cid = elem.attrib.get("id")

            display = elem.findtext("display-name") or cid

            # FORCE KEEP CHANNEL (NO DROPPING EVER)
            channels[cid] = display

            elem.clear()

        # ---------------- PROGRAMME ----------------
        elif elem.tag == "programme":
            programmes.append(elem)
            elem.clear()

    return channels, programmes


# -----------------------------
# WRITE XML + GZ
# -----------------------------
def save_xml(channels, programmes, xml_file, gz_file=None):

    def write(f):
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(b"<tv>\n")

        # ---------------- WRITE CHANNELS FIRST ----------------
        for cid, display in channels.items():
            channel_xml = f"""
<channel id="{cid}">
  <display-name lang="en">{display}</display-name>
</channel>
"""
            f.write(channel_xml.encode("utf-8"))

        # ---------------- WRITE PROGRAMMES ----------------
        for elem in programmes:
            f.write(ET.tostring(elem, encoding="utf-8"))

        f.write(b"</tv>")

    with open(xml_file, "wb") as f:
        write(f)

    if gz_file:
        with gzip.open(gz_file, "wb") as f:
            write(f)


# -----------------------------
# LOCAL FILE (same data)
# -----------------------------
def create_local(channels, programmes):
    save_xml(channels, programmes, OUTPUT_LOCAL_XML, OUTPUT_LOCAL_XML_GZ)


# -----------------------------
# ARABIC2 FILE (FOR IPTV)
# -----------------------------
def create_arabic2():
    with open(OUTPUT_XML, "rb") as f:
        data = f.read()

    with gzip.open("arabic2.xml.gz", "wb") as f:
        f.write(data)


# -----------------------------
# MAIN
# -----------------------------
def main():
    sources = load_epg_sources()

    all_channels = {}
    all_programmes = []

    for url in sources:
        content = fetch_content(url)
        if not content:
            continue

        channels, programmes = parse_xml_stream(content)

        all_channels.update(channels)
        all_programmes.extend(programmes)

    # FULL MERGE
    save_xml(all_channels, all_programmes, OUTPUT_XML, OUTPUT_XML_GZ)

    # LOCAL COPY
    create_local(all_channels, all_programmes)

    # IPTV FILE
    create_arabic2()

    print("Done")


if __name__ == "__main__":
    main()
