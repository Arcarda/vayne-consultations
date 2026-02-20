#!/usr/bin/env python3
"""
🎯 Niche Builder — Smart Scout Target List Generator
=====================================================
Vayne Consulting — Liquidity Acceleration Tool

Builds a targets.txt list by searching Google for businesses
in a specific niche and location, filtering out aggregator sites.

RECOMMENDED TARGET NICHES (highest conversion for Vayne Consulting):
  - "CPA accounting firm"           (outdated sites, strong budgets)
  - "immigration consultant"        (Bill 96 bilingual angle in QC)
  - "mortgage broker"               (crowded market, high differentiation need)
  - "physiotherapy clinic"          (broken booking widgets, poor SEO)
  - "boutique law firm"             (neglected sites, clear ROI case)

Usage:
    python niche_builder.py --niche "CPA accounting firm" --location "Montreal" --count 50
    python niche_builder.py --niche "immigration consultant" --location "Toronto" --count 100
    python niche_builder.py --niche "mortgage broker" --location "Vancouver" --count 75

Requirements:
    pip install requests python-dotenv

    Option A (Free, 100 queries/day): Google Custom Search API
        1. Get API key:      https://console.developers.google.com/
        2. Create Search Engine: https://cse.google.com/ (set to "Search the entire web")
        3. Add to .env:
              GOOGLE_API_KEY=your_key
              GOOGLE_CSE_ID=your_engine_id

    Option B (Paid ~$50/mo, no daily limit): SerpAPI
        1. Sign up: https://serpapi.com/
        2. Add to .env: SERPAPI_KEY=your_key
        3. Run with: --engine serpapi
"""

import argparse
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# AGGREGATOR / DIRECTORY BLACKLIST
# Sites to exclude from results — these are not direct business websites
# ============================================================================
BLACKLIST = [
    "yelp.", "facebook.", "instagram.", "linkedin.", "houzz.",
    "homestars.", "google.", "yellowpages.", "canadabusiness.",
    "bark.com", "thumbtack.", "pagesjaunes.", "canpages.",
    "trustpilot.", "bbb.", "angieslist.", "angi.", "reddit.",
    "twitter.", "tiktok.", "youtube.", "wikipedia.",
    "tripadvisor.", "groupon.", "kijiji."
]


def is_valid_target(url: str) -> bool:
    """Check if a URL is a valid direct business website (not an aggregator)."""
    return not any(b in url.lower() for b in BLACKLIST)


