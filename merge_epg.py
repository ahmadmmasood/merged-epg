import os
import gzip
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta
import pytz
from io import BytesIO

MASTER_LIST_FILE = "master_channels.txt"
OUTPUT_XML_GZ = "merged.xml.gz"
INDEX_HTML = "index.html"

# Mapping from raw EPG names to desired final names (excluding locals)
EPG_TO_FINAL_NAME = {
    "home.and.garden.television.hd.us2": "hgtv",
    "5.starmax.hd.east.us2": "5starmax",
    # Add any other mappings here for non-local channels...
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
# NORMALIZATION
# -----------------------------
remove_words = ["hd", "hdtv", "tv", "channel", "network", "east", "west"]
regex_remove = re.compile(r"[^\w\s]")

def clean_text(name):
    name = name.lower()
    for word in remove_words:
        name = re.sub(r"\b" + word + r"\b", " ", name)
    name = name.replace("&", " and ").replace("-", " ")
    name = regex_remove.sub(" ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()

# -----------------------------
# FETCH
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
# PARSE TXT
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
# PARSE XML (STREAMED)
# -----------------------------
def parse_xml_stream(content_bytes, days_limit=3):
    channels = set()
    programmes = []
    cutoff = datetime.utcnow() + timedelta(days=days_limit)

    with gzip.open(BytesIO(content_bytes), "rb") as f:
        context = ET.iterparse(f, events=("end",))
        for event, elem in context:
            # Collect channel IDs for mapping
            if elem.tag == "channel":
                ch_id = elem.attrib.get("id")
                ch_name = elem.findtext("display-name") or ch_id
                # Skip cleaning for local channels (keep as-is if in master)
                channels.add(ch_name.strip())
                elem.clear()
            # Collect programme elements within 3-day limit
            elif elem.tag == "programme":
                start_str = elem.attrib.get("start")
                if start_str:
                    start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
                    if start_dt <= cutoff:
                        programmes.append(ET.tostring(elem, encoding="utf-8"))
                elem.clear()
    return channels, programmes

# -----------------------------
# MASTER LIST
# -----------------------------
def load_master_list():
    master = set()
    with open(MASTER_LIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            master.add(line)  # keep as-is for locals
    return master

# -----------------------------
# MATCHING
# -----------------------------
def smart_match(master_channels, parsed_channels):
    found = set()
    for master in master_channels:
        master_clean = clean_text(master)
        # Exact match
        for parsed in parsed_channels:
            parsed_clean = clean_text(parsed)
            if master_clean == parsed_clean or master in parsed or parsed in master:
                found.add(master)
                break
    return found

# -----------------------------
# SAVE MERGED XML
# -----------------------------
def save_merged_xml(channels, programmes):
    root = ET.Element("tv")
    # Add manually matched channels
    for epg_name, final_name in EPG_TO_FINAL_NAME.items():
        ch_elem = ET.SubElement(root, "channel", id=final_name)
        ET.SubElement(ch_elem, "display-name").text = final_name
    # Add channels from master/XML
    for ch in sorted(channels):
        ch_elem = ET.SubElement(root, "channel", id=ch)
        ET.SubElement(ch_elem, "display-name").text = ch
    # Write XML incrementally to temp file
    temp_xml = "temp_merged.xml"
    tree = ET.ElementTree(root)
    tree.write(temp_xml, encoding="utf-8", xml_declaration=True)
    # Append programmes
    with gzip.open(OUTPUT_XML_GZ, "wb") as f_out, open(temp_xml, "rb") as f_in:
        f_out.writelines(f_in)
        for prog in programmes:
            f_out.write(prog)
    os.remove(temp_xml)

# -----------------------------
# TIMESTAMP
# -----------------------------
def get_eastern_timestamp():
    eastern = pytz.timezone("US/Eastern")
    return datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S %Z")

# -----------------------------
# INDEX UPDATE
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
    parsed_all_channels = set()
    all_programmes = []

    for url in epg_sources:
        print(f"Fetching {url}")
        content = fetch_content(url)
        if not content:
            continue
        if url.endswith(".txt"):
            parsed = parse_txt(content)
            parsed_all_channels.update(parsed)
        else:
            channels, programmes = parse_xml_stream(content)
            parsed_all_channels.update(channels)
            all_programmes.extend(programmes)
            print(f"Processed XML {url} - {len(channels)} channels, {len(programmes)} programmes")

    found = smart_match(master, parsed_all_channels)
    not_found = master - found

    save_merged_xml(parsed_all_channels, all_programmes)
    update_index(master, found, not_found)

    print(f"Final merged file size: {os.path.getsize(OUTPUT_XML_GZ)/(1024*1024):.2f} MB")

if __name__ == "__main__":
    main()
