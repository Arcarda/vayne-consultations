#!/usr/bin/env python3
"""
🔍 Smart Scout - Automated Website Audit Lead Generator
=========================================================
Vayne Consulting - Liquidity Acceleration Tool

This script automates the "Helpful Observer" outreach strategy by:
1. Scraping target websites for technical issues (Hard Checks)
2. Using an LLM to analyze messaging/UX for friction points (Soft Checks)
3. Generating personalized outreach email drafts

Requirements:
    pip install requests beautifulsoup4 openai python-dotenv

Usage:
    python smart_scout.py --url https://example.com
    python smart_scout.py --file targets.txt

Environment Variables (.env):
    OPENAI_API_KEY=your-api-key-here
"""

import argparse
import json
import os
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("Missing dependencies. Run: pip install requests beautifulsoup4")
    exit(1)

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False
    print("Warning: OpenAI not installed. LLM analysis will be skipped.")

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class HardCheckResult:
    """Technical audit results"""
    url: str
    load_time_seconds: float
    has_viewport_meta: bool
    has_ssl: bool
    broken_links: list[str]
    missing_alt_tags: int
    title_tag: str
    meta_description: str
    issues_found: list[str]


@dataclass
class SoftCheckResult:
    """LLM-powered UX/Messaging analysis"""
    hero_text: str
    friction_point: str
    improvement_suggestion: str
    tone_analysis: str


@dataclass
class AuditReport:
    """Complete audit report for a website"""
    url: str
    timestamp: str
    hard_checks: HardCheckResult
    soft_checks: Optional[SoftCheckResult]
    email_draft: str
    priority_score: int  # 1-10, higher = more likely to convert


# ============================================================================
# HARD CHECKS (Technical Audit)
# ============================================================================

def perform_hard_checks(url: str, timeout: int = 10) -> HardCheckResult:
    """
    Perform technical audits on a website.
    
    Checks:
    - Load time
    - Mobile viewport meta tag
    - SSL certificate
    - Broken links (first 10 only)
    - Missing alt tags on images
    - Title and meta description
    """
    issues = []
    
    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    parsed = urlparse(url)
    has_ssl = parsed.scheme == 'https'
    if not has_ssl:
        issues.append("Site does not use HTTPS (insecure)")
    
    # Measure load time
    start = time.time()
    try:
        response = requests.get(url, timeout=timeout, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        load_time = time.time() - start
    except requests.RequestException as e:
        return HardCheckResult(
            url=url,
            load_time_seconds=-1,
            has_viewport_meta=False,
            has_ssl=has_ssl,
            broken_links=[],
            missing_alt_tags=0,
            title_tag="",
            meta_description="",
            issues_found=[f"Could not load site: {str(e)}"]
        )
    
    if load_time > 3:
        issues.append(f"Slow load time: {load_time:.1f}s (should be < 3s)")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Check viewport meta
    viewport = soup.find('meta', attrs={'name': 'viewport'})
    has_viewport = viewport is not None
    if not has_viewport:
        issues.append("Missing viewport meta tag (not mobile-friendly)")
    
    # Get title and description
    title_tag = soup.find('title')
    title_text = title_tag.get_text().strip() if title_tag else ""
    if not title_text:
        issues.append("Missing <title> tag")
    elif len(title_text) > 60:
        issues.append(f"Title tag too long ({len(title_text)} chars, recommend < 60)")
    
    meta_desc = soup.find('meta', attrs={'name': 'description'})
    meta_desc_text = meta_desc.get('content', '').strip() if meta_desc else ""
    if not meta_desc_text:
        issues.append("Missing meta description")
    elif len(meta_desc_text) > 160:
        issues.append(f"Meta description too long ({len(meta_desc_text)} chars, recommend < 160)")
    
    # Check for broken links (sample first 10)
    broken_links = []
    links = soup.find_all('a', href=True)[:10]
    for link in links:
        href = link['href']
        if href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue
        if not href.startswith(('http://', 'https://')):
            href = f"{parsed.scheme}://{parsed.netloc}/{href.lstrip('/')}"
        try:
            link_resp = requests.head(href, timeout=5, allow_redirects=True)
            if link_resp.status_code >= 400:
                broken_links.append(href)
        except:
            pass  # Skip on timeout
    
    if broken_links:
        issues.append(f"Found {len(broken_links)} broken link(s)")
    
    # Check for missing alt tags
    images = soup.find_all('img')
    missing_alt = sum(1 for img in images if not img.get('alt'))
    if missing_alt > 0:
        issues.append(f"{missing_alt} images missing alt text (accessibility issue)")
    
    return HardCheckResult(
        url=url,
        load_time_seconds=round(load_time, 2),
        has_viewport_meta=has_viewport,
        has_ssl=has_ssl,
        broken_links=broken_links,
        missing_alt_tags=missing_alt,
        title_tag=title_text,
        meta_description=meta_desc_text,
        issues_found=issues
    )


# ============================================================================
# SOFT CHECKS (LLM Analysis)
# ============================================================================

def extract_hero_section(url: str) -> str:
    """Extract the hero/header section text from a webpage."""
    try:
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try common hero section selectors
        hero_selectors = [
            'header', '.hero', '#hero', '[class*="hero"]',
            'main > section:first-child', '.banner', '#banner'
        ]
        
        hero_text = ""
        for selector in hero_selectors:
            element = soup.select_one(selector)
            if element:
                hero_text = element.get_text(separator=' ', strip=True)
                break
        
        if not hero_text:
            # Fallback: get first 500 chars of body
            body = soup.find('body')
            if body:
                hero_text = body.get_text(separator=' ', strip=True)[:500]
        
        return hero_text[:1000]  # Limit to 1000 chars
    except:
        return ""


def perform_soft_checks(hero_text: str, url: str) -> Optional[SoftCheckResult]:
    """
    Use LLM to analyze the hero section for UX/messaging issues.
    """
    if not HAS_OPENAI:
        return None
    
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        print("Warning: OPENAI_API_KEY not set. Skipping LLM analysis.")
        return None
    
    client = OpenAI(api_key=api_key)
    
    prompt = f"""Analyze this website's hero section text. Identify ONE specific friction point in clarity, messaging, or tone that could hurt conversions.

Website: {url}

Hero Section Text:
\"\"\"
{hero_text}
\"\"\"

Respond in this exact JSON format:
{{
    "friction_point": "One specific issue (be concise, professional)",
    "improvement_suggestion": "One actionable fix",
    "tone_analysis": "Brief assessment of the current tone (professional, casual, unclear, etc.)"
}}

Be helpful, not salesy. Sound like a peer giving feedback, not a marketer pitching."""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Use gpt-4o for better analysis, gpt-4o-mini for cost savings
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            max_tokens=300
        )
        
        result = json.loads(response.choices[0].message.content)
        return SoftCheckResult(
            hero_text=hero_text[:200] + "..." if len(hero_text) > 200 else hero_text,
            friction_point=result.get("friction_point", ""),
            improvement_suggestion=result.get("improvement_suggestion", ""),
            tone_analysis=result.get("tone_analysis", "")
        )
    except Exception as e:
        print(f"LLM analysis error: {e}")
        return None


