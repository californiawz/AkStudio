let apps = [];
let notes = [];
let currentNoteContent = '';
let activeTabId = null;
let activeAppId = 'home';
const $ = (id) => document.getElementById(id);





function applySidebarCollapsed(collapsed) {
  document.querySelector('.layout').classList.toggle('sidebar-collapsed', collapsed);
  localStorage.setItem('akstudio.portal.sidebarCollapsed', collapsed ? '1' : '0');
  $('sidebarToggleBtn').textContent = collapsed ? '›' : '‹';
  $('sidebarToggleBtn').title = collapsed ? '展开侧栏' : '收起侧栏';
}

function toggleSidebar() {
  applySidebarCollapsed(!document.querySelector('.layout').classList.contains('sidebar-collapsed'));
}

function getApp(id) {
  return apps.find((item) => item.id === id);
}

function isWebApp(id) {
  return getApp(id)?.kind === 'web';
}

function updateFullscreenButton() {
  const button = $('fullscreenActiveBtn');
  button.classList.toggle('hidden', !activeTabId || !isWebApp(activeAppId) || document.body.classList.contains('tool-fullscreen'));
}

function enterToolFullscreen(tabId = activeTabId) {
  if (!tabId) return;
  const appId = tabId.replace(/^tab-/, '');
  if (!isWebApp(appId)) return;
  activateTab(tabId, appId);
  document.body.classList.add('tool-fullscreen');
  updateFullscreenButton();
}

function exitToolFullscreen() {
  document.body.classList.remove('tool-fullscreen');
  updateFullscreenButton();
}

async function api(url, options = {}) {


  const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  const data = await response.json();
  if (!data.ok) throw new Error(data.error || data.message || '操作失败');
  return data;
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[c]));
}

async function loadApps() {
  const data = await api('/api/apps');
  apps = data.apps || [];
  renderApps();
}

function renderApps() {
  const grid = $('appGrid');
  grid.innerHTML = '';
  for (const app of apps) {
    const state = app.running ? '运行中' : (app.exists ? '可启动' : '未拉取');
    const stateClass = app.running ? 'running' : (app.exists ? 'ready' : 'missing');
    const card = document.createElement('article');
    card.className = 'app-card';
    const launchText = app.kind === 'notes' ? '查看笔记' : '打开 / 启动';
    card.innerHTML = `
      <div class="app-head">
        <div>
          <div class="app-title">${escapeHtml(app.title)}</div>
          <div class="app-module">${escapeHtml(app.name)}</div>
        </div>
        <span class="badge ${stateClass}">${state}</span>
      </div>
      <p>${escapeHtml(app.description)}</p>
      <code>${escapeHtml(app.path)}</code>
      <div class="app-actions">
        <button data-launch="${escapeHtml(app.id)}">${launchText}</button>
        ${app.kind === 'web' ? `<button data-launch-fullscreen="${escapeHtml(app.id)}">全屏</button>` : ''}

      </div>
    `;
    card.querySelector('[data-launch]').onclick = () => launchApp(app.id);
    const fullscreenLaunch = card.querySelector('[data-launch-fullscreen]');
    if (fullscreenLaunch) fullscreenLaunch.onclick = () => launchApp(app.id, true);

    grid.appendChild(card);
  }
}

function setActiveNav(id) {
  document.querySelectorAll('.nav-item').forEach((item) => {
    item.classList.toggle('active', item.dataset.openApp === id || (id === 'home' && item.dataset.tab === 'home'));
  });
}

function setWorkspaceVisible(visible) {
  document.querySelector('.workspace').classList.toggle('hidden', !visible);
}

function showHome() {
  exitToolFullscreen();
  activeTabId = null;
  activeAppId = 'home';
  $('homeView').classList.add('active');
  $('notesView').classList.remove('active');
  setWorkspaceVisible(false);
  document.querySelectorAll('.tool-frame').forEach((frame) => frame.classList.remove('active'));
  document.querySelectorAll('.tab').forEach((tab) => tab.classList.remove('active'));
  setActiveNav('home');
  updateFullscreenButton();
}

async function showNotes() {
  exitToolFullscreen();
  activeTabId = null;
  activeAppId = 'obsidian';
  $('homeView').classList.remove('active');
  $('notesView').classList.add('active');
  setWorkspaceVisible(false);
  document.querySelectorAll('.tool-frame').forEach((frame) => frame.classList.remove('active'));
  document.querySelectorAll('.tab').forEach((tab) => tab.classList.remove('active'));
  setActiveNav('obsidian');
  updateFullscreenButton();
  await loadNotes();
}

async function loadNotes() {
  const data = await api('/api/notes');
  notes = data.notes || [];
  $('notesCount').textContent = `${notes.length} 篇`;
  renderNotes();
  if (notes.length && !$('noteContent').dataset.path) {
    openNote(notes[0].path);
  }
}

function renderNotes() {
  const keyword = $('notesSearch').value.trim().toLowerCase();
  const list = $('notesList');
  const filtered = notes.filter((note) => `${note.name} ${note.folder} ${note.path}`.toLowerCase().includes(keyword));
  list.innerHTML = '';
  if (!filtered.length) {
    list.innerHTML = '<div class="notes-empty">没有匹配的笔记</div>';
    return;
  }
  for (const note of filtered) {
    const item = document.createElement('button');
    item.className = `note-item ${$('noteContent').dataset.path === note.path ? 'active' : ''}`;
    item.innerHTML = `
      <span>${escapeHtml(note.name)}</span>
      <small>${escapeHtml(note.folder || '根目录')}</small>
    `;
    item.onclick = () => openNote(note.path);
    list.appendChild(item);
  }
}

