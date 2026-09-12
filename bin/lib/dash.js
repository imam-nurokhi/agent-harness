/* Command Center — renders live harness state. */
'use strict';

const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const ago = ts => {
  const d = Date.now() / 1000 - ts;
  if (d < 60) return Math.max(0, Math.round(d)) + 's';
  if (d < 3600) return Math.round(d / 60) + 'm';
  if (d < 86400) return Math.round(d / 3600) + 'h';
  return Math.round(d / 86400) + 'd';
};

const TABS = [
  ['terminal', 'terminal', d => d.jobs.filter(j => j.status === 'running').length],
  ['floor', 'floor', d => d.agents.filter(a => a.status !== 'idle').length],
  ['tasks', 'tasks', d => d.tasks.length],
  ['monitor', 'monitor', d => d.worktrees.length],
  ['triggers', 'triggers', d => d.triggers.length],
  ['activity', 'activity', null],
];

let DATA = null;
let TAB = localStorage.getItem('ah.tab') || 'terminal';

/* -------------------------------------------------- shell */

function nav(d) {
  $('#nav').innerHTML = TABS.map(([id, label, count]) => {
    const n = count ? count(d) : null;
    return `<button class="${id === TAB ? 'on' : ''}" onclick="go('${id}')">${label}` +
      (n ? `<span class="n">${n}</span>` : '') + `</button>`;
  }).join('');
  TABS.forEach(([id]) => $('#tab-' + id).classList.toggle('on', id === TAB));
}

function go(id) { TAB = id; localStorage.setItem('ah.tab', id); if (DATA) nav(DATA); }

const sprite = a => `<div class="sp" title="${esc(a.piece)}">${esc(a.glyph)}</div>`;

/* -------------------------------------------------- floor */

function floor(d) {
  const working = d.agents.filter(a => a.status === 'working');
  const assigned = d.agents.filter(a => a.status === 'assigned');
  const lead = d.agents.find(a => a.role === 'lead');

  $('#sub').textContent = working.length
    ? `${working.length} agent${working.length > 1 ? 's' : ''} working · ${lead ? lead.name : 'Lead'} runs the floor`
    : assigned.length ? `${assigned.length} assigned, none running · run one with \`ah run\``
    : 'the floor is quiet';

  $('#floorline').textContent =
    `${d.agents.length} desks · ${working.length} working · ${assigned.length} assigned · ` +
    `${d.agents.length - working.length - assigned.length} idle`;

  $('#desks').innerHTML = d.agents.map(a => `
    <div class="desk ${a.status}" onclick="openAgent('${a.role}')">
      <div class="top">${sprite(a)}
        <div><div class="nm">${esc(a.name)}</div>
          <div class="rl">${esc(a.title)}</div>
          <div class="pc">${esc(a.piece)}</div></div>
      </div>
      <div class="st ${a.status}">${a.status}</div>
      <div class="job">${a.task
        ? `<b>${esc(a.task)}</b><br>${esc((a.task_title || '').slice(0, 62))}`
        : '<span class="muted">waiting for a task</span>'}</div>
    </div>`).join('');

  $('#legend').innerHTML = d.agents.map(a =>
    `<div class="lg" onclick="openAgent('${a.role}')">
       <span class="g">${esc(a.glyph)}</span>
       <span><b>${esc(a.name)}</b> <span class="muted">${esc(a.piece)}</span><br>
       <span class="muted">${esc(a.title)} · <code>${esc(a.role)}</code></span></span>
     </div>`).join('');

  const s = d.summary.by_status;
  $('#floorstats').innerHTML = [
    ['Working now', working.length, working.map(a => a.name).join(', ') || 'nobody', working.length ? 'ok' : ''],
    ['Tasks open', s.planned + s.active + s.review, `${s.reported} reported`, ''],
    ['Worktrees', d.worktrees.length, `${d.worktrees.filter(w => w.dirty).length} with edits`, ''],
    ['Triggers', d.triggers.length, `${d.triggers.filter(t => t.installed).length} installed`, ''],
  ].map(([k, v, sub, cl]) =>
    `<div class="stat"><div class="k">${k}</div><div class="v ${cl}">${esc(v)}</div>
     <div class="s">${esc(sub)}</div></div>`).join('');
}

/* -------------------------------------------------- kanban */

const COLS = [
  ['todo', 'To do', t => t.status === 'planned'],
  ['doing', 'Doing', t => t.status === 'active'],
  ['blocked', 'Needs review', t => t.status === 'review'],
  ['done', 'Done', t => t.status === 'reported'],
];

