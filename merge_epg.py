import os
import gzip
import requests
import pytz
import xml.etree.ElementTree as ET
from datetime import datetime

#=========================
# Load master channels
#=========================
def load_master_channels(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        channels = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    return channels

#=========================
# Normalize channel names
#=========================
def normalize_channel_name(name):
    if not name:
        return None
    name = name.lower()
    # Remove known suffixes
    for suffix in [".us2", ".us_locals1", ".txt"]:
        if name.endswith(suffix):
            name = name.replace(suffix, "")
    # Remove TV, HD, HDTV, East, West, Pacific, trailing/leading -
    for remove_word in ["tv", "hd", "hdtv", "east", "west", "pacific", "-"]:
        name = name.replace(remove_word, "")
    # Replace dots with spaces
    name = name.replace(".", " ")
    # Replace & with 'and'
    name = name.replace("&", "and")
    # Remove extra spaces
    name = " ".join(name.split())
    return name.strip()

#=========================
# Fetch and parse EPG
#=========================
def fetch_and_parse_epg(url):
    try:
        print(f"Fetching {url}")
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        content = response.content

        # Handle gzipped files
        if url.endswith(".gz"):
            tmp_file = "tmp_epg.xml.gz"
            with open(tmp_file, "wb") as f:
                f.write(content)
            with gzip.open(tmp_file, "rb") as f_in:
                content = f_in.read()
            os.remove(tmp_file)

        # TXT files
        if url.endswith(".txt"):
            lines = content.decode("utf-8", errors="ignore").splitlines()
            channels = [line.strip() for line in lines if line.strip()]
            print(f"Processed {url} - Parsed {len(channels)} channels")
            return channels

        # XML files
        root = ET.fromstring(content)
        channels = []
        for ch in root.findall(".//channel"):
            ch_name = ch.get("id") or ch.findtext("display-name")
            if ch_name:
                channels.append(ch_name.strip())
        print(f"Processed {url} - Parsed {len(channels)} channels")
        return channels

    except Exception as e:
        print(f"Error parsing {url}: {e}")
        return []

#=========================
# Update index.html
#=========================
def update_index_page(found_channels, not_found_channels, master_channels, merged_file_path):
    eastern = pytz.timezone('US/Eastern')
    last_updated = datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S')

    # Proper file size calculation
    final_size = os.path.getsize(merged_file_path) / (1024 * 1024) if os.path.exists(merged_file_path) else 0.0

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>EPG Merge Status</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            table {{ border-collapse: collapse; width: 100%; max-width: 700px; font-size: 14px; }}
            th, td {{ border: 1px solid #ccc; padding: 5px; text-align: left; }}
            th {{ background-color: #f2f2f2; }}
            .found {{ background-color: #d4edda; }}
            .notfound {{ background-color: #f8d7da; }}
            button {{ margin: 5px 0; }}
        </style>
    </head>
    <body>
    <h1>EPG Merge Status</h1>
    <p><strong>Last updated:</strong> {last_updated}</p>
    <p><strong>Total channels in master list:</strong> {len(master_channels)}</p>
    <p><strong>Channels found:</strong> {len(found_channels)}</p>
    <p><strong>Channels not found:</strong> {len(not_found_channels)}</p>
    <p><strong>Final merged file size:</strong> {final_size:.2f} MB</p>

    <h2>Channels Found</h2>
    <button onclick="document.getElementById('found').style.display='block'">Show Found</button>
    <button onclick="document.getElementById('found').style.display='none'">Hide Found</button>
    <div id="found" style="display:none;">
        <table>
            <tr><th>Channel Name</th></tr>
            {''.join([f'<tr class="found"><td>{ch}</td></tr>' for ch in found_channels])}
        </table>
    </div>

    <h2>Channels Not Found</h2>
    <button onclick="document.getElementById('notfound').style.display='block'">Show Not Found</button>
    <button onclick="document.getElementById('notfound').style.display='none'">Hide Not Found</button>
    <div id="notfound" style="display:none;">
        <table>
            <tr><th>Channel Name</th></tr>
            {''.join([f'<tr class="notfound"><td>{ch}</td></tr>' for ch in not_found_channels])}
        </table>
    </div>
    </body>
    </html>
    """

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print("index.html has been updated.")

#=========================
# Main merge function
#=========================
def main():
    master_channels = load_master_channels("master_channels.txt")
    epg_sources = []
    with open("epg_sources.txt", "r", encoding="utf-8") as f:
        epg_sources = [line.strip() for line in f if line.strip()]

    found_channels = []
    all_parsed_channels = []

    # Parse all EPG sources
    for url in epg_sources:
        channels = fetch_and_parse_epg(url)
        all_parsed_channels.extend(channels)

    # Normalize and match with master list
    normalized_master = [normalize_channel_name(ch) for ch in master_channels]
    for ch in all_parsed_channels:
        norm_ch = normalize_channel_name(ch)
        if norm_ch in normalized_master and norm_ch not in found_channels:
            found_channels.append(norm_ch)

    not_found_channels = [normalize_channel_name(ch) for ch in master_channels if normalize_channel_name(ch) not in found_channels]

    # Write merged EPG XML (just found channels)
    merged_file = "merged_epg.xml.gz"
    with gzip.open(merged_file, "wt", encoding="utf-8") as f:
        f.write("<tv>\n")
        for ch in found_channels:
            f.write(f'  <channel id="{ch}"><display-name>{ch}</display-name></channel>\n')
        f.write("</tv>\n")

    # Now the merged file exists, size will be correct
    update_index_page(found_channels, not_found_channels, master_channels, merged_file)

if __name__ == "__main__":
    main()

