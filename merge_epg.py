import gzip
import requests
import xml.etree.ElementTree as ET
import re

EPG_SOURCES_FILE = "epg_sources.txt"

OUTPUT_XML = "merged.xml"
OUTPUT_XML_GZ = "merged.xml.gz"

OUTPUT_LOCAL_XML = "local.xml"
OUTPUT_LOCAL_XML_GZ = "local.xml.gz"

OUTPUT_ARABIC_XML = "arabic2.xml"
OUTPUT_ARABIC_XML_GZ = "arabic2.xml.gz"

MUAZT_URL = "https://raw.githubusercontent.com/MuazT/EPG-Guide/master/ArabicEPG.xml"

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

    preview = decoded[:300].decode("utf-8", errors="ignore")
    print("RAW PREVIEW:", preview)

    try:
        root = ET.fromstring(decoded)
    except Exception as e:
        print("XML PARSE ERROR:", e)
        print("========== ARABIC2 DEBUG END ==========\n")
        return decoded

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

    merged_items = []
    local_items = []
    arabic_items = []

    for url in sources:
        print("\n=========================")
        print("SOURCE:", url)

        raw = fetch_content(url)
        print("DOWNLOADED BYTES:", len(raw))

        is_arabic = (MUAZT_URL in url or "ArabicEPG.xml" in url)

        if is_arabic:
            print("[ROUTE] ARABIC PIPELINE ACTIVE")
            raw = process_muazt(raw, url)
        else:
            print("[ROUTE] STANDARD PIPELINE")

        decoded = decode_content(raw)

        try:
            root = ET.fromstring(decoded)

            count = 0

            for elem in root.iter():
                if elem.tag not in ["programme", "channel"]:
                    continue

                xml = ET.tostring(elem, encoding="utf-8")

                if is_arabic:
                    arabic_items.append((elem.tag, xml))
                elif "local" in url.lower():
                    local_items.append((elem.tag, xml))
                else:
                    merged_items.append((elem.tag, xml))

                count += 1

            print("ITEMS FROM FEED:", count)

        except Exception as e:
            print("PARSE ERROR:", e)

    print("\nFINAL TOTAL ITEMS (merged):", len(merged_items))
    print("FINAL TOTAL ITEMS (local):", len(local_items))
    print("FINAL TOTAL ITEMS (arabic):", len(arabic_items))

    save_xml(OUTPUT_XML, OUTPUT_XML_GZ, merged_items)
    save_xml(OUTPUT_LOCAL_XML, OUTPUT_LOCAL_XML_GZ, local_items)
    save_xml(OUTPUT_ARABIC_XML, OUTPUT_ARABIC_XML_GZ, arabic_items)

if __name__ == "__main__":
    main()