function kanban(d) {
  $('#kb').innerHTML = COLS.map(([cls, label, pred]) => {
    const items = d.tasks.filter(pred);
    const who = r => (d.agents.find(a => a.role === r) || {}).name || r;
    const cards = items.map(t => {
      const pct = t.criteria_total ? Math.round(t.criteria_done / t.criteria_total * 100) : 0;
      return `<div class="kcard" onclick="openTask('${t.id}')">
        <div class="id">${esc(t.id)}</div>
        <div class="t">${esc(t.title)}</div>
        ${t.role ? `<div class="who">${esc(who(t.role))} · ${esc(t.role)}</div>` : ''}
        <div class="chips">
          ${t.klass ? `<span class="chip">${esc(t.klass)}</span>` : ''}
          ${t.has_worktree ? `<span class="chip">worktree</span>` : ''}
          ${t.criteria_total ? `<span class="chip ${pct === 100 ? 'ac' : ''}">${t.criteria_done}/${t.criteria_total} AC</span>` : ''}
        </div>
        ${t.criteria_total ? `<div class="bar"><i style="width:${pct}%"></i></div>` : ''}
        ${t.role ? `<button class="btn sm runbtn" onclick="event.stopPropagation();runTask('${t.id}','${t.role}')">run</button>` : ''}
      </div>`;
    }).join('') || `<div class="kempty">—</div>`;
    return `<div class="kcol ${cls}">
      <div class="h"><span>${label}</span><span>${items.length}</span></div>
      <div class="body">${cards}</div></div>`;
  }).join('');
}

/* -------------------------------------------------- monitor */

function monitor(d) {
  const h = d.health;
  const eng = Object.entries(h.engines).filter(([, v]) => v).length;
  const dk = h.disk_pct >= 95 ? 'bad' : h.disk_pct >= 85 ? 'warn' : 'ok';
  $('#health').innerHTML = [
    ['Engines', `${eng}/5`, h.codex_auth ? 'codex authed' : 'codex NOT authed', h.codex_auth ? 'ok' : 'bad'],
    ['Roles', h.roles.length, 'contracts loaded', 'ok'],
    ['Guardrail', h.documents_guard ? 'ON' : 'OFF', '~/Documents blocked', h.documents_guard ? 'ok' : 'bad'],
    ['Disk free', h.disk_free_gb + 'G', h.disk_pct + '% used', dk],
    ['Workspace', h.workspace.split('/').pop(), h.workspace.replace(/^\/Users\/[^/]+/, '~'), ''],
  ].map(([k, v, s, cl]) =>
    `<div class="stat"><div class="k">${k}</div><div class="v ${cl}">${esc(v)}</div>
     <div class="s">${esc(s)}</div></div>`).join('');

  $('#wcount').textContent = d.worktrees.length;
  $('#wt').innerHTML = d.worktrees.length ? `<table><thead><tr>
      <th>Task</th><th>Branch</th><th>State</th><th>Changes</th><th>Last commit</th>
    </tr></thead><tbody>` + d.worktrees.map(w => `<tr>
      <td>${esc(w.task)}</td><td>${esc(w.branch)}</td>
      <td><span class="dot ${w.dirty ? 'warn' : 'ok'}"></span>${w.dirty ? w.dirty + ' modified' : 'clean'}</td>
      <td>${esc(w.diffstat || '—')}${w.files.length
        ? `<div class="muted" style="margin-top:4px">${w.files.slice(0, 5).map(esc).join('<br>')}</div>` : ''}</td>
      <td class="muted">${esc(w.last_commit || '—')}<br>${esc(w.last_when || '')}</td>
    </tr>`).join('') + `</tbody></table>`
    : `<div class="empty">No worktrees. <code>ah wt add &lt;task-id&gt; &lt;project&gt;</code></div>`;

  $('#pcount').textContent = d.projects.length;
  $('#pj').innerHTML = d.projects.length ? `<table><thead><tr>
      <th>Project</th><th>Class</th><th>Git</th><th>AGENTS.md</th><th>Path</th>
    </tr></thead><tbody>` + d.projects.map(p => `<tr>
      <td>${esc(p.name)}</td><td><span class="chip">${esc(p.klass)}</span></td>
      <td>${p.git ? `<span class="dot ok"></span>${esc(p.branch || '—')}` : '<span class="dot bad"></span>not a repo'}</td>
      <td>${p.has_agents_md ? '<span class="dot ok"></span>yes' : '<span class="dot warn"></span>missing'}</td>
      <td class="muted">${esc(p.path.replace(/^\/Users\/[^/]+/, '~'))}</td>
    </tr>`).join('') + `</tbody></table>`
    : `<div class="empty">No projects under <code>~/AI-Workspace/projects/</code></div>`;

  $('#rcount').textContent = d.reports.length;
  $('#rp').innerHTML = d.reports.length ? `<table><thead><tr>
      <th>File</th><th>Task</th><th>Verdict</th><th>Size</th><th>Updated</th>
    </tr></thead><tbody>` + d.reports.map((r, i) => `<tr onclick="openReport(${i})" style="cursor:pointer">
      <td>${esc(r.name)}</td><td class="muted">${esc(r.task)}</td>
      <td>${r.verdict ? esc(r.verdict) : '<span class="muted">—</span>'}</td>
      <td class="muted">${(r.size / 1024).toFixed(1)}K</td>
      <td class="muted">${ago(r.mtime)} ago</td>
    </tr>`).join('') + `</tbody></table>`
    : `<div class="empty">No reports yet. <code>ah run --exec &lt;role&gt; &lt;task-id&gt;</code></div>`;
}

