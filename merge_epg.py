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
OUTPUT_XML_GZ = "merged.xml.gz"
INDEX_HTML = "index.html"

LOCAL_FEED_URL = "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz"

# -----------------------------
# NORMALIZATION
# -----------------------------
remove_words = ["hd", "hdtv", "tv", "channel", "network", "east", "west", "us", "usa"]
regex_remove = re.compile(r"[^\w\s]")

def clean_text(name):
    if not name:
        return ""
    name = name.lower()
    name = name.replace("+", " plus ")
    name = name.replace("×", "x")
    for word in remove_words:
        name = re.sub(r"\b" + word + r"\b", " ", name)
    name = name.replace("&", " and ").replace("-", " ")
    name = regex_remove.sub(" ", name)
    name = re.sub(r"\s+", " ", name)
    return name.strip()

# -----------------------------
# FUZZY MATCHING
# -----------------------------
def similar(a, b):
    return SequenceMatcher(None, a, b).ratio()

# -----------------------------
# LOAD MASTER LIST
# -----------------------------
def load_master_list():
    master_cleaned = {}
    master_display = []

    with open(MASTER_LIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                master_cleaned[clean_text(line)] = line
                master_display.append(line)

    # remove duplicates safely
    master_display = list(dict.fromkeys(master_display))

    return master_cleaned, master_display

# -----------------------------
# SPLIT LOCAL VS NON-LOCAL
# -----------------------------
def split_master(master_display):
    local = set()
    non_local = set()

    for ch in master_display:
        if re.match(r"^[WK].+-", ch):
            local.add(ch)
        else:
            non_local.add(ch)

    return local, non_local

# -----------------------------
# LOAD EPG SOURCES
# -----------------------------
def load_epg_sources():
    sources = []
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and line.startswith("http"):
                sources.append(line)
    return sources

# -----------------------------
# FETCH
# -----------------------------
def fetch_content(url):
    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        return r.content
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

# -----------------------------
# PARSE XML STREAM
# -----------------------------
def parse_xml_stream(content_bytes, master_cleaned, days_limit=3):

    channel_matches = {}
    programmes = []
    cutoff = datetime.utcnow() + timedelta(days=days_limit)

    try:
        f = gzip.open(BytesIO(content_bytes), "rb")
        f.peek(1)
    except:
        f = BytesIO(content_bytes)

    context = ET.iterparse(f, events=("end",))

    for event, elem in context:

        if elem.tag == "channel":
            raw_id = elem.attrib.get("id", "")
            display = elem.findtext("display-name") or raw_id

            cleaned_display = clean_text(display)
            cleaned_id = clean_text(raw_id)

            matched_display = None

            # exact
            if cleaned_display in master_cleaned:
                matched_display = master_cleaned[cleaned_display]

            # substring
            if not matched_display:
                for master_clean, master_disp in master_cleaned.items():
                    if master_clean in cleaned_display or cleaned_display in master_clean:
                        matched_display = master_disp
                        break

            # fuzzy
            if not matched_display:
                for master_clean, master_disp in master_cleaned.items():
                    if similar(cleaned_display, master_clean) >= 0.6:
                        matched_display = master_disp
                        break
                    if similar(cleaned_id, master_clean) >= 0.6:
                        matched_display = master_disp
                        break

            if matched_display:
                channel_matches[raw_id] = matched_display

            elem.clear()

        elif elem.tag == "programme":
            raw_channel = elem.attrib.get("channel")
            start_str = elem.attrib.get("start")

            if raw_channel not in channel_matches:
                elem.clear()
                continue

            try:
                start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
            except:
                elem.clear()
                continue

            if start_dt <= cutoff:
                title = elem.findtext("title") or ""
                key = (raw_channel, start_str, title)

                if key not in parse_xml_stream.seen_programmes:
                    programmes.append((raw_channel, ET.tostring(elem, encoding="utf-8")))
                    parse_xml_stream.seen_programmes.add(key)

            elem.clear()

    return channel_matches, programmes

parse_xml_stream.seen_programmes = set()

# -----------------------------
# SAVE MERGED XML
# -----------------------------
def save_merged_xml(channel_id_map, programmes, master_display):

    with gzip.open(OUTPUT_XML_GZ, "wb") as f_out:
        f_out.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f_out.write(b"<tv>\n")

        used_display = set()

        for raw_id, display in sorted(channel_id_map.items()):
            if display not in master_display:
                continue
            if display in used_display:
                continue
            used_display.add(display)

            ch_elem = ET.Element("channel", id=display)
            ET.SubElement(ch_elem, "display-name").text = display
            f_out.write(ET.tostring(ch_elem, encoding="utf-8"))

        for raw_channel, prog_xml in programmes:
            if raw_channel in channel_id_map:
                f_out.write(prog_xml)

        f_out.write(b"\n</tv>")

# -----------------------------
# INDEX REPORT
# -----------------------------
def update_index(master_display, matched_display_names):

    found = sorted(matched_display_names)
    not_found = sorted(set(master_display) - matched_display_names)

    size_mb = os.path.getsize(OUTPUT_XML_GZ) / (1024 * 1024)
    timestamp = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y-%m-%d %H:%M:%S %Z")

    found_rows = "".join(f"<tr><td>{c}</td></tr>" for c in found)
    not_rows = "".join(f"<tr><td>{c}</td></tr>" for c in not_found)

    html = f"""
<html>
<head>
<title>EPG Merge Report</title>
<style>
body {{ font-family: Arial; }}
table {{
    border-collapse: collapse;
    width: 100%;
    display: block;
    max-height: 300px;
    overflow-y: auto;
}}
td {{
    border: 1px solid #ccc;
    padding: 4px;
}}
.collapsible {{
    background-color: #eee;
    cursor: pointer;
    padding: 10px;
    border: none;
    text-align: left;
    font-size: 16px;
    width: 100%;
}}
.content {{
    display: none;
}}
</style>
</head>
<body>

<h2>EPG Merge Report</h2>
<p>Generated: {timestamp}</p>
<p>Total master channels: {len(master_display)}</p>
<p>Channels found: {len(found)}</p>
<p>Channels not found: {len(not_found)}</p>
<p>Final merged file size: {size_mb:.2f} MB</p>

<button class="collapsible">Found Channels</button>
<div class="content"><table>{found_rows}</table></div>

<button class="collapsible">Not Found Channels</button>
<div class="content"><table>{not_rows}</table></div>

<script>
var coll = document.getElementsByClassName("collapsible");
for (var i = 0; i < coll.length; i++) {{
  coll[i].addEventListener("click", function() {{
    var content = this.nextElementSibling;
    content.style.display = content.style.display === "block" ? "none" : "block";
  }});
}}
</script>

</body>
</html>
"""

    with open(INDEX_HTML, "w", encoding="utf-8") as f:
        f.write(html)

# -----------------------------
# MAIN
# -----------------------------
def main():

    master_cleaned, master_display = load_master_list()
    local_master, non_local_master = split_master(master_display)
    sources = load_epg_sources()

    fulfilled = set()
    all_channel_map = {}
    all_programmes = []

    print(f"Master channels loaded: {len(master_display)}")

    for url in sources:

        print(f"\nProcessing: {url}")
        content = fetch_content(url)
        if not content:
            continue

        is_local_feed = (url == LOCAL_FEED_URL)

        channel_map, programmes = parse_xml_stream(content, master_cleaned)

        accepted_raw_ids = set()

        for raw_id, display in channel_map.items():

            if display in fulfilled:
                continue

            if is_local_feed:
                if display not in local_master:
                    continue
            else:
                if display not in non_local_master:
                    continue

            fulfilled.add(display)
            all_channel_map[raw_id] = display
            accepted_raw_ids.add(raw_id)

        for raw_channel, prog_xml in programmes:
            if raw_channel in accepted_raw_ids:
                all_programmes.append((raw_channel, prog_xml))

        print(f"  Channels accepted: {len(accepted_raw_ids)}")
        print(f"  Total fulfilled: {len(fulfilled)}")

        if len(fulfilled) >= len(master_display):
            print("All master channels fulfilled.")
            break

    save_merged_xml(all_channel_map, all_programmes, master_display)
    update_index(master_display, fulfilled)

    print("\nFinished.")
    print(f"Final channels: {len(fulfilled)}")
    print(f"Final programmes: {len(all_programmes)}")

if __name__ == "__main__":
    main()
