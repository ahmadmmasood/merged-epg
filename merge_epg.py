import requests
import gzip
import xml.etree.ElementTree as ET
from io import BytesIO

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


# -----------------------------
# ROBUST XML LOADER
# -----------------------------
def parse_content(data):
    if not data:
        return None

    # try gzip first
    if data[:2] == b"\x1f\x8b":
        try:
            data = gzip.decompress(data)
        except:
            return None

    try:
        return ET.fromstring(data)
    except:
        return None


def build_xml(channels, programmes):
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
        data = fetch(url)
        root = parse_content(data)

        if root is None:
            continue

        for elem in root:

            if elem.tag == "channel":
                cid = elem.attrib.get("id")
                if cid:
                    channels[cid] = elem

            elif elem.tag == "programme":
                programmes.append(elem)

    xml_data = build_xml(channels, programmes)

    write_gz(xml_data, OUTPUT_GZ)
    write_gz(xml_data, OUTPUT_LOCAL_GZ)
    write_gz(xml_data, OUTPUT_ARABIC_GZ)

    print("DONE:", len(channels), "channels", len(programmes), "programmes")


if __name__ == "__main__":
    main()
