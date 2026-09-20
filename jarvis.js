'use strict';

// ═══════════════════════════════════════════════════════════
//  J.A.R.V.I.S — MAIN ENGINE
// ═══════════════════════════════════════════════════════════

// ── CONFIG ─────────────────────────────────────────────────
const GEMINI_API_KEY = "YOUR_GEMINI_API_KEY_HERE";
const GEMINI_BASE     = 'https://generativelanguage.googleapis.com/v1beta/models';

const PERSONALITIES = {
  jarvis:   'You are J.A.R.V.I.S (Just A Rather Very Intelligent System), a sophisticated AI assistant inspired by Iron Man\'s JARVIS. You are highly intelligent, formal yet personable, efficient, and occasionally witty. Address the user respectfully. Keep responses structured and precise.',
  friendly: 'You are JARVIS, a friendly and casual AI assistant. Be warm, conversational, use simple language, and feel free to be playful and encouraging.',
  concise:  'You are JARVIS. Be extremely concise and direct. Give short, accurate answers. No fluff.',
  detailed: 'You are JARVIS. Give thorough, well-structured, detailed explanations. Use examples, bullet points and clear formatting when helpful.',
};

// ── STATE ───────────────────────────────────────────────────
const STATE = {
  apiKey: localStorage.getItem('jarvis_api_key') || DEFAULT_API_KEY,
  model: localStorage.getItem('jarvis_model') || 'gemini-2.0-flash',
  personality: localStorage.getItem('jarvis_personality') || 'jarvis',
  ttsEnabled: localStorage.getItem('jarvis_tts') !== 'false',
  voiceSpeed: parseFloat(localStorage.getItem('jarvis_voice_speed') || '1'),
  voicePitch: parseFloat(localStorage.getItem('jarvis_voice_pitch') || '1'),
  selectedVoice: localStorage.getItem('jarvis_voice') || '',
  conversationHistory: [],
  tasks: JSON.parse(localStorage.getItem('jarvis_tasks') || '[]'),
  notes: JSON.parse(localStorage.getItem('jarvis_notes') || '[]'),
  reminders: JSON.parse(localStorage.getItem('jarvis_reminders') || '[]'),
  activeNote: null,
  taskFilter: 'all',
  isListening: false,
  recognition: null,
  reminderTimers: [],
};

// ── DOM SHORTCUTS ────────────────────────────────────────────
const $ = id => document.getElementById(id);
const el = (tag, cls) => { const e = document.createElement(tag); if (cls) e.className = cls; return e; };

// ═══════════════════════════════════════════════════════════
//  BOOT SEQUENCE
// ═══════════════════════════════════════════════════════════
const BOOT_MSGS = [
  { text: '[ INIT ] Neural interface loading...', delay: 200 },
  { text: '[ INIT ] Gemini AI core connecting...', delay: 600 },
  { text: '[ INIT ] Voice recognition module ready...', delay: 1000 },
  { text: '[ INIT ] Loading user data...', delay: 1400 },
  { text: '[ INIT ] Sensor array calibrated...', delay: 1800 },
  { text: '[ OK ] All systems operational. Welcome back.', delay: 2300, ok: true },
];

function boot() {
  const log = $('boot-log');
  const bar = $('boot-bar');
  BOOT_MSGS.forEach((m, i) => {
    setTimeout(() => {
      const d = el('div');
      d.textContent = m.text;
      if (m.ok) d.classList.add('ok');
      log.appendChild(d);
      bar.style.width = ((i + 1) / BOOT_MSGS.length * 100) + '%';
    }, m.delay);
  });
  setTimeout(() => {
    $('boot-screen').classList.add('fade');
    setTimeout(() => {
      $('boot-screen').style.display = 'none';
      $('app').classList.remove('hidden');
      initAll();
    }, 700);
  }, 3000);
}

// ═══════════════════════════════════════════════════════════
//  INIT
// ═══════════════════════════════════════════════════════════
function initAll() {
  initClock();
  initNav();
  initChat();
  initTasks();
  initNotes();
  initReminders();
  initPC();
  initSettings();
  initVoice();
  initCmdBar();
  loadVoices();
  scheduleReminders();
  updateBadges();
  toast('info', '🤖 JARVIS Online', 'AI assistant ready. How can I help?');
}

// ── CLOCK ───────────────────────────────────────────────────
function initClock() {
  function tick() {
    const now = new Date();
    $('clock').textContent = now.toLocaleTimeString('en-US', { hour12: false });
  }
  tick();
  setInterval(tick, 1000);
}

