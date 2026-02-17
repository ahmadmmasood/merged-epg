import os
import gzip
import requests
import xml.etree.ElementTree as ET
import re
from datetime import datetime, timedelta
import pytz

MASTER_LIST_FILE = "master_channels.txt"
OUTPUT_XML_GZ = "merged.xml.gz"
INDEX_HTML = "index.html"

# Map non-matching IDs from sources to final names
EPG_TO_FINAL_NAME = {
    "home.and.garden.television.hd.us2": "hgtv",
    "5.starmax.hd.east.us2": "5starmax",
    # Add more if needed
}

# Load EPG sources from a file
EPG_SOURCES_FILE = "epg_sources.txt"
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

epg_sources = load_epg_sources(EPG_SOURCES_FILE)
print(f"Loaded {len(epg_sources)} EPG sources from {EPG_SOURCES_FILE}")

# -----------------------------
# Text cleaning / normalization
# -----------------------------
def clean_text(name):
    name = name.lower()
    name = name.replace(".", " ")
    name = name.replace("&", " and ")
    name = name.replace("-", " ")

    # Remove common words
    remove_words = ["hd", "hdtv", "tv", "channel", "network", "east", "west", "pacific"]
    for word in remove_words:
        name = re.sub(r"\b" + word + r"\b", " ", name)

    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name)

    return name.strip()

# -----------------------------
# Fetch content
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
# Parse TXT sources
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
# Parse XML sources
# -----------------------------
def parse_xml(content):
    channels = set()
    try:
        try:
            content = gzip.decompress(content)
        except:
            pass
        root = ET.fromstring(content)
        for ch in root.findall("channel"):
            name = ch.attrib.get("id") or ch.findtext("display-name") or ""
            cleaned = clean_text(name)
            if cleaned:
                channels.add(cleaned)
    except Exception as e:
        print(f"Error parsing XML: {e}")
    return channels

# -----------------------------
# Master list
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
# Smart match logic
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
# Save merged XML incrementally
# -----------------------------
def save_merged_xml(channels, xml_sources):
    temp_xml = "temp_merged.xml"
    three_days_utc = datetime.utcnow() + timedelta(days=3)

    # Open temporary XML file
    with open(temp_xml, "w", encoding="utf-8") as f_out:
        f_out.write('<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n')

        # Write manually mapped channels
        for epg_name, final_name in EPG_TO_FINAL_NAME.items():
            f_out.write(f'  <channel id="{final_name}">\n')
            f_out.write(f'    <display-name>{final_name}</display-name>\n')
            f_out.write('  </channel>\n')

        # Write dynamically found channels
        for ch in sorted(channels):
            f_out.write(f'  <channel id="{ch}">\n')
            f_out.write(f'    <display-name>{ch}</display-name>\n')
            f_out.write('  </channel>\n')

        # Now iterate XML sources and write <programme> incrementally
        for url in xml_sources:
            if not url.endswith(".xml.gz"):
                continue
            print(f"Fetching XML {url}")
            content = fetch_content(url)
            if not content:
                continue
            try:
                try:
                    content = gzip.decompress(content)
                except:
                    pass

                # Stream parsing for memory efficiency
                for event, elem in ET.iterparse(
                    bytes(content), events=("end",)
                ):
                    if elem.tag == "programme":
                        start_str = elem.attrib.get("start")
                        if start_str:
                            try:
                                start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
                                if start_dt > three_days_utc:
                                    elem.clear()
                                    continue
                            except:
                                pass
                        # Write programme element
                        xml_string = ET.tostring(elem, encoding="utf-8").decode("utf-8")
                        f_out.write(f"{xml_string}\n")
                        elem.clear()
            except Exception as e:
                print(f"Error streaming XML from {url}: {e}")

        f_out.write("</tv>\n")

    # Compress to .gz
    with open(temp_xml, "rb") as f_in:
        with gzip.open(OUTPUT_XML_GZ, "wb") as f_out_gz:
            f_out_gz.writelines(f_in)

    os.remove(temp_xml)
    print(f"Compressed XML saved to {OUTPUT_XML_GZ}")

# -----------------------------
# Timestamp for index
# -----------------------------
def get_eastern_timestamp():
    eastern = pytz.timezone("US/Eastern")
    return datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S %Z")

# -----------------------------
# Update index.html
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
    parsed_all = set()

    # First parse all TXT or XML sources for channel discovery
    for url in epg_sources:
        print(f"Processing {url}")
        content = fetch_content(url)
        if not content:
            continue
        if url.endswith(".txt"):
            parsed = parse_txt(content)
        else:
            parsed = parse_xml(content)
        print(f"Parsed {len(parsed)} channels from {url}")
        parsed_all.update(parsed)

    found = smart_match(master, parsed_all)
    not_found = master - found

    # Save merged XML including <programme> elements (3-day limit)
    save_merged_xml(parsed_all, epg_sources)

    # Update index.html
    update_index(master, found, not_found)

    print(f"Final merged file size: {os.path.getsize(OUTPUT_XML_GZ)/(1024*1024):.2f} MB")

if __name__ == "__main__":
    main()
