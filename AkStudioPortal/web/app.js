let apps = [];
const $ = (id) => document.getElementById(id);

function applyTheme(theme) {
  document.body.dataset.theme = theme;
  localStorage.setItem('akstudio.portal.theme', theme);
  $('themeToggleBtn').textContent = theme === 'dark' ? '白色模式' : '黑色模式';
}

function toggleTheme() {
  applyTheme(document.body.dataset.theme === 'dark' ? 'light' : 'dark');
}

function applySidebarCollapsed(collapsed) {
  document.querySelector('.layout').classList.toggle('sidebar-collapsed', collapsed);
  localStorage.setItem('akstudio.portal.sidebarCollapsed', collapsed ? '1' : '0');
  $('sidebarToggleBtn').textContent = collapsed ? '›' : '‹';
  $('sidebarToggleBtn').title = collapsed ? '展开侧栏' : '收起侧栏';
}

function toggleSidebar() {
  applySidebarCollapsed(!document.querySelector('.layout').classList.contains('sidebar-collapsed'));
}

function fullscreenFrame(tabId) {

  const frame = document.querySelector(`.tool-frame[data-tab="${tabId}"]`);
  if (!frame) return;
  const request = frame.requestFullscreen || frame.webkitRequestFullscreen || frame.msRequestFullscreen;
  if (request) request.call(frame);
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
      <button data-launch="${escapeHtml(app.id)}">打开 / 启动</button>
    `;
    card.querySelector('[data-launch]').onclick = () => launchApp(app.id);
    grid.appendChild(card);
  }
}

function setActiveNav(id) {
  document.querySelectorAll('.nav-item').forEach((item) => {
    item.classList.toggle('active', item.dataset.openApp === id || (id === 'home' && item.dataset.tab === 'home'));
  });
}

function showHome() {
  $('homeView').classList.add('active');
  document.querySelectorAll('.tool-frame').forEach((frame) => frame.classList.remove('active'));
  document.querySelectorAll('.tab').forEach((tab) => tab.classList.remove('active'));
  setActiveNav('home');
}

function openTab(app, url) {
  $('homeView').classList.remove('active');
  const id = `tab-${app.id}`;
  let tab = document.querySelector(`.tab[data-tab="${id}"]`);
  if (!tab) {
    tab = document.createElement('button');
    tab.className = 'tab';
    tab.dataset.tab = id;
    const fullscreenButton = app.id === 'lua-viewer' ? '<span class="tab-fullscreen" title="全屏 Lua Viewer">全屏</span>' : '';
    tab.innerHTML = `${escapeHtml(app.title)} ${fullscreenButton} <span class="tab-close">×</span>`;
    tab.onclick = () => activateTab(id, app.id);
    const fullscreen = tab.querySelector('.tab-fullscreen');
    if (fullscreen) {
      fullscreen.onclick = (event) => {
        event.stopPropagation();
        activateTab(id, app.id);
        fullscreenFrame(id);
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
  $('homeView').classList.remove('active');
  document.querySelectorAll('.tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.tab === tabId));
  document.querySelectorAll('.tool-frame').forEach((frame) => frame.classList.toggle('active', frame.dataset.tab === tabId));
  setActiveNav(appId);
}

async function launchApp(id) {
  const app = apps.find((item) => item.id === id);
  if (!app) return;
  try {
    const data = await api('/api/app/launch', { method: 'POST', body: JSON.stringify({ id }) });
    if (data.url) openTab(app, data.url);
    await loadApps();
  } catch (err) {
    alert(err.message);
  }
}

$('themeToggleBtn').onclick = toggleTheme;
applyTheme(localStorage.getItem('akstudio.portal.theme') || 'light');
$('sidebarToggleBtn').onclick = toggleSidebar;
applySidebarCollapsed(localStorage.getItem('akstudio.portal.sidebarCollapsed') === '1');
$('refreshAppsBtn').onclick = loadApps;

document.querySelectorAll('[data-open-app]').forEach((item) => {

  item.onclick = () => launchApp(item.dataset.openApp);
});
document.querySelector('[data-tab="home"]').onclick = showHome;

loadApps();