/* -------------------------------------------------- triggers + feed */

function triggers(d) {
  $('#trg').innerHTML = d.triggers.length ? d.triggers.map(t => `
    <div class="trg">
      <div class="r1">
        <span class="cad">${esc(t.schedule)}</span>
        <span class="lb">${esc(t.label)}</span>
        <span class="chip">${esc(t.role || 'lead')}</span>
        <span class="chip">${t.installed ? 'installed' : 'not installed'}</span>
        <span class="chip">${t.enabled ? 'enabled' : 'disabled'}</span>
        <span class="muted" style="margin-left:auto;font-size:11px">
          ${t.last_run ? 'last run ' + esc(t.last_run) : 'never run'}</span>
        <button class="btn sm" onclick="runTrigger('${t.id}')">run now</button>
      </div>
      <div class="pr">${esc(t.prompt)}</div>
    </div>`).join('')
    : `<div class="empty">No triggers defined yet.</div>`;
}

function feed(d) {
  $('#feed').innerHTML = d.activity.map(e =>
    `<div><span class="ago">${ago(e.mtime)} ago</span>
     <span class="kind ${esc(e.kind)}">${esc(e.kind)}</span>
     <span class="n">${esc(e.name)}</span></div>`).join('')
    || '<div><span class="n">nothing yet</span></div>';
}

function dock(d) {
  $('#dock').innerHTML = d.agents.map(a => `
    <div class="ag" onclick="openAgent('${a.role}')">
      ${sprite(a)}
      <div><div class="i">${esc(a.name)}</div>
        <div class="s ${a.status}">${esc(a.status)}</div></div>
    </div>`).join('');
}

/* -------------------------------------------------- modals */

function show(html) { $('#mbox').innerHTML = html; $('#modal').classList.add('on'); }
function closeModal() { $('#modal').classList.remove('on'); }
addEventListener('keydown', e => e.key === 'Escape' && closeModal());

function openAgent(role) {
  const a = DATA.agents.find(x => x.role === role); if (!a) return;
  const mine = DATA.tasks.filter(t => t.role === role);
  show(`<button class="close" onclick="closeModal()">esc</button>
    <h3>${esc(a.glyph)} ${esc(a.name)} — ${esc(a.title)}</h3>
    <div class="muted">${esc(a.piece)} · role <code>${esc(a.role)}</code> · ${esc(a.status)} · ${esc(a.detail)}</div>
    <h2 style="margin-top:18px">Assigned tasks <b>${mine.length}</b></h2>
    ${mine.length ? `<ul class="crit">${mine.map(t =>
      `<li><span class="o">${esc(t.status)}</span><span>${esc(t.id)} — ${esc(t.title)}</span></li>`).join('')}</ul>`
      : '<div class="muted">Nothing assigned.</div>'}
    <h2>Contract</h2>
    <div class="muted">${a.has_contract
      ? `Loaded from <code>agents/roles/${esc(a.role)}.md</code> and prepended to every run.`
      : 'MISSING — this role has no contract file.'}</div>
    <h2>Put ${esc(a.name)} to work</h2>
    <div class="q-row"><button class="btn primary" onclick="briefAgent('${a.role}')">brief ${esc(a.name)} →</button></div>
    <pre>ah run ${esc(a.role)} &lt;task-id&gt;      # or from the CLI</pre>`);
}

