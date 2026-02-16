import gzip
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
from io import BytesIO

# ---------------- Sources ----------------
sources = [
    # US feeds
    "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",

    # Foreign feeds
    "https://iptv-epg.org/files/epg-eg.xml.gz",
    "https://iptv-epg.org/files/epg-in.xml.gz",
    "https://iptv-epg.org/files/epg-lb.xml.gz"
]

# ---------------- Indian Channels ----------------
indian_channels = [
    "star plus",
    "star bharat",
    "star gold",
    "star sports",
    "zee tv",
    "zee cinema",
    "zee news",
    "sony entertainment",
    "sony sab",
    "sony max",
    "colors",
    "colors cineplex",
    "b4u balle balle",
    "mtv india",
]

# ---------------- US East / Local Rules ----------------
def keep_us_channel(channel_name):
    name_lower = channel_name.lower()
    if "us_locals1" in channel_name.lower():
        return True
    return "east" in name_lower or ("east" not in name_lower and "west" not in name_lower)

# ---------------- Fetch and parse XML ----------------
all_channels = {}
all_programs = {}

for url in sources:
    try:
        # Only fetch TXT for URLs with 'epgshare01'
        if "epgshare01" in url:
            txt_url = url.replace("xml.gz", "txt")
            try:
                txt_response = requests.get(txt_url, timeout=15)
                txt_response.raise_for_status()
                txt_content = txt_response.text
                # Parse TXT content (process based on your specific format)
                # Example: extract and add channels to all_channels based on the content
                print(f"TXT fetch successful for {txt_url}")
            except requests.exceptions.RequestException as e:
                print(f"TXT fetch failed for {txt_url}: {e}")
        else:
            # Process XML for non-epgshare01 URLs (iptv-epg.org)
            print(f"Processing XML: {url}")
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            content = gzip.decompress(r.content)
            tree = ET.parse(BytesIO(content))
            root = tree.getroot()

            # Process channels
            for ch in root.findall('channel'):
                ch_id = ch.get('id')
                ch_name_el = ch.find('display-name')
                if ch_id and ch_name_el is not None:
                    ch_name = ch_name_el.text.strip()
                    # Keep only East or Local Channels
                    if "epg_ripper_US2" in url or "unitedstates10" in url:
                        if not keep_us_channel(ch_name):
                            continue
                    # Deduplicate by channel ID
                    if ch_id not in all_channels:
                        all_channels[ch_id] = ET.tostring(ch, encoding='unicode')

            # Process programs
            for pr in root.findall('programme'):
                pr_id = f"{pr.get('channel')}_{pr.find('title').text if pr.find('title') is not None else ''}"
                if pr_id not in all_programs:
                    all_programs[pr_id] = ET.tostring(pr, encoding='unicode')

    except Exception as e:
        print(f"Error fetching/parsing {url}: {e}")

# ---------------- Build final XML ----------------
root = ET.Element("tv")

# Add channels
for ch_xml in all_channels.values():
    root.append(ET.fromstring(ch_xml))

# Add programs
for pr_xml in all_programs.values():
    root.append(ET.fromstring(pr_xml))

final_xml = ET.tostring(root, encoding='utf-8')

# ---------------- Write to merged file ----------------
merged_file = "merged.xml.gz"
with gzip.open(merged_file, "wb") as f:
    f.write(final_xml)

# ---------------- Stats ----------------
timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
channels_count = len(all_channels)
programs_count = len(all_programs)
file_size_mb = round(len(final_xml) / (1024 * 1024), 2)

print(f"EPG Merge Status")
print(f"Last updated: {timestamp}")
print(f"Channels kept: {channels_count}")
print(f"Programs kept: {programs_count}")
print(f"Final merged file size: {file_size_mb} MB")

