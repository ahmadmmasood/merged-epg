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

MUAZT_URL = "https://raw.githubusercontent.com/MuazT/EPG-Guide/master/ArabicEPG.xml"

remove_words = ["hd", "hdtv", "tv", "channel", "network", "east", "west", "us", "us2"]
regex_remove = re.compile(r"[^\w\s]")

def fetch_content(url):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content

def is_gz(data):
    return len(data) > 2 and data[0] == 0x1f and data[1] == 0x8b

def decode_content(data):
    if is_gz(data):
        return gzip.decompress(data)
    return data

def process_muazt(content, url):
    print("\n========== ARABIC2 DEBUG START ==========")
    print("URL:", url)
    print("RAW BYTES:", len(content))

    decoded = decode_content(content)
    print("DECODED BYTES:", len(decoded))
    print("RAW PREVIEW:", decoded[:300])

    try:
        root = ET.fromstring(decoded)
    except Exception as e:
        print("XML PARSE ERROR:", e)
        print("========== ARABIC2 DEBUG END ==========")
        return content

    programmes = root.findall(".//programme")
    print("PROGRAMMES FOUND:", len(programmes))

    for i, p in enumerate(programmes[:3]):
        print("SAMPLE PROGRAMME", i, ET.tostring(p, encoding="unicode"))

    fixed = 0

    for prog in programmes:
        titles = prog.findall("title")
        if not titles:
            continue

        first = titles[0].text or ""
        first = re.sub(r"\s+", " ", first).strip()

        for t in titles:
            prog.remove(t)

        new_title = ET.Element("title")
        new_title.text = first
        prog.insert(0, new_title)

        fixed += 1

    result = ET.tostring(root, encoding="utf-8")

    print("PROGS FIXED:", fixed)
    print("FINAL ARABIC2 SIZE:", len(result))
    print("FINAL ARABIC2 PREVIEW:", result[:300])

    print("========== ARABIC2 DEBUG END ==========\n")

    return result

def load_sources():
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip().startswith("http")]

def save_xml(file_xml, file_gz, items):
    print("FINAL CLEAN ITEMS TO WRITE:", len(items))

    def write(f):
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(b"<tv>\n")
        for _, xml in items:
            f.write(xml)
        f.write(b"</tv>")

    with open(file_xml, "wb") as f:
        write(f)

    with gzip.open(file_gz, "wb") as f:
        write(f)

def main():
    sources = load_sources()
    all_items = []

    for url in sources:
        print("\n=========================")
        print("SOURCE:", url)

        raw = fetch_content(url)
        print("DOWNLOADED BYTES:", len(raw))

        # FIX: ALWAYS process BEFORE parsing
        if "MuazT/EPG-Guide" in url or "ArabicEPG.xml" in url:
            print("[ROUTE] ARABIC PIPELINE ACTIVE")
            raw = process_muazt(raw, url)
        else:
            print("[ROUTE] STANDARD PIPELINE")

        decoded = decode_content(raw)

        try:
            root = ET.fromstring(decoded)

            count = 0
            for elem in root.iter():
                if elem.tag in ["programme", "channel"]:
                    all_items.append((elem.tag, ET.tostring(elem, encoding="utf-8")))
                    count += 1

            print("ITEMS FROM FEED:", count)

        except Exception as e:
            print("PARSE ERROR:", e)

    print("\nFINAL TOTAL ITEMS:", len(all_items))
    save_xml(OUTPUT_XML, OUTPUT_XML_GZ, all_items)

if __name__ == "__main__":
    main()