# ============================================================================
# EMAIL GENERATION
# ============================================================================

def generate_email_draft(hard: HardCheckResult, soft: Optional[SoftCheckResult]) -> str:
    """
    Generate a personalized, helpful outreach email.
    """
    # Pick the most impactful issue
    primary_issue = ""
    if hard.load_time_seconds > 3:
        primary_issue = f"your site loads in {hard.load_time_seconds:.1f} seconds (industry benchmark is under 3s)"
    elif not hard.has_viewport_meta:
        primary_issue = "your site may not display correctly on mobile devices"
    elif not hard.has_ssl:
        primary_issue = "your site isn't using HTTPS, which browsers now flag as 'not secure'"
    elif hard.broken_links:
        primary_issue = f"there's a broken link on your homepage ({hard.broken_links[0]})"
    elif soft and soft.friction_point:
        primary_issue = soft.friction_point.lower()
    
    if not primary_issue:
        primary_issue = "a few small tweaks could improve your site's first impression"
    
    # Build the email
    email = f"""Subject: Quick heads up about your website

Hey there,

I was browsing your site and noticed {primary_issue}.

Just wanted to give you a heads up since this might be costing you visitors or conversions. No agenda here — I just hate seeing good products held back by small technical issues.

"""
    
    if soft and soft.improvement_suggestion:
        email += f"One quick win: {soft.improvement_suggestion}\n\n"
    
    email += """If you ever want a second pair of eyes on your site, I'm happy to help. No strings attached.

Best,
[Your Name]
Vayne Consulting

P.S. If this was helpful, feel free to reach out. If not, no worries at all — just wanted to share what I saw."""

    return email


