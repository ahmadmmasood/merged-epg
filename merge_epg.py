import gzip
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta
from io import BytesIO

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

def clean_text(name):
    if not name:
        return ""
    name = name.lower()
    name = name.replace("×", "x").replace("/", " ").replace("(", " ").replace(")", " ").replace("&", " and ").replace("-", " ")
    for word in remove_words:
        name = re.sub(r"\b" + word + r"\b", " ", name)
    name = regex_remove.sub(" ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()

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

def fix_muazt_epg(content):
    print("========== MUAZT DEBUG START ==========")
    print("RAW SIZE:", len(content))
    try:
        decoded = decode_content(content)
        print("DECOMPRESSED SIZE:", len(decoded))
        print("RAW PREVIEW:", decoded[:200])

        root = ET.fromstring(decoded)

        for prog in root.findall(".//programme"):
            titles = prog.findall("title")
            if not titles:
                continue
            txt = titles[0].text or ""
            txt = re.sub(r"\s+", " ", txt).strip()

            for t in titles:
                prog.remove(t)

            new_title = ET.Element("title")
            new_title.text = txt
            prog.insert(0, new_title)

        fixed = ET.tostring(root, encoding="utf-8")
        print("AFTER FIX SIZE:", len(fixed))
        print("AFTER FIX PREVIEW:", fixed[:200])

        print("========== MUAZT DEBUG END ==========")
        return fixed

    except Exception as e:
        print("MUAZT PARSE FAILED:", str(e))
        print("========== MUAZT DEBUG END ==========")
        return decode_content(content)

def load_sources():
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip().startswith("http")]

def save_xml(file_xml, file_gz, items):
    clean_items = [(t, x) for t, x in items if t in ["programme", "channel"]]

    print("CLEAN ITEMS TO WRITE:", len(clean_items))

    def write(f):
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(b"<tv>\n")
        for _, xml in clean_items:
            f.write(xml)
        f.write(b"</tv>")

    with open(file_xml, "wb") as f:
        write(f)

    with gzip.open(file_gz, "wb") as f:
        write(f)

def main():
    sources = load_sources()
    all_prog = []

    for url in sources:
        print("SOURCE:", url)

        content = fetch_content(url)
        print("DOWNLOADED BYTES:", len(content))

        if MUAZT_URL in url:
            content = fix_muazt_epg(content)

        try:
            decoded = decode_content(content)
            root = ET.fromstring(decoded)

            count = 0
            for elem in root.iter():
                if elem.tag in ["programme", "channel"]:
                    all_prog.append((elem.tag, ET.tostring(elem, encoding="utf-8")))
                    count += 1

            print("ITEMS FROM FEED:", count)

        except Exception as e:
            print("PARSE ERROR:", str(e))

    print("FINAL TOTAL ITEMS:", len(all_prog))
    save_xml(OUTPUT_XML, OUTPUT_XML_GZ, all_prog)

if __name__ == "__main__":
    main()
