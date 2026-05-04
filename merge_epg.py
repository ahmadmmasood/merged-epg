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

MUAZT_URL_HINT = "MuazT/EPG-Guide"
MUAZT_FILE_HINT = "ArabicEPG.xml"

remove_words = ["hd", "hdtv", "tv", "channel", "network", "east", "west", "us", "us2"]
regex_remove = re.compile(r"[^\w\s]")

def decode_content(data):
    try:
        if data[:2] == b"\x1f\x8b":
            return gzip.decompress(data)
    except:
        pass
    return data

def fetch(url):
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    return r.content

def clean_text(name):
    if not name:
        return ""
    name = name.lower()
    name = name.replace("×", "x").replace("/", " ")
    for w in remove_words:
        name = re.sub(r"\b" + w + r"\b", " ", name)
    name = regex_remove.sub(" ", name)
    return re.sub(r"\s+", " ", name).strip()

# =========================
# MUAZT PIPELINE (FORCED DEBUG)
# =========================
def process_muazt(content, url):

    print("\n========== ARABIC2 DEBUG START ==========")
    print(">>> ENTERED MUAZT PROCESSOR <<<")
    print("URL:", url)
    print("RAW BYTES:", len(content))

    decoded = decode_content(content)
    print("DECODED BYTES:", len(decoded))

    print("RAW PREVIEW:")
    print(decoded[:300].decode("utf-8", errors="ignore"))

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

    # cleanup titles
    for prog in programmes:
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

    print("FINAL ARABIC2 SIZE:", len(fixed))
    print("FINAL ARABIC2 PREVIEW:", fixed[:300])
    print("========== ARABIC2 DEBUG END ==========\n")

    return fixed

def load_sources():
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        return [x.strip() for x in f if x.strip().startswith("http")]

def save(file_xml, file_gz, items):
    def write(f):
        f.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n')
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

        # =========================
        # ROUTING DEBUG (ALWAYS ON)
        # =========================
        print("\n=========================")
        print("[ROUTE CHECK] URL:", url)

        is_muazt = (
            MUAZT_URL_HINT.lower() in url.lower()
            or MUAZT_FILE_HINT.lower() in url.lower()
        )

        if is_muazt:
            print("[ROUTE] MUAZT PIPELINE SELECTED")
        else:
            print("[ROUTE] STANDARD PIPELINE SELECTED")

        content = fetch(url)
        print("DOWNLOADED BYTES:", len(content))

        if is_muazt:
            content = process_muazt(content, url)

        try:
            decoded = decode_content(content)
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
    save(OUTPUT_XML, OUTPUT_XML_GZ, all_items)

if __name__ == "__main__":
    main()
