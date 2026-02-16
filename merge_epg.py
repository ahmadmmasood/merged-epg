import os
from datetime import datetime
import pytz
import gzip
import shutil

def update_index_page(channels_count, programs_count, file_size, log_data):
    # Set timezone to Eastern Time
    eastern = pytz.timezone('US/Eastern')
    last_updated = datetime.now(eastern).strftime('%Y-%m-%d %H:%M:%S')

    # Prepare the HTML content
    html_content = f"""
    <html>
    <head><title>EPG Merge Status</title></head>
    <body>
    <h1>EPG Merge Status</h1>
    <p><strong>Last updated:</strong> {last_updated}</p>
    <p><strong>Channels kept:</strong> {channels_count}</p>
    <p><strong>Programs kept:</strong> {programs_count}</p>
    <p><strong>Final merged file size:</strong> {file_size:.2f} MB</p>
    <h2>Logs:</h2>
    <button onclick="document.getElementById('logs').style.display='block'">Show Logs</button>
    <button onclick="document.getElementById('logs').style.display='none'">Hide Logs</button>
    <div id="logs" style="display:none;">
        <pre>{log_data}</pre>
    </div>
    </body>
    </html>
    """

    # Write the content to the index.html file
    with open("index.html", "w") as file:
        file.write(html_content)
    print("index.html has been updated.")

def process_epg_data():
    # Sample data for this example (replace with actual merging logic)
    channels_all = ['Channel 1', 'Channel 2', 'Channel 3']  # Replace with actual channels list
    programs_all = ['Program 1', 'Program 2', 'Program 3']  # Replace with actual programs list

    # Write merged data to merged.xml.gz (assuming you generate the XML)
    merged_file = 'merged.xml.gz'
    with gzip.open(merged_file, 'wt') as f:
        # Replace this with actual merging logic
        f.write("<channels><channel><name>Example Channel</name></channel></channels>")  # Example XML content

    # Calculate counts and file size
    channels_count = len(channels_all)
    programs_count = len(programs_all)
    file_size = os.path.getsize(merged_file) / (1024 * 1024)  # File size in MB

    # Capture logs (you can format logs as needed)
    log_data = "Processing complete. No errors."  # Example log data, replace with actual logs

    # Update the index.html dynamically
    update_index_page(channels_count, programs_count, file_size, log_data)

if __name__ == "__main__":
    process_epg_data()

