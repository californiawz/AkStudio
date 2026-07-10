let allNodes = [];
let flatNodes = [];
let selected = null;
let filter = 'all';
let collapsedPaths = new Set();


const $ = (id) => document.getElementById(id);

async function api(url, options = {}) {
  const res = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await res.json();
  if (!data.ok) throw new Error(data.error || data.output || '操作失败');
  return data;
}

function flatten(nodes, depth = 0, parent = null) {
  return nodes.flatMap((node) => {
    const item = { ...node, depth, parent };
    return [item, ...flatten(node.children || [], depth + 1, item)];
  });
}

function matchNode(node) {
  const q = $('searchInput').value.trim().toLowerCase();
  const text = `${node.name} ${node.path} ${node.url}`.toLowerCase();
  const filterOk = filter === 'all'
    || node.category === filter
    || (filter === 'modules' && ['gitmodules', 'external', 'submodule'].includes(node.category));

  const searchOk = !q || text.includes(q);
  return filterOk && searchOk;
}

function isAhead(node) {
  return Boolean(node.status?.aheadBehind?.includes('ahead'));
}

function statusClass(node) {
  if (!node.status) return 'missing';
  if (node.status.dirty) return 'dirty';
  if (isAhead(node)) return 'ahead';
  return 'clean';
}

function statusText(node) {
  if (!node.status) return '未检测到 Git';
  if (isAhead(node) && !node.status.dirty) return `待推送，${node.status.aheadBehind}`;
  return node.status.summary || (node.status.dirty ? '有变更' : '干净');
}


function hasVisibleMatch(node) {
  return matchNode(node) || Boolean(node.children?.some((child) => hasVisibleMatch(child)));
}

function visibleNodes(nodes, depth = 0, parent = null) {
  const q = $('searchInput').value.trim();
  const isFiltered = Boolean(q || filter !== 'all');
  const result = [];

  for (const node of nodes) {
    const item = { ...node, depth, parent };
    const hasChildren = Boolean(node.children?.length);
    const selfMatches = matchNode(item);
    const childMatches = hasChildren && node.children.some((child) => hasVisibleMatch(child));

    if (!isFiltered || selfMatches || childMatches) {
      result.push({ ...item, ancestorOnly: isFiltered && !selfMatches && childMatches });
    }

    if (hasChildren && (isFiltered || !collapsedPaths.has(node.path)) && (!isFiltered || selfMatches || childMatches)) {
      result.push(...visibleNodes(node.children, depth + 1, item));
    }
  }

  return result;
}


function render() {
  const tree = $('repoTree');
  tree.innerHTML = '';
  flatNodes = flatten(allNodes);
  const visible = visibleNodes(allNodes);
  let dirty = 0;
  flatNodes.forEach((node) => { if (node.status?.dirty) dirty += 1; });
  $('repoCount').textContent = flatNodes.length;
  $('dirtyCount').textContent = dirty;

  if (!visible.length) {
    tree.innerHTML = '<div class="empty">没有匹配的仓库</div>';
    return;
  }

  for (const node of visible) {
    const hasChildren = Boolean(node.children?.length);
    const collapsed = collapsedPaths.has(node.path);
    const card = document.createElement('div');
    const parentName = node.parent?.name || '';
    const parentMeta = parentName ? `<span> · 父仓库: ${escapeHtml(parentName)}</span>` : '';
    card.className = `repo-card ${node.depth ? 'child' : ''} ${node.ancestorOnly ? 'ancestor' : ''} ${selected?.path === node.path ? 'active' : ''}`;
    card.style.paddingLeft = `${16 + node.depth * 20}px`;
    card.innerHTML = `

      <div class="repo-row">
        <div class="repo-name">
          <button class="tree-toggle ${hasChildren ? '' : 'empty'}" data-path="${escapeHtml(node.path)}" title="${collapsed ? '展开' : '折叠'}">${hasChildren ? (collapsed ? '›' : '⌄') : ''}</button>
          <span>${icon(node.category)}</span>${escapeHtml(node.name)}
        </div>
        <span class="status-pill ${statusClass(node)}">${escapeHtml(statusText(node))}</span>
      </div>
      <div class="repo-meta">
        <span class="badge">${escapeHtml(node.categoryLabel)}</span>
        ${parentMeta}
        <span>${escapeHtml(node.status?.branch || '-')}</span>
        <span> · ${escapeHtml(node.path)}</span>

      </div>
    `;
    card.onclick = () => selectNode(node);
    const toggle = card.querySelector('.tree-toggle');
    toggle.onclick = (event) => {
      event.stopPropagation();
      if (!hasChildren) return;
      if (collapsedPaths.has(node.path)) collapsedPaths.delete(node.path);
      else collapsedPaths.add(node.path);
      render();
    };
    tree.appendChild(card);
  }
}


