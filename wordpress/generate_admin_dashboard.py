#!/usr/bin/env python3
"""
Generate the Gravel God Course Admin Dashboard.

Produces a single static HTML page at wordpress/output/course/admin/index.html
that fetches live data from the course-access Worker's /admin/dashboard endpoint.

Not linked from public nav. Protected by ADMIN_API_KEY prompt on load.
Excluded from sitemap. noindex, nofollow.

Usage:
    python wordpress/generate_admin_dashboard.py
    python wordpress/generate_admin_dashboard.py --output-dir ./output/course/admin
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_tokens import get_tokens_css, get_font_face_css

WORKER_URL = "https://course-access.gravelgodcoaching.workers.dev"
OUTPUT_DIR = Path(__file__).parent / "output" / "course" / "admin"


def build_dashboard_css() -> str:
    """Return admin dashboard CSS."""
    return """
/* ── Admin Dashboard ── */
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Sometype Mono', monospace; background: #1a1612; color: #ede4d8; min-height: 100vh; }

.admin-header { padding: 24px 32px; border-bottom: 2px solid #178079; display: flex; justify-content: space-between; align-items: center; }
.admin-header h1 { font-family: 'Source Serif 4', Georgia, serif; font-size: 1.5rem; }
.admin-header .admin-refresh { background: #178079; color: #fff; border: none; padding: 8px 20px; font-family: 'Sometype Mono', monospace; font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; cursor: pointer; border-radius: 2px; }
.admin-header .admin-refresh:hover { background: #1A8A82; }
.admin-status { font-size: 11px; color: #8c7568; }

.admin-auth { display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 24px; }
.admin-auth-card { background: #3a2e25; padding: 48px 36px; border-radius: 4px; text-align: center; max-width: 400px; width: 100%; }
.admin-auth-card h2 { font-family: 'Source Serif 4', Georgia, serif; margin-bottom: 16px; }
.admin-auth-card input { width: 100%; padding: 12px 14px; font-family: 'Sometype Mono', monospace; font-size: 14px; border: 1px solid #59473c; border-radius: 2px; background: #1a1612; color: #ede4d8; margin-bottom: 12px; }
.admin-auth-card button { width: 100%; background: #178079; color: #fff; border: none; padding: 12px; font-family: 'Sometype Mono', monospace; font-size: 12px; letter-spacing: 1.5px; text-transform: uppercase; cursor: pointer; border-radius: 2px; }
.admin-auth-card .admin-error { color: #c0392b; font-size: 12px; margin-top: 8px; display: none; }

.admin-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 24px; padding: 32px; max-width: 1400px; margin: 0 auto; }

.admin-card { background: #3a2e25; border-radius: 4px; padding: 24px; }
.admin-card h3 { font-size: 11px; letter-spacing: 2px; text-transform: uppercase; color: #1A8A82; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 1px solid #59473c; }

.admin-stat-row { display: flex; justify-content: space-between; padding: 8px 0; font-size: 13px; }
.admin-stat-row .label { color: #8c7568; }
.admin-stat-row .value { color: #ede4d8; font-weight: 700; }

.admin-table { width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 8px; }
.admin-table th { text-align: left; color: #8c7568; padding: 6px 8px; border-bottom: 1px solid #59473c; font-weight: 400; letter-spacing: 1px; text-transform: uppercase; }
.admin-table td { padding: 6px 8px; border-bottom: 1px solid rgba(89,71,60,.3); color: #ede4d8; }
.admin-table tr:last-child td { border-bottom: none; }

.admin-bar { background: #59473c; height: 6px; border-radius: 3px; overflow: hidden; margin-top: 4px; }
.admin-bar-fill { height: 100%; background: #178079; border-radius: 3px; }

.admin-loading { text-align: center; padding: 60px 24px; color: #8c7568; font-size: 14px; }

.admin-card-full { grid-column: 1 / -1; }

@media (max-width: 768px) {
  .admin-grid { grid-template-columns: 1fr; padding: 16px; }
  .admin-header { padding: 16px; flex-wrap: wrap; gap: 8px; }
}
"""


def build_dashboard_js() -> str:
    """Return admin dashboard client-side JS."""
    return f"""
var WORKER_URL = '{WORKER_URL}';
var apiKey = '';

function init() {{
  apiKey = sessionStorage.getItem('gg-admin-key') || '';
  if (apiKey) {{
    document.getElementById('auth-screen').style.display = 'none';
    document.getElementById('dashboard-screen').style.display = 'block';
    fetchDashboard();
  }}
}}

function authenticate() {{
  var input = document.getElementById('admin-key-input');
  apiKey = input.value.trim();
  if (!apiKey) return;
  sessionStorage.setItem('gg-admin-key', apiKey);

  // Test the key
  fetch(WORKER_URL + '/admin/dashboard', {{
    method: 'POST',
    headers: {{
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + apiKey
    }},
    body: JSON.stringify({{}})
  }}).then(function(r) {{
    if (r.status === 401) {{
      document.getElementById('admin-auth-error').style.display = 'block';
      document.getElementById('admin-auth-error').textContent = 'Invalid API key';
      sessionStorage.removeItem('gg-admin-key');
      return;
    }}
    document.getElementById('auth-screen').style.display = 'none';
    document.getElementById('dashboard-screen').style.display = 'block';
    return r.json();
  }}).then(function(data) {{
    if (data) renderDashboard(data);
  }}).catch(function(err) {{
    document.getElementById('admin-auth-error').style.display = 'block';
    document.getElementById('admin-auth-error').textContent = 'Connection failed';
  }});
}}

function fetchDashboard() {{
  document.getElementById('admin-status').textContent = 'Loading...';
  fetch(WORKER_URL + '/admin/dashboard', {{
    method: 'POST',
    headers: {{
      'Content-Type': 'application/json',
      'Authorization': 'Bearer ' + apiKey
    }},
    body: JSON.stringify({{}})
  }}).then(function(r) {{
    if (r.status === 401) {{
      sessionStorage.removeItem('gg-admin-key');
      location.reload();
      return;
    }}
    return r.json();
  }}).then(function(data) {{
    if (data) renderDashboard(data);
  }}).catch(function(err) {{
    document.getElementById('admin-status').textContent = 'Error loading data';
  }});
}}

function renderDashboard(data) {{
  document.getElementById('admin-status').textContent = 'Updated ' + new Date(data.generated_at).toLocaleTimeString();

  // Revenue
  var rev = data.revenue || {{}};
  setVal('total-enrollments', rev.total_enrollments || 0);
  setVal('total-revenue', '$' + ((rev.total_revenue_cents || 0) / 100).toFixed(2));

  // Revenue by course
  var courseRevHtml = '';
  (rev.by_course || []).forEach(function(c) {{
    courseRevHtml += '<tr><td>' + esc(c.course_id) + '</td><td>' + c.enrollments + '</td><td>$' + (c.revenue / 100).toFixed(2) + '</td></tr>';
  }});
  setHtml('revenue-by-course', courseRevHtml);

  // Recent purchases
  var purchasesHtml = '';
  (rev.recent_purchases || []).slice(0, 10).forEach(function(p) {{
    var d = new Date(p.purchased_at);
    purchasesHtml += '<tr><td>' + esc(p.email) + '</td><td>' + esc(p.course_id) + '</td><td>$' + ((p.amount_cents || 0) / 100).toFixed(2) + '</td><td>' + d.toLocaleDateString() + '</td></tr>';
  }});
  setHtml('recent-purchases', purchasesHtml);

  // Engagement
  var eng = data.engagement || {{}};
  setVal('active-24h', eng.active_24h || 0);
  setVal('active-7d', eng.active_7d || 0);
  setVal('active-30d', eng.active_30d || 0);

  // Streaks
  var streaksHtml = '';
  (data.streaks && data.streaks.active_streaks || []).forEach(function(s) {{
    streaksHtml += '<tr><td>' + esc(s.email_hash) + '</td><td>' + s.current_streak + ' days</td><td>' + s.longest_streak + ' days</td></tr>';
  }});
  setHtml('active-streaks', streaksHtml);

  // Course health
  var healthHtml = '';
  (data.course_health || []).forEach(function(c) {{
    var completionRate = c.enrolled > 0 ? Math.round((c.completed / c.enrolled) * 100) : 0;
    healthHtml += '<tr><td>' + esc(c.course_id) + '</td><td>' + c.enrolled + '</td><td>' + c.started + '</td><td>' + c.completed + '</td><td>' + completionRate + '%</td></tr>';
  }});
  setHtml('course-health', healthHtml);

  // KC accuracy
  var kcHtml = '';
  (data.knowledge_checks || []).forEach(function(kc) {{
    var barColor = kc.accuracy_pct < 50 ? '#c0392b' : kc.accuracy_pct < 75 ? '#f39c12' : '#178079';
    kcHtml += '<tr><td>' + esc(kc.lesson_id) + '</td><td>' + esc(kc.question_hash) + '</td><td>' + kc.attempts + '</td><td>' + kc.accuracy_pct + '%<div class="admin-bar"><div class="admin-bar-fill" style="width:' + kc.accuracy_pct + '%;background:' + barColor + '"></div></div></td></tr>';
  }});
  setHtml('kc-accuracy', kcHtml);

  // Nudge stats
  var nudgeHtml = '';
  (data.nudges || []).forEach(function(n) {{
    nudgeHtml += '<tr><td>' + esc(n.nudge_type) + '</td><td>' + n.sent + '</td></tr>';
  }});
  setHtml('nudge-stats', nudgeHtml);
}}

function setVal(id, val) {{
  var el = document.getElementById(id);
  if (el) el.textContent = val;
}}

function setHtml(id, html) {{
  var el = document.getElementById(id);
  if (el) el.innerHTML = html;
}}

function esc(s) {{
  if (!s) return '';
  var d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}}

document.addEventListener('DOMContentLoaded', init);
"""


def build_dashboard_html() -> str:
    """Build the admin dashboard HTML page."""
    tokens_css = get_tokens_css()
    font_css = get_font_face_css("/race/assets/fonts")
    dashboard_css = build_dashboard_css()
    dashboard_js = build_dashboard_js()

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Admin Dashboard | Gravel God Courses</title>
  <meta name="robots" content="noindex, nofollow">
  <style>
{font_css}
{tokens_css}
{dashboard_css}
  </style>
</head>
<body>

<!-- Auth Screen -->
<div id="auth-screen" class="admin-auth">
  <div class="admin-auth-card">
    <h2>Course Admin</h2>
    <p style="color:#8c7568;font-size:12px;margin-bottom:16px">Enter your admin API key to access the dashboard.</p>
    <input type="password" id="admin-key-input" placeholder="Admin API Key" onkeydown="if(event.key==='Enter')authenticate()">
    <button onclick="authenticate()">ACCESS DASHBOARD</button>
    <div class="admin-error" id="admin-auth-error"></div>
  </div>
</div>

<!-- Dashboard Screen -->
<div id="dashboard-screen" style="display:none">
  <div class="admin-header">
    <h1>Course Dashboard</h1>
    <div>
      <span class="admin-status" id="admin-status"></span>
      <button class="admin-refresh" onclick="fetchDashboard()">REFRESH</button>
    </div>
  </div>

  <div class="admin-grid">

    <!-- Revenue Overview -->
    <div class="admin-card">
      <h3>Revenue</h3>
      <div class="admin-stat-row"><span class="label">Total Enrollments</span><span class="value" id="total-enrollments">—</span></div>
      <div class="admin-stat-row"><span class="label">Total Revenue</span><span class="value" id="total-revenue">—</span></div>
    </div>

    <!-- Revenue by Course -->
    <div class="admin-card">
      <h3>Revenue by Course</h3>
      <table class="admin-table">
        <thead><tr><th>Course</th><th>Enrolled</th><th>Revenue</th></tr></thead>
        <tbody id="revenue-by-course"><tr><td colspan="3" style="color:#8c7568">Loading...</td></tr></tbody>
      </table>
    </div>

    <!-- Engagement -->
    <div class="admin-card">
      <h3>Engagement</h3>
      <div class="admin-stat-row"><span class="label">Active (24h)</span><span class="value" id="active-24h">—</span></div>
      <div class="admin-stat-row"><span class="label">Active (7d)</span><span class="value" id="active-7d">—</span></div>
      <div class="admin-stat-row"><span class="label">Active (30d)</span><span class="value" id="active-30d">—</span></div>
    </div>

    <!-- Streaks -->
    <div class="admin-card">
      <h3>Active Streaks</h3>
      <table class="admin-table">
        <thead><tr><th>User</th><th>Current</th><th>Longest</th></tr></thead>
        <tbody id="active-streaks"><tr><td colspan="3" style="color:#8c7568">Loading...</td></tr></tbody>
      </table>
    </div>

    <!-- Course Health -->
    <div class="admin-card admin-card-full">
      <h3>Course Health</h3>
      <table class="admin-table">
        <thead><tr><th>Course</th><th>Enrolled</th><th>Started</th><th>Completed</th><th>Completion Rate</th></tr></thead>
        <tbody id="course-health"><tr><td colspan="5" style="color:#8c7568">Loading...</td></tr></tbody>
      </table>
    </div>

    <!-- Recent Purchases -->
    <div class="admin-card admin-card-full">
      <h3>Recent Purchases (Last 7 Days)</h3>
      <table class="admin-table">
        <thead><tr><th>Email</th><th>Course</th><th>Amount</th><th>Date</th></tr></thead>
        <tbody id="recent-purchases"><tr><td colspan="4" style="color:#8c7568">Loading...</td></tr></tbody>
      </table>
    </div>

    <!-- KC Accuracy -->
    <div class="admin-card admin-card-full">
      <h3>Knowledge Check Accuracy</h3>
      <table class="admin-table">
        <thead><tr><th>Lesson</th><th>Question</th><th>Attempts</th><th>Accuracy</th></tr></thead>
        <tbody id="kc-accuracy"><tr><td colspan="4" style="color:#8c7568">Loading...</td></tr></tbody>
      </table>
    </div>

    <!-- Nudge Performance -->
    <div class="admin-card">
      <h3>Nudge Emails</h3>
      <table class="admin-table">
        <thead><tr><th>Type</th><th>Sent</th></tr></thead>
        <tbody id="nudge-stats"><tr><td colspan="2" style="color:#8c7568">Loading...</td></tr></tbody>
      </table>
    </div>

  </div>
</div>

<script>
{dashboard_js}
</script>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(
        description="Generate Gravel God Course Admin Dashboard."
    )
    parser.add_argument(
        "--output-dir", default=str(OUTPUT_DIR),
        help=f"Output directory (default: {OUTPUT_DIR})"
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    dashboard_html = build_dashboard_html()
    (output_dir / "index.html").write_text(dashboard_html, encoding="utf-8")
    print(f"Generated admin dashboard: {output_dir / 'index.html'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
