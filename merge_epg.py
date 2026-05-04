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


def save_xml(file_xml, file_gz, items):

    clean_items = []

    for tag, xml in items:
        if tag not in ["programme", "channel"]:
            continue
        clean_items.append((tag, xml))

    print("\nCLEAN ITEMS TO WRITE:", len(clean_items))

    def write(f):
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(b"<tv>\n")
        for tag, xml in clean_items:
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
        print("\nSOURCE:", url)

        content = fetch_content(url)
        print("DOWNLOADED BYTES:", len(content) if content else 0)

        if not content:
            continue

        # ================= MUAZT DEBUG BLOCK =================
        if MUAZT_URL in url:
            print("\n========== MUAZT DEBUG START ==========")

            try:
                print("RAW PREVIEW:")
                print(content.decode("utf-8", errors="ignore")[:600])
            except:
                print("RAW PREVIEW FAILED")

            content = fix_muazt_epg(content)
            print("\nMUAZT FIX APPLIED")

            try:
                print("\nFIXED PREVIEW:")
                print(content.decode("utf-8", errors="ignore")[:600])
            except:
                print("FIXED PREVIEW FAILED")

            try:
                root = ET.fromstring(content)

                ch_count = 0
                pr_count = 0
                found = False

                for ch in root.findall("channel"):
                    ch_count += 1
                    xml = ET.tostring(ch, encoding="utf-8").decode("utf-8", errors="ignore")

                    if "Network Arabic" in xml:
                        print("\nFOUND CHANNEL BLOCK:")
                        print(xml[:300])
                        found = True

                for pr in root.findall("programme"):
                    pr_count += 1
                    xml = ET.tostring(pr, encoding="utf-8").decode("utf-8", errors="ignore")

                    if "Network Arabic" in xml:
                        print("\nFOUND PROGRAMME BLOCK:")
                        print(xml[:300])
                        found = True

                print("\nCHANNEL COUNT:", ch_count)
                print("PROGRAMME COUNT:", pr_count)
                print("NETWORK ARABIC FOUND:", found)

            except Exception as e:
                print("PARSE ERROR:", str(e))

            print("========== MUAZT DEBUG END ==========\n")

        # ================= NORMAL FLOW =================
        events = parse(content)

        count = 0

        for event, elem in events:
            tag = elem.tag
            if tag in ["programme", "channel"]:
                all_prog.append((tag, ET.tostring(elem, encoding="utf-8")))
                count += 1

        print("ITEMS FROM FEED:", count)

    print("\nFINAL TOTAL ITEMS:", len(all_prog))

    save_xml(OUTPUT_XML, OUTPUT_XML_GZ, all_prog)


if __name__ == "__main__":
    main()
