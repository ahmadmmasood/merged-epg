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
    """Return similarity ratio between 0 and 1"""
    return SequenceMatcher(None, a, b).ratio()

# -----------------------------
# ALIASES (Exact raw EPG IDs)
# -----------------------------
EPG_ALIASES = {
    # Premium
    "home.and.garden.television.hd.us2": "HGTV",
    "5_starmax.hd.east.us2": "5StarMax",
    "hbo_family.us2": "HBO Family",
    "hbo.us": "HBO",
    "hbo_hits.us": "HBO Hits",
    "hbo_comedy.us": "HBO Comedy",
    "hbo_drama.us": "HBO Drama",
    "hbo_signature.us": "HBO Signature",
    "hbo_zone.us": "HBO Zone",
    "cinemax.us": "Cinemax",
    "actionmax.hd": "ActionMax",
    "moremax.hd": "MoreMax",
    "thrillermax.hd": "ThrillerMax",
    "moviemax.hd": "MovieMax",
    "outermax.hd": "OuterMax",
    "showtime.us": "Showtime",
    "showtime2.us": "Showtime 2",
    "sho_bet.us": "SHO×BET",
    "showtime_extreme.us": "Showtime Extreme",
    "showtime_family.us": "Showtime Family Zone",
    "showtime_next.us": "Showtime Next",
    "showtime_showcase.us": "Showtime Showcase",
    "showtime_women.us": "Showtime Women",
    "tmc.us": "The Movie Channel",
    "tmc_xtra.hd": "The Movie Channel Xtra",
    "flix.us": "Flix",
    "starz.us": "Starz",
    "starz_cinema.hd": "Starz Cinema",
    "starz_comedy.hd": "Starz Comedy",
    "starz_edge.hd": "Starz Edge",
    "starz_inblack.hd": "Starz InBlack",
    "starz_kids_family.hd": "Starz Kids & Family",
    "starz_encore.hd": "Starz Encore",
    "starz_encore_action.hd": "Starz Encore Action",
    "starz_encore_black.hd": "Starz Encore Black",
    "starz_encore_classic.hd": "Starz Encore Classic",
    "starz_encore_family.hd": "Starz Encore Family",
    "starz_encore_suspense.hd": "Starz Encore Suspense",
    "starz_encore_westerns.hd": "Starz Encore Westerns",
    "indieplex.hd": "IndiePlex",
    "movieplex.hd": "MoviePlex",
    "retroplex.hd": "RetroPlex",

    # Foreign / International
    "aajtak.in": "Aaj Tak",
    "al_ahram.tv": "Al Ahram TV",
    "al_hayat.tv": "Al Hayat TV",
    "al_masriya.tv": "Al Masriya TV",
    "al_nahar.tv": "Al Nahar TV",
    "cbc.egypt": "CBC (Egypt)",
    "dream.tv": "Dream TV",
    "lbci.tv": "LBCI",
    "mtv_lebanon": "MTV Lebanon",
    "nile.tv": "Nile TV International",
    "otv_lebanon": "OTV Lebanon",
    "republic.tv": "Republic TV",
    "sun.tv": "Sun TV",
    "tv9": "TV9",
    
    # Local / Regional
    "buzzr": "BUZZR",
    "crimes": "CRIMES",
    "cwwnuv": "CWWNUV",
    "csn_midatlantic": "Comcast SportsNet Mid-Atlantic",
    "crime_tv": "Crime TV",
    "fox_weather": "Fox Weather",
    "future_tv": "Future TV",
    "gettv": "GetTV",
    "heroes_icons": "Heroes & Icons",
    "mpt_kids": "MPT Kids",
    "mpt2": "MPT-2",
    "mtv2": "MTV2",
    "metv": "MeTV",
    "metro": "Metro",
    "wjla_news": "NewsChannel 8 (WJLA News)",
    "wusa_hd": "WUSA-HD",
    "wjz_cbs": "WJZ 13 (CBS Baltimore)",
    "wmar_abc": "WMAR 2 (ABC Baltimore)",
    "weta_kids": "WETA Kids",
    "weta_uk": "WETA UK",
    "weta_hd": "WETA-HD",
    "xitos": "XITOS",

    # Kids / Cartoon
    "cartoonito.us": "Cartoonito",
    "nick_at_nite.us": "Nick at Nite",
    "teennick.us": "TeenNick"
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
# LOCAL ID NORMALIZATION
# -----------------------------
def normalize_epg_id(raw_id):
    """Remove source-specific suffixes like .us_locals1"""
    if not raw_id:
        return ""
    local_suffixes = [".us_locals1", ".us_locals2", ".us_locals"]
    for suffix in local_suffixes:
        if raw_id.lower().endswith(suffix):
            return raw_id[: -len(suffix)]
    return raw_id

# -----------------------------
# PARSE XML STREAM
# -----------------------------
def parse_xml_stream(content_bytes, master_cleaned, days_limit=3):
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
            base_id = normalize_epg_id(raw_id)
            display = elem.findtext("display-name") or raw_id
            cleaned = clean_text(display)
            matched = False

            # Exact-ID alias mapping
            if base_id in EPG_ALIASES:
                allowed_channel_ids.add(raw_id)
                channel_id_to_display[raw_id] = EPG_ALIASES[base_id]
                matched = True

            # Exact cleaned master match
            if not matched and base_id.lower() in master_cleaned:
                allowed_channel_ids.add(raw_id)
                channel_id_to_display[raw_id] = master_cleaned[base_id.lower()]
                matched = True

            # Substring match
            if not matched:
                for master_clean, master_disp in master_cleaned.items():
                    if master_clean in cleaned or cleaned in master_clean:
                        allowed_channel_ids.add(raw_id)
                        channel_id_to_display[raw_id] = master_disp
                        matched = True
                        break

            # Enhanced fuzzy match
            if not matched:
                for master_clean, master_disp in master_cleaned.items():
                    if similar(cleaned, master_clean) >= 0.7 or similar(clean_text(raw_id), master_clean) >= 0.7:
                        allowed_channel_ids.add(raw_id)
                        channel_id_to_display[raw_id] = master_disp
                        matched = True
                        break

            if not matched:
                unmatched_channels.append((raw_id, display))

            elem.clear()

        elif elem.tag == "programme":
            raw_channel = elem.attrib.get("channel")
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
def save_merged_xml(channel_ids, programmes):
    with gzip.open(OUTPUT_XML_GZ, "wb") as f_out:
        f_out.write(b'<?xml version="1.0" encoding="UTF-8"?>\n')
        f_out.write(b"<tv>\n")

        for cid in sorted(channel_ids):
            ch_elem = ET.Element("channel", id=cid)
            ET.SubElement(ch_elem, "display-name").text = cid
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
    master_cleaned, master_display = load_master_list()
    sources = load_epg_sources()

    all_channel_ids = set()
    all_programmes = []
    matched_display_names = set()

    print(f"Master channels loaded: {len(master_display)}")
    print(f"EPG sources loaded: {len(sources)}")

    for url in sources:
        print(f"\nProcessing: {url}")
        content = fetch_content(url)
        if not content:
            continue

        try:
            channel_ids, id_to_display, programmes = parse_xml_stream(content, master_cleaned)
        except ET.ParseError as e:
            print(f"XML parse error in {url}: {e}")
            continue

        all_channel_ids.update(channel_ids)
        all_programmes.extend(programmes)

        for disp in id_to_display.values():
            matched_display_names.add(disp)

        print(f"  Channels kept: {len(channel_ids)}")
        print(f"  Programmes kept: {len(programmes)}")

    save_merged_xml(all_channel_ids, all_programmes)
    update_index(master_display, matched_display_names)

    size_mb = os.path.getsize(OUTPUT_XML_GZ) / (1024 * 1024)
    print("\nFinished.")
    print(f"Final channels: {len(all_channel_ids)}")
    print(f"Final programmes: {len(all_programmes)}")
    print(f"Output size: {size_mb:.2f} MB")

if __name__ == "__main__":
    main()