function openTask(id) {
  const t = DATA.tasks.find(x => x.id === id); if (!t) return;
  const li = a => a.map(c =>
    `<li><span class="${c.done ? 'x' : 'o'}">${c.done ? '✓' : '○'}</span><span>${esc(c.text)}</span></li>`).join('');
  const w = DATA.worktrees.find(x => x.task === id);
  show(`<button class="close" onclick="closeModal()">esc</button>
    <h3>${esc(t.title)}</h3>
    <div class="muted">${esc(t.id)} · ${esc(t.role || 'no role')} · ${esc(t.project || 'no project')}</div>
    <h2 style="margin-top:18px">Acceptance criteria <b>${t.criteria_done}/${t.criteria_total}</b></h2>
    <ul class="crit">${li(t.criteria) || '<li class="muted">none defined</li>'}</ul>
    <h2>Required checks</h2>
    <ul class="crit">${li(t.checks) || '<li class="muted">none defined</li>'}</ul>
    ${w ? `<h2>Worktree</h2><pre>branch: ${esc(w.branch)}
path:   ${esc(w.path)}
state:  ${w.dirty} modified file(s)
${esc(w.diffstat || '')}
${w.files.map(esc).join('\n')}</pre>` : ''}
    ${t.logs.length ? `<h2>Transcripts</h2><pre>${t.logs.map(esc).join('\n')}</pre>` : ''}
    <h2>Run it</h2>
    <div class="q-row">
      <button class="btn primary" onclick="runTask('${t.id}','${esc(t.role || '')}')">run ${esc(t.role || 'agent')} on ${esc(t.id)} →</button>
    </div>
    <pre>ah run ${esc(t.role || '&lt;role&gt;')} ${esc(t.id)}</pre>`);
}

function openReport(i) {
  const r = DATA.reports[i];
  show(`<button class="close" onclick="closeModal()">esc</button>
    <h3>${esc(r.name)}</h3>
    <div class="muted">${ago(r.mtime)} ago · ${(r.size / 1024).toFixed(1)}K</div>
    <h2 style="margin-top:16px">Tail</h2><pre>${esc(r.tail)}</pre>`);
}

/* -------------------------------------------------- loop */

async function tick() {
  try {
    DATA = await (await fetch('/api/state')).json();
    nav(DATA); floor(DATA); kanban(DATA); monitor(DATA);
    triggers(DATA); feed(DATA); dock(DATA); jobList(DATA); rolePicker(DATA); taskPicker(DATA);
    $('#live').classList.remove('down');
    $('#stamp').textContent = 'live ' + new Date().toLocaleTimeString();
  } catch (e) {
    $('#live').classList.add('down');
    $('#stamp').textContent = 'disconnected';
  }
}
/* ============================ interactive layer ============================ */

let JOB = null;          // selected job id
let OFFSET = 0;          // bytes of that job already rendered
let FOLLOW = true;
let ROLE = localStorage.getItem('ah.role') || 'lead';

async function post(path, body) {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-AH-Token': window.AH_TOKEN },
    body: JSON.stringify(body || {}),
  });
  const j = await r.json().catch(() => ({ error: 'bad response' }));
  if (!r.ok || j.error) throw new Error(j.error || ('HTTP ' + r.status));
  return j;
}

function qerr(msg) {
  $('#qerr').textContent = msg || '';
  if (msg) setTimeout(() => { if ($('#qerr').textContent === msg) $('#qerr').textContent = ''; }, 6000);
}

/* ---------- run list ---------- */

function jobList(d) {
  const el = $('#jobs');
  if (!d.jobs.length) {
    el.innerHTML = `<div class="jl-empty">No runs yet.<br><br>Dispatch one from the Queue below.</div>`;
    return;
  }
  el.innerHTML = d.jobs.map(j => {
    const who = (d.agents.find(a => a.role === j.role) || {}).name || j.role;
    return `<div class="job ${j.id === JOB ? 'on' : ''}" onclick="selectJob('${j.id}')">
      <div class="jr">${esc(who)} <span class="muted">${esc(j.role)}</span></div>
      <div class="jm">${esc(j.status)} · ${j.elapsed}s · ${esc(j.engine)}</div>
      <div class="jd">${esc(j.title || '')}</div>
    </div>`;
  }).join('');

  // Nothing selected yet: follow the newest run automatically.
  if (!JOB && d.jobs.length) selectJob(d.jobs[0].id);
}

