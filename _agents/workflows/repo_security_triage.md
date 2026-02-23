---
description: Repo security triage — classify files, audit git tracking, and confirm only public-safe assets are pushed to the live service
---

# Workspace Repo Security — Triage → Audit → Confirm

Run this workflow on any new or existing project workspace before pushing to a live hosting service. The goal is to ensure internal tools, sensitive business documents, and private data are never exposed.

> [!IMPORTANT]
> This workflow must be run from the root of the workspace repo unless otherwise noted.

---

## Stage 1 — TRIAGE: Classify the Workspace

Scan the workspace and mentally (or physically) sort every file into one of four buckets:

| Bucket | Description | Destination |
|:---|:---|:---|
| 🌐 **Public** | Files the live website needs to serve | Keep in repo |
| 🔧 **Tool** | Scripts, local CLIs, automation code | Gitignore |
| 📄 **Internal Doc** | Strategy, plans, proposals, drafts | Gitignore |
| 🔑 **Secret** | API keys, `.env`, email drafts, acquisition plans | Gitignore + never commit |

### Step 1.1 — List all tracked files

```powershell
git ls-files
```

Review the output. Flag any file that does not belong in the **Public** bucket.

### Step 1.2 — List all untracked files to check for accidental staging

```powershell
git status
```

Confirm no sensitive file is staged or about to be committed.

### Step 1.3 — Identify high-risk files by pattern

Look for any tracked file matching these patterns — they must be gitignored:

- `*.md` files at root level (check if internal — strategy, plans, pricing, emails)
- `*.py`, `*.sh`, `*.bat` — scripts/tools
- `*.env`, `.env*` — API keys
- `__pycache__/`, `*.pyc` — Python artifacts
- Any folder not directly serving the website (`tools/`, `docs/`, `sales_assets/`, `content/`, `synchro/` etc.)
- `*.bak`, `*.code-workspace`, `.idea/`, `.vscode/`

---

## Stage 2 — AUDIT: Verify Git Tracking & Bandwidth Exposure

### Step 2.1 — Check current .gitignore exists and is non-trivial

```powershell
Get-Content .gitignore
```

If `.gitignore` is missing or minimal (less than 20 lines), it needs to be rebuilt. The minimum required sections are:
- Internal tools block
- Sensitive document block
- Python/environment block
- System/editor block

### Step 2.2 — Check what git would push right now

```powershell
git diff --stat HEAD~1 HEAD
```

Review file count and total KB. A push of more than ~20KB for a static website is a red flag.

### Step 2.3 — Check for previously committed secrets still in history

```powershell
git log --all --oneline | Select-Object -First 10
git show --stat HEAD
```

If sensitive files were committed in a **previous** commit, they remain in git history even after gitignoring. In that case, note them — a history rewrite (`git filter-repo`) may be needed (document in findings, do not auto-execute).

### Step 2.4 — Confirm the remote is the expected service

```powershell
git remote -v
```

Verify the push destination is correct and is the intended hosting service (not a public mirror or backup).

---

## Stage 3 — CONFIRM: Apply Fixes and Lock Down

### Step 3.1 — If .gitignore needs updating, rewrite it now

Use the following template as the base — adjust buckets to the project:

```gitignore
# ── INTERNAL TOOLS ───────────────────────────────────────────
<tool_folders>/
tools/

# ── SENSITIVE BUSINESS DOCUMENTS ─────────────────────────────
*_plan.md
*_strategy.md
*_draft*.md
*_proposal.md

# ── PYTHON / RUNTIME ─────────────────────────────────────────
__pycache__/
*.pyc
.env
.venv/
reports/
targets/

# ── EDITOR / SYSTEM ──────────────────────────────────────────
.DS_Store
Thumbs.db
*.bak
*.code-workspace
.vscode/
.idea/
*.swp
*.log
```

### Step 3.2 — Untrack any currently-tracked files that should be gitignored

// turbo
```powershell
git rm -r --cached .
git add .
```

This re-stages only what is NOT gitignored. All previously-tracked internal files are removed from the index on next commit.

### Step 3.3 — Commit the cleanup

```powershell
git commit -m "security: untrack internal files, lock .gitignore to public-only"
```

### Step 3.4 — Final verification before push

// turbo
```powershell
git ls-files
```

**Review the full output.** Every single file listed must be in the Public bucket. If any file is unexpected, do NOT push — return to Stage 1.

If the list is clean:

```powershell
git push origin main
```

### Step 3.5 — Record the push size

Note the KB pushed. For bandwidth-constrained services, target under 50KB per push for static website updates.

---

## Checklist Summary

- [ ] Stage 1: All tracked files classified
- [ ] Stage 1: No sensitive files staged or committed
- [ ] Stage 2: `.gitignore` is comprehensive
- [ ] Stage 2: Push delta is within expected size
- [ ] Stage 2: Remote URL confirmed correct
- [ ] Stage 3: `.gitignore` updated if needed
- [ ] Stage 3: `git rm -r --cached .` run if files were untracked
- [ ] Stage 3: `git ls-files` reviewed — only public files listed
- [ ] Stage 3: Push completed and size noted