def calculate_priority_score(hard: HardCheckResult, soft: Optional[SoftCheckResult]) -> int:
    """
    Calculate a priority score (1-10) for follow-up.
    Higher = more likely to convert.
    """
    score = 5  # Base score
    
    # Technical issues increase likelihood they need help
    if hard.load_time_seconds > 3:
        score += 1
    if not hard.has_viewport_meta:
        score += 2  # Major mobile issue
    if hard.broken_links:
        score += 1
    if not hard.meta_description:
        score += 1
    
    # If they have a clear value prop but technical issues, they're invested
    if soft and "unclear" not in soft.tone_analysis.lower():
        score += 1
    
    return min(10, max(1, score))


# ============================================================================
# MAIN ORCHESTRATION
# ============================================================================

def audit_website(url: str) -> AuditReport:
    """Run a complete audit on a single website."""
    print(f"🔍 Auditing: {url}")
    
    # Hard checks
    print("  ├─ Running technical checks...")
    hard = perform_hard_checks(url)
    
    # Soft checks
    soft = None
    if not hard.issues_found or "Could not load" not in hard.issues_found[0]:
        print("  ├─ Extracting hero section...")
        hero_text = extract_hero_section(url)
        if hero_text:
            print("  ├─ Running LLM analysis...")
            soft = perform_soft_checks(hero_text, url)
    
    # Generate email
    print("  ├─ Generating email draft...")
    email = generate_email_draft(hard, soft)
    
    # Calculate priority
    priority = calculate_priority_score(hard, soft)
    
    print(f"  └─ Done! Priority score: {priority}/10")
    
    return AuditReport(
        url=url,
        timestamp=datetime.now().isoformat(),
        hard_checks=hard,
        soft_checks=soft,
        email_draft=email,
        priority_score=priority
    )


def save_report(report: AuditReport, output_dir: str = "scout_reports"):
    """Save audit report to JSON and markdown files."""
    Path(output_dir).mkdir(exist_ok=True)
    
    # Clean URL for filename
    parsed = urlparse(report.url)
    filename = re.sub(r'[^\w\-]', '_', parsed.netloc)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save JSON
    json_path = Path(output_dir) / f"{filename}_{timestamp}.json"
    with open(json_path, 'w') as f:
        json.dump({
            "url": report.url,
            "timestamp": report.timestamp,
            "priority_score": report.priority_score,
            "hard_checks": asdict(report.hard_checks),
            "soft_checks": asdict(report.soft_checks) if report.soft_checks else None,
            "email_draft": report.email_draft
        }, f, indent=2)
    
    # Save Markdown (human-readable)
    md_path = Path(output_dir) / f"{filename}_{timestamp}.md"
    with open(md_path, 'w') as f:
        f.write(f"# Smart Scout Report: {report.url}\n\n")
        f.write(f"**Date:** {report.timestamp}\n")
        f.write(f"**Priority Score:** {report.priority_score}/10\n\n")
        
        f.write("## Technical Issues\n\n")
        if report.hard_checks.issues_found:
            for issue in report.hard_checks.issues_found:
                f.write(f"- ⚠️ {issue}\n")
        else:
            f.write("- ✅ No major technical issues found\n")
        
        f.write(f"\n**Load Time:** {report.hard_checks.load_time_seconds}s\n")
        
        if report.soft_checks:
            f.write("\n## Messaging Analysis\n\n")
            f.write(f"**Friction Point:** {report.soft_checks.friction_point}\n\n")
            f.write(f"**Suggestion:** {report.soft_checks.improvement_suggestion}\n\n")
            f.write(f"**Tone:** {report.soft_checks.tone_analysis}\n")
        
        f.write("\n## Draft Email\n\n")
        f.write("```\n")
        f.write(report.email_draft)
        f.write("\n```\n")
    
    print(f"📁 Report saved: {md_path}")
    return md_path


def main():
    parser = argparse.ArgumentParser(description="Smart Scout - Website Audit Lead Generator")
    parser.add_argument('--url', help='Single URL to audit')
    parser.add_argument('--file', help='File with list of URLs (one per line)')
    parser.add_argument('--output', default='scout_reports', help='Output directory')
    args = parser.parse_args()
    
    urls = []
    if args.url:
        urls.append(args.url)
    elif args.file:
        with open(args.file) as f:
            urls = [line.strip() for line in f if line.strip()]
    else:
        print("Usage: python smart_scout.py --url https://example.com")
        print("   or: python smart_scout.py --file targets.txt")
        return
    
    print(f"\n🚀 Smart Scout - Auditing {len(urls)} site(s)\n")
    
    for url in urls:
        try:
            report = audit_website(url)
            save_report(report, args.output)
        except Exception as e:
            print(f"❌ Error auditing {url}: {e}")
        print()
    
    print("✅ All audits complete!")


if __name__ == "__main__":
    main()
