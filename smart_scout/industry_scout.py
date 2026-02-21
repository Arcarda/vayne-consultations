#!/usr/bin/env python3
"""
🚀  Industry Scout — Smart Scout Multi-Industry Orchestrator
=============================================================
Vayne Consulting — Smart Scout Multi-Industry Edition

The central command-line tool for the Smart Scout pipeline.
Replaces the single-vertical scout.py with a configurable, 3-stage workflow.

WORKFLOW:
  Step 1 — BUILD:   Collect target URLs for an industry in a location
  Step 2 — ADVISE:  Generate a strategic market brief (pre-flight)
  Step 3 — AUDIT:   Audit targets, extract contacts, draft outreach

COMMANDS:
  python industry_scout.py build  --industry law_firms   --location Montreal --count 50
  python industry_scout.py advise --industry law_firms   [--notes "Focus on bilingual sites"]
  python industry_scout.py audit  --industry law_firms   --targets targets.txt [--dry-run]
  python industry_scout.py list                          # Show available industry configs

ENVIRONMENT:
  Set the following in a .env file inside smart_scout/:
    OPENAI_API_KEY=sk-...
    GOOGLE_API_KEY=...       (for 'build' with --engine google)
    GOOGLE_CSE_ID=...        (for 'build' with --engine google)
    SERPAPI_KEY=...          (for 'build' with --engine serpapi)
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from colorama import init, Fore, Style
from dotenv import load_dotenv
from openai import OpenAI

from config_loader import load_industry, list_available_industries, IndustryConfig
from advisor import generate_advisory, save_advisory
from contact_extractor import extract_contact
from report_generator import AuditResult, save_audit_run
import prompts

# ── Setup ─────────────────────────────────────────────────────────────────────

load_dotenv()
init(autoreset=True)

REPORTS_DIR = Path(__file__).parent / "reports"
TARGETS_DIR = Path(__file__).parent / "targets"


def get_llm_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print(f"{Fore.YELLOW}[!] OPENAI_API_KEY not set — LLM features will use config-based fallback.")
        return None
    return OpenAI(api_key=api_key)


# ── BUILD ─────────────────────────────────────────────────────────────────────

def cmd_build(args):
    """Collect target URLs for an industry using niche_builder logic."""
    from niche_builder import search_google_cse, search_serpapi, dedupe_against_existing

    config = load_industry(
        args.industry,
        custom_keywords=args.add_keywords.split(",") if args.add_keywords else [],
        custom_locations=args.add_locations.split(",") if args.add_locations else [],
        custom_notes=args.notes or ""
    )

    location = args.location or (config.get_all_locations()[0] if config.get_all_locations() else "Canada")
    keywords = config.get_all_keywords()

    print(f"\n{Fore.CYAN}🎯 Smart Scout — BUILD MODE")
    print(f"   Industry:  {config.name}")
    print(f"   Location:  {location}")
    print(f"   Keywords:  {len(keywords)} configured")
    print(f"   Engine:    {args.engine}")
    print(f"   Count:     {args.count}\n")

    all_urls = []
    for keyword in keywords[:3]:  # Use first 3 keywords to keep query count low
        query = (
            f'"{keyword}" {location} '
            f'(site:.ca OR site:.com) '
            f'-yelp -facebook -instagram -houzz -homestars -yellowpages'
        )
        print(f"{Fore.YELLOW}[>] Searching: {keyword} in {location}...")

        if args.dry_run:
            print(f"    {Fore.BLUE}[DRY RUN] Query: {query}")
            continue

        if args.engine == "serpapi":
            urls = search_serpapi(query, args.count // len(keywords[:3]) + 5)
        else:
            urls = search_google_cse(query, args.count // len(keywords[:3]) + 5)

        all_urls.extend(urls)
        print(f"    {Fore.GREEN}[+] Found {len(urls)} URLs")
        time.sleep(1.0)

    if args.dry_run:
        print(f"\n{Fore.CYAN}[DRY RUN] Would have searched {len(keywords[:3])} queries.")
        print("    Add --engine and API keys to .env to run for real.")
        return

    # Dedupe & output
    TARGETS_DIR.mkdir(exist_ok=True)
    output_file = TARGETS_DIR / f"{config.slug}_{location.lower().replace(' ', '_')}.txt"
    all_urls = list(dict.fromkeys(all_urls))  # Deduplicate preserving order
    all_urls = dedupe_against_existing(all_urls, str(output_file))
    all_urls = all_urls[:args.count]

    with open(output_file, "a", encoding="utf-8") as f:
        for url in all_urls:
            f.write(url + "\n")

    print(f"\n{Fore.GREEN}✅ Added {len(all_urls)} new targets → {output_file}")
    print(f"\n{Fore.CYAN}Next step:")
    print(f"  python industry_scout.py advise --industry {args.industry}")
    print(f"  python industry_scout.py audit  --industry {args.industry} --targets {output_file}")


# ── ADVISE ────────────────────────────────────────────────────────────────────

def cmd_advise(args):
    """Generate a pre-flight advisory report for an industry."""
    config = load_industry(
        args.industry,
        custom_notes=args.notes or ""
    )
    client = get_llm_client()

    print(f"\n{Fore.CYAN}🧠 Smart Scout — ADVISE MODE")
    print(f"   Industry: {config.name}")
    if args.notes:
        print(f"   Notes:    {args.notes}")
    print(f"\n   Generating advisory report...\n")

    report = generate_advisory(config, client=client)
    output_path = save_advisory(report)

    print(f"{Fore.GREEN}✅ Advisory report saved → {output_path}\n")
    print(f"{Fore.WHITE}{'─'*60}")
    print(report.markdown[:800] + "...\n")
    print(f"{Fore.CYAN}Next step:")
    print(f"  python industry_scout.py audit --industry {args.industry} --targets targets/<file>.txt")


# ── AUDIT ─────────────────────────────────────────────────────────────────────

def _hard_check(url: str) -> dict:
    """Fetch URL and return tech data. Same logic as original scout.py."""
    try:
        if not url.startswith("http"):
            url = f"https://{url}"
        start = time.time()
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0 (VayneConsulting Scout)"})
        elapsed = round(time.time() - start, 2)
        return {
            "status": resp.status_code,
            "response_time_sec": elapsed,
            "valid": resp.status_code == 200,
            "html": resp.text,
            "final_url": resp.url,
            "has_ssl": resp.url.startswith("https://")
        }
    except Exception as e:
        return {"error": str(e), "valid": False}


def _score_target(tech: dict, contact, config: IndustryConfig) -> tuple[int, list[str]]:
    """
    Compute a priority score (1–10) and list of detected issues.
    Base score from technical signals + industry-specific bumps.
    """
    score = 5  # Start neutral
    issues = []

    # Technical signals
    load_time = tech.get("response_time_sec", 0)
    if load_time > 5.0:
        score += 2
        issues.append(f"Very slow load: {load_time}s")
    elif load_time > 3.0:
        score += 1
        issues.append(f"Slow load: {load_time}s")

    if not tech.get("has_ssl"):
        score += 2
        issues.append("No SSL")

    if not contact.email:
        score += 1
        issues.append("No email found")

    # Industry-specific indicator bumps
    for issue in issues:
        score += config.score_issue(issue)

    return min(score, 10), issues


def _soft_check(html: str, client: OpenAI | None, config: IndustryConfig) -> str:
    """Industry-aware LLM analysis of hero section content."""
    if not client:
        return "LLM analysis skipped (no API key configured)."

    soup = BeautifulSoup(html, "html.parser")
    hero_parts = []
    for tag, label in [("h1", "H1"), ("h2", "H2"), ("p", "P")]:
        el = soup.find(tag)
        if el:
            hero_parts.append(f"{label}: {el.get_text(strip=True)[:200]}")

    if not hero_parts:
        body = soup.find("body")
        if body:
            hero_parts.append(f"Body: {body.get_text(strip=True)[:400]}")

    if not hero_parts:
        return "Could not extract content for analysis."

    content_blob = "\n".join(hero_parts)
    system_prompt = prompts.get_analysis_prompt(config.to_prompt_context())

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze this hero section:\n\n{content_blob}"}
            ],
            temperature=0.7,
            max_tokens=150
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        return f"LLM error: {e}"


def cmd_audit(args):
    """Run audits against a target list for an industry."""
    config = load_industry(
        args.industry,
        custom_notes=args.notes or ""
    )
    client = get_llm_client()

    # Load targets
    targets_path = Path(args.targets)
    if not targets_path.exists():
        # Try in targets/ subdirectory
        targets_path = TARGETS_DIR / args.targets
    if not targets_path.exists():
        print(f"{Fore.RED}[!] Targets file not found: {args.targets}")
        sys.exit(1)

    # Support both CSV and plain .txt
    suffix = targets_path.suffix.lower()
    if suffix == ".csv":
        with open(targets_path, newline="") as f:
            targets = [row[0].strip() for row in csv.reader(f) if row and row[0].strip()]
    else:
        with open(targets_path) as f:
            targets = [line.strip() for line in f if line.strip()]

    limit = args.limit or len(targets)
    targets = targets[:limit]

    print(f"\n{Fore.CYAN}🔍 Smart Scout — AUDIT MODE")
    print(f"   Industry: {config.name}")
    print(f"   Targets:  {len(targets)}")
    if args.dry_run:
        print(f"   {Fore.YELLOW}[DRY RUN] No API calls will be made.\n")
    print()

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (VayneConsulting Scout)"})
    results: list[AuditResult] = []

    for i, target in enumerate(targets, 1):
        url = target if target.startswith("http") else f"https://{target}"
        domain = url.replace("https://", "").replace("http://", "").split("/")[0]
        print(f"{Fore.YELLOW}[{i}/{len(targets)}] {domain}")

        result = AuditResult(
            url=url,
            domain=domain,
            industry=config.name,
            industry_slug=config.slug
        )

        if args.dry_run:
            result.status = "skipped"
            result.insight = "[DRY RUN] No analysis performed."
            results.append(result)
            continue

        # 1. Technical check
        tech = _hard_check(url)
        if not tech.get("valid"):
            print(f"    {Fore.RED}[x] Unreachable: {tech.get('error', tech.get('status'))}")
            result.status = "failed"
            result.error = str(tech.get("error", tech.get("status")))
            results.append(result)
            continue

        result.status_code = tech.get("status", 0)
        result.load_time_sec = tech.get("response_time_sec", 0)
        result.has_ssl = tech.get("has_ssl", False)
        print(f"    {Fore.GREEN}[+] Online ({result.load_time_sec}s) {'🔒' if result.has_ssl else '🔓'}")

        # 2. Contact extraction
        contact = extract_contact(url, tech["html"], session=session)
        result.company_name = contact.company_name
        result.first_name = contact.first_name
        result.contact_email = contact.email
        result.contact_tier = contact.tier
        print(f"    {Fore.BLUE}[~] Contact Tier {contact.tier} | {contact.company_name or 'Unknown Co.'}")

        # 3. Scoring
        result.base_score, result.detected_issues = _score_target(tech, contact, config)
        result.industry_score_bump = sum(config.score_issue(i) for i in result.detected_issues)
        result.final_score = min(result.base_score + result.industry_score_bump, 10)

        # 4. LLM insight
        print(f"    {Fore.BLUE}[~] Running industry-aware analysis...")
        result.insight = _soft_check(tech["html"], client, config)
        print(f"    {Fore.MAGENTA}[i] {result.insight[:120]}...")

        # 5. Build the specific_issue string
        specific_issue = (
            result.detected_issues[0] if result.detected_issues
            else "some friction in your digital presence"
        )

        # 6. Draft email
        result.email_draft = prompts.get_email(
            priority_score=result.final_score,
            first_name=result.first_name,
            company_name=result.company_name,
            domain=domain,
            specific_issue=specific_issue,
            insight=result.insight,
            load_time=result.load_time_sec
        )

        results.append(result)
        time.sleep(0.5)  # Be polite

    # 7. Save reports
    if not args.dry_run:
        paths = save_audit_run(results, config.slug, config.name)
        ok = [r for r in results if r.status == "ok"]
        high = [r for r in ok if r.final_score >= 8]
        print(f"\n{Fore.GREEN}{'═'*50}")
        print(f"{Fore.GREEN}✅ Audit complete")
        print(f"   Audited:       {len(ok)}/{len(results)}")
        print(f"   High Priority: {len(high)}")
        print(f"   Report (MD):   {paths['markdown']}")
        print(f"   Report (JSON): {paths['json']}")
        print(f"\n{Fore.CYAN}Open the Markdown summary to review leads and email drafts.")
    else:
        print(f"\n{Fore.YELLOW}[DRY RUN] {len(results)} targets would be audited.")
        print("    Remove --dry-run and ensure API keys are set to execute.")


# ── LIST ──────────────────────────────────────────────────────────────────────

def cmd_list(args):
    """List all available industry configs."""
    industries = list_available_industries()
    if not industries:
        print(f"{Fore.RED}[!] No industry configs found.")
        print(f"    Add YAML files to: {Path(__file__).parent / 'industries'}")
        return

    print(f"\n{Fore.CYAN}📋 Available Industry Configs\n")
    for slug in industries:
        try:
            config = load_industry(slug)
            print(f"  {Fore.GREEN}✓ {Fore.WHITE}{slug:<25} {Fore.CYAN}{config.name}")
            print(f"      Keywords: {len(config.search_keywords)} | "
                  f"Locations: {len(config.locations)} | "
                  f"Pain points: {len(config.pain_points)}")
        except Exception as e:
            print(f"  {Fore.RED}✗ {slug} — Error: {e}")
    print()


# ── CLI Entry Point ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="industry_scout",
        description="Smart Scout Multi-Industry Edition — Vayne Consulting"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── build ──
    build_p = subparsers.add_parser("build", help="Build a target URL list")
    build_p.add_argument("--industry",   required=True, help="Industry slug (e.g. law_firms)")
    build_p.add_argument("--location",   default="", help="City/region (overrides config default)")
    build_p.add_argument("--count",      type=int, default=50, help="Number of targets (default: 50)")
    build_p.add_argument("--engine",     choices=["google", "serpapi"], default="google")
    build_p.add_argument("--add-keywords", default="", help="Comma-separated extra keywords")
    build_p.add_argument("--add-locations", default="", help="Comma-separated extra locations")
    build_p.add_argument("--notes",      default="", help="Free-text notes for this run")
    build_p.add_argument("--dry-run",    action="store_true", help="Show queries without calling APIs")
    build_p.set_defaults(func=cmd_build)

    # ── advise ──
    advise_p = subparsers.add_parser("advise", help="Generate a pre-flight advisory report")
    advise_p.add_argument("--industry",  required=True, help="Industry slug")
    advise_p.add_argument("--notes",     default="", help="Custom context for this run")
    advise_p.set_defaults(func=cmd_advise)

    # ── audit ──
    audit_p = subparsers.add_parser("audit", help="Audit targets and generate outreach drafts")
    audit_p.add_argument("--industry",   required=True, help="Industry slug")
    audit_p.add_argument("--targets",    required=True, help="Path to targets file (.txt or .csv)")
    audit_p.add_argument("--limit",      type=int, default=None, help="Max targets to audit")
    audit_p.add_argument("--notes",      default="", help="Custom notes for this run")
    audit_p.add_argument("--dry-run",    action="store_true", help="Skip all API calls")
    audit_p.set_defaults(func=cmd_audit)

    # ── list ──
    list_p = subparsers.add_parser("list", help="List available industry configs")
    list_p.set_defaults(func=cmd_list)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
