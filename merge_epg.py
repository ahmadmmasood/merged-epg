#!/usr/bin/env python3
import requests, gzip, io
from lxml import etree
from datetime import datetime, timezone
import os

# ===== CONFIGURE YOUR FEEDS =====
epg_sources = {
    "US Main": "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz",
    "US Locals": "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz",
    "Indian 1": "https://iptv-epg.org/files/epg-in.xml.gz",
    "Indian 2": "https://www.open-epg.com/files/india3.xml.gz",
    "Digital TV": "https://www.open-epg.com/files/unitedstates10.xml.gz",
}

# ===== CHANNEL WHITELIST =====
whitelist = {
    # Local DC / Maryland / Northern Virginia
    "wjla-dt", "wusa-dt", "wttg-dt", "wdca-dt", "wrc-dt", "wdcw-dt",
    # PBS East Coast
    "weta-dt", "wdcq-dt", "wcvp-dt", "wmpb-dt", "wcpb-dt",
    # Local networks
    "abc", "cbs", "fox", "nbc", "the cw", "pbs", "telemundo", "univision", "mynetworktv", "ion television", "telexitos",
    # Premium / Movie Channels
    "hbo", "max", "cinemax", "paramount+ with showtime", "starz", "starz encore", "mgm+", "the movie channel", "flix", "screenpix", "adult swimmax", "showtime",
    # General entertainment
    "a&e", "amc", "bravo", "comedy central", "freeform", "fx", "fxx", "lifetime", "paramount network", "tbs", "tnt", "trutv", "usa", "vh1", "wetv",
    # News
    "bbc america", "bloomberg", "cnbc", "cnn", "cnn international", "fox business", "fox news", "hln", "msnbc", "newsnation", "the weather channel",
    # Sports (all timezones)
    "espn", "espn2", "espnu", "espnews", "fox sports 1", "fox sports 2", "nba tv", "nfl network", "nhl network", "mlb network", "sec network", "tennis channel", "big ten network", "cbs sports network", "golf channel", "tyc sports", "tudn",
    # Kids / Family
    "boomerang", "cartoon network", "disney channel", "disney junior", "disney xd", "nickelodeon", "nick jr.", "nicktoons", "teenick", "babyfirst", "tv one", "telehit", "telehit musica", "tr3s: mtv",
    # Lifestyle / Documentary
    "animal planet", "cooking channel", "destination america", "discovery channel", "discovery life", "discovery family", "food network", "hgtv", "history channel", "investigation discovery", "id", "magnolia network", "national geographic", "own", "science channel", "tlc", "travel channel",
    # Music / Variety
    "bet", "bet soul", "cmt", "mtv", "mtv2", "mtv classic", "fuse",
    # Classic / Religious / Other
    "fetv", "gsn", "hallmark channel", "hallmark mystery", "hallmark drama", "insp", "metv", "ovation", "reelz", "tv land",
}

# ===== STATUS FILE =====
status_file = "index.html"
with open(status_file, "w") as f:
    f.write(f"<html><body><h1>EPG merge in progress</h1><p>Started at {datetime.now(timezone.utc)} UTC</p></body></html>\n")

# ===== HELPER FUNCTION =====
def fetch_xml(url):
    print(f"Downloading {url} ...")
    r = requests.get(url, stream=True)
    r.raise_for_status()
    if url.endswith(".gz") or "gzip" in r.headers.get('Content-Type', ''):
        with gzip.open(io.BytesIO(r.content), "rb") as f:
            return etree.parse(f)
    else:
        return etree.fromstring(r.content)

def channel_in_whitelist(ch_element):
    names = [dn.text.lower() for dn in ch_element.xpath("display-name")]
    return any(name in whitelist for name in names)

# ===== MERGE XML =====
all_channels = {}
all_programs = []

for name, url in epg_sources.items():
    try:
        tree = fetch_xml(url)
        print(f"Processing {name} ...")
        for ch in tree.xpath("//channel"):
            ch_id = ch.get("id")
            if ch_id not in all_channels and channel_in_whitelist(ch):
                all_channels[ch_id] = ch
        for prog in tree.xpath("//programme"):
            ch_id = prog.get("channel")
            if ch_id in all_channels:
                all_programs.append(prog)
    except Exception as e:
        print(f"Failed to fetch {name}: {e}")

# ===== CREATE MERGED TREE =====
root = etree.Element("tv")
for ch in all_channels.values():
    root.append(ch)
for prog in all_programs:
    root.append(prog)

# ===== WRITE OUTPUT XML.GZ TO ROOT =====
merged_file = "merged.xml.gz"
with gzip.open(merged_file, "wb") as f:
    f.write(etree.tostring(root, xml_declaration=True, encoding="UTF-8"))

# ===== UPDATE STATUS =====
with open(status_file, "w") as f:
    f.write(f"<html><body><h1>EPG merge completed</h1><p>Last updated: {datetime.now(timezone.utc)} UTC</p>")
    f.write(f"<p>Channels kept: {len(all_channels)}</p><p>Programs kept: {len(all_programs)}</p></body></html>\n")

print(f"Done! Merged EPG written to {merged_file}")

