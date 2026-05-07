import gzip
import requests
import xml.etree.ElementTree as ET
import re

MASTER_LIST_FILE = "master_channels.txt"
EPG_SOURCES_FILE = "epg_sources.txt"

OUTPUT_XML = "merged.xml"
OUTPUT_XML_GZ = "merged.xml.gz"

OUTPUT_LOCAL_XML = "local.xml"
OUTPUT_LOCAL_XML_GZ = "local.xml.gz"

OUTPUT_ARABIC_XML = "arabic2.xml"
OUTPUT_ARABIC_XML_GZ = "arabic2.xml.gz"

regex_remove = re.compile(r"[^\w\s]")


def fetch_content(url):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content


def is_gz(data):
    return len(data) > 2 and data[0] == 0x1F and data[1] == 0x8B


def decode_content(data):
    if is_gz(data):
        return gzip.decompress(data)
    return data


def load_sources():
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip().startswith("http")]


def process_muazt(content, url):

    print("\n========== ARABIC2 DEBUG START ==========")

    decoded = decode_content(content)

    try:
        root = ET.fromstring(decoded)
    except Exception as e:
        print("XML PARSE ERROR:", e)
        return []

    fixed_items = []

    channels = root.findall(".//channel")
    print("CHANNELS FOUND:", len(channels))

    for ch in channels:
        fixed_items.append(("channel", ET.tostring(ch, encoding="utf-8")))

    programmes = root.findall(".//programme")
    print("PROGRAMMES FOUND:", len(programmes))

    for prog in programmes:

        titles = prog.findall("title")

        if titles:
            first = titles[0]
            first.text = re.sub(r"\s+", " ", first.text or "").strip()

            for t in titles[1:]:
                prog.remove(t)

        fixed_items.append(("programme", ET.tostring(prog, encoding="utf-8")))

    print("TOTAL ARABIC ITEMS:", len(fixed_items))
    print("========== ARABIC2 DEBUG END ==========\n")

    return fixed_items


def process_standard_feed(content):

    decoded = decode_content(content)
    root = ET.fromstring(decoded)

    items = []

    for elem in root.iter():
        if elem.tag in ["programme", "channel"]:
            items.append((elem.tag, ET.tostring(elem, encoding="utf-8")))

    return items


def save_xml(file_xml, file_gz, items):

    print(f"\nWRITING: {file_xml}")
    print("TOTAL ITEMS:", len(items))

    def write(f):
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(b'<tv generator-info-name="EPG Merge">\n')

        for _, xml in items:
            f.write(xml)
            f.write(b"\n")

        f.write(b"</tv>")

    with open(file_xml, "wb") as f:
        write(f)

    with gzip.open(file_gz, "wb", compresslevel=9) as f:
        write(f)


def main():

    sources = load_sources()

    all_items = []
    local_items = []
    arabic_items = []

    for url in sources:

        print("\n=========================")
        print("SOURCE:", url)

        try:
            raw = fetch_content(url)
            print("DOWNLOADED BYTES:", len(raw))

            if "MuazT/EPG-Guide" in url or "ArabicEPG.xml" in url:

                print("[ARABIC PIPELINE]")

                items = process_muazt(raw, url)

                arabic_items.extend(items)
                all_items.extend(items)

                continue

            elif "LOCAL" in url.upper() or "LOCALS" in url.upper():

                print("[LOCAL PIPELINE]")

                items = process_standard_feed(raw)

                local_items.extend(items)
                all_items.extend(items)

            else:

                print("[STANDARD PIPELINE]")

                items = process_standard_feed(raw)

                all_items.extend(items)

        except Exception as e:
            print("FAILED:", url, e)

    print("\nFINAL TOTAL:", len(all_items))
    print("FINAL LOCAL:", len(local_items))
    print("FINAL ARABIC:", len(arabic_items))

    save_xml(OUTPUT_XML, OUTPUT_XML_GZ, all_items)
    save_xml(OUTPUT_LOCAL_XML, OUTPUT_LOCAL_XML_GZ, local_items)
    save_xml(OUTPUT_ARABIC_XML, OUTPUT_ARABIC_XML_GZ, arabic_items)


if __name__ == "__main__":
    main()