// ── NAVIGATION ──────────────────────────────────────────────
function initNav() {
  document.querySelectorAll('.nav-btn').forEach(btn => {
    btn.addEventListener('click', () => switchPanel(btn.dataset.panel));
  });
  $('sidebar-toggle').addEventListener('click', () => {
    const sb = document.querySelector('.sidebar');
    if (window.innerWidth < 768) {
      sb.classList.toggle('mobile-open');
    } else {
      sb.classList.toggle('collapsed');
    }
  });
}

function switchPanel(name) {
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.panel === name));
  document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === `panel-${name}`));
  if (name === 'notes' && !STATE.activeNote && STATE.notes.length > 0) openNote(STATE.notes[0].id);
}

// ═══════════════════════════════════════════════════════════
//  GEMINI AI
// ═══════════════════════════════════════════════════════════
async function askGemini(userMessage, opts = {}) {
  const key = STATE.apiKey;
  if (!key) { toast('error', 'No API Key', 'Please add your Gemini API key in Settings.'); return null; }

  const systemInstruction = opts.system || PERSONALITIES[STATE.personality];
  const model = opts.model || STATE.model;

  // Build contents array
  const contents = [];
  if (!opts.fresh) {
    STATE.conversationHistory.forEach(h => contents.push(h));
  }
  contents.push({ role: 'user', parts: [{ text: userMessage }] });

  const body = {
    system_instruction: { parts: [{ text: systemInstruction }] },
    contents,
    generationConfig: { temperature: 0.85, maxOutputTokens: 2048 }
  };

  const url = `${GEMINI_BASE}/${model}:generateContent?key=${key}`;
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    const msg = err?.error?.message || `HTTP ${res.status}`;
    throw new Error(msg);
  }

  const data = await res.json();
  const text = data?.candidates?.[0]?.content?.parts?.[0]?.text || '';

  // Save to history
  if (!opts.fresh) {
    STATE.conversationHistory.push({ role: 'user', parts: [{ text: userMessage }] });
    STATE.conversationHistory.push({ role: 'model', parts: [{ text }] });
    if (STATE.conversationHistory.length > 40) STATE.conversationHistory.splice(0, 2);
  }

  return text;
}

// ═══════════════════════════════════════════════════════════
//  CHAT
// ═══════════════════════════════════════════════════════════
function initChat() {
  const input  = $('chat-input');
  const sendB  = $('send-btn');
  const attachB = $('attach-btn');

  sendB.addEventListener('click', () => sendChat());
  input.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
  });
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 150) + 'px';
  });

  // Quick actions
  document.querySelectorAll('.qa-btn').forEach(btn => {
    btn.addEventListener('click', () => { input.value = btn.dataset.prompt; sendChat(); });
  });

  // Attach / paste modal
  attachB.addEventListener('click', () => $('paste-modal').classList.remove('hidden'));
  $('paste-close').addEventListener('click', () => $('paste-modal').classList.add('hidden'));
  $('paste-summarize').addEventListener('click', () => pasteAction('Summarize the following text concisely:\n\n'));
  $('paste-analyze').addEventListener('click', () => pasteAction('Extract the key points from this text as a numbered list:\n\n'));
  $('paste-rewrite').addEventListener('click', () => pasteAction('Rewrite this text to be clearer and more professional:\n\n'));
}

function pasteAction(prefix) {
  const text = $('paste-input').value.trim();
  if (!text) return;
  $('paste-modal').classList.add('hidden');
  switchPanel('chat');
  sendChat(prefix + text);
}

async function sendChat(override) {
  const input = $('chat-input');
  const text  = (override || input.value).trim();
  if (!text) return;
  if (!override) { input.value = ''; input.style.height = 'auto'; }

  // Welcome card gone
  const wc = document.querySelector('.welcome-card');
  if (wc) wc.remove();

  // PC commands intercept
  if (handlePCCommand(text)) return;

  appendUserMsg(text);
  const typingEl = appendTyping();

  try {
    const reply = await askGemini(text);
    typingEl.remove();
    if (reply) {
      appendJarvisMsg(reply);
      if (STATE.ttsEnabled) speak(reply);
    }
  } catch (err) {
    typingEl.remove();
    appendJarvisMsg(`⚠️ I encountered an error: **${err.message}**\n\nPlease check your API key in Settings.`);
    toast('error', 'AI Error', err.message);
  }
}

