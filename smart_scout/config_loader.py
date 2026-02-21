"""
⚙️  Config Loader — Smart Scout Industry Configuration Reader
=============================================================
Vayne Consulting — Smart Scout Multi-Industry Edition

Loads and validates a YAML industry config file from the industries/ folder.
Returns an IndustryConfig dataclass consumed by all Scout modules.

Usage:
    from config_loader import load_industry

    config = load_industry("law_firms")
    print(config.name)
    print(config.pain_points)
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

try:
    import yaml
except ImportError:
    print("[!] Missing dependency: pyyaml")
    print("    Run: pip install pyyaml")
    sys.exit(1)

# Path to the industries/ folder relative to this file
INDUSTRIES_DIR = Path(__file__).parent / "industries"


@dataclass
class IndustryConfig:
    """Structured representation of an industry YAML config."""
    name: str
    slug: str
    search_keywords: list[str]
    locations: list[str]
    pain_points: list[str]
    kpis: list[str]
    trust_signals: list[str]
    offer_angle: str
    analysis_focus: str
    outreach_angle: str
    priority_indicators: dict  # keys: "high", "medium", "low"

    # Additional specifics (optional, set at runtime)
    custom_keywords: list[str] = field(default_factory=list)
    custom_locations: list[str] = field(default_factory=list)
    custom_notes: str = ""

    def get_all_keywords(self) -> list[str]:
        """Returns all search keywords including any runtime additions."""
        return self.search_keywords + self.custom_keywords

    def get_all_locations(self) -> list[str]:
        """Returns all locations including any runtime additions."""
        return self.locations + self.custom_locations

    def to_prompt_context(self) -> str:
        """
        Renders a concise context block to inject into LLM prompts.
        Gives the model industry-specific knowledge to ground its analysis.
        """
        pain_points_str = "\n".join(f"  - {p}" for p in self.pain_points[:4])
        trust_signals_str = "\n".join(f"  - {t}" for t in self.trust_signals[:3])
        indicators_high = "\n".join(
            f"  - {i}" for i in self.priority_indicators.get("high", [])[:3]
        )
        return (
            f"INDUSTRY: {self.name}\n"
            f"ANALYSIS FOCUS: {self.analysis_focus}\n\n"
            f"COMMON PAIN POINTS IN THIS VERTICAL:\n{pain_points_str}\n\n"
            f"KEY TRUST SIGNALS CLIENTS LOOK FOR:\n{trust_signals_str}\n\n"
            f"HIGH PRIORITY RED FLAGS TO DETECT:\n{indicators_high}"
        )

    def score_issue(self, issue_text: str) -> int:
        """
        Returns a priority bump score (0-3) based on whether the issue text
        matches any high/medium priority indicators for the industry.
        Used to weight the final audit score.
        """
        issue_lower = issue_text.lower()
        for indicator in self.priority_indicators.get("high", []):
            if any(word in issue_lower for word in indicator.lower().split()):
                return 3
        for indicator in self.priority_indicators.get("medium", []):
            if any(word in issue_lower for word in indicator.lower().split()):
                return 1
        return 0


def list_available_industries() -> list[str]:
    """Returns slugs of all available industry configs."""
    if not INDUSTRIES_DIR.exists():
        return []
    return [f.stem for f in INDUSTRIES_DIR.glob("*.yaml")]


def load_industry(
    slug: str,
    custom_keywords: Optional[list[str]] = None,
    custom_locations: Optional[list[str]] = None,
    custom_notes: str = ""
) -> IndustryConfig:
    """
    Load an industry config by slug name.

    Args:
        slug:             The filename stem, e.g. "law_firms" for law_firms.yaml
        custom_keywords:  Additional search keywords to append at runtime
        custom_locations: Additional locations to append at runtime
        custom_notes:     Free-text notes for this scout run (stored in report)

    Returns:
        IndustryConfig dataclass

    Raises:
        FileNotFoundError: If the YAML file doesn't exist
        ValueError:        If required fields are missing from the YAML
    """
    yaml_path = INDUSTRIES_DIR / f"{slug}.yaml"

    if not yaml_path.exists():
        available = list_available_industries()
        raise FileNotFoundError(
            f"Industry config '{slug}' not found.\n"
            f"Available industries: {', '.join(available) if available else 'none'}\n"
            f"Add a new config to: {INDUSTRIES_DIR}"
        )

    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Validate required fields
    required_fields = [
        "name", "slug", "search_keywords", "locations",
        "pain_points", "kpis", "trust_signals",
        "offer_angle", "analysis_focus", "outreach_angle", "priority_indicators"
    ]
    missing = [field for field in required_fields if field not in data]
    if missing:
        raise ValueError(
            f"Industry config '{slug}' is missing required fields: {missing}"
        )

    return IndustryConfig(
        name=data["name"],
        slug=data["slug"],
        search_keywords=data["search_keywords"],
        locations=data["locations"],
        pain_points=data["pain_points"],
        kpis=data["kpis"],
        trust_signals=data["trust_signals"],
        offer_angle=data["offer_angle"],
        analysis_focus=data["analysis_focus"],
        outreach_angle=data["outreach_angle"],
        priority_indicators=data["priority_indicators"],
        custom_keywords=custom_keywords or [],
        custom_locations=custom_locations or [],
        custom_notes=custom_notes
    )


if __name__ == "__main__":
    """Quick validation: run directly to test loading all available configs."""
    from colorama import init, Fore, Style
    init(autoreset=True)

    industries = list_available_industries()
    if not industries:
        print(f"{Fore.RED}[!] No industry configs found in {INDUSTRIES_DIR}")
        sys.exit(1)

    for slug in industries:
        try:
            config = load_industry(slug)
            print(f"{Fore.GREEN}[✓] {config.name} ({slug})")
            print(f"    Keywords:  {len(config.search_keywords)} | "
                  f"Pain points: {len(config.pain_points)} | "
                  f"Locations: {len(config.locations)}")
            print(f"    Prompt context preview:")
            ctx_lines = config.to_prompt_context().split('\n')[:3]
            for line in ctx_lines:
                print(f"      {Fore.CYAN}{line}")
            print()
        except (FileNotFoundError, ValueError) as e:
            print(f"{Fore.RED}[!] Failed to load '{slug}': {e}")