function setNoteEditing(editing) {
  const hasNote = Boolean($('noteContent').dataset.path);
  $('noteContent').readOnly = !editing;
  $('noteContent').classList.toggle('editing', editing);
  $('noteEditBtn').classList.toggle('hidden', editing || !hasNote);
  $('noteSaveBtn').classList.toggle('hidden', !editing || !hasNote);
  $('noteCancelBtn').classList.toggle('hidden', !editing || !hasNote);
}

async function openNote(path) {
  if (!$('noteContent').readOnly && $('noteContent').value !== currentNoteContent && !confirm('当前笔记有未保存修改，确定切换？')) return;
  const data = await api(`/api/note?path=${encodeURIComponent(path)}`);
  $('noteTitle').textContent = data.name || path;
  $('notePath').textContent = data.path || path;
  $('noteContent').value = data.content || '';
  $('noteContent').dataset.path = data.path || path;
  currentNoteContent = data.content || '';
  setNoteEditing(false);
  renderNotes();
}

async function saveCurrentNote() {
  const path = $('noteContent').dataset.path;
  if (!path) return;
  const data = await api('/api/note/save', {
    method: 'POST',
    body: JSON.stringify({ path, content: $('noteContent').value }),
  });
  currentNoteContent = $('noteContent').value;
  $('notePath').textContent = `${data.path} · 已保存`;
  setNoteEditing(false);
  await loadNotes();
}

function cancelNoteEdit() {
  $('noteContent').value = currentNoteContent;
  setNoteEditing(false);
}


function openTab(app, url) {
  $('homeView').classList.remove('active');
  $('notesView').classList.remove('active');
  setWorkspaceVisible(true);
  const id = `tab-${app.id}`;
  let tab = document.querySelector(`.tab[data-tab="${id}"]`);
  if (!tab) {
    tab = document.createElement('button');
    tab.className = 'tab';
    tab.dataset.tab = id;
    const fullscreenButton = app.kind === 'web' ? '<span class="tab-fullscreen" title="全屏">全屏</span>' : '';


    tab.innerHTML = `${escapeHtml(app.title)} ${fullscreenButton} <span class="tab-close">×</span>`;

    tab.onclick = () => activateTab(id, app.id);
    const fullscreen = tab.querySelector('.tab-fullscreen');
    if (fullscreen) {
      fullscreen.onclick = (event) => {
        event.stopPropagation();
        enterToolFullscreen(id);
      };

    }
    tab.querySelector('.tab-close').onclick = (event) => {
      event.stopPropagation();
      tab.remove();
      document.querySelector(`.tool-frame[data-tab="${id}"]`)?.remove();
      showHome();
    };
    $('tabBar').appendChild(tab);

  }

  let frame = document.querySelector(`.tool-frame[data-tab="${id}"]`);

  if (!frame) {
    frame = document.createElement('iframe');
    frame.className = 'tool-frame';
    frame.dataset.tab = id;
    frame.allow = 'fullscreen';
    frame.src = url;
    $('frameHost').appendChild(frame);

  } else if (frame.src !== url) {
    frame.src = url;
  }


  activateTab(id, app.id);
}

function activateTab(tabId, appId) {
  setWorkspaceVisible(true);
  activeTabId = tabId;
  activeAppId = appId;
  $('homeView').classList.remove('active');
  document.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.tab === tabId));
  document.querySelectorAll('.tool-frame').forEach((frame) => frame.classList.toggle('active', frame.dataset.tab === tabId));
  setActiveNav(appId);
  updateFullscreenButton();
}

async function launchApp(id, fullscreen = false) {

  const app = apps.find((item) => item.id === id);
  if (!app) return;
  if (app.kind === 'notes') {
    await showNotes();
    return;
  }
  try {
    const data = await api('/api/app/launch', { method: 'POST', body: JSON.stringify({ id }) });
    if (data.url) openTab(app, data.url);
    if (fullscreen && app.kind === 'web') enterToolFullscreen(`tab-${id}`);

    await loadApps();

  } catch (err) {
    alert(err.message);
  }
}

$('fullscreenActiveBtn').onclick = () => enterToolFullscreen(activeTabId);
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') exitToolFullscreen();
});


$('sidebarToggleBtn').onclick = toggleSidebar;
applySidebarCollapsed(localStorage.getItem('akstudio.portal.sidebarCollapsed') === '1');
$('refreshAppsBtn').onclick = loadApps;
$('notesSearch').oninput = renderNotes;
$('noteEditBtn').onclick = () => setNoteEditing(true);
$('noteSaveBtn').onclick = saveCurrentNote;
$('noteCancelBtn').onclick = cancelNoteEdit;

document.querySelectorAll('[data-open-app]').forEach((item) => {

  item.onclick = () => launchApp(item.dataset.openApp);
});
document.querySelector('[data-tab="home"]').onclick = showHome;

loadApps();