function handlePCCommand(text) {
  const lower = text.toLowerCase();
  if (lower.startsWith('open ')) {
    const site = text.slice(5).trim();
    const urls = { youtube: 'https://youtube.com', google: 'https://google.com', github: 'https://github.com', gmail: 'https://gmail.com', maps: 'https://maps.google.com', twitter: 'https://twitter.com', spotify: 'https://spotify.com' };
    const found = Object.entries(urls).find(([k]) => lower.includes(k));
    if (found) { window.open(found[1], '_blank'); appendUserMsg(text); appendJarvisMsg(`Opening **${found[0]}** for you.`); return true; }
    if (site.startsWith('http')) { window.open(site, '_blank'); appendUserMsg(text); appendJarvisMsg(`Opening **${site}**.`); return true; }
  }
  if (lower.startsWith('search ') || lower.startsWith('search for ')) {
    const q = text.replace(/^search (for )?/i, '').trim();
    window.open(`https://google.com/search?q=${encodeURIComponent(q)}`, '_blank');
    appendUserMsg(text); appendJarvisMsg(`Searching Google for **"${q}"**.`); return true;
  }
  if (lower.includes('remind me in')) {
    const m = text.match(/remind me in (\d+)\s*(min|minute|hour|sec)/i);
    if (m) {
      const amt = parseInt(m[1]);
      const unit = m[2].toLowerCase();
      const ms = unit.startsWith('h') ? amt * 3600000 : unit.startsWith('s') ? amt * 1000 : amt * 60000;
      const label = text.replace(/remind me in .*/i, '').trim() || `Reminder in ${amt} ${unit}(s)`;
      addReminder(label || 'JARVIS Reminder', new Date(Date.now() + ms).toISOString());
      appendUserMsg(text);
      appendJarvisMsg(`Reminder set for **${amt} ${unit}(s)** from now. I'll notify you when the time comes.`);
      return true;
    }
  }
  return false;
}

function appendUserMsg(text) {
  const wrap = el('div', 'chat-msg user');
  wrap.innerHTML = `
    <div class="msg-avatar">U</div>
    <div>
      <div class="msg-bubble">${escHTML(text)}</div>
      <div class="msg-time">${timeNow()}</div>
    </div>`;
  $('chat-messages').appendChild(wrap);
  scrollChat();
}

function appendJarvisMsg(text) {
  const wrap = el('div', 'chat-msg jarvis');
  const bubble = el('div', 'msg-bubble');
  bubble.innerHTML = markdownToHTML(text);
  const timeEl = el('div', 'msg-time'); timeEl.textContent = timeNow();
  const actions = el('div', 'msg-actions');
  const copyBtn = el('button', 'msg-action-btn'); copyBtn.textContent = '📋 Copy';
  copyBtn.onclick = () => { navigator.clipboard.writeText(text); toast('success', 'Copied', 'Response copied to clipboard.'); };
  const saveBtn = el('button', 'msg-action-btn'); saveBtn.textContent = '📝 Save Note';
  saveBtn.onclick = () => { addNote('JARVIS Response', text); toast('success', 'Saved', 'Response saved to Notes.'); };
  actions.append(copyBtn, saveBtn);
  wrap.innerHTML = `<div class="msg-avatar">J</div>`;
  const right = el('div');
  right.append(bubble, actions, timeEl);
  wrap.appendChild(right);
  $('chat-messages').appendChild(wrap);
  scrollChat();
  return wrap;
}

function appendTyping() {
  const wrap = el('div', 'chat-msg jarvis');
  wrap.innerHTML = `<div class="msg-avatar">J</div><div class="msg-bubble"><div class="typing-bubble"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div></div>`;
  $('chat-messages').appendChild(wrap);
  scrollChat();
  return wrap;
}

function scrollChat() { const c = $('chat-messages'); c.scrollTop = c.scrollHeight; }

