"""
📡  Stream Routes — Smart Scout Web UI SSE Endpoints
=====================================================
Server-Sent Events for real-time scout command output.
Each endpoint runs a scout function in a background thread
and yields its stdout line-by-line to the browser.
"""

import sys
import json
import queue
import threading
from pathlib import Path

from flask import Blueprint, Response, request

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

stream_bp = Blueprint("stream", __name__)


def _make_sse(data: str, event: str = "message") -> str:
    """Format a server-sent event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _run_in_thread(fn, args: dict, q: queue.Queue):
    """
    Run a scout function, capturing print output via a proxy stdout.
    All printed lines are put on the queue.
    On completion or error, puts a sentinel.
    """
    import io

    class QueueWriter(io.TextIOBase):
        def write(self, s):
            if s and s.strip():
                q.put(("log", s.rstrip()))
            return len(s)
        def flush(self): pass

    old_stdout = sys.stdout
    sys.stdout = QueueWriter()
    try:
        result = fn(**args)
        q.put(("done", result))
    except Exception as e:
        q.put(("error", str(e)))
    finally:
        sys.stdout = old_stdout


def _stream_queue(q: queue.Queue):
    """Generator that yields SSE messages from a queue until done/error."""
    while True:
        try:
            kind, data = q.get(timeout=60)
            if kind == "log":
                yield _make_sse({"type": "log", "text": data})
            elif kind == "done":
                # data may be a dict with report paths
                payload = data if data else {}
                if isinstance(payload, dict):
                    payload = {k: str(v) for k, v in payload.items()}
                yield _make_sse({"type": "done", "result": payload}, event="done")
                break
            elif kind == "error":
                yield _make_sse({"type": "error", "text": data}, event="error")
                break
        except queue.Empty:
            yield _make_sse({"type": "ping"}, event="ping")


# ── Build Stream ──────────────────────────────────────────────────────────────

@stream_bp.route("/build")
def stream_build():
    from config_loader import load_industry
    from niche_builder import search_google_cse, search_serpapi, dedupe_against_existing
    import time

    params = request.args
    industry_slug = params.get("industry", "")
    location      = params.get("location", "")
    count         = int(params.get("count", 50))
    engine        = params.get("engine", "google")
    dry_run       = params.get("dry_run", "false").lower() == "true"
    add_keywords  = [k.strip() for k in params.get("add_keywords", "").split(",") if k.strip()]
    add_locations = [l.strip() for l in params.get("add_locations", "").split(",") if l.strip()]
    notes         = params.get("notes", "")

    BASE = Path(__file__).parent.parent.parent
    TARGETS_DIR = BASE / "targets"

    def run_build():
        config = load_industry(industry_slug, custom_keywords=add_keywords,
                               custom_locations=add_locations, custom_notes=notes)
        loc = location or (config.get_all_locations()[0] if config.get_all_locations() else "Canada")
        keywords = config.get_all_keywords()[:3]
        all_urls = []

        for kw in keywords:
            query = (f'"{kw}" {loc} (site:.ca OR site:.com) '
                     f'-yelp -facebook -instagram -houzz -homestars -yellowpages')
            print(f"[>] Searching: {kw} in {loc}...")
            if dry_run:
                print(f"    [DRY RUN] Query: {query}")
                continue
            if engine == "serpapi":
                urls = search_serpapi(query, count // len(keywords) + 5)
            else:
                urls = search_google_cse(query, count // len(keywords) + 5)
            all_urls.extend(urls)
            print(f"    [+] Found {len(urls)} URLs")
            time.sleep(1.0)

        if dry_run:
            print(f"[DRY RUN] Would search {len(keywords)} queries.")
            return {}

        TARGETS_DIR.mkdir(exist_ok=True)
        out_file = TARGETS_DIR / f"{config.slug}_{loc.lower().replace(' ', '_')}.txt"
        all_urls = list(dict.fromkeys(all_urls))
        all_urls = dedupe_against_existing(all_urls, str(out_file))[:count]
        with open(out_file, "a", encoding="utf-8") as f:
            for u in all_urls:
                f.write(u + "\n")
        print(f"[✓] Saved {len(all_urls)} URLs → {out_file.name}")
        return {"file": str(out_file)}

    q = queue.Queue()
    threading.Thread(target=_run_in_thread, args=(run_build, {}, q), daemon=True).start()
    return Response(_stream_queue(q), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Advise Stream ─────────────────────────────────────────────────────────────

@stream_bp.route("/advise")
def stream_advise():
    from config_loader import load_industry
    from advisor import generate_advisory, save_advisory

    params = request.args
    industry_slug = params.get("industry", "")
    notes         = params.get("notes", "")

    def run_advise():
        config = load_industry(industry_slug, custom_notes=notes)
        print(f"[>] Generating advisory for: {config.name}...")
        report = generate_advisory(config)
        output_path = save_advisory(report)
        print(f"[✓] Advisory saved → {output_path.name}")
        return {"markdown": report.markdown, "path": str(output_path)}

    q = queue.Queue()
    threading.Thread(target=_run_in_thread, args=(run_advise, {}, q), daemon=True).start()
    return Response(_stream_queue(q), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ── Audit Stream ──────────────────────────────────────────────────────────────

@stream_bp.route("/audit")
def stream_audit():
    import time
    import csv as csv_module
    import requests as req_lib
    from bs4 import BeautifulSoup
    from config_loader import load_industry
    from contact_extractor import extract_contact
    from report_generator import AuditResult, save_audit_run
    import prompts

    params         = request.args
    industry_slug  = params.get("industry", "")
    target_file    = params.get("target_file", "")
    target_urls    = params.get("target_urls", "")   # newline-separated
    limit          = int(params.get("limit", 50))
    dry_run        = params.get("dry_run", "false").lower() == "true"
    notes          = params.get("notes", "")

    BASE = Path(__file__).parent.parent.parent

    def _hard_check(url):
        try:
            if not url.startswith("http"):
                url = f"https://{url}"
            import time
            start = time.time()
            resp = req_lib.get(url, timeout=10,
                               headers={"User-Agent": "Mozilla/5.0 (VayneConsulting Scout)"})
            elapsed = round(time.time() - start, 2)
            return {"status": resp.status_code, "response_time_sec": elapsed,
                    "valid": resp.status_code == 200, "html": resp.text,
                    "final_url": resp.url, "has_ssl": resp.url.startswith("https://")}
        except Exception as e:
            return {"error": str(e), "valid": False}

    def _soft_check(html, config):
        import os
        from openai import OpenAI
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return "LLM analysis skipped (no API key)."
        client = OpenAI(api_key=api_key)
        soup = BeautifulSoup(html, "html.parser")
        parts = []
        for tag, label in [("h1","H1"),("h2","H2"),("p","P")]:
            el = soup.find(tag)
            if el:
                parts.append(f"{label}: {el.get_text(strip=True)[:200]}")
        if not parts:
            return "No content extracted."
        try:
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompts.get_analysis_prompt(config.to_prompt_context())},
                    {"role": "user", "content": "\n".join(parts)}
                ],
                temperature=0.7, max_tokens=150
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"LLM error: {e}"

    def run_audit():
        from dotenv import load_dotenv
        load_dotenv(BASE / ".env")

        config = load_industry(industry_slug, custom_notes=notes)

        # Resolve targets
        targets = []
        if target_urls.strip():
            targets = [u.strip() for u in target_urls.strip().splitlines() if u.strip()]
        elif target_file:
            fpath = BASE / target_file if not Path(target_file).is_absolute() else Path(target_file)
            if fpath.suffix == ".csv":
                with open(fpath, newline="") as f:
                    targets = [row[0].strip() for row in csv_module.reader(f) if row and row[0].strip()]
            else:
                targets = [l.strip() for l in fpath.read_text().splitlines() if l.strip()]

        targets = targets[:limit]
        print(f"[>] Starting audit: {len(targets)} targets — Industry: {config.name}")
        if dry_run:
            print("[DRY RUN] Skipping all HTTP/LLM calls.")

        session = req_lib.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (VayneConsulting Scout)"})
        results = []

        for i, t in enumerate(targets, 1):
            url = t if t.startswith("http") else f"https://{t}"
            domain = url.replace("https://","").replace("http://","").split("/")[0]
            print(f"[{i}/{len(targets)}] {domain}")

            result = AuditResult(url=url, domain=domain,
                                 industry=config.name, industry_slug=config.slug)
            if dry_run:
                result.status = "skipped"
                result.insight = "[DRY RUN]"
                results.append(result)
                continue

            tech = _hard_check(url)
            if not tech.get("valid"):
                print(f"    [x] Unreachable: {tech.get('error', tech.get('status'))}")
                result.status = "failed"
                result.error = str(tech.get("error", tech.get("status")))
                results.append(result)
                continue

            result.status_code = tech.get("status", 0)
            result.load_time_sec = tech.get("response_time_sec", 0)
            result.has_ssl = tech.get("has_ssl", False)

            contact = extract_contact(url, tech["html"], session=session)
            result.company_name = contact.company_name
            result.first_name   = contact.first_name
            result.contact_email = contact.email
            result.contact_tier = contact.tier

            # Score
            score, issues = 5, []
            if result.load_time_sec > 5.0: score += 2; issues.append(f"Very slow: {result.load_time_sec}s")
            elif result.load_time_sec > 3.0: score += 1; issues.append(f"Slow: {result.load_time_sec}s")
            if not result.has_ssl: score += 2; issues.append("No SSL")
            if not contact.email: score += 1; issues.append("No email found")
            result.base_score = min(score, 10)
            result.detected_issues = issues
            result.final_score = min(result.base_score + sum(config.score_issue(i) for i in issues), 10)

            result.insight = _soft_check(tech["html"], config)
            specific_issue = issues[0] if issues else "friction in your digital presence"
            result.email_draft = prompts.get_email(
                result.final_score, result.first_name, result.company_name,
                domain, specific_issue, result.insight, result.load_time_sec
            )
            print(f"    [+] Score: {result.final_score}/10 | Tier: {result.contact_tier} | SSL: {result.has_ssl}")
            results.append(result)
            time.sleep(0.5)

        if not dry_run and results:
            paths = save_audit_run(results, config.slug, config.name)
            ok = [r for r in results if r.status == "ok"]
            high = [r for r in ok if r.final_score >= 8]
            print(f"[✓] Audit complete — {len(ok)} audited, {len(high)} high priority")
            summary_md = paths["markdown"].read_text(encoding="utf-8")
            return {"markdown": summary_md, "json_path": str(paths["json"]),
                    "md_path": str(paths["markdown"]),
                    "total": len(results), "high": len(high)}
        return {"total": len(results), "dry_run": True}

    q = queue.Queue()
    threading.Thread(target=_run_in_thread, args=(run_audit, {}, q), daemon=True).start()
    return Response(_stream_queue(q), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
