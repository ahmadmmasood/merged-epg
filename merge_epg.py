{\rtf1\ansi\ansicpg1252\cocoartf2868
\cocoatextscaling0\cocoaplatform0{\fonttbl\f0\fswiss\fcharset0 Helvetica;}
{\colortbl;\red255\green255\blue255;}
{\*\expandedcolortbl;;}
\margl1440\margr1440\vieww11520\viewh8400\viewkind0
\pard\tx720\tx1440\tx2160\tx2880\tx3600\tx4320\tx5040\tx5760\tx6480\tx7200\tx7920\tx8640\pardirnatural\partightenfactor0

\f0\fs24 \cf0 import gzip\
import shutil\
import xml.etree.ElementTree as ET\
import requests\
from pathlib import Path\
from datetime import datetime, timedelta\
\
# ---------------------------\
# Configuration\
# ---------------------------\
\
# Main US XML sources\
sources = \{\
    "us_general": "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",\
    "us_locals": "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",\
    "digital_tv": "https://www.open-epg.com/files/unitedstates10.xml.gz",\
\}\
\
# Country EPGs for missing channels (one-time scan)\
country_sources = \{\
    "chile": "https://iptv-epg.org/files/epg-cl.xml.gz",\
    "egypt": "https://iptv-epg.org/files/epg-eg.xml.gz",\
    "uae": "https://iptv-epg.org/files/epg-ae.xml.gz",\
    "lebanon": "https://iptv-epg.org/files/epg-lb.xml.gz",\
    "saudi_arabia": "https://iptv-epg.org/files/epg-sa.xml.gz",\
    "turkey": "https://iptv-epg.org/files/epg-tr.xml.gz",\
    "india": "https://iptv-epg.org/files/epg-in.xml.gz",\
\}\
\
# Missing / extra channels to scan once\
missing_channels = [\
    "Ahgani TV", "Arabica TV", "NagoumFMTB", "MBC Masr", "MBC Masr2",\
    "MBC1", "Jalwa 9X", "Balle Balle", "Love Nature"\
]\
\
# US East Coast local keywords\
east_coast_keywords = ["Washington", "DC", "Baltimore", "Northern VA", "New York", "Boston", "Philadelphia"]\
\
# Regional sports keywords (filtered East Coast)\
regional_sports_keywords = ["NESN", "MSG", "NBC Sports Washington"]\
\
# National/international sports keywords (keep all)\
national_sports_keywords = ["NBA", "Soccer", "Football", "Tennis", "ESPN", "NBC Sports"]\
\
# Output paths\
output_file = Path("merged_epg.xml.gz")\
extra_channels_file = Path("extra_channels.xml.gz")  # stores one-time scan\
temp_dir = Path("temp_epg")\
temp_dir.mkdir(exist_ok=True)\
\
# ---------------------------\
# Helper Functions\
# ---------------------------\
\
def download_and_extract(url, filename):\
    local_path = temp_dir / filename\
    r = requests.get(url, stream=True)\
    r.raise_for_status()\
    with open(local_path, "wb") as f:\
        f.write(r.content)\
    # Extract gzip\
    extracted = temp_dir / filename.replace(".gz", "")\
    with gzip.open(local_path, "rb") as f_in:\
        with open(extracted, "wb") as f_out:\
            shutil.copyfileobj(f_in, f_out)\
    return extracted\
\
def parse_xml(file_path):\
    tree = ET.parse(file_path)\
    return tree.getroot()\
\
def write_xml_gz(root, path):\
    tree = ET.ElementTree(root)\
    temp_path = temp_dir / "temp.xml"\
    tree.write(temp_path, encoding="utf-8", xml_declaration=True)\
    with open(temp_path, "rb") as f_in:\
        with gzip.open(path, "wb") as f_out:\
            shutil.copyfileobj(f_in, f_out)\
\
def filter_channels(root, include_keywords=None, exclude_keywords=None):\
    result = []\
    for ch in root.findall("channel"):\
        name = ch.get("display-name") or ch.get("id") or ""\
        if include_keywords and not any(k.lower() in name.lower() for k in include_keywords):\
            continue\
        if exclude_keywords and any(k.lower() in name.lower() for k in exclude_keywords):\
            continue\
        result.append(ch)\
    return result\
\
def filter_programs_by_channel(root, channel_ids):\
    result = []\
    for prog in root.findall("programme"):\
        if prog.get("channel") in channel_ids:\
            result.append(prog)\
    return result\
\
def trim_programs(root, days=5):\
    now = datetime.utcnow()\
    end_time = now + timedelta(days=days)\
    result = []\
    for prog in root.findall("programme"):\
        start = prog.get("start")\
        if not start:\
            continue\
        # XMLTV time format: YYYYMMDDHHMMSS + optional TZ\
        dt = datetime.strptime(start[:14], "%Y%m%d%H%M%S")\
        if dt <= end_time:\
            result.append(prog)\
    return result\
\
def merge_epgs(main_files, extra_root=None):\
    merged_root = ET.Element("tv")\
    channel_ids = set()\
\
    for f in main_files:\
        root = parse_xml(f)\
        for ch in root.findall("channel"):\
            cid = ch.get("id")\
            if cid not in channel_ids:\
                merged_root.append(ch)\
                channel_ids.add(cid)\
        for prog in root.findall("programme"):\
            if prog.get("channel") in channel_ids:\
                merged_root.append(prog)\
\
    # Add extra channels from one-time scan\
    if extra_root:\
        for ch in extra_root.findall("channel"):\
            cid = ch.get("id")\
            if cid not in channel_ids:\
                merged_root.append(ch)\
                channel_ids.add(cid)\
        for prog in extra_root.findall("programme"):\
            if prog.get("channel") in channel_ids:\
                merged_root.append(prog)\
\
    return merged_root\
\
# ---------------------------\
# Step 1: Download main US sources\
# ---------------------------\
\
main_files = []\
for key, url in sources.items():\
    print(f"Downloading \{key\}...")\
    f = download_and_extract(url, f"\{key\}.xml.gz")\
    main_files.append(f)\
\
# ---------------------------\
# Step 2: One-time scan for missing channels\
# ---------------------------\
\
if not extra_channels_file.exists():\
    print("Performing one-time scan for missing channels...")\
    extra_root = ET.Element("tv")\
    for key, url in country_sources.items():\
        print(f"Checking \{key\} EPG...")\
        f = download_and_extract(url, f"\{key\}.xml.gz")\
        root = parse_xml(f)\
        for ch in root.findall("channel"):\
            name = ch.get("display-name") or ch.get("id") or ""\
            if any(mc.lower() in name.lower() for mc in missing_channels) \\\
               or any(sk.lower() in name.lower() for sk in national_sports_keywords + regional_sports_keywords):\
                extra_root.append(ch)\
        for prog in root.findall("programme"):\
            ch_id = prog.get("channel")\
            if any(mc.lower() in ch_id.lower() for mc in missing_channels) \\\
               or any(sk.lower() in ch_id.lower() for sk in national_sports_keywords + regional_sports_keywords):\
                extra_root.append(prog)\
    write_xml_gz(extra_root, extra_channels_file)\
else:\
    print("Using previously scanned extra channels...")\
    with gzip.open(extra_channels_file, "rb") as f:\
        extra_root = ET.parse(f).getroot()\
\
# ---------------------------\
# Step 3: Filter US channels to East Coast only\
# ---------------------------\
\
# US locals\
us_locals_root = parse_xml(main_files[1])\
east_coast_locals = filter_channels(us_locals_root, include_keywords=east_coast_keywords)\
east_coast_local_ids = [ch.get("id") for ch in east_coast_locals]\
\
# Other US sources\
us_general_root = parse_xml(main_files[0])\
digital_root = parse_xml(main_files[2])\
\
def filter_us_channels(root):\
    return filter_channels(root, include_keywords=east_coast_keywords)\
\
filtered_us_general = filter_us_channels(us_general_root)\
filtered_digital = filter_us_channels(digital_root)\
\
# ---------------------------\
# Step 4: Merge all\
# ---------------------------\
\
all_main_files = []\
\
# Write filtered US sources to temp files\
def write_temp(root, name):\
    path = temp_dir / f"\{name\}.xml"\
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)\
    return path\
\
all_main_files.append(write_temp(filtered_us_general, "us_general_filtered"))\
all_main_files.append(write_temp(filtered_digital, "digital_filtered"))\
all_main_files.append(write_temp(east_coast_locals, "locals_filtered"))\
\
merged_root = merge_epgs(all_main_files, extra_root)\
\
# Trim programs to 5 days\
for prog in merged_root.findall("programme"):\
    merged_root.remove(prog)\
for prog in trim_programs(merged_root, days=5):\
    merged_root.append(prog)\
\
# ---------------------------\
# Step 5: Write merged XML.GZ\
# ---------------------------\
\
write_xml_gz(merged_root, output_file)\
print(f"Merged EPG written to \{output_file\}")\
}