// ── Markdown renderer ────────────────────────────────────────
function markdownToHTML(text) {
  return text
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^### (.+)$/gm, '<h4>$1</h4>')
    .replace(/^## (.+)$/gm, '<h3>$1</h3>')
    .replace(/^# (.+)$/gm, '<h2>$1</h2>')
    .replace(/^\* (.+)$/gm, '<li>$1</li>')
    .replace(/^\d+\. (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
    .replace(/\n{2,}/g, '</p><p>')
    .replace(/\n/g, '<br>')
    .replace(/^(.+)$/, '<p>$1</p>');
}

function escHTML(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
function timeNow() { return new Date().toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit',hour12:false}); }

// ═══════════════════════════════════════════════════════════
//  COMMAND BAR
// ═══════════════════════════════════════════════════════════
function initCmdBar() {
  const bar = $('cmd-bar');
  bar.addEventListener('keydown', e => {
    if (e.key !== 'Enter') return;
    const text = bar.value.trim();
    if (!text) return;
    bar.value = '';
    // Route to chat
    switchPanel('chat');
    const wc = document.querySelector('.welcome-card');
    if (wc) wc.remove();
    if (!handlePCCommand(text)) {
      appendUserMsg(text);
      const t = appendTyping();
      askGemini(text).then(r => { t.remove(); if (r) { appendJarvisMsg(r); if (STATE.ttsEnabled) speak(r); } }).catch(err => { t.remove(); appendJarvisMsg(`⚠️ ${err.message}`); });
    }
  });
}

// ═══════════════════════════════════════════════════════════
//  TASKS
// ═══════════════════════════════════════════════════════════
function initTasks() {
  const input  = $('task-input');
  const addBtn = $('task-add-btn');
  function add() {
    const text = input.value.trim();
    if (!text) return;
    STATE.tasks.unshift({ id: Date.now(), text, priority: $('task-priority').value, done: false, created: new Date().toISOString() });
    saveTasks(); renderTasks(); input.value = '';
    toast('success', 'Task Added', text.slice(0, 40));
  }
  addBtn.addEventListener('click', add);
  input.addEventListener('keydown', e => { if (e.key === 'Enter') add(); });
  $('clear-done-tasks').addEventListener('click', () => {
    STATE.tasks = STATE.tasks.filter(t => !t.done);
    saveTasks(); renderTasks();
  });
  document.querySelectorAll('.filter-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active'); STATE.taskFilter = btn.dataset.filter; renderTasks();
    });
  });
  renderTasks();
}

function saveTasks() { localStorage.setItem('jarvis_tasks', JSON.stringify(STATE.tasks)); updateBadges(); }

function renderTasks() {
  const list = $('task-list');
  let tasks = STATE.tasks;
  if (STATE.taskFilter === 'pending') tasks = tasks.filter(t => !t.done);
  if (STATE.taskFilter === 'done')    tasks = tasks.filter(t => t.done);
  if (STATE.taskFilter === 'high')    tasks = tasks.filter(t => t.priority !== 'normal');
  list.innerHTML = '';
  if (!tasks.length) {
    list.innerHTML = '<div class="empty-state">No tasks yet. Add one above!</div>';
  } else {
    tasks.forEach(task => {
      const item = el('div', `task-item${task.done?' done':''}`);
      item.innerHTML = `
        <div class="task-check" data-id="${task.id}">${task.done?'✓':''}</div>
        <span class="task-text">${escHTML(task.text)}</span>
        <span class="task-priority priority-${task.priority}">${task.priority !== 'normal' ? task.priority.toUpperCase() : ''}</span>
        <button class="task-delete" data-id="${task.id}">✕</button>`;
      item.querySelector('.task-check').addEventListener('click', () => toggleTask(task.id));
      item.querySelector('.task-delete').addEventListener('click', () => deleteTask(task.id));
      list.appendChild(item);
    });
  }
  const done = STATE.tasks.filter(t => t.done).length;
  $('task-stats').textContent = `${STATE.tasks.length} total · ${done} completed · ${STATE.tasks.length - done} pending`;
}

function toggleTask(id) {
  const t = STATE.tasks.find(t => t.id === id);
  if (t) { t.done = !t.done; saveTasks(); renderTasks(); }
}
function deleteTask(id) {
  STATE.tasks = STATE.tasks.filter(t => t.id !== id);
  saveTasks(); renderTasks();
}

// ═══════════════════════════════════════════════════════════
//  NOTES
// ═══════════════════════════════════════════════════════════
function initNotes() {
  $('new-note-btn').addEventListener('click', () => {
    const note = { id: Date.now(), title: 'New Note', body: '', updated: new Date().toISOString() };
    STATE.notes.unshift(note);
    saveNotes(); renderNotesList(); openNote(note.id);
  });
  $('note-save-btn').addEventListener('click', saveCurrentNote);
  $('note-delete-btn').addEventListener('click', () => {
    if (!STATE.activeNote) return;
    STATE.notes = STATE.notes.filter(n => n.id !== STATE.activeNote);
    STATE.activeNote = null;
    saveNotes(); renderNotesList();
    $('note-title').value = ''; $('note-body').value = '';
    if (STATE.notes.length) openNote(STATE.notes[0].id);
  });
  $('note-copy-btn').addEventListener('click', () => {
    navigator.clipboard.writeText(`${$('note-title').value}\n\n${$('note-body').value}`);
    toast('success', 'Copied', 'Note copied to clipboard.');
  });
  $('note-ai-btn').addEventListener('click', async () => {
    const body = $('note-body').value.trim();
    if (!body) return;
    toast('info', 'AI Enhancing', 'Improving your note...');
    try {
      const result = await askGemini(`Improve and enhance this note, making it clearer and more structured. Keep the core content:\n\n${body}`, { fresh: true });
      if (result) { $('note-body').value = result; updateWordCount(); }
    } catch(e) { toast('error', 'Error', e.message); }
  });
  $('note-body').addEventListener('input', updateWordCount);
  $('note-title').addEventListener('input', () => {
    if (STATE.activeNote) {
      const n = STATE.notes.find(n => n.id === STATE.activeNote);
      if (n) { n.title = $('note-title').value; renderNotesList(); }
    }
  });
  renderNotesList();
  if (STATE.notes.length) openNote(STATE.notes[0].id);
}

function saveNotes() { localStorage.setItem('jarvis_notes', JSON.stringify(STATE.notes)); updateBadges(); }

function renderNotesList() {
  const list = $('notes-list');
  list.innerHTML = '';
  if (!STATE.notes.length) { list.innerHTML = '<div class="empty-state" style="padding:20px;font-size:12px">No notes. Create one!</div>'; return; }
  STATE.notes.forEach(n => {
    const card = el('div', `note-card${n.id === STATE.activeNote ? ' active' : ''}`);
    card.innerHTML = `<div class="note-card-title">${escHTML(n.title||'Untitled')}</div><div class="note-card-preview">${escHTML((n.body||'').slice(0,60))}</div><div class="note-card-date">${new Date(n.updated).toLocaleDateString()}</div>`;
    card.addEventListener('click', () => openNote(n.id));
    list.appendChild(card);
  });
}

function openNote(id) {
  STATE.activeNote = id;
  const n = STATE.notes.find(n => n.id === id);
  if (!n) return;
  $('note-title').value = n.title || '';
  $('note-body').value  = n.body  || '';
  updateWordCount();
  renderNotesList();
}

function saveCurrentNote() {
  if (!STATE.activeNote) return;
  const n = STATE.notes.find(n => n.id === STATE.activeNote);
  if (!n) return;
  n.title   = $('note-title').value;
  n.body    = $('note-body').value;
  n.updated = new Date().toISOString();
  saveNotes(); renderNotesList();
  toast('success', 'Note Saved', n.title || 'Untitled');
}

function addNote(title, body) {
  const note = { id: Date.now(), title, body, updated: new Date().toISOString() };
  STATE.notes.unshift(note);
  saveNotes(); renderNotesList();
}

function updateWordCount() {
  const w = ($('note-body').value.trim().match(/\S+/g) || []).length;
  $('note-word-count').textContent = `${w} word${w !== 1 ? 's' : ''}`;
}

// ═══════════════════════════════════════════════════════════
//  REMINDERS
// ═══════════════════════════════════════════════════════════
function initReminders() {
  $('reminder-add-btn').addEventListener('click', () => {
    const text = $('reminder-text').value.trim();
    const time = $('reminder-time').value;
    if (!text || !time) { toast('warning', 'Missing Info', 'Enter both reminder text and time.'); return; }
    addReminder(text, new Date(time).toISOString());
    $('reminder-text').value = ''; $('reminder-time').value = '';
  });

  // Set default datetime to now + 15 min
  const dt = new Date(Date.now() + 15 * 60000);
  $('reminder-time').value = dt.toISOString().slice(0, 16);

  document.querySelectorAll('.qr-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const text = $('reminder-text').value.trim() || 'Quick Reminder';
      const mins = parseInt(btn.dataset.mins);
      addReminder(text, new Date(Date.now() + mins * 60000).toISOString());
      $('reminder-text').value = '';
    });
  });

  // Request notification permission
  if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();

  renderReminders();
}

