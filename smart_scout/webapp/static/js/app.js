/**
 * Smart Scout Web UI — Frontend Application
 * ==========================================
 * Vayne Consulting — Smart Scout Multi-Industry Edition
 *
 * Vanilla JS — no framework, no build step.
 * Uses Fetch API for REST calls and EventSource for SSE streaming.
 */

// ── Minimal Markdown renderer ──────────────────────────────────────────────
function renderMarkdown(md) {
    if (!md) return '';
    let html = md
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        // Headers
        .replace(/^### (.+)$/gm, '<h3>$1</h3>')
        .replace(/^## (.+)$/gm, '<h2>$1</h2>')
        .replace(/^# (.+)$/gm, '<h1>$1</h1>')
        // Bold/Italic
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        // Inline code
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        // Horizontal rule
        .replace(/^---+$/gm, '<hr>')
        // Blockquote
        .replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>')
        // Unordered list
        .replace(/^\s*[-*] (.+)$/gm, '<li>$1</li>')
        // Ordered list
        .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
        // Tables (basic)
        .replace(/\|(.+)\|\n\|[-| :]+\|\n((?:\|.+\|\n?)+)/g, (match, header, rows) => {
            const ths = header.split('|').filter(Boolean).map(h => `<th>${h.trim()}</th>`).join('');
            const trs = rows.trim().split('\n').map(row => {
                const tds = row.split('|').filter(Boolean).map(c => `<td>${c.trim()}</td>`).join('');
                return `<tr>${tds}</tr>`;
            }).join('');
            return `<table><thead><tr>${ths}</tr></thead><tbody>${trs}</tbody></table>`;
        })
        // Code blocks
        .replace(/```[\w]*\n([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
        // Paragraphs (wrap orphan lines)
        .replace(/^(?!<[h|u|o|l|p|b|t|h|c|p]|<\/|<h|<li|<pre|<bl|<hr)(.+)$/gm, '<p>$1</p>')
        // Wrap consecutive <li> in <ul>
        .replace(/(<li>[\s\S]*?<\/li>\n?)+/g, match => `<ul>${match}</ul>`);
    return html;
}

// ── State ────────────────────────────────────────────────────────────────────
const state = {
    industries: [],
    targetFiles: [],
    reports: [],
    activeReport: null,
    advisoryMarkdown: null,
    auditMarkdown: null,
    auditMdPath: null,
    advisoryPath: null,
    currentStream: null,
    auditTotal: 0,
    auditDone: 0,
};

// ── DOM helpers ──────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const setStatus = (text, cls = '') => {
    $('statusText').textContent = text;
    const dot = $('statusDot');
    dot.className = 'status-dot' + (cls ? ' ' + cls : '');
};

// ── Navigation ───────────────────────────────────────────────────────────────
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
        document.querySelectorAll('.nav-item').forEach(i => i.classList.remove('active'));
        document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
        item.classList.add('active');
        $('panel-' + item.dataset.panel).classList.add('active');
        if (item.dataset.panel === 'reports') loadReports();
    });
});

// ── Industry selectors sync ──────────────────────────────────────────────────
function populateIndustrySelects(industries) {
    ['buildIndustry', 'adviseIndustry', 'auditIndustry'].forEach(id => {
        const sel = $(id);
        if (!sel) return;
        const current = sel.value;
        sel.innerHTML = '';
        industries.forEach(ind => {
            const opt = document.createElement('option');
            opt.value = ind.slug;
            opt.textContent = ind.name;
            sel.appendChild(opt);
        });
        if (current) sel.value = current;
    });
}

// ── Terminal logger ──────────────────────────────────────────────────────────
function termLog(termId, text, cls = '') {
    const term = $(termId);
    // Remove placeholder on first log
    const placeholder = term.querySelector('.term-prompt');
    if (placeholder) placeholder.remove();

    const line = document.createElement('div');
    line.className = 'term-log ' + cls;
    line.textContent = text;
    term.appendChild(line);
    term.scrollTop = term.scrollHeight;
}

function termClear(termId) {
    $(termId).innerHTML = '';
}

function classifyLog(text) {
    const t = text.toLowerCase();
    if (t.includes('[✓]') || t.includes('complete') || t.includes('saved')) return 'done';
    if (t.includes('[!]') || t.includes('error') || t.includes('failed')) return 'error';
    if (t.includes('[dry run]') || t.includes('warning')) return 'warn';
    if (t.includes('[+]') || t.includes('[>]') || t.includes('[~]')) return 'info';
    return '';
}

// ── SSE stream runner ────────────────────────────────────────────────────────
function runStream(endpoint, params, termId, onDone, onError) {
    // Close any existing stream
    if (state.currentStream) { state.currentStream.close(); state.currentStream = null; }

    termClear(termId);
    setStatus('Running…', 'running');

    const url = new URL('/stream/' + endpoint, window.location.origin);
    Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
    });

    const es = new EventSource(url.toString());
    state.currentStream = es;

    es.addEventListener('message', e => {
        const data = JSON.parse(e.data);
        if (data.type === 'log') termLog(termId, data.text, classifyLog(data.text));
    });

    es.addEventListener('done', e => {
        const data = JSON.parse(e.data);
        es.close();
        state.currentStream = null;
        setStatus('Done', 'done');
        if (onDone) onDone(data.result || {});
    });

    es.addEventListener('error', e => {
        es.close();
        state.currentStream = null;
        setStatus('Error', 'error');
        try {
            const data = JSON.parse(e.data);
            termLog(termId, '[!] ' + (data.text || 'Unknown error'), 'error');
        } catch (_) { }
        if (onError) onError();
    });

    es.onerror = () => {
        if (es.readyState === EventSource.CLOSED) return;
        setStatus('Connection error', 'error');
        es.close();
    };
}

// ════════════════════════════════════════════════════════════════════════════
// INDUSTRIES PANEL
// ════════════════════════════════════════════════════════════════════════════

async function loadIndustries() {
    const grid = $('industryGrid');
    grid.innerHTML = '<div class="loading-spinner">Loading…</div>';
    const res = await fetch('/api/industries');
    state.industries = await res.json();
    populateIndustrySelects(state.industries);

    if (state.industries.length === 0) {
        grid.innerHTML = '<div class="empty-state">No industry configs found.<br>Create one to get started.</div>';
        return;
    }

    grid.innerHTML = '';
    state.industries.forEach(ind => {
        const card = document.createElement('div');
        card.className = 'industry-card';
        card.innerHTML = `
      <div class="card-slug">${ind.slug}</div>
      <div class="card-name">${ind.name}</div>
      <div class="card-stats">
        <span class="card-stat">${ind.keyword_count} keywords</span>
        <span class="card-stat">${ind.location_count} locations</span>
        <span class="card-stat">${ind.pain_point_count} pain points</span>
      </div>
      <div class="card-pain">${(ind.pain_points || [''])[0]}</div>
      <div class="card-actions">
        <button class="btn btn-ghost btn-sm" data-slug="${ind.slug}" data-action="edit">Edit</button>
        <button class="btn btn-danger btn-sm" data-slug="${ind.slug}" data-action="delete">Delete</button>
      </div>`;
        grid.appendChild(card);
    });

    grid.querySelectorAll('[data-action="edit"]').forEach(btn => {
        btn.addEventListener('click', () => openIndustryModal(btn.dataset.slug));
    });
    grid.querySelectorAll('[data-action="delete"]').forEach(btn => {
        btn.addEventListener('click', () => deleteIndustry(btn.dataset.slug));
    });
}

const YAML_TEMPLATE = `name: "New Industry"
slug: "new_industry"

search_keywords:
  - "your keyword here"

locations:
  - "Montreal"

pain_points:
  - "Common problem in this vertical"

kpis:
  - "Conversion rate"

trust_signals:
  - "Key trust signal clients look for"

offer_angle: >
  Why Vayne Consulting's offer resonates here.

analysis_focus: >
  What the LLM should look for when auditing sites.

outreach_angle: >
  The hook for the outreach email.

priority_indicators:
  high:
    - "No contact form"
  medium:
    - "No SSL"
  low:
    - "Missing meta description"
`;

async function openIndustryModal(slug) {
    const isNew = !slug;
    $('modalTitle').textContent = isNew ? 'New Industry Config' : `Edit: ${slug}`;
    $('industrySlug').value = slug || '';
    $('industrySlug').disabled = !isNew;
    $('industryYaml').value = YAML_TEMPLATE;

    if (!isNew) {
        const res = await fetch(`/api/industries/${slug}`);
        const data = await res.json();
        $('industryYaml').value = data.yaml || '';
    }
    $('industryModal').classList.remove('hidden');
}

$('btnNewIndustry').addEventListener('click', () => openIndustryModal(null));
$('modalClose').addEventListener('click', () => $('industryModal').classList.add('hidden'));
$('modalCancel').addEventListener('click', () => $('industryModal').classList.add('hidden'));

$('modalSave').addEventListener('click', async () => {
    const slug = $('industrySlug').value.trim().replace(/\s+/g, '_').toLowerCase();
    const yamlContent = $('industryYaml').value;
    if (!slug) { alert('Slug is required.'); return; }
    if (!yamlContent.trim()) { alert('YAML content is required.'); return; }

    const isNew = !$('industrySlug').disabled || !state.industries.find(i => i.slug === slug);
    const method = isNew ? 'POST' : 'PUT';
    const url = isNew ? '/api/industries' : `/api/industries/${slug}`;

    const res = await fetch(url, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ slug, yaml: yamlContent })
    });
    const data = await res.json();
    if (data.error) { alert('Error: ' + data.error); return; }
    $('industryModal').classList.add('hidden');
    loadIndustries();
});

async function deleteIndustry(slug) {
    if (!confirm(`Delete '${slug}'? This cannot be undone.`)) return;
    await fetch(`/api/industries/${slug}`, { method: 'DELETE' });
    loadIndustries();
}

// ════════════════════════════════════════════════════════════════════════════
// BUILD PANEL
// ════════════════════════════════════════════════════════════════════════════

$('buildDryRun').addEventListener('change', function () {
    $('buildDryLabel').textContent = this.checked ? 'On — no API calls' : 'Off — live search';
});

$('btnRunBuild').addEventListener('click', () => {
    const params = {
        industry: $('buildIndustry').value,
        location: $('buildLocation').value,
        count: $('buildCount').value,
        engine: $('buildEngine').value,
        add_keywords: $('buildKeywords').value,
        add_locations: $('buildLocations').value,
        dry_run: $('buildDryRun').checked,
        notes: ''
    };
    runStream('build', params, 'buildTerminal',
        result => {
            termLog('buildTerminal', `[✓] ${result.file ? 'Targets saved → ' + result.file.split(/[\\/]/).pop() : 'Dry run complete'}`, 'done');
            loadTargetFiles(); // refresh audit dropdown
        }
    );
});

// ════════════════════════════════════════════════════════════════════════════
// ADVISE PANEL
// ════════════════════════════════════════════════════════════════════════════

$('btnRunAdvise').addEventListener('click', () => {
    const params = {
        industry: $('adviseIndustry').value,
        notes: $('adviseNotes').value,
    };
    runStream('advise', params, 'adviseTerminal', result => {
        if (result.markdown) {
            state.advisoryMarkdown = result.markdown;
            state.advisoryPath = result.path;
            $('advisePreview').innerHTML = renderMarkdown(result.markdown);
            $('btnDownloadAdvisory').classList.remove('hidden');
        }
    });
});

$('btnDownloadAdvisory').addEventListener('click', () => {
    if (!state.advisoryMarkdown) return;
    const blob = new Blob([state.advisoryMarkdown], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'advisory_report.md';
    a.click();
});

// ════════════════════════════════════════════════════════════════════════════
// AUDIT PANEL
// ════════════════════════════════════════════════════════════════════════════

async function loadTargetFiles() {
    const res = await fetch('/api/targets');
    state.targetFiles = await res.json();
    const sel = $('auditTargetFile');
    sel.innerHTML = state.targetFiles.length
        ? state.targetFiles.map(f => `<option value="${f.path}">${f.name} (${f.lines} lines)</option>`).join('')
        : '<option value="">No target files found — run Build first</option>';
}

document.querySelectorAll('input[name="targetSrc"]').forEach(r => {
    r.addEventListener('change', () => {
        const isPaste = $('srcPaste').checked;
        $('fileSourceGroup').classList.toggle('hidden', isPaste);
        $('pasteSourceGroup').classList.toggle('hidden', !isPaste);
    });
});

$('auditDryRun').addEventListener('change', function () {
    $('auditDryLabel').textContent = this.checked ? 'On — no HTTP/LLM calls' : 'Off — live audit';
});

$('btnRunAudit').addEventListener('click', () => {
    const isPaste = $('srcPaste').checked;
    const limit = parseInt($('auditLimit').value) || 10;
    state.auditTotal = limit;
    state.auditDone = 0;
    $('auditProgress').classList.remove('hidden');
    $('progressFill').style.width = '0%';
    $('progressLabel').textContent = `0 / ${limit}`;

    const params = {
        industry: $('auditIndustry').value,
        target_file: isPaste ? '' : $('auditTargetFile').value,
        target_urls: isPaste ? $('auditTargetUrls').value : '',
        limit: limit,
        dry_run: $('auditDryRun').checked,
        notes: $('auditNotes').value,
    };

    // Patch the stream handler to update progress
    const origRun = runStream;
    termClear('auditTerminal');
    setStatus('Auditing…', 'running');
    if (state.currentStream) { state.currentStream.close(); state.currentStream = null; }

    const url = new URL('/stream/audit', window.location.origin);
    Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, String(v));
    });

    const es = new EventSource(url.toString());
    state.currentStream = es;

    es.addEventListener('message', e => {
        const data = JSON.parse(e.data);
        if (data.type === 'log') {
            const text = data.text;
            termLog('auditTerminal', text, classifyLog(text));
            // Check if it looks like a target line [N/M]
            const match = text.match(/^\[(\d+)\/(\d+)\]/);
            if (match) {
                state.auditDone = parseInt(match[1]);
                state.auditTotal = parseInt(match[2]);
                const pct = Math.round((state.auditDone / state.auditTotal) * 100);
                $('progressFill').style.width = pct + '%';
                $('progressLabel').textContent = `${state.auditDone} / ${state.auditTotal}`;
            }
        }
    });

    es.addEventListener('done', e => {
        const data = JSON.parse(e.data);
        es.close(); state.currentStream = null;
        setStatus('Audit complete', 'done');
        $('progressFill').style.width = '100%';
        $('progressLabel').textContent = `${state.auditTotal} / ${state.auditTotal}`;
        const result = data.result || {};
        if (result.markdown) {
            state.auditMarkdown = result.markdown;
            state.auditMdPath = result.md_path;
            $('auditPreview').innerHTML = renderMarkdown(result.markdown);
            $('btnDownloadAudit').classList.remove('hidden');
            termLog('auditTerminal', `[✓] Audit complete — ${result.total} audited, ${result.high} high priority`, 'done');
        } else {
            $('auditPreview').innerHTML = '<p class="preview-placeholder">Dry run complete. Remove dry-run to generate a real report.</p>';
        }
        loadReports();
    });

    es.addEventListener('error', e => {
        es.close(); state.currentStream = null;
        setStatus('Error', 'error');
        try { const d = JSON.parse(e.data); termLog('auditTerminal', '[!] ' + d.text, 'error'); } catch (_) { }
    });
});

$('btnDownloadAudit').addEventListener('click', () => {
    if (!state.auditMarkdown) return;
    const blob = new Blob([state.auditMarkdown], { type: 'text/markdown' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'audit_summary.md';
    a.click();
});

// ════════════════════════════════════════════════════════════════════════════
// REPORTS PANEL
// ════════════════════════════════════════════════════════════════════════════

$('btnRefreshReports').addEventListener('click', loadReports);

async function loadReports() {
    const container = $('reportsList');
    container.innerHTML = '<div class="loading-spinner">Loading…</div>';
    const res = await fetch('/api/reports');
    state.reports = await res.json();

    if (state.reports.length === 0) {
        container.innerHTML = '<div class="empty-state">No reports yet.<br>Run an Advise or Audit to generate one.</div>';
        return;
    }

    // Group by industry
    const byIndustry = {};
    state.reports.forEach(r => {
        if (!byIndustry[r.industry]) byIndustry[r.industry] = [];
        byIndustry[r.industry].push(r);
    });

    container.innerHTML = '';
    Object.entries(byIndustry).forEach(([industry, reports]) => {
        const group = document.createElement('div');
        group.className = 'report-group';
        group.innerHTML = `<div class="report-group-header">${industry}</div>`;
        reports.forEach(r => {
            const item = document.createElement('div');
            item.className = 'report-item';
            item.innerHTML = `
        <div>
          <div class="report-name">${r.filename}</div>
          <div class="report-meta">${r.size_kb} KB · ${r.format.toUpperCase()}</div>
        </div>
        <span class="report-badge ${r.type}">${r.type}</span>`;
            item.addEventListener('click', () => openReport(r, item));
            group.appendChild(item);
        });
        container.appendChild(group);
    });
}

async function openReport(report, itemEl) {
    document.querySelectorAll('.report-item').forEach(i => i.classList.remove('active'));
    itemEl.classList.add('active');
    state.activeReport = report;

    $('reportPreviewTitle').textContent = report.filename;
    $('reportPreview').innerHTML = '<div class="loading-spinner">Loading…</div>';
    $('btnDownloadReport').classList.remove('hidden');

    const res = await fetch(`/api/reports/${report.industry}/${report.filename}`);
    const data = await res.json();

    if (report.format === 'md') {
        $('reportPreview').innerHTML = renderMarkdown(data.content);
    } else {
        $('reportPreview').innerHTML = `<pre><code>${JSON.stringify(JSON.parse(data.content), null, 2)}</code></pre>`;
    }

    $('btnDownloadReport').onclick = () => {
        window.location.href = `/api/reports/${report.industry}/${report.filename}/download`;
    };
}

// ════════════════════════════════════════════════════════════════════════════
// INIT
// ════════════════════════════════════════════════════════════════════════════

async function init() {
    await loadIndustries();
    await loadTargetFiles();
}

init();
