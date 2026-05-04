import gzip
import requests
import xml.etree.ElementTree as ET
import re
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

def fetch_content(url):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content

def is_gz(data):
    return len(data) > 2 and data[0] == 0x1f and data[1] == 0x8b

def decode(data):
    if is_gz(data):
        return gzip.decompress(data)
    return data

def clean_text(name):
    if not name:
        return ""
    name = name.lower()
    name = name.replace("×", "x").replace("/", " ").replace("(", " ").replace(")", " ").replace("&", " and ").replace("-", " ")
    for word in remove_words:
        name = re.sub(r"\b" + word + r"\b", " ", name)
    name = regex_remove.sub(" ", name)
    return re.sub(r"\s+", " ", name).strip()

def load_sources():
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip().startswith("http")]

# =========================
# 🔥 ARABIC BUILD FUNCTION
# =========================
def build_arabic2():
    print("\n========== ARABIC2 DEBUG START ==========")

    raw = fetch_content(MUAZT_URL)
    decoded = decode(raw)

    print("RAW BYTES:", len(raw))
    print("DECODED BYTES:", len(decoded))
    print("RAW PREVIEW:", decoded[:300])

    root = ET.fromstring(decoded)

    new_root = ET.Element("tv")

    programmes = root.findall(".//programme")

    print("PROGRAMMES FOUND:", len(programmes))

    for i, prog in enumerate(programmes):
        new_prog = ET.Element("programme")

        for attr in prog.attrib:
            new_prog.set(attr, prog.attrib[attr])

        title = prog.find("title")
        if title is not None and title.text:
            cleaned_title = clean_text(title.text)
        else:
            cleaned_title = ""

        new_title = ET.Element("title")
        new_title.text = cleaned_title
        new_prog.append(new_title)

        desc = prog.find("desc")
        if desc is not None and desc.text:
            new_desc = ET.Element("desc")
            new_desc.text = desc.text.strip()
            new_prog.append(new_desc)

        new_root.append(new_prog)

        if i < 3:
            print("SAMPLE PROGRAMME", i, ET.tostring(new_prog, encoding="unicode"))

    final_xml = ET.tostring(new_root, encoding="utf-8")

    print("FINAL ARABIC2 SIZE:", len(final_xml))
    print("FINAL ARABIC2 PREVIEW:", final_xml[:300])
    print("========== ARABIC2 DEBUG END ==========")

    return final_xml

# =========================
# SAVE
# =========================
def save(file_xml, file_gz, data):
    def write(f):
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write(b"<tv>\n")
        f.write(data)
        f.write(b"</tv>")

    with open(file_xml, "wb") as f:
        write(f)

    with gzip.open(file_gz, "wb") as f:
        write(f)

# =========================
# MAIN
# =========================
def main():
    sources = load_sources()
    all_prog = []

    for url in sources:
        print("\nSOURCE:", url)

        content = fetch_content(url)
        print("DOWNLOADED BYTES:", len(content))

        decoded = decode(content)
        root = ET.fromstring(decoded)

        count = 0

        for elem in root.iter():
            if elem.tag in ["programme", "channel"]:
                all_prog.append((elem.tag, ET.tostring(elem, encoding="utf-8")))
                count += 1

        print("ITEMS FROM FEED:", count)

    print("\nFINAL TOTAL ITEMS:", len(all_prog))

    # build arabic2 from MuazT
    arabic2 = build_arabic2()
    save(OUTPUT_ARABIC_XML, OUTPUT_ARABIC_XML_GZ, arabic2)

    # (your existing merged output stays conceptually here)

if __name__ == "__main__":
    main()