function addReminder(text, isoTime) {
  STATE.reminders.push({ id: Date.now(), text, time: isoTime, fired: false });
  saveReminders(); renderReminders(); scheduleReminders();
  toast('success', 'Reminder Set', `"${text.slice(0,30)}" at ${new Date(isoTime).toLocaleTimeString()}`);
  updateBadges();
}

function saveReminders() { localStorage.setItem('jarvis_reminders', JSON.stringify(STATE.reminders)); }

function scheduleReminders() {
  STATE.reminderTimers.forEach(clearTimeout);
  STATE.reminderTimers = [];
  STATE.reminders.filter(r => !r.fired).forEach(r => {
    const ms = new Date(r.time) - Date.now();
    if (ms > 0) {
      const t = setTimeout(() => fireReminder(r.id), ms);
      STATE.reminderTimers.push(t);
    } else if (ms > -3000) {
      fireReminder(r.id);
    }
  });
}

function fireReminder(id) {
  const r = STATE.reminders.find(r => r.id === id);
  if (!r || r.fired) return;
  r.fired = true;
  saveReminders(); renderReminders();
  toast('warning', '🔔 Reminder!', r.text, 8000);
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification('J.A.R.V.I.S Reminder', { body: r.text, icon: '' });
  }
  speak(`Reminder: ${r.text}`);
}

