import os
import gzip
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta
from io import BytesIO
import pytz
from difflib import SequenceMatcher

MASTER_LIST_FILE = "master_channels.txt"
EPG_SOURCES_FILE = "epg_sources.txt"

OUTPUT_XML = "merged.xml"
OUTPUT_XML_GZ = "merged.xml.gz"

OUTPUT_LOCAL_XML = "local.xml"
OUTPUT_LOCAL_XML_GZ = "local.xml.gz"

OUTPUT_ARABIC_XML = "arabic2.xml"
OUTPUT_ARABIC_XML_GZ = "arabic2.xml.gz"

LOCAL_FEED_URL = "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz"
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


def safe_parse(content):
    try:
        f = gzip.open(BytesIO(content), "rb")
        f.peek(1)
    except:
        f = BytesIO(content)

    return list(ET.iterparse(f, events=("end",)))


def fix_muazt_epg(content):
    try:
        root = ET.fromstring(content)

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

        return ET.tostring(root, encoding="utf-8")

    except:
        return content


def load_sources():
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip().startswith("http")]


def load_master():
    with open(MASTER_LIST_FILE, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip() and not x.startswith("#")]


def parse(content):
    return safe_parse(content)


def save_xml(file_xml, file_gz, data):

    print("\n================ XML BUILD DEBUG ================")
    print("TOTAL PROGRAMMES TO WRITE:", len(data))

    for i, item in enumerate(data[:10]):
        try:
            preview = item[1].decode("utf-8", errors="ignore")[:300]
        except:
            preview = str(item[1])[:300]

        print("\n--- ITEM", i, "---")
        print("CHANNEL:", item[0])
        print(preview)

    print("=================================================\n")

    def write(f):
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(b"<tv>\n")
        for cid, data in data:
            f.write(data)
        f.write(b"</tv>")

    with open(file_xml, "wb") as f:
        write(f)

    with gzip.open(file_gz, "wb") as f:
        write(f)


def main():
    sources = load_sources()

    all_prog = []

    for url in sources:
        print("\nSOURCE:", url)

        content = fetch_content(url)
        print("DOWNLOADED BYTES:", len(content) if content else 0)

        if not content:
            continue

        if MUAZT_URL in url:
            content = fix_muazt_epg(content)
            print("MUAZT FIX APPLIED")

        events = parse(content)

        count = 0
        for event, elem in events:
            all_prog.append((elem.tag, ET.tostring(elem, encoding="utf-8")))
            count += 1

        print("ITEMS FROM FEED:", count)

    print("\nFINAL TOTAL ITEMS:", len(all_prog))

    save_xml(OUTPUT_XML, OUTPUT_XML_GZ, all_prog)


if __name__ == "__main__":
    main()
