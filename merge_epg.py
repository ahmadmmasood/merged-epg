import requests
import gzip
import xml.etree.ElementTree as ET
from io import BytesIO
import re

EPG_SOURCES_FILE = "epg_sources.txt"

OUTPUT_GZ = "merged.xml.gz"
OUTPUT_LOCAL_GZ = "local.xml.gz"
OUTPUT_ARABIC_GZ = "arabic2.xml.gz"


def fetch(url):
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        return r.content
    except:
        return None


def load_sources():
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip().startswith("http")]


def safe_parse(content):
    try:
        f = gzip.open(BytesIO(content), "rb")
        f.peek(1)
    except:
        f = BytesIO(content)

    try:
        return ET.parse(f).getroot()
    except:
        return None


def build_tree(channels, programmes):
    tv = ET.Element("tv")

    for c in channels.values():
        tv.append(c)

    for p in programmes:
        tv.append(p)

    return ET.tostring(tv, encoding="utf-8", xml_declaration=True)


def write_gz(data, filename):
    with gzip.open(filename, "wb") as f:
        f.write(data)


def main():
    sources = load_sources()

    channels = {}
    programmes = []

    for url in sources:
        content = fetch(url)
        if not content:
            continue

        root = safe_parse(content)
        if root is None:
            continue

        for elem in root:

            if elem.tag == "channel":
                cid = elem.attrib.get("id")
                if cid:
                    channels[cid] = elem

            elif elem.tag == "programme":
                programmes.append(elem)

    xml_data = build_tree(channels, programmes)

    write_gz(xml_data, OUTPUT_GZ)
    write_gz(xml_data, OUTPUT_LOCAL_GZ)
    write_gz(xml_data, OUTPUT_ARABIC_GZ)

    print("DONE")


if __name__ == "__main__":
    main()