def search_google_cse(query: str, count: int = 50) -> list[str]:
    """
    Use Google Custom Search Engine API.
    Free tier: 100 queries/day. Each query returns up to 10 results.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")

    if not api_key or not cse_id:
        print("[!] Google CSE not configured.")
        print("    Set GOOGLE_API_KEY and GOOGLE_CSE_ID in your .env file.")
        print("    See: https://cse.google.com/ and https://console.developers.google.com/")
        return []

    urls = []
    start = 1
    max_pages = (count // 10) + 2  # How many API pages to fetch

    for page in range(max_pages):
        if len(urls) >= count:
            break

        try:
            resp = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params={
                    "key": api_key,
                    "cx": cse_id,
                    "q": query,
                    "start": start,
                    "num": 10,
                },
                timeout=10
            )
        except requests.RequestException as e:
            print(f"[!] Network error: {e}")
            break

        if resp.status_code == 429:
            print("[!] Rate limit hit. Try again tomorrow or switch to SerpAPI.")
            break
        elif resp.status_code != 200:
            print(f"[!] CSE Error {resp.status_code}: {resp.text[:200]}")
            break

        data = resp.json()
        items = data.get("items", [])
        if not items:
            print("[i] No more results from Google CSE.")
            break

        for item in items:
            url = item.get("link", "")
            if url and is_valid_target(url):
                urls.append(url)

        start += 10
        time.sleep(1.0)  # Be polite to the API

    return urls[:count]


def search_serpapi(query: str, count: int = 50) -> list[str]:
    """
    Use SerpAPI for Google search results.
    More reliable, no daily limit issues. ~$50/mo for 5,000 queries.
    """
    api_key = os.getenv("SERPAPI_KEY")

    if not api_key:
        print("[!] SerpAPI not configured. Set SERPAPI_KEY in your .env file.")
        print("    Sign up at: https://serpapi.com/")
        return []

    urls = []
    start = 0

    while len(urls) < count:
        try:
            resp = requests.get(
                "https://serpapi.com/search",
                params={
                    "engine": "google",
                    "q": query,
                    "start": start,
                    "num": 10,
                    "api_key": api_key,
                    "gl": "ca",   # Canada results
                    "hl": "en",
                },
                timeout=15
            )
        except requests.RequestException as e:
            print(f"[!] Network error: {e}")
            break

        if resp.status_code != 200:
            print(f"[!] SerpAPI Error {resp.status_code}: {resp.text[:200]}")
            break

        data = resp.json()
        results = data.get("organic_results", [])
        if not results:
            break

        for r in results:
            url = r.get("link", "")
            if url and is_valid_target(url):
                urls.append(url)

        start += 10
        time.sleep(0.5)

    return urls[:count]


def dedupe_against_existing(urls: list[str], existing_file: str) -> list[str]:
    """Remove URLs already in the targets file to avoid re-contacting."""
    if not Path(existing_file).exists():
        return urls

    with open(existing_file) as f:
        already_seen = set(line.strip().lower() for line in f if line.strip())

    new_urls = [u for u in urls if u.lower() not in already_seen]
    dupes = len(urls) - len(new_urls)

    if dupes > 0:
        print(f"[i] Filtered {dupes} duplicate URL(s) already in {existing_file}")

    return new_urls


def main():
    parser = argparse.ArgumentParser(
        description="Niche Builder — generate target URL lists for Smart Scout"
    )
    parser.add_argument("--niche", required=True,
                        help='Business type to target. E.g. "interior designer"')
    parser.add_argument("--location", required=True,
                        help='City or region. E.g. "Montreal" or "Ontario"')
    parser.add_argument("--count", type=int, default=50,
                        help="Number of target URLs to collect (default: 50)")
    parser.add_argument("--output", default="targets.txt",
                        help="Output file to append URLs to (default: targets.txt)")
    parser.add_argument("--engine", choices=["google", "serpapi"], default="google",
                        help="Search engine to use (default: google CSE)")
    args = parser.parse_args()

    # Build the search query
    # Targeting .ca and .com, excluding major directories
    query = (
        f'"{args.niche}" {args.location} '
        f'(site:.ca OR site:.com) '
        f'-yelp -facebook -instagram -houzz -homestars -yellowpages'
    )

    print(f"\n🎯 Niche Builder")
    print(f"   Niche:    {args.niche}")
    print(f"   Location: {args.location}")
    print(f"   Engine:   {args.engine}")
    print(f"   Count:    {args.count}")
    print(f"   Output:   {args.output}")
    print(f"   Query:    {query}\n")

    # Search
    if args.engine == "serpapi":
        urls = search_serpapi(query, args.count)
    else:
        urls = search_google_cse(query, args.count)

    if not urls:
        print("\n[!] No URLs found.")
        print("    Check your API keys or try a different niche/location.")
        return

    # Deduplicate
    urls = dedupe_against_existing(urls, args.output)

    if not urls:
        print("\n[i] All found URLs are already in your target list. Nothing new to add.")
        return

    # Append to output file
    with open(args.output, "a") as f:
        for url in urls:
            f.write(url + "\n")

    print(f"\n✅ Added {len(urls)} new targets to: {args.output}")
    print(f"\nNext step:")
    print(f"  python ../tools/smart_scout.py --file {args.output} --output reports/")


if __name__ == "__main__":
    main()