function icon(category) {
  return ({ root: 'ROOT', public: 'PUB', project: 'GAME', submodule: 'SUB', linked: 'REPO', gitmodules: 'MOD', external: 'EXT' }[category] || 'REPO');
}



function escapeHtml(text) {
  return String(text ?? '').replace(/[&<>'"]/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[c]));
}

function selectNode(node) {
  selected = node;
  $('emptyState').classList.add('hidden');
  $('detail').classList.remove('hidden');
  $('detailName').textContent = node.name;
  $('detailType').textContent = node.categoryLabel;
  $('detailStatus').textContent = statusText(node);
  $('detailStatus').className = `status-pill ${statusClass(node)}`;
  $('detailPath').textContent = node.path;
  $('detailParent').textContent = node.parent?.name || '-';
  $('detailBranch').textContent = node.status?.branch || node.branchHint || '-';

  $('detailHead').textContent = node.status?.head || '-';
  $('detailUrl').textContent = node.url || node.status?.remote || '-';
  $('console').textContent = '就绪';
  render();
}

async function refresh() {
  $('repoTree').innerHTML = '<div class="empty">扫描中...</div>';
  try {
    const data = await api('/api/scan');
    allNodes = data.nodes;
    selected = selected ? flatten(allNodes).find((n) => n.path === selected.path) || null : null;
    render();
    if (selected) selectNode(selected);
  } catch (err) {
    $('repoTree').innerHTML = `<div class="empty">${escapeHtml(err.message)}</div>`;
  }
}

async function runAction(action, target = selected) {
  if (!target) return alert('请先选择仓库');
  if (action === 'init_all' && !confirm('首次拉取全部会包含 UnrealEngine，体积很大且需要 EpicGames 权限。确认继续？')) return;

  const body = { action, path: target.path };
  if (action === 'commit' || (action === 'commit_push' && target.status?.dirty)) {
    const message = prompt('提交信息', 'Update repository');
    if (!message) return;
    body.message = message;
  }

  if (target !== selected) {
    selectNode(target);
  }
  $('console').textContent = '执行中，请等待。首次拉取可能需要较长时间...';
  try {
    const data = await api('/api/action', { method: 'POST', body: JSON.stringify(body) });
    $('console').textContent = data.output || '完成';
    if (action !== 'open_folder') {
      await refresh();
    }
  } catch (err) {

    $('console').textContent = err.message;
  }
}

function rootNode() {
  return allNodes[0] || null;
}


function openPathDialog(key, title) {
  $('pathDialogTitle').textContent = title;
  $('pathInput').value = '';
  $('pathDialog').showModal();
  $('pathConfirm').onclick = async (event) => {
    event.preventDefault();
    const path = $('pathInput').value.trim();
    if (!path) return;
    try {
      await api('/api/config/path', { method: 'POST', body: JSON.stringify({ key, path }) });
      $('pathDialog').close();
      await refresh();
    } catch (err) { alert(err.message); }
  };
}

function openSubmoduleDialog() {
  if (!selected) return alert('请先选择父仓库');
  $('subParent').value = selected.path;
  $('subName').value = '';
  $('subPath').value = '';
  $('subUrl').value = '';
  $('subBranch').value = 'main';
  $('submoduleDialog').showModal();
  $('subConfirm').onclick = async (event) => {
    event.preventDefault();
    const payload = {
      parentPath: selected.path,
      name: $('subName').value.trim(),
      relPath: $('subPath').value.trim(),
      url: $('subUrl').value.trim(),
      branch: $('subBranch').value.trim() || 'main',
    };
    try {
      const data = await api('/api/submodule', { method: 'POST', body: JSON.stringify(payload) });
      $('submoduleDialog').close();
      $('console').textContent = data.output || '已添加关联';
      await refresh();
    } catch (err) { alert(err.message); }
  };
}

$('refreshBtn').onclick = refresh;
$('initRecommendedBtn').onclick = () => runAction('init_recommended', rootNode());
$('initAllBtn').onclick = () => runAction('init_all', rootNode());
$('addPublicBtn').onclick = () => openPathDialog('public_repos', '新增公共仓库');

$('addProjectBtn').onclick = () => openPathDialog('project_repos', '新增项目仓库');
$('addSubmoduleBtn').onclick = openSubmoduleDialog;
$('searchInput').oninput = render;
$('expandAllBtn').onclick = () => {
  collapsedPaths.clear();
  render();
};
$('collapseAllBtn').onclick = () => {
  collapsedPaths = new Set(flatten(allNodes).filter((node) => node.children?.length).map((node) => node.path));
  render();
};

document.querySelectorAll('.nav').forEach((btn) => {
  btn.onclick = () => {
    document.querySelectorAll('.nav').forEach((item) => item.classList.remove('active'));
    btn.classList.add('active');
    filter = btn.dataset.filter;
    render();
  };
});
document.querySelectorAll('[data-action]').forEach((btn) => {
  btn.onclick = () => runAction(btn.dataset.action);
});

refresh();
