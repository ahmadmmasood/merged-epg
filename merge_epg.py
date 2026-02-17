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
remove_words = ["hd", "hdtv", "tv", "channel", "network", "east", "west"]
regex_remove = re.compile(r"[^\w\s]")

def clean_text(name):
    if not name:
        return ""
    name = name.lower()
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
# ALIASES (Exact raw EPG IDs)
# -----------------------------
EPG_ALIASES = {
    # Premium / specialty
    "5_starmax": "5StarMax",
    "outermax": "OuterMax",
    "moviemax": "MovieMax",
    "thrillermax": "ThrillerMax",
    "sho×bet": "SHO×BET",
    # HBO / Cinemax / Showtime aliases
    "hbo family": "HBO Family",
    # Starz / Encore
    "starz encore family": "Starz Encore Family",
    "starz encore westerns": "Starz Encore Westerns",
    "starz inblack": "Starz InBlack",
    "starz kids and family": "Starz Kids & Family",
    # Local DC/Baltimore
    "wbaldt": "WBAL-DT",
    "wdca-dt": "WDCA-DT",
    "wdcw-dt": "WDCW-DT",
    "wdvm-sd": "WDVM-SD",
    "weta kids": "WETA Kids",
    "weta uk": "WETA UK",
    "weta-hd": "WETA-HD",
    "wfdc-dt": "WFDC-DT",
    "whut": "WHUT",
    "wjla-dt": "WJLA-DT",
    "wjz 13": "WJZ 13 (CBS Baltimore)",
    "wmar 2": "WMAR 2 (ABC Baltimore)",
    "wmpb": "WMPB (PBS Maryland)",
    "wnuv-dt": "WNUV-DT",
    "wrc-hd": "WRC-HD",
    "wttg-dt": "WTTG-DT",
    "wusa-hd": "WUSA-HD",
    "wzdc": "WZDC",
    # Other international / specialty
    "aaj tak": "Aaj Tak",
    "al ahram tv": "Al Ahram TV",
    "al hayat tv": "Al Hayat TV",
    "al masriya tv": "Al Masriya TV",
    "al nahar tv": "Al Nahar TV",
    "al jadeed": "Al Jadeed",
    "altavsn": "AltaVsn",
    "buzzr": "BUZZR",
    "bloomberg television": "Bloomberg Television",
    "cbc": "CBC (Egypt)",
    "crimes": "CRIMES",
    "cwwnuv": "CWWNUV",
    "cartoonito": "Cartoonito",
    "colors tv": "Colors TV",
    "comcast sportsnet mid atlantic": "Comcast SportsNet Mid-Atlantic",
    "crime tv": "Crime TV",
    "dream tv": "Dream TV",
    "e!": "E!",
    "fox sports 1": "Fox Sports 1",
    "fox sports 2": "Fox Sports 2",
    "fox weather": "Fox Weather",
    "future tv": "Future TV",
    "gettv": "GetTV",
    "hsn": "HSN",
    "heroes and icons": "Heroes & Icons",
    "ion plus": "ION Plus",
    "lbci": "LBCI",
    "mpt kids": "MPT Kids",
    "mpt-2": "MPT-2",
    "mpt-hd": "MPT-HD",
    "mtv": "MTV",
    "mtv lebanon": "MTV Lebanon",
    "mtv live": "MTV Live",
    "mtv2": "MTV2",
    "metv": "MeTV",
    "metro": "Metro",
    "nbc sports washington": "NBC Sports Washington",
    "ndtv": "NDTV",
    "nhk world japan": "NHK World Japan",
    "newschannel 8": "NewsChannel 8 (WJLA News)",
    "nick at nite": "Nick at Nite",
    "nickmusic": "NickMusic",
    "nile tv international": "Nile TV International",
    "otv lebanon": "OTV Lebanon",
    "oxygen": "Oxygen",
    "republic tv": "Republic TV",
    "showtime": "Showtime",
    "showtime family zone": "Showtime Family Zone",
    "sony tv": "Sony TV",
    "star plus": "Star Plus",
    "story television": "Story Television",
    "sun tv": "Sun TV",
    "tcm": "TCM",
    "tlc": "TLC",
    "tv9": "TV9",
    "teennick": "TeenNick",
    "telexitos": "Telexitos",
    "the movie channel xtra": "The Movie Channel Xtra",
    "times now": "Times Now",
    "travel channel": "Travel Channel",
    "xitos": "XITOS",
}

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

    return master_cleaned, master_display

