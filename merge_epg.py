name: Merge EPG Daily

on:
  push:
    branches:
      - main
  schedule:
    - cron: '0 */6 * * *'
  workflow_dispatch:

jobs:
  merge-epg:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v3
        with:
          fetch-depth: 0

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install requests lxml pytz

      - name: Run EPG merge
        run: python merge_epg.py

      - name: Debug output files
        run: ls -lah

      - name: Configure Git
        run: |
          git config user.name "GitHub Actions"
          git config user.email "actions@github.com"

      - name: Commit XML.GZ only
        run: |
          git add merged.xml.gz local.xml.gz arabic2.xml.gz index.html merge_epg.py

          if git diff --cached --quiet; then
            echo "No changes to commit"
          else
            git commit -m "Auto-update EPG (gz only)"
            git push origin main
          fi

      - name: Create GitHub Release with XML files
        uses: softprops/action-gh-release@v1
        with:
          tag_name: latest
          name: "EPG Latest Build"
          overwrite: true
          files: |
            merged.xml
            local.xml
            arabic2.xml
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
