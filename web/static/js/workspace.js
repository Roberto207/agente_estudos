(function () {
  const root = document.getElementById("workspace");
  const spaceId = root.dataset.spaceId;
  const contentArea = document.getElementById("content-area");
  const fileTree = document.getElementById("file-tree");

  async function openFile(path) {
    contentArea.innerHTML = '<div class="text-muted text-sm">Carregando...</div>';
    try {
      const data = await EstudAI.api.get(
        `/api/spaces/${spaceId}/file?path=${encodeURIComponent(path)}`
      );
      if (data.html) {
        contentArea.innerHTML = `<article class="markdown-body max-w-3xl">${data.html}</article>`;
        bindWikilinks();
      } else {
        contentArea.innerHTML = `<pre class="text-sm text-secondary whitespace-pre-wrap">${escapeHtml(data.raw)}</pre>`;
      }
      highlightActiveFile(path);
    } catch (err) {
      contentArea.innerHTML = `<div class="text-danger text-sm">Erro ao abrir arquivo: ${err.message}</div>`;
    }
  }

  function highlightActiveFile(path) {
    fileTree.querySelectorAll(".file-link").forEach((btn) => {
      btn.classList.toggle("text-accent", btn.dataset.path === path);
    });
  }

  function bindWikilinks() {
    contentArea.querySelectorAll("a.wikilink").forEach((a) => {
      a.addEventListener("click", (e) => {
        e.preventDefault();
        const target = a.dataset.wikilink;
        const match = fileTree.querySelector(
          `.file-link[data-path$="${target}.md"], .file-link[data-path$="/${target}.md"]`
        );
        if (match) openFile(match.dataset.path);
      });
    });
  }

  function escapeHtml(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function renderTreeHtml(nodes) {
    const items = nodes.map((node) => {
      if (node.type === "dir") {
        return `<li><details class="tree-node" open>
          <summary class="text-secondary text-sm py-1 px-1 rounded hover:bg-surface2 flex items-center gap-1.5">
            <span class="text-muted">📁</span> ${escapeHtml(node.name)}
          </summary>
          <div class="ml-3 border-l border-edge pl-1">${renderTreeHtml(node.children)}</div>
        </details></li>`;
      }
      return `<li><button type="button" data-path="${escapeHtml(node.path)}"
        class="file-link w-full text-left text-sm py-1 px-2 rounded hover:bg-surface2 hover:text-primary text-secondary truncate block">
        ${escapeHtml(node.name)}
      </button></li>`;
    });
    return `<ul class="pl-2">${items.join("")}</ul>`;
  }

  async function refreshTree() {
    const { tree } = await EstudAI.api.get(`/api/spaces/${spaceId}/tree`);
    fileTree.innerHTML = renderTreeHtml(tree);
  }
  window.EstudAI.refreshTree = refreshTree;

  fileTree.addEventListener("click", (e) => {
    const btn = e.target.closest(".file-link");
    if (btn) openFile(btn.dataset.path);
  });

  // Abas do painel direito
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.dataset.active = "false");
      btn.dataset.active = "true";
      const tab = btn.dataset.tab;
      document.querySelectorAll(".tab-panel").forEach((p) => {
        p.classList.toggle("hidden", p.dataset.tab !== tab);
      });
    });
  });
})();