function renderReminders() {
  const list = $('reminder-list');
  list.innerHTML = '';
  const sorted = [...STATE.reminders].sort((a, b) => new Date(a.time) - new Date(b.time));
  if (!sorted.length) { list.innerHTML = '<div class="empty-state">No reminders set.</div>'; return; }
  sorted.forEach(r => {
    const item = el('div', `reminder-item${r.fired ? ' fired' : ''}`);
    const timeLeft = new Date(r.time) - Date.now();
    const countdown = r.fired ? '✅ Fired' : timeLeft < 0 ? '⏰ Overdue' : formatDuration(timeLeft);
    item.innerHTML = `
      <div class="reminder-icon">${r.fired ? '✅' : '🔔'}</div>
      <div class="reminder-info">
        <div class="reminder-text-display">${escHTML(r.text)}</div>
        <div class="reminder-time-display">${new Date(r.time).toLocaleString()}</div>
      </div>
      <div class="reminder-countdown">${countdown}</div>
      <button class="reminder-delete" data-id="${r.id}">✕</button>`;
    item.querySelector('.reminder-delete').addEventListener('click', () => {
      STATE.reminders = STATE.reminders.filter(x => x.id !== r.id);
      saveReminders(); renderReminders(); updateBadges();
    });
    list.appendChild(item);
  });
}

