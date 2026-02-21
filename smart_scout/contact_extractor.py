"""
🔍  Contact Extractor — Smart Scout Lead Enrichment Module
===========================================================
Vayne Consulting — Smart Scout Multi-Industry Edition

Attempts to extract contact information from a target business website.
Feeds into the 3-tier email personalization in prompts.py.

Extraction targets:
  - Email addresses (from mailto: links and text scanning)
  - Contact/owner first name (from About, Team, or Contact pages)
  - Company name (from <title> tag, <h1>, or Open Graph metadata)

The module is intentionally lightweight — no headless browser.
Pure requests + BeautifulSoup for maximum speed across bulk targets.

Usage:
    from contact_extractor import extract_contact

    result = extract_contact("https://luxdesign.ca", html_content)
    print(result.first_name)    # "Marie" or ""
    print(result.email)         # "hello@luxdesign.ca" or ""
    print(result.company_name)  # "Lux Design Studio" or ""
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# Domains to skip when found in mailto links (generic providers, not business emails)
GENERIC_EMAIL_DOMAINS = {
    "gmail.com", "hotmail.com", "yahoo.com", "outlook.com",
    "icloud.com", "me.com", "live.com", "protonmail.com"
}

# Common page slugs to check for contact/team information
CONTACT_PAGE_SLUGS = [
    "/contact", "/contact-us", "/contactus",
    "/about", "/about-us", "/aboutus",
    "/team", "/our-team", "/staff",
    "/equipe", "/a-propos",  # French variants
]

# Patterns that suggest a name is being introduced (About page heuristic)
NAME_INTRODUCTION_PATTERNS = [
    r"(?:I(?:'m| am)|My name is|About|Hi,?\s+I(?:'m| am))\s+([A-Z][a-z]{1,20})",
    r"(?:Founder|Owner|Principal|Director|Propriétaire|Fondateur(?:trice)?),?\s+([A-Z][a-z]{1,20})",
    r"(?:Meet\s+)([A-Z][a-z]{1,20})\s+(?:[A-Z][a-z]+)",
]


@dataclass
class ContactInfo:
    """Contact information extracted from a target website."""
    domain: str
    email: str = ""
    first_name: str = ""
    company_name: str = ""
    contact_page_found: bool = False
    extraction_notes: str = ""

    @property
    def tier(self) -> int:
        """Returns the personalization tier (1 = best, 3 = fallback)."""
        if self.first_name and self.company_name:
            return 1
        elif self.company_name:
            return 2
        return 3

    def to_dict(self) -> dict:
        return {
            "domain": self.domain,
            "email": self.email,
            "first_name": self.first_name,
            "company_name": self.company_name,
            "contact_page_found": self.contact_page_found,
            "personalization_tier": self.tier,
            "extraction_notes": self.extraction_notes
        }


def _extract_emails_from_html(html: str) -> list[str]:
    """Extract all email addresses from raw HTML."""
    # Match mailto: links
    mailto_emails = re.findall(r'mailto:([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})', html)
    # Match plain emails in text
    plain_emails = re.findall(r'\b([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})\b', html)
    all_emails = list(dict.fromkeys(mailto_emails + plain_emails))  # dedupe, preserve order
    return all_emails


def _filter_business_email(emails: list[str], domain: str) -> str:
    """
    Prefer an email that matches the site's domain.
    Falls back to any non-generic email, then returns empty string.
    """
    base_domain = urlparse(domain).netloc.replace("www.", "")

    # First: exact domain match
    for email in emails:
        if base_domain in email:
            return email

    # Second: any non-generic email
    for email in emails:
        email_domain = email.split("@")[-1].lower()
        if email_domain not in GENERIC_EMAIL_DOMAINS:
            return email

    return ""


def _extract_company_name(soup: BeautifulSoup) -> str:
    """
    Try to extract the business name from the page.
    Order of preference: OG site_name → <title> tag → <h1>
    """
    # Open Graph
    og_name = soup.find("meta", property="og:site_name")
    if og_name and og_name.get("content"):
        return og_name["content"].strip()

    # Title tag — strip generic suffixes
    title = soup.find("title")
    if title and title.get_text():
        raw = title.get_text().strip()
        # Strip common separators: "Company | Tagline" → "Company"
        for sep in [" | ", " — ", " - ", " :: ", " » "]:
            if sep in raw:
                raw = raw.split(sep)[0].strip()
        return raw

    # H1 fallback
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)[:60]

    return ""


def _extract_first_name(html: str, soup: BeautifulSoup) -> str:
    """
    Attempt to extract the owner/founder's first name using
    named entity heuristics on About/Team page content.
    """
    for pattern in NAME_INTRODUCTION_PATTERNS:
        match = re.search(pattern, html)
        if match:
            candidate = match.group(1).strip()
            # Sanity check: avoid generic English words
            if len(candidate) >= 2 and candidate.isalpha():
                return candidate

    # Fallback: check for structured author/person markup
    person_schema = soup.find(attrs={"itemprop": "name"})
    if person_schema:
        text = person_schema.get_text(strip=True)
        parts = text.split()
        if parts and parts[0][0].isupper():
            return parts[0]

    return ""


def _try_fetch_contact_page(base_url: str, session: requests.Session) -> Optional[BeautifulSoup]:
    """
    Try common contact/about page slugs and return the parsed HTML of the first success.
    """
    for slug in CONTACT_PAGE_SLUGS:
        try:
            url = urljoin(base_url, slug)
            resp = session.get(url, timeout=8)
            if resp.status_code == 200 and len(resp.text) > 200:
                return BeautifulSoup(resp.text, "html.parser")
        except Exception:
            continue
    return None


def extract_contact(
    url: str,
    homepage_html: str,
    session: Optional[requests.Session] = None
) -> ContactInfo:
    """
    Extract contact information for a given target URL.

    Args:
        url:           The target's full URL (e.g. "https://luxdesign.ca")
        homepage_html: Already-fetched homepage HTML (from scout.py's hard_check)
        session:       Requests session to reuse (creates one if None)

    Returns:
        ContactInfo dataclass
    """
    if session is None:
        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (VayneConsulting Scout)"})

    result = ContactInfo(domain=url)
    notes = []

    # --- Parse homepage ---
    soup = BeautifulSoup(homepage_html, "html.parser")
    result.company_name = _extract_company_name(soup)

    # Try to find emails on homepage
    homepage_emails = _extract_emails_from_html(homepage_html)
    business_email = _filter_business_email(homepage_emails, url)
    if business_email:
        result.email = business_email
        notes.append("Email from homepage")

    # Try to get name from homepage
    result.first_name = _extract_first_name(homepage_html, soup)
    if result.first_name:
        notes.append("Name from homepage")

    # --- Try contact/about sub-pages if still missing info ---
    if not result.email or not result.first_name:
        contact_soup = _try_fetch_contact_page(url, session)
        if contact_soup:
            result.contact_page_found = True
            contact_html = str(contact_soup)

            if not result.email:
                subpage_emails = _extract_emails_from_html(contact_html)
                subpage_email = _filter_business_email(subpage_emails, url)
                if subpage_email:
                    result.email = subpage_email
                    notes.append("Email from contact/about page")

            if not result.first_name:
                result.first_name = _extract_first_name(contact_html, contact_soup)
                if result.first_name:
                    notes.append("Name from contact/about page")

    result.extraction_notes = "; ".join(notes) if notes else "No contact data found"
    return result
