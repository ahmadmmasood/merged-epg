#!/usr/bin/env python3
import gzip
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import os

# ====== CONFIG ======
# Sources
sources = {
    "EPG_US": "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "EPG_LOCALS": "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "Indian1": "https://iptv-epg.org/files/epg-in.xml.gz",
    "Indian2": "https://www.open-epg.com/files/india3.xml.gz",
    "DigitalTV": "https://www.open-epg.com/files/unitedstates10.xml.gz"
}

# Channels to keep (best effort)
keep_channels = [
    # DC/MD/VA locals
    "WJLA-DT", "WUSA-DT", "WTTG-DT", "WDCA-DT", "WRC-DT", "WETA", "WMPT", "WFDC-DT", "WDCW", "WZDC-CD",
    # Premium & major networks
    "HBO", "HBO Zone", "HBO Comedy", "HBO Signature", "HBO2", "HBO East",
    "Max", "Cinemax", "Paramount+", "STARZ", "STARZ ENCORE", "MGM+", "The Movie Channel", "Flix", "ScreenPix", "Adult SwimMax",
    # General entertainment & news (East Coast)
    "A&E", "AMC", "AHC", "Animal Planet", "Baby TV US", "BBC America HD", "Boomerang", "Bravo",
    "Cartoon Network", "CNBC", "CMT", "CNN", "CNN International", "CourtTV", "Discovery Life", "Destination America",
    "Discovery Channel HD", "Discovery Family", "Disney Channel", "Disney Junior", "Disney XD", "E!", "ESPN HD",
    "ESPN2 HD", "ESPNews", "Fox Business", "Game Show Network", "Golf Channel", "HBO", "History HD", "HLN HD",
    "ID", "IFC", "IndiePlex", "Love Nature", "MBC1", "MBC Masr", "MBC Masr2", "Nogoum", "Balle Balle",
    "9X Jalwa", "MTV India", "National Geographic", "NBA", "NHL", "NFL", "Paramount Network", "Nick", "Nick Jr.",
    "Showtime", "Starz", "Syfy", "TBS", "TNT", "TravelXP", "USA", "VHI", "TV Land",
    # Local major networks
    "ABC", "CBS", "FOX", "NBC", "The CW", "PBS", "Telemundo", "Univision", "MyNetworkTV", "ION Television",
    "TeleXitos"
]

# ====== FUNCTIONS ======
def download_xml_gz(url):
    print(f"Downloading {url}")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    return gzip.decompress(r.content)

def parse_xml(data):
    return ET.fromstring(data)

def filter_channels(root):
    channels_to_keep = []
    programs_to_keep = []
    
    for channel in root.findall("channel"):
        if any(ch.lower() in channel.get("id", "").lower() for ch in keep_channels):
            channels_to_keep.append(channel)
    
    for program in root.findall("programme"):
        if any(ch.get("id") in [c.get("id") for c in channels_to_keep] for ch in [program]):
            programs_to_keep.append(program)
    
    return channels_to_keep, programs_to_keep

def save_merged_xml(channels, programs, filename="merged.xml.gz"):
    tv = ET.Element("tv")
    tv.set("source", "Custom Merge EPG")
    tv.set("last_updated", datetime.now().isoformat())  # local time
    
    for ch in channels:
        tv.append(ch)
    for pr in programs:
        tv.append(pr)
    
    tree = ET.ElementTree(tv)
    xml_bytes = ET.tostring(tree.getroot(), encoding="utf-8")
    with gzip.open(filename, "wb") as f:
        f.write(xml_bytes)
    print(f"Merged EPG saved: {filename}")

# ====== MAIN ======
all_channels = []
all_programs = []

for name, url in sources.items():
    try:
        data = download_xml_gz(url)
        root = parse_xml(data)
        channels, programs = filter_channels(root)
        all_channels.extend(channels)
        all_programs.extend(programs)
        print(f"Processed {name}: {len(channels)} channels, {len(programs)} programs")
    except Exception as e:
        print(f"Error processing {name}: {e}")

save_merged_xml(all_channels, all_programs)
print(f"EPG merge completed")
print(f"Last updated: {datetime.now().isoformat()}")
print(f"Channels kept: {len(all_channels)}")
print(f"Programs kept: {len(all_programs)}")