# -----------------------------
# LOAD EPG SOURCES
# -----------------------------
def load_epg_sources():
    sources = []
    with open(EPG_SOURCES_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and line.startswith("http") and line != LOCAL_FEED_URL:
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
def parse_xml_stream(content_bytes, master_cleaned, allowed_master_channels, days_limit=3, local_only=False):
    allowed_channel_ids = set()
    channel_id_to_display = {}
    programmes = []
    unmatched_channels = []

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
            canonical_id = raw_id.lower()
            matched = False

            if local_only and cleaned_display not in allowed_master_channels:
                elem.clear()
                continue

            if canonical_id in EPG_ALIASES:
                matched = True
                channel_id_to_display[canonical_id] = EPG_ALIASES[canonical_id]
            elif cleaned_display in master_cleaned:
                matched = True
                channel_id_to_display[canonical_id] = master_cleaned[cleaned_display]

            if matched:
                allowed_channel_ids.add(canonical_id)
            else:
                unmatched_channels.append((canonical_id, display))

            elem.clear()

        elif elem.tag == "programme":
            raw_channel = elem.attrib.get("channel", "").lower()
            start_str = elem.attrib.get("start")
            if not raw_channel or not start_str or raw_channel not in allowed_channel_ids:
                elem.clear()
                continue

            try:
                start_dt = datetime.strptime(start_str[:14], "%Y%m%d%H%M%S")
            except:
                elem.clear()
                continue

            if start_dt <= cutoff:
                title = elem.findtext("title") or ""
                prog_key = (raw_channel, start_str, title)
                if prog_key not in parse_xml_stream.seen_programmes:
                    programmes.append(ET.tostring(elem, encoding="utf-8"))
                    parse_xml_stream.seen_programmes.add(prog_key)

            elem.clear()

    if unmatched_channels:
        print("Unmatched EPG channels in this source:")
        for cid, disp in unmatched_channels:
            print(f"  {cid} -> {disp}")

    return allowed_channel_ids, channel_id_to_display, programmes

parse_xml_stream.seen_programmes = set()

# -----------------------------
# SAVE MERGED XML
# -----------------------------
def save_merged_xml(channel_ids, programmes, channel_id_to_display):
    with gzip.open(OUTPUT_XML_GZ, "wb") as f_out:
        f_out.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f_out.write(b"<tv>\n")

        for cid in sorted(channel_ids):
            ch_elem = ET.Element("channel", id=cid)
            ET.SubElement(ch_elem, "display-name").text = channel_id_to_display.get(cid, cid)
            f_out.write(ET.tostring(ch_elem, encoding="utf-8"))

        for prog in programmes:
            f_out.write(prog)

        f_out.write(b"\n</tv>")

# -----------------------------
# INDEX UPDATE
# -----------------------------
def get_eastern_timestamp():
    eastern = pytz.timezone("US/Eastern")
    return datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S %Z")

def update_index(master_display, matched_display_names):
    found = []
    not_found = []

    for channel in master_display:
        if channel in matched_display_names:
            found.append(channel)
        else:
            not_found.append(channel)

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

<p>Total channels in master list: {len(master_display)}</p>
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
    global channel_id_to_display
    channel_id_to_display = {}

    master_cleaned, master_display = load_master_list()
    allowed_master_channels = set(clean_text(c) for c in master_display)
    sources = load_epg_sources()

    all_channel_ids = set()
    all_programmes = []
    matched_display_names = set()

    print(f"Master channels loaded: {len(master_display)}")
    print(f"EPG sources loaded: {len(sources) + 1} (including locals feed)")

    # 1️⃣ Process all non-local feeds
    for url in sources:
        print(f"\nProcessing: {url}")
        content = fetch_content(url)
        if not content:
            continue

        try:
            channel_ids, id_to_display, programmes = parse_xml_stream(content, master_cleaned, allowed_master_channels)
        except ET.ParseError as e:
            print(f"XML parse error in {url}: {e}")
            continue

        all_channel_ids.update(channel_ids)
        all_programmes.extend(programmes)
        channel_id_to_display.update(id_to_display)
        matched_display_names.update(id_to_display.values())

        print(f"  Channels kept: {len(channel_ids)}")
        print(f"  Programmes kept: {len(programmes)}")

    # 2️⃣ Process local channels only from local feed
    print(f"\nProcessing local feed: {LOCAL_FEED_URL}")
    local_content = fetch_content(LOCAL_FEED_URL)
    if local_content:
        try:
            channel_ids, id_to_display, programmes = parse_xml_stream(
                local_content, master_cleaned, allowed_master_channels, local_only=True
            )
        except ET.ParseError as e:
            print(f"XML parse error in local feed: {e}")
        else:
            all_channel_ids.update(channel_ids)
            all_programmes.extend(programmes)
            channel_id_to_display.update(id_to_display)
            matched_display_names.update(id_to_display.values())
            print(f"  Local channels kept: {len(channel_ids)}")
            print(f"  Local programmes kept: {len(programmes)}")

    save_merged_xml(all_channel_ids, all_programmes, channel_id_to_display)
    update_index(master_display, matched_display_names)

    size_mb = os.path.getsize(OUTPUT_XML_GZ) / (1024 * 1024)
    print("\nFinished.")
    print(f"Final channels: {len(all_channel_ids)}")
    print(f"Final programmes: {len(all_programmes)}")
    print(f"Output size: {size_mb:.2f} MB")

if __name__ == "__main__":
    main()
