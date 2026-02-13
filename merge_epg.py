#!/usr/bin/env python3
import requests
import gzip
import shutil
import os

# Create output folder if not exists
os.makedirs("output", exist_ok=True)

# Function to update index.html with current status
def update_status(message, done=False):
    if done:
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head><meta charset="UTF-8"><title>EPG Ready</title></head>
        <body>
            <h1>EPG Merge Complete!</h1>
            <p><a href="merged.xml.gz">Download the merged EPG XML</a></p>
        </body>
        </html>
        """
    else:
        html_content = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head><meta charset="UTF-8"><title>EPG Merge Status</title></head>
        <body>
            <h1>EPG Merge in Progress</h1>
            <p>Current step: {message}</p>
        </body>
        </html>
        """
    with open("output/index.html", "w") as f:
        f.write(html_content)

# List of EPG URLs to download
epg_sources = [
    ("US EPG", "https://epgshare01.online/epgshare01/epg_ripper_US2.xml.gz"),
    ("US Locals", "https://epgshare01.online/epgshare01/epg_ripper_US_LOCALS1.xml.gz"),
    ("Indian 1", "https://iptv-epg.org/files/epg-in.xml.gz"),
    ("Indian 2", "https://www.open-epg.com/files/india3.xml.gz"),
    ("Digital TV", "https://www.open-epg.com/files/unitedstates10.xml.gz"),
]

downloaded_files = []

for name, url in epg_sources:
    update_status(f"Downloading {name}...")
    r = requests.get(url, stream=True)
    local_file = f"output/{name.replace(' ', '_')}.xml.gz"
    with open(local_file, "wb") as f:
        f.write(r.content)
    downloaded_files.append(local_file)

# Merge files
update_status("Merging EPG files...")
merged_file = "output/merged.xml"
with open(merged_file, "wb") as outfile:
    for file in downloaded_files:
        with gzip.open(file, "rb") as f:
            shutil.copyfileobj(f, outfile)

# Compress merged.xml to merged.xml.gz
update_status("Compressing merged EPG...")
with open(merged_file, "rb") as f_in:
    with gzip.open("output/merged.xml.gz", "wb") as f_out:
        shutil.copyfileobj(f_in, f_out)

# Clean up temporary merged.xml if desired
os.remove(merged_file)

# Update index.html to final link
update_status("EPG merge complete!", done=True)
print("EPG merge finished: output/merged.xml.gz")

