"""
📧 Smart Scout — Email Templates & LLM Prompts (Multi-Industry Edition)
========================================================================
Vayne Consulting — Smart Scout Multi-Industry Edition

UPGRADED from single-vertical UX analysis to industry-aware auditing.

Changes from v1:
  - ANALYSIS_SYSTEM_PROMPT now accepts {industry_context} injection
  - get_analysis_prompt() replaces the bare string constant
  - Email templates and subject logic unchanged (still 3-tier)
"""

# ============================================================================
# LLM SYSTEM PROMPT — Industry-Aware Hero Section Analysis
# ============================================================================

_ANALYSIS_BASE = """\
You are an expert conversion auditor and digital strategist.
You specialize in identifying high-impact weaknesses in small business websites.

INDUSTRY CONTEXT YOU ARE WORKING IN:
{industry_context}

YOUR TASK:
Analyze the "Hero Section" content provided and identify ONE high-impact insight
that is SPECIFIC to this industry.

GUIDELINES:
1.  BE SPECIFIC and industry-relevant.
    Good: "For a law firm, the absence of a 'Book a Free Consultation' CTA means
          walk-in clients go to whoever makes it easiest."
    Good: "This interior designer's portfolio is in a PDF — a fatal friction
          point when mobile users are 60% of referral traffic."
    Bad:  "The design could look more professional."

2.  TONE: Expert peer, not sales pitch.
3.  LENGTH: 1-2 sentences. Dense, punchy, and actionable.
4.  OUTPUT: The insight text ONLY. No preamble or labels.
"""

def get_analysis_prompt(industry_context: str = "") -> str:
    """
    Returns the fully-rendered system prompt for hero section analysis.

    Args:
        industry_context: The output of IndustryConfig.to_prompt_context()
                          Leave empty for the generic (v1) behavior.
    """
    if not industry_context:
        industry_context = (
            "INDUSTRY: General (no specific vertical configured)\n"
            "ANALYSIS FOCUS: UX/CRO — conversion friction, value proposition clarity,\n"
            "                mobile performance, and contact accessibility."
        )
    return _ANALYSIS_BASE.format(industry_context=industry_context)


# Keep the old constant for backward compatibility with scout.py
ANALYSIS_SYSTEM_PROMPT = get_analysis_prompt()


# ============================================================================
# EMAIL TEMPLATES — 3 Tiers (unchanged from v1)
# ============================================================================

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

SUBJECT_TEMPLATES = {
    "data_driven": "Your site loads in {load_time}s on mobile",
    "named":       "{company_name} — noticed something on your site",
    "re":          "Re: {company_name}'s landing page",
    "generic":     "Quick heads up about {domain}",
}


def get_subject(
    priority_score: int,
    company_name: str,
    domain: str,
    load_time: float = None
) -> str:
    """Return the most appropriate subject line based on available data."""
    if load_time and load_time > 3.0:
        return SUBJECT_TEMPLATES["data_driven"].format(load_time=f"{load_time:.1f}")
    elif company_name and priority_score >= 8:
        return SUBJECT_TEMPLATES["re"].format(company_name=company_name)
    elif company_name:
        return SUBJECT_TEMPLATES["named"].format(company_name=company_name)
    else:
        return SUBJECT_TEMPLATES["generic"].format(domain=domain)


def get_email(
    priority_score: int,
    first_name: str,
    company_name: str,
    domain: str,
    specific_issue: str,
    insight: str,
    load_time: float = None
) -> str:
    """
    Select the appropriate email tier and return a formatted draft.

    Args:
        priority_score:  1-10 from Smart Scout scoring
        first_name:      Contact first name (empty string if unknown)
        company_name:    Business name (empty string if unknown)
        domain:          Domain URL, e.g. "luxdesign.ca"
        specific_issue:  Short description of the main issue found
        insight:         LLM-generated industry-aware insight
        load_time:       Load time in seconds (None if not available)
    """
    subject = get_subject(priority_score, company_name, domain, load_time)

    if first_name and company_name:
        return EMAIL_TIER1_TEMPLATE.format(
            subject=subject,
            first_name=first_name,
            company_name=company_name,
            specific_issue=specific_issue,
            insight=insight
        )
    elif company_name:
        return EMAIL_TIER2_TEMPLATE.format(
            subject=subject,
            company_name=company_name,
            specific_issue=specific_issue,
            insight=insight
        )
    else:
        return EMAIL_TIER3_TEMPLATE.format(
            subject=subject,
            domain=domain,
            specific_issue=specific_issue,
            insight=insight
        )