function formatDuration(ms) {
  const s = Math.floor(ms / 1000);
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ${s % 60}s`;
  return `${Math.floor(m / 60)}h ${m % 60}m`;
}

// Update countdowns every second
setInterval(() => {
  if (document.querySelector('#panel-reminders.active')) renderReminders();
}, 5000);

// ═══════════════════════════════════════════════════════════
//  PC CONTROL
// ═══════════════════════════════════════════════════════════
function initPC() {
  document.querySelectorAll('.pc-btn[data-url]').forEach(btn => {
    btn.addEventListener('click', () => window.open(btn.dataset.url, '_blank'));
  });
  $('open-url-btn').addEventListener('click', () => {
    const url = $('custom-url').value.trim();
    if (!url) return;
    window.open(url.startsWith('http') ? url : 'https://' + url, '_blank');
  });
  $('search-btn').addEventListener('click', () => {
    const q = $('search-query').value.trim();
    if (!q) return;
    window.open($('search-engine').value + encodeURIComponent(q), '_blank');
  });
  $('search-query').addEventListener('keydown', e => { if (e.key === 'Enter') $('search-btn').click(); });
  $('custom-url').addEventListener('keydown', e => { if (e.key === 'Enter') $('open-url-btn').click(); });
  $('copy-clip-btn').addEventListener('click', () => {
    const text = $('clipboard-text').value;
    navigator.clipboard.writeText(text).then(() => toast('success', 'Copied', 'Text copied to clipboard.'));
  });
  $('paste-clip-btn').addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      $('clipboard-text').value = text;
      toast('success', 'Pasted', 'Clipboard content read.');
    } catch { toast('error', 'Permission Denied', 'Clipboard read requires user gesture.'); }
  });
  $('download-clip-btn').addEventListener('click', () => {
    const text = $('clipboard-text').value;
    const blob = new Blob([text], { type: 'text/plain' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `jarvis_note_${Date.now()}.txt`;
    a.click();
    toast('success', 'Downloaded', 'File saved.');
  });
  $('fullscreen-btn').addEventListener('click', () => {
    if (!document.fullscreenElement) document.documentElement.requestFullscreen();
    else document.exitFullscreen();
  });
  $('print-btn').addEventListener('click', () => window.print());
  $('dark-toggle-btn').addEventListener('click', () => {
    document.body.classList.toggle('light');
    toast('info', 'Theme', 'Theme toggled.');
  });
  $('screenshot-btn').addEventListener('click', async () => {
    try {
      const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
      const track = stream.getVideoTracks()[0];
      const imageCapture = new ImageCapture(track);
      const bitmap = await imageCapture.grabFrame();
      track.stop();
      const canvas = document.createElement('canvas');
      canvas.width = bitmap.width; canvas.height = bitmap.height;
      canvas.getContext('2d').drawImage(bitmap, 0, 0);
      const a = document.createElement('a');
      a.href = canvas.toDataURL('image/png');
      a.download = `screenshot_${Date.now()}.png`;
      a.click();
      toast('success', 'Screenshot', 'Saved as PNG.');
    } catch { toast('warning', 'Screenshot', 'Screenshot cancelled or not supported.'); }
  });
}

// ═══════════════════════════════════════════════════════════
//  SETTINGS
// ═══════════════════════════════════════════════════════════
function initSettings() {
  const keyInput = $('api-key-input');
  keyInput.value = STATE.apiKey;
  $('model-select').value = STATE.model;
  $('personality-select').value = STATE.personality;

  $('show-key-btn').addEventListener('click', () => {
    keyInput.type = keyInput.type === 'password' ? 'text' : 'password';
    $('show-key-btn').textContent = keyInput.type === 'password' ? 'Show' : 'Hide';
  });
  $('save-key-btn').addEventListener('click', () => {
    STATE.apiKey = keyInput.value.trim();
    localStorage.setItem('jarvis_api_key', STATE.apiKey);
    toast('success', 'Saved', 'API key saved.');
  });
  $('model-select').addEventListener('change', () => {
    STATE.model = $('model-select').value;
    localStorage.setItem('jarvis_model', STATE.model);
    toast('info', 'Model', `Switched to ${STATE.model}`);
  });
  $('personality-select').addEventListener('change', () => {
    STATE.personality = $('personality-select').value;
    localStorage.setItem('jarvis_personality', STATE.personality);
    toast('info', 'Personality', `JARVIS personality updated.`);
  });
  $('test-ai-btn').addEventListener('click', async () => {
    toast('info', 'Testing...', 'Connecting to Gemini AI...');
    try {
      const r = await askGemini('Reply only: "Connection successful."', { fresh: true });
      toast('success', 'AI Connected ✓', r || 'Connection successful.');
    } catch(e) { toast('error', 'AI Error', e.message); }
  });
  $('clear-chat-btn').addEventListener('click', () => {
    $('chat-messages').innerHTML = '';
    STATE.conversationHistory = [];
    toast('success', 'Cleared', 'Chat history cleared.');
  });
  $('reset-all-btn').addEventListener('click', () => {
    if (confirm('Reset ALL data? This cannot be undone.')) {
      localStorage.clear();
      location.reload();
    }
  });

  // Voice settings
  $('voice-speed').value = STATE.voiceSpeed;
  $('voice-speed-val').textContent = STATE.voiceSpeed + 'x';
  $('voice-speed').addEventListener('input', () => {
    STATE.voiceSpeed = parseFloat($('voice-speed').value);
    $('voice-speed-val').textContent = STATE.voiceSpeed.toFixed(1) + 'x';
    localStorage.setItem('jarvis_voice_speed', STATE.voiceSpeed);
  });
  $('voice-pitch').value = STATE.voicePitch;
  $('voice-pitch-val').textContent = STATE.voicePitch;
  $('voice-pitch').addEventListener('input', () => {
    STATE.voicePitch = parseFloat($('voice-pitch').value);
    $('voice-pitch-val').textContent = STATE.voicePitch.toFixed(1);
    localStorage.setItem('jarvis_voice_pitch', STATE.voicePitch);
  });

  // Accent colors
  document.querySelectorAll('.color-swatch').forEach(sw => {
    sw.addEventListener('click', () => {
      document.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('active'));
      sw.classList.add('active');
      document.body.dataset.accent = sw.dataset.color;
      localStorage.setItem('jarvis_accent', sw.dataset.color);
    });
  });
  const savedAccent = localStorage.getItem('jarvis_accent') || 'cyan';
  document.body.dataset.accent = savedAccent;
  document.querySelectorAll('.color-swatch').forEach(sw => {
    sw.classList.toggle('active', sw.dataset.color === savedAccent);
  });
}

// ═══════════════════════════════════════════════════════════
//  VOICE
// ═══════════════════════════════════════════════════════════
function initVoice() {
  const ttsBtn = $('tts-toggle');
  const micBtn = $('mic-btn');
  const viStop = $('vi-stop');

  ttsBtn.classList.toggle('active', STATE.ttsEnabled);
  ttsBtn.addEventListener('click', () => {
    STATE.ttsEnabled = !STATE.ttsEnabled;
    ttsBtn.classList.toggle('active', STATE.ttsEnabled);
    localStorage.setItem('jarvis_tts', STATE.ttsEnabled);
    toast('info', 'Voice Output', STATE.ttsEnabled ? 'Voice output enabled.' : 'Voice output disabled.');
  });

  micBtn.addEventListener('click', () => {
    if (STATE.isListening) stopListening();
    else startListening();
  });
  viStop.addEventListener('click', stopListening);
}

function loadVoices() {
  function populate() {
    const voices = speechSynthesis.getVoices();
    const sel = $('voice-select');
    sel.innerHTML = '';
    voices.forEach((v, i) => {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = `${v.name} (${v.lang})`;
      sel.appendChild(opt);
    });
    sel.addEventListener('change', () => {
      STATE.selectedVoice = parseInt(sel.value);
      localStorage.setItem('jarvis_voice', STATE.selectedVoice);
    });
  }
  speechSynthesis.onvoiceschanged = populate;
  populate();
}

function speak(text) {
  if (!STATE.ttsEnabled) return;
  speechSynthesis.cancel();
  const clean = text.replace(/[*#`>_~\[\]()]/g, '').replace(/<[^>]+>/g, '').slice(0, 500);
  const utt = new SpeechSynthesisUtterance(clean);
  utt.rate  = STATE.voiceSpeed;
  utt.pitch = STATE.voicePitch;
  const voices = speechSynthesis.getVoices();
  if (voices[STATE.selectedVoice]) utt.voice = voices[STATE.selectedVoice];
  speechSynthesis.speak(utt);
}

