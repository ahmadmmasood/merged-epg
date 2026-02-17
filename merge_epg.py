import os
import gzip
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime
import pytz

MASTER_LIST_FILE = "master_channels.txt"
OUTPUT_XML_GZ = "merged.xml.gz"
INDEX_HTML = "index.html"

# Mapping from raw EPG names to desired final names
EPG_TO_FINAL_NAME = {
    "home.and.garden.television.hd.us2": "hgtv",
    "5.starmax.hd.east.us2": "5starmax",
    "wjla-dt": "abc",
    "wdcw-dt": "cd",
    "wttg-dt": "fox",
    "wdca-dt": "foxplus",
    "wrc-dt": "nbc",
}

# -----------------------------
# Load EPG Sources from File
# -----------------------------
def load_epg_sources(file_path):
    epg_sources = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    epg_sources.append(line)
    except Exception as e:
        print(f"Error loading EPG sources from {file_path}: {e}")
    return epg_sources

EPG_SOURCES_FILE = "epg_sources.txt"
epg_sources = load_epg_sources(EPG_SOURCES_FILE)
print(f"Loaded {len(epg_sources)} EPG sources from {EPG_SOURCES_FILE}")

# -----------------------------
# CLEANING FUNCTION (UNCHANGED)
# -----------------------------
def clean_text(name):
    name = name.lower()
    name = name.replace(".", " ")
    name = name.replace("hd", "")
    name = name.replace("east", "")
    name = name.replace("west", "")
    if "pacific" in name or "west" in name:
        return None
    name = name.replace("&", " and ")
    name = name.replace("-", " ")
    remove_words = ["hd", "hdtv", "tv", "channel", "network", "east"]
    for word in remove_words:
        name = re.sub(r"\b" + word + r"\b", " ", name)
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()

# -----------------------------
# FETCH CONTENT
# -----------------------------
def fetch_content(url):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"Error fetching content from {url}: {e}")
        return None

# -----------------------------
# PARSE TXT (FOR MATCHING ONLY)
# -----------------------------
def parse_txt(content):
    channels = set()
    lines = content.decode(errors="ignore").splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        cleaned = clean_text(line)
        if cleaned:
            channels.add(cleaned)
    return channels

# -----------------------------
# PARSE XML (PRESERVE ORIGINAL IDs)
# -----------------------------
def parse_xml(content):
    channels = {}  # key = cleaned display-name, value = original ID
    try:
        try:
            content = gzip.decompress(content)
        except:
            pass
        root = ET.fromstring(content)
        for ch in root.findall("channel"):
            original_id = ch.attrib.get("id", "")
            display_name = ch.findtext("display-name") or original_id
            cleaned = clean_text(display_name)
            if cleaned:
                channels[cleaned] = original_id
    except Exception as e:
        print(f"Error parsing XML: {e}")
    return channels

# -----------------------------
# LOAD MASTER LIST
# -----------------------------
def load_master_list():
    master = set()
    with open(MASTER_LIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            cleaned = clean_text(line)
            if cleaned:
                master.add(cleaned)
    return master

# -----------------------------
# SMART MATCHING
# -----------------------------
def smart_match(master_channels, parsed_channels):
    found = set()
    for master in master_channels:
        if master in parsed_channels:
            found.add(master)
            continue
        master_words = master.split()
        for parsed in parsed_channels:
            if all(word in parsed for word in master_words):
                found.add(master)
                break
    return found

# -----------------------------
# SAVE MERGED XML
# -----------------------------
def save_merged_xml(channels):
    root = ET.Element("tv")
    for cleaned_name, original_id in sorted(channels.items()):
        if "pacific" in cleaned_name or "west" in cleaned_name or "tbs superstation" in cleaned_name:
            continue
        final_id = EPG_TO_FINAL_NAME.get(original_id, original_id)
        ch_elem = ET.SubElement(root, "channel", id=final_id)
        ET.SubElement(ch_elem, "display-name").text = cleaned_name

    tree = ET.ElementTree(root)
    temp_xml = "temp_merged.xml"
    tree.write(temp_xml, encoding="utf-8", xml_declaration=True)
    with open(temp_xml, "rb") as f_in:
        with gzip.open(OUTPUT_XML_GZ, "wb") as f_out:
            f_out.writelines(f_in)
    os.remove(temp_xml)

# -----------------------------
# GET EASTERN TIME
# -----------------------------
def get_eastern_timestamp():
    eastern = pytz.timezone("US/Eastern")
    return datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S %Z")

# -----------------------------
# UPDATE INDEX
# -----------------------------
def update_index(master, found, not_found):
    size_mb = os.path.getsize(OUTPUT_XML_GZ) / (1024 * 1024)
    timestamp = get_eastern_timestamp()
    found_rows = "".join(f"<tr><td>{c}</td></tr>" for c in sorted(found))
    not_rows = "".join(f"<tr><td>{c}</td></tr>" for c in sorted(not_found))

    html = f"""
<!DOCTYPE html>
<html>
<head>
<title>EPG Merge Report</title>
<style>
body {{ font-family: Arial; }}
table {{ border-collapse: collapse; width: 50%; }}
td {{ border: 1px solid #999; padding: 4px; }}
.hidden {{ display:none; }}
</style>
<script>
function toggle(id){{
  var e=document.getElementById(id);
  e.classList.toggle("hidden");
}}
</script>
</head>
<body>

<h2>EPG Merge Report</h2>
<p><strong>Report generated on:</strong> {timestamp}</p>

<p>Total channels in master list: {len(master)}</p>
<p>Channels found: {len(found)} <a href="#" onclick="toggle('found')">(show/hide)</a></p>
<p>Channels not found: {len(not_found)} <a href="#" onclick="toggle('notfound')">(show/hide)</a></p>
<p>Final merged file size: {size_mb:.2f} MB</p>

<h3>Found Channels</h3>
<table id="found" class="hidden">{found_rows}</table>

<h3>Not Found Channels</h3>
<table id="notfound" class="hidden">{not_rows}</table>

</body>
</html>
"""
    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)

# -----------------------------
# MAIN
# -----------------------------
def main():
    master = load_master_list()
    parsed_all = {}

    # 1️⃣ First process XML sources for all IDs
    for url in epg_sources:
        if url.endswith(".xml") or url.endswith(".xml.gz"):
            print(f"Fetching XML {url}")
            content = fetch_content(url)
            if not content:
                continue
            parsed = parse_xml(content)
            parsed_all.update(parsed)
            print(f"Processed {url} - Parsed {len(parsed)} channels")

    # 2️⃣ Then process TXT sources only for matching
    for url in epg_sources:
        if url.endswith(".txt"):
            print(f"Fetching TXT {url}")
            content = fetch_content(url)
            if not content:
                continue
            parsed_txt = parse_txt(content)
            # TXT used only for matching, don't add IDs
            for ch in parsed_txt:
                if ch not in parsed_all:
                    parsed_all[ch] = None
            print(f"Processed {url} - Parsed {len(parsed_txt)} channels (for matching)")

    found = smart_match(master, parsed_all.keys())
    not_found = master - found

    save_merged_xml(parsed_all)
    update_index(master, found, not_found)

    print(f"Final merged file size: {os.path.getsize(OUTPUT_XML_GZ)/(1024*1024):.2f} MB")


if __name__ == "__main__":
    main()
