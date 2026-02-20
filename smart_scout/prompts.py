"""
📧 Smart Scout — Email Templates & LLM Prompts
================================================
Vayne Consulting — Liquidity Acceleration Tool

UPGRADED: 3-tier email personalization system.
Tier 1 (best): Named recipient + specific data point
Tier 2 (good): Company name only  
Tier 3 (fallback): Generic
"""

# ============================================================================
# LLM SYSTEM PROMPT — Hero Section Analysis
# ============================================================================

ANALYSIS_SYSTEM_PROMPT = """
You are an expert UX/UI auditor and conversion rate optimization specialist.
Analyze the "Hero Section" of a website and provide ONE high-impact insight.

Guidelines:
1.  BE SPECIFIC: Identify a specific friction point.
    Good: "The value prop is buried below the fold."
    Good: "The CTA says 'Submit' — replacing it with 'Get My Free Quote' adds urgency."
    Bad: "The design could be improved."
2.  TONE: Expert peer giving free advice — not a salesperson.
3.  LENGTH: 1-2 sentences max. Punchy.
4.  OUTPUT: The insight text only. No preamble ("Here is my analysis:").

Example outputs:
"Your headline focuses on features rather than benefits — switching from 'We offer X' to 'Achieve Y with X' could increase conversions."
"The hero CTA ('Learn More') is too passive for a service business — 'Book a Free Consultation' would convert better."
"The page opens with your company name instead of your client's problem, which buries your value proposition."
"""

# ============================================================================
# EMAIL TEMPLATES — 3 Tiers
# ============================================================================

# Tier 1: Named contact + specific data issue
# Use when: You have a first name AND a hard technical issue (load time, broken link, etc.)
EMAIL_TIER1_TEMPLATE = """\
Subject: {subject}

Hi {first_name},

I was just looking at {company_name}'s site and noticed {specific_issue}.

{insight}

Just wanted to flag it — this kind of thing is easy to miss when you're heads-down running the business.

If you'd ever want a quick second pair of eyes, happy to chat. No pressure at all.

Best,
[Your Name]
Vayne Consulting | vayneconsulting.com

P.S. If this isn't relevant, totally fine — just wanted to share what I saw.
"""

# Tier 2: Company name known, no personal name
# Use when: Business name extractable from title tag, but no founder/contact name found
EMAIL_TIER2_TEMPLATE = """\
Subject: {subject}

Hi there,

I was browsing {company_name}'s site and wanted to flag something: {specific_issue}.

{insight}

Small thing, but it might be worth a quick look. Happy to provide more context if useful.

Best,
[Your Name]
Vayne Consulting | vayneconsulting.com
"""

# Tier 3: Generic fallback
# Use sparingly — only if no name AND no company name extractable
EMAIL_TIER3_TEMPLATE = """\
Subject: {subject}

Hi there,

I was just browsing {domain} and noticed {specific_issue}.

{insight}

Just wanted to share — no agenda here. If it's useful, great. If not, no worries.

Best,
[Your Name]
Vayne Consulting
"""

# ============================================================================
# SUBJECT LINE VARIANTS
# ============================================================================
# Format strings. Use the one that fits your available data.
# Note: "Re:" variant is reserved for HIGH priority leads only (score >= 8).

SUBJECT_TEMPLATES = {
    "data_driven": "Your site loads in {load_time}s on mobile",       # Best for load time issues
    "named":       "{company_name} — noticed something on your site", # Best for Tier 1/2
    "re":          "Re: {company_name}'s landing page",               # HIGH PRIORITY ONLY (score 8+)
    "generic":     "Quick heads up about {domain}",                   # Fallback
}

def get_subject(priority_score: int, company_name: str, domain: str, 
                load_time: float = None) -> str:
    """Return the most appropriate subject line based on available data."""
    if load_time and load_time > 3.0:
        return SUBJECT_TEMPLATES["data_driven"].format(load_time=f"{load_time:.1f}")
    elif company_name and priority_score >= 8:
        return SUBJECT_TEMPLATES["re"].format(company_name=company_name)
    elif company_name:
        return SUBJECT_TEMPLATES["named"].format(company_name=company_name)
    else:
        return SUBJECT_TEMPLATES["generic"].format(domain=domain)


def get_email(priority_score: int, first_name: str, company_name: str,
              domain: str, specific_issue: str, insight: str, 
              load_time: float = None) -> str:
    """
    Select the appropriate email tier and return a formatted draft.
    
    Args:
        priority_score:  1-10 from Smart Scout
        first_name:      Contact first name (empty string if unknown)
        company_name:    Business name (empty string if unknown)
        domain:          Domain URL, e.g. "luxdesign.ca"
        specific_issue:  Short description of the main issue found
        insight:         LLM-generated messaging insight
        load_time:       Load time in seconds (None if not available)
    """
    subject = get_subject(priority_score, company_name, domain, load_time)

    if first_name and company_name:
        template = EMAIL_TIER1_TEMPLATE
        return template.format(
            subject=subject,
            first_name=first_name,
            company_name=company_name,
            specific_issue=specific_issue,
            insight=insight
        )
    elif company_name:
        template = EMAIL_TIER2_TEMPLATE
        return template.format(
            subject=subject,
            company_name=company_name,
            specific_issue=specific_issue,
            insight=insight
        )
    else:
        template = EMAIL_TIER3_TEMPLATE
        return template.format(
            subject=subject,
            domain=domain,
            specific_issue=specific_issue,
            insight=insight
        )
