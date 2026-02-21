"""
🔌  API Routes — Smart Scout Web UI
=====================================
REST endpoints for CRUD on industries, reports, and targets.
"""

import json
import os
import sys
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from config_loader import load_industry, list_available_industries

import yaml

api_bp = Blueprint("api", __name__)

BASE = Path(__file__).parent.parent.parent  # smart_scout/
INDUSTRIES_DIR = BASE / "industries"
REPORTS_DIR    = BASE / "reports"
TARGETS_DIR    = BASE / "targets"


# ── Industries ────────────────────────────────────────────────────────────────

@api_bp.route("/industries", methods=["GET"])
def get_industries():
    slugs = list_available_industries()
    industries = []
    for slug in slugs:
        try:
            cfg = load_industry(slug)
            industries.append({
                "slug": cfg.slug,
                "name": cfg.name,
                "keyword_count": len(cfg.search_keywords),
                "location_count": len(cfg.locations),
                "pain_point_count": len(cfg.pain_points),
                "keywords": cfg.search_keywords,
                "locations": cfg.locations,
                "pain_points": cfg.pain_points,
                "kpis": cfg.kpis,
                "trust_signals": cfg.trust_signals,
                "offer_angle": cfg.offer_angle,
                "analysis_focus": cfg.analysis_focus,
                "outreach_angle": cfg.outreach_angle,
                "priority_indicators": cfg.priority_indicators,
            })
        except Exception as e:
            industries.append({"slug": slug, "error": str(e)})
    return jsonify(industries)


@api_bp.route("/industries/<slug>", methods=["GET"])
def get_industry(slug):
    try:
        cfg = load_industry(slug)
        yaml_path = INDUSTRIES_DIR / f"{slug}.yaml"
        raw_yaml = yaml_path.read_text(encoding="utf-8")
        return jsonify({"slug": slug, "config": cfg.__dict__, "yaml": raw_yaml})
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 404


@api_bp.route("/industries", methods=["POST"])
def create_industry():
    data = request.json
    slug = data.get("slug", "").strip().replace(" ", "_").lower()
    if not slug:
        return jsonify({"error": "slug is required"}), 400
    yaml_path = INDUSTRIES_DIR / f"{slug}.yaml"
    if yaml_path.exists():
        return jsonify({"error": f"Industry '{slug}' already exists"}), 409
    try:
        yaml_path.write_text(data.get("yaml", ""), encoding="utf-8")
        return jsonify({"success": True, "slug": slug})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/industries/<slug>", methods=["PUT"])
def update_industry(slug):
    yaml_path = INDUSTRIES_DIR / f"{slug}.yaml"
    if not yaml_path.exists():
        return jsonify({"error": "Not found"}), 404
    data = request.json
    try:
        # Validate YAML before saving
        yaml.safe_load(data.get("yaml", ""))
        yaml_path.write_text(data["yaml"], encoding="utf-8")
        return jsonify({"success": True})
    except yaml.YAMLError as e:
        return jsonify({"error": f"Invalid YAML: {e}"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route("/industries/<slug>", methods=["DELETE"])
def delete_industry(slug):
    yaml_path = INDUSTRIES_DIR / f"{slug}.yaml"
    if not yaml_path.exists():
        return jsonify({"error": "Not found"}), 404
    yaml_path.unlink()
    return jsonify({"success": True})


# ── Targets ───────────────────────────────────────────────────────────────────

@api_bp.route("/targets", methods=["GET"])
def get_targets():
    TARGETS_DIR.mkdir(exist_ok=True)
    # Also include root-level .txt and .csv
    files = []
    for f in sorted(BASE.glob("*.csv")) + sorted(BASE.glob("*.txt")) + sorted(TARGETS_DIR.glob("*.txt")):
        files.append({
            "name": f.name,
            "path": str(f.relative_to(BASE)),
            "lines": len(f.read_text(encoding="utf-8", errors="ignore").splitlines()),
        })
    return jsonify(files)


# ── Reports ───────────────────────────────────────────────────────────────────

@api_bp.route("/reports", methods=["GET"])
def get_reports():
    if not REPORTS_DIR.exists():
        return jsonify([])
    reports = []
    for industry_dir in sorted(REPORTS_DIR.iterdir()):
        if industry_dir.is_dir():
            for f in sorted(industry_dir.iterdir(), reverse=True):
                reports.append({
                    "industry": industry_dir.name,
                    "filename": f.name,
                    "type": "advisory" if "advisory" in f.name else "audit",
                    "format": f.suffix.lstrip("."),
                    "size_kb": round(f.stat().st_size / 1024, 1),
                    "path": f"{industry_dir.name}/{f.name}",
                })
    return jsonify(reports)


@api_bp.route("/reports/<slug>/<filename>", methods=["GET"])
def get_report(slug, filename):
    report_path = REPORTS_DIR / slug / filename
    if not report_path.exists():
        return jsonify({"error": "Not found"}), 404
    content = report_path.read_text(encoding="utf-8")
    return jsonify({"content": content, "format": report_path.suffix.lstrip(".")})


@api_bp.route("/reports/<slug>/<filename>/download", methods=["GET"])
def download_report(slug, filename):
    report_path = REPORTS_DIR / slug / filename
    if not report_path.exists():
        return jsonify({"error": "Not found"}), 404
    return send_file(str(report_path), as_attachment=True, download_name=filename)
