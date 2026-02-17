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

EPG_TO_FINAL_NAME = {
    "home.and.garden.television.hd.us2": "hgtv",
    "5.starmax.hd.east.us2": "5starmax",
}

EPG_SOURCES_FILE = "epg_sources.txt"

# -----------------------------
def load_epg_sources(file_path):
    sources = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and (line.endswith(".xml") or line.endswith(".xml.gz")):
                sources.append(line)
    return sources

epg_sources = load_epg_sources(EPG_SOURCES_FILE)
print(f"Loaded {len(epg_sources)} XML EPG sources")

# -----------------------------
def clean_text(name):
    name = name.lower().replace(".", " ").replace("hd", "").replace("east", "").replace("west", "")
    if "pacific" in name or "west" in name:
        return None
    name = name.replace("&", " and ").replace("-", " ")
    remove_words = ["hd", "hdtv", "tv", "channel", "network", "east"]
    for word in remove_words:
        name = re.sub(r"\b" + word + r"\b", " ", name)
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()

# -----------------------------
def fetch_content(url):
    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

# -----------------------------
def load_master_list():
    master = set()
    with open(MASTER_LIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                cleaned = clean_text(line)
                if cleaned:
                    master.add(cleaned)
    return master

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
def get_eastern_timestamp():
    eastern = pytz.timezone("US/Eastern")
    return datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S %Z")

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
function toggle(id){{ var e=document.getElementById(id); e.classList.toggle("hidden"); }}
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
def save_incremental_xml(channels_dict):
    with gzip.open(OUTPUT_XML_GZ, "wt", encoding="utf-8") as f_out:
        f_out.write('<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n')

        # Write channels first
        for cleaned_name, info in sorted(channels_dict.items()):
            if "pacific" in cleaned_name or "west" in cleaned_name:
                continue
            original_id = info.get("id") or cleaned_name
            display_name = info.get("display_name") or cleaned_name
            final_id = EPG_TO_FINAL_NAME.get(original_id, original_id) or cleaned_name
            f_out.write(f'  <channel id="{final_id}"><display-name>{display_name}</display-name></channel>\n')

        # Then write programmes
        for info in channels_dict.values():
            for prog in info.get("programmes", []):
                f_out.write(ET.tostring(prog, encoding="unicode"))

        f_out.write("\n</tv>")

# -----------------------------
def main():
    master = load_master_list()
    parsed_all = {}

    # Only process XML sources (skip TXT)
    for url in epg_sources:
        print(f"Fetching {url}")
        content = fetch_content(url)
        if not content:
            continue
        try:
            try:
                content = gzip.decompress(content)
            except:
                pass
            root = ET.fromstring(content)
            # Collect channels and programmes
            for ch in root.findall("channel"):
                original_id = ch.attrib.get("id")
                display_name = ch.findtext("display-name") or original_id
                cleaned = clean_text(display_name)
                if not cleaned:
                    continue
                programmes = [prog for prog in root.findall("programme") if prog.attrib.get("channel") == original_id]
                parsed_all[cleaned] = {
                    "id": original_id,
                    "display_name": display_name,
                    "programmes": programmes
                }
            print(f"Processed {url} - Parsed {len(parsed_all)} channels")
        except MemoryError:
            print(f"Skipping {url} due to memory constraints")
        except Exception as e:
            print(f"Error processing {url}: {e}")

    found = smart_match(master, parsed_all.keys())
    not_found = master - found

    save_incremental_xml(parsed_all)
    update_index(master, found, not_found)

    print(f"Final merged file size: {os.path.getsize(OUTPUT_XML_GZ)/(1024*1024):.2f} MB")

if __name__ == "__main__":
    main()
