import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO
import gzip
import pytz

# ---------------- Define sources ----------------
sources = [
    # US feeds (text files)
    "https://epgshare01.online/epgshare01/epg_ripper_US2.txt",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.txt",

    # Foreign feeds (xml.gz)
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://www.open-epg.com/files/egypt1.xml.gz",
    "https://www.open-epg.com/files/egypt2.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://www.open-epg.com/files/india3.xml.gz",
    "https://iptv-epg.org/files/epg-lb.xml.gz"
]

# ---------------- Define channels ----------------
local_channels = [
    "WRC-HD", "COZI", "CRIMES", "Oxygen", "WTTG-DT", "BUZZR", "START", "WJLA", "Charge!",
    "Comet", "ROAR", "WUSA-HD", "Crime", "Quest", "NEST", "QVC", "WBAL-DT", "MeTV", "Story",
    "GetTV", "QVC", "WFDC-DT", "getTV", "GRIT", "UniMas", "WDCA", "MOVIES", "HEROES", "FOXWX",
    "MPT-HD", "MPT-2", "MPTKIDS", "NHK-WLD", "WDVM-SD", "WETA-HD", "WETA UK", "KIDS", "WORLD",
    "METRO", "WHUT", "PBSKids", "WZDC", "XITOS", "WDCW-DT", "Antenna", "CWWNUV", "Comet", "TheNest",
    "ION", "Bounce", "CourtTV", "Laff", "IONPlus", "BUSTED", "GameSho", "HSN", "AltaVsn", "DEFY"
]

# ---------------- Define valid channel filters ----------------
def keep_us_channel(channel_name):
    """Only keep East Coast channels and no duplicates"""
    name_lower = channel_name.lower()
    if "us_locals1" in channel_name.lower():
        return True
    return "east" in name_lower and "west" not in name_lower

def is_valid_foreign_channel(channel_name):
    """Check if the channel is in one of the allowed foreign categories"""
    allowed_foreign_channels = [
        "b4u", "zee", "sony", "colors", "egypt", "lebanon"
    ]
    return any(channel.lower() in channel_name.lower() for channel in allowed_foreign_channels)

# ---------------- Fetch and parse XML ----------------
def fetch_channels_and_programs(url):
    try:
        if url.endswith(".txt"):
            # For .txt files, we use a much faster method (direct parsing)
            response = requests.get(url)
            response.raise_for_status()
            # Process the channel list directly from text
            channels = response.text.splitlines()
            return channels, []
        elif url.endswith(".xml.gz"):
            # For .xml.gz files, we use XML parsing
            response = requests.get(url)
            response.raise_for_status()
            content = gzip.decompress(response.content)
            tree = ET.ElementTree(ET.fromstring(content))
            root = tree.getroot()
            channels = []
            programs = []
            for ch in root.findall('channel'):
                ch_name = ch.find('display-name').text if ch.find('display-name') is not None else ''
                ch_id = ch.get('id')
                if keep_us_channel(ch_name) or is_valid_foreign_channel(ch_name):
                    channels.append((ch_id, ch_name))
            for pr in root.findall('programme'):
                programs.append(pr)
            return channels, programs
        return [], []
    except Exception as e:
        print(f"Error fetching/parsing {url}: {e}")
        return [], []

# ---------------- Build final XML ----------------
def build_final_xml(channels, programs):
    root = ET.Element("tv")
    for ch_id, ch_name in channels:
        ch_elem = ET.SubElement(root, "channel", id=ch_id)
        ET.SubElement(ch_elem, "display-name").text = ch_name
    for pr in programs:
        root.append(pr)
    return ET.tostring(root, encoding='utf-8')

# ---------------- Main execution ----------------
channels_all = []
programs_all = []

# Fetch and parse channels
for url in sources:
    channels, programs = fetch_channels_and_programs(url)
    channels_all.extend(channels)
    programs_all.extend(programs)

# Remove duplicates
channels_all = list(set(channels_all))

# Generate final XML
final_xml = build_final_xml(channels_all, programs_all)

# Write the merged EPG file
with gzip.open('merged.xml.gz', 'wb') as f:
    f.write(final_xml)

# ---------------- Stats ----------------
timestamp = datetime.now(pytz.timezone('US/Eastern')).strftime("%Y-%m-%d %H:%M:%S %Z")
channels_count = len(channels_all)
programs_count = len(programs_all)
file_size_mb = round(len(final_xml) / (1024 * 1024), 2)

# Update index.html with stats and logs
with open('index.html', 'w') as f:
    f.write(f"""
    <!DOCTYPE html>
    <html>
    <head>
    <title>EPG Merge Status</title>
    <meta charset="UTF-8">
    </head>
    <body>
    <h1>EPG Merge Status</h1>
    <p><strong>Last updated:</strong> {timestamp}</p>
    <p><strong>Channels kept:</strong> {channels_count}</p>
    <p><strong>Programs kept:</strong> {programs_count}</p>
    <p><strong>Final merged file size:</strong> {file_size_mb} MB</p>
    <p><strong>Logs:</strong></p>
    <button onclick="document.getElementById('log').style.display='block'">Show Logs</button>
    <div id="log" style="display:none; background-color:#f4f4f4; padding:10px;">
    Processing completed with {channels_count} channels and {programs_count} programs.
    <button onclick="document.getElementById('log').style.display='none'">Close</button>
    </div>
    </body>
    </html>
    """)

