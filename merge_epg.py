import os
import gzip
import requests
import xml.etree.ElementTree as ET
import re

MASTER_LIST_FILE = "master_channels.txt"
OUTPUT_XML_GZ = "merged.xml.gz"
INDEX_HTML = "index.html"

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


# Replace the hardcoded list with dynamic loading from epg_sources.txt
EPG_SOURCES_FILE = "epg_sources.txt"
epg_sources = load_epg_sources(EPG_SOURCES_FILE)

# Check if the list has been populated correctly
print(f"Loaded {len(epg_sources)} EPG sources from {EPG_SOURCES_FILE}")

# -----------------------------
# NORMALIZATION (WITH SPECIFIC FIXES AND LOOSER MATCHING)
# -----------------------------

def clean_text(name):
    name = name.lower()

    # Specific rules to fix known issues
    if "home and garden television" in name:
        return "hgtv"
    if "5 starmax" in name:
        return "5starmax"

    # Remove any periods, "HD", "East", "West"
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
# FETCH (UNCHANGED)
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
# PARSE TXT (UNCHANGED)
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
# PARSE XML (UNCHANGED)
# -----------------------------

def parse_xml(content):
    channels = set()
    try:
        # Safely decompress if gzipped
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
# MASTER LIST (UNCHANGED)
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
# MATCHING (INCLUDING LOOSE MATCH FOR UNMATCHED CHANNELS)
# -----------------------------

def smart_match(master_channels, parsed_channels):
    found = set()

    # Exact match first
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
# LOOSE MATCHING FOR UNMATCHED CHANNELS
# -----------------------------

def loose_match(master_channels, parsed_channels):
    found = set()

    # Looser match for channels that weren't found in the first pass
    for master in master_channels:
        if master not in found:
            for parsed in parsed_channels:
                if master in parsed or parsed in master:
                    found.add(master)
                    break

    return found


# -----------------------------
# XML CREATION (UNCHANGED)
# -----------------------------

def save_merged_xml(channels):
    root = ET.Element("tv")

    for ch in sorted(channels):
        ch_elem = ET.SubElement(root, "channel", id=ch)
        ET.SubElement(ch_elem, "display-name").text = ch

    tree = ET.ElementTree(root)

    temp_xml = "temp_merged.xml"
    tree.write(temp_xml, encoding="utf-8", xml_declaration=True)

    with open(temp_xml, "rb") as f_in:
        with gzip.open(OUTPUT_XML_GZ, "wb") as f_out:
            f_out.write(f_in.read())

    os.remove(temp_xml)


# -----------------------------
# INDEX UPDATE (WITH TITLE FIX)
# -----------------------------

def update_index(master, found, not_found):
    size_mb = os.path.getsize(OUTPUT_XML_GZ) / (1024 * 1024)

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
# MAIN (UNCHANGED)
# -----------------------------

def main():
    master = load_master_list()
    parsed_all = set()

    for url in epg_sources:
        print(f"Fetching {url}")
        content = fetch_content(url)
        if not content:
            continue

        if url.endswith(".txt"):
            parsed = parse_txt(content)
        else:
            parsed = parse_xml(content)

        print(f"Processed {url} - Parsed {len(parsed)} channels")
        parsed_all.update(parsed)

    # Step 1: Smart match (exact matching)
    found = smart_match(master, parsed_all)
    not_found = master - found

    # Step 2: Loose match for remaining unmatched channels
    loose_found = loose_match(not_found, parsed_all)

    # Combine found results
    all_found = found.union(loose_found)

    # Step 3: Save merged XML and update the index
    save_merged_xml(parsed_all)
    update_index(master, all_found, not_found)

    print(f"Final merged file size: {os.path.getsize(OUTPUT_XML_GZ)/(1024*1024):.2f} MB")


if __name__ == "__main__":
    main()