function startListening() {
  if (!('webkitSpeechRecognition' in window || 'SpeechRecognition' in window)) {
    toast('error', 'Not Supported', 'Voice recognition requires Google Chrome.'); return;
  }
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  STATE.recognition = new SR();
  STATE.recognition.continuous = false;
  STATE.recognition.interimResults = false;
  STATE.recognition.lang = 'en-US';
  STATE.recognition.onresult = e => {
    const t = e.results[0][0].transcript;
    $('chat-input').value = t;
    stopListening();
    sendChat();
  };
  STATE.recognition.onerror = () => stopListening();
  STATE.recognition.onend   = () => { if (STATE.isListening) stopListening(); };
  STATE.recognition.start();
  STATE.isListening = true;
  $('mic-btn').classList.add('listening');
  $('voice-indicator').classList.remove('hidden');
  $('voice-status-dot').classList.add('listening');
  $('voice-status-text').textContent = 'LISTENING';
}

function stopListening() {
  if (STATE.recognition) { STATE.recognition.stop(); STATE.recognition = null; }
  STATE.isListening = false;
  $('mic-btn').classList.remove('listening');
  $('voice-indicator').classList.add('hidden');
  $('voice-status-dot').classList.remove('listening');
  $('voice-status-text').textContent = 'VOICE OFF';
}

// ═══════════════════════════════════════════════════════════
//  BADGES & UTILS
// ═══════════════════════════════════════════════════════════
function updateBadges() {
  const pending = STATE.tasks.filter(t => !t.done).length;
  const badge = $('badge-tasks');
  if (pending > 0) { badge.textContent = pending; badge.classList.add('show'); }
  else badge.classList.remove('show');

  const upcoming = STATE.reminders.filter(r => !r.fired).length;
  const rbadge = $('badge-reminders');
  if (upcoming > 0) { rbadge.textContent = upcoming; rbadge.classList.add('show'); }
  else rbadge.classList.remove('show');
}

function toast(type, title, msg, duration = 4000) {
  const icons = { success: '✅', error: '❌', info: '💡', warning: '⚠️' };
  const t = el('div', `toast ${type}`);
  t.innerHTML = `<span class="toast-icon">${icons[type]||'ℹ️'}</span><div class="toast-body"><div class="toast-title">${title}</div><div class="toast-msg">${msg}</div></div><button class="toast-close">✕</button>`;
  t.querySelector('.toast-close').addEventListener('click', () => t.remove());
  $('toast-container').appendChild(t);
  setTimeout(() => t.remove(), duration);
}

// ═══════════════════════════════════════════════════════════
//  START
// ═══════════════════════════════════════════════════════════
document.addEventListener('DOMContentLoaded', boot);