function selectJob(id) {
  if (JOB === id) return;
  JOB = id; OFFSET = 0; FOLLOW = true;
  $('#term').textContent = '';
  $('#btnfollow').textContent = 'following';
  pump();
  if (DATA) jobList(DATA);
}

/* ---------- terminal stream ---------- */

async function pump() {
  if (!JOB) return;
  let r;
  try {
    r = await (await fetch(`/api/tail?id=${encodeURIComponent(JOB)}&offset=${OFFSET}`)).json();
  } catch { return; }
  if (r.error) return;

  const term = $('#term');
  if (r.chunk) {
    // Strip ANSI; the pane styles itself.
    term.textContent += r.chunk.replace(/\x1b\[[0-9;]*[A-Za-z]/g, '');
    OFFSET = r.offset;
    if (FOLLOW) term.scrollTop = term.scrollHeight;
  }

  const st = $('#termstat');
  st.textContent = r.status;
  st.className = 'tstat ' + r.status;
  $('#termtitle').textContent =
    `${r.role || ''} · ${r.engine || ''} · ${r.elapsed || 0}s` + (r.task ? ` · ${r.task}` : '');
  $('#btnstop').disabled = r.status !== 'running';

  if (r.status === 'running' && !term.textContent) term.textContent = 'starting…\n';
}

function toggleFollow() {
  FOLLOW = !FOLLOW;
  $('#btnfollow').textContent = FOLLOW ? 'following' : 'follow';
  if (FOLLOW) $('#term').scrollTop = $('#term').scrollHeight;
}

async function stopJob() {
  if (!JOB) return;
  try { await post('/api/stop', { id: JOB }); qerr(''); }
  catch (e) { qerr(e.message); }
}

/* ---------- queue ---------- */

function rolePicker(d) {
  const el = $('#rolepick');
  const sig = d.agents.map(a => a.role + a.status).join() + ROLE;
  if (el.dataset.sig === sig) return;
  el.dataset.sig = sig;
  el.innerHTML = d.agents.map(a =>
    `<button class="rp ${a.role === ROLE ? 'on' : ''}" onclick="pickRole('${a.role}')"
      title="${esc(a.title)}"><span class="g">${esc(a.glyph)}</span>${esc(a.name)}</button>`).join('');
}

function pickRole(r) {
  ROLE = r; localStorage.setItem('ah.role', r);
  if (DATA) rolePicker(DATA);
  const a = DATA.agents.find(x => x.role === r);
  $('#qhint').textContent = a ? `${a.name} — ${a.title}` : '';
}

function taskPicker(d) {
  const sel = $('#qtask');
  const sig = d.tasks.map(t => t.id + t.status).join();
  if (sel.dataset.sig === sig) return;
  sel.dataset.sig = sig;
  const keep = sel.value;
  sel.innerHTML = `<option value="">— no task, ad-hoc instruction —</option>` +
    d.tasks.map(t => `<option value="${esc(t.id)}">${esc(t.id)} · ${esc(t.title)}</option>`).join('');
  if (keep) sel.value = keep;
}

async function dispatch() {
  const prompt = $('#qtext').value.trim();
  const task = $('#qtask').value;
  if (!prompt && !task) return qerr('type an instruction or pick a task');
  try {
    const r = await post('/api/dispatch', { role: ROLE, prompt, task });
    $('#qtext').value = '';
    qerr('');
    go('terminal');
    JOB = null; selectJob(r.job.id);
    tick();
  } catch (e) { qerr(e.message); }
}

async function runTask(id, role) {
  if (!role) return qerr('this task has no Role set — edit its task file first');
  try {
    const r = await post('/api/dispatch', { role, task: id });
    closeModal(); go('terminal'); JOB = null; selectJob(r.job.id); tick();
  } catch (e) { qerr(e.message); alert(e.message); }
}

async function runTrigger(id) {
  try {
    const r = await post('/api/trigger/run', { id });
    go('terminal'); JOB = null; selectJob(r.job.id); tick();
  } catch (e) { alert(e.message); }
}

function briefAgent(role) {
  pickRole(role); closeModal(); go('terminal'); $('#qtext').focus();
}

async function newTaskPrompt() {
  const title = prompt('Task title');
  if (!title) return;
  try { await post('/api/task/new', { title }); await tick(); qerr(''); }
  catch (e) { qerr(e.message); }
}

// Cmd/Ctrl+Enter sends from the queue box.
addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && document.activeElement === $('#qtext')) dispatch();
});

setInterval(pump, 1200);

tick();
setInterval(tick, 4000);
