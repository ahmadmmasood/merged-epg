import gzip
import requests
from lxml import etree
from datetime import datetime
import pytz

# --- URLs to pull EPG from ---
EPG_URLS = [
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://www.open-epg.com/files/unitedstates10.xml.gz"
]

# --- Channels you want to keep (partial list shown, extend as needed) ---
KEEP_CHANNELS = [
    # Local DC/MD/VA
    "WRC-DT", "WUSA-DT", "WJLA-DT", "WTTG-DT", "WDCA-DT", "WETA", "WMPT",
    "WFDC-DT", "WDCW", "WZDC-CD", "WDVM-TV", "WJAL",
    # Major US Cable/Streaming (East coast)
    "A&E", "AMC", "AHC", "Animal Planet", "Baby TV US", "BBC America HD", "Boomerang",
    "Bravo", "Cartoon Network", "CNBC", "CMT", "CNN", "CNN International", "CourtTV",
    "Discovery Life", "Destination America", "Discovery Channel HD", "Discovery Family",
    "Disney Channel", "Disney Junior", "Disney XD", "E!", "ESPN HD", "ESPN2 HD", "ESPNews",
    "Fox Business", "FX HD", "Game Show Network", "Golf USA", "HBO", "HBO Max", "HBO Signature",
    "History HD", "HLN HD", "ID", "IFC", "IndiePlex", "Love Nature",
    "MBC1", "MBC Masr", "MBC Masr2", "Nogoum", "Balle Balle", "9X Jalwa", "MTV India",
    "NBA", "NHL", "NFL", "Paramount Network", "Nick", "Showtime", "STARZ", "Syfy",
    "TBS", "TNT", "TravelXP", "USA", "VHI", "TVLand", "TeleXitos",
    # Add more as needed
]

# --- Function to fetch and parse XML.gz ---
def fetch_epg(url):
    print(f"Downloading {url} ...")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    with gzip.GzipFile(fileobj=r.raw) as f:
        tree = etree.parse(f)
    return tree

# --- Merge all EPGs ---
merged_channels = {}
merged_programs = []

for url in EPG_URLS:
    tree = fetch_epg(url)
    root = tree.getroot()
    for channel in root.findall("channel"):
        ch_id = channel.get("id")
        ch_name = channel.findtext("display-name") or ""
        if any(k.lower() in ch_name.lower() or k.lower() in ch_id.lower() for k in KEEP_CHANNELS):
            merged_channels[ch_id] = channel
    for program in root.findall("programme"):
        prog_ch = program.get("channel")
        if prog_ch in merged_channels:
            merged_programs.append(program)

# --- Create merged XML tree ---
tv = etree.Element("tv")
for ch in merged_channels.values():
    tv.append(ch)
for prog in merged_programs:
    tv.append(prog)

# --- Save merged XML.gz to root ---
output_file = "merged.xml.gz"
with gzip.open(output_file, "wb") as f:
    f.write(etree.tostring(tv, xml_declaration=True, encoding="UTF-8", pretty_print=True))

# --- Generate index.html with local Eastern Time ---
eastern = pytz.timezone("US/Eastern")
now = datetime.now(eastern).strftime("%Y-%m-%d %H:%M:%S %Z")
index_html = f"""<html>
<head><title>EPG Merge</title></head>
<body>
<h1>EPG Merge Completed</h1>
<p>Last updated: {now}</p>
<p>Channels kept: {len(merged_channels)}</p>
<p>Programs kept: {len(merged_programs)}</p>
</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(index_html)

print(f"EPG merge completed. Channels kept: {len(merged_channels)}, Programs kept: {len(merged_programs)}")
print(f"Last updated: {now}")

