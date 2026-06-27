(function () {
  const root = document.getElementById("workspace");
  const spaceId = root.dataset.spaceId;
  const fileTree = document.getElementById("file-tree");
  const contentBody = document.getElementById("content-body");
  const fileActions = document.getElementById("file-actions");

  let currentFilePath = null;
  let currentFileRaw = null;

  // ── Leitura de arquivo ────────────────────────────────────────────────────────

  async function openFile(path) {
    contentBody.innerHTML = '<div class="text-muted text-sm">Carregando...</div>';
    try {
      const data = await EstudAI.api.get(
        `/api/spaces/${spaceId}/file?path=${encodeURIComponent(path)}`
      );
      currentFilePath = path;
      currentFileRaw = data.raw;
      renderFileContent(data.raw, data.html);
      fileActions.classList.remove("hidden");
      setViewMode();
      highlightActiveFile(path);
    } catch (err) {
      contentBody.innerHTML = `<div class="text-danger text-sm">Erro ao abrir arquivo: ${err.message}</div>`;
    }
  }

  function renderFileContent(raw, html) {
    if (html) {
      contentBody.innerHTML = `<article class="markdown-body max-w-3xl">${html}</article>`;
      bindWikilinks();
    } else if (currentFilePath && currentFilePath.endsWith('.html')) {
      const src = `/api/spaces/${spaceId}/raw-file?path=${encodeURIComponent(currentFilePath)}`;
      contentBody.innerHTML = `<iframe src="${src}" class="w-full border-0 rounded" style="height:75vh"></iframe>`;
    } else {
      contentBody.innerHTML = `<pre class="text-sm text-secondary whitespace-pre-wrap">${escapeHtml(raw)}</pre>`;
    }
  }

  // ── Modo edição ───────────────────────────────────────────────────────────────

  function setViewMode() {
    document.getElementById("btn-edit").classList.remove("hidden");
    document.getElementById("btn-save").classList.add("hidden");
    document.getElementById("btn-cancel-edit").classList.add("hidden");
  }

  function setEditMode() {
    document.getElementById("btn-edit").classList.add("hidden");
    document.getElementById("btn-save").classList.remove("hidden");
    document.getElementById("btn-cancel-edit").classList.remove("hidden");
    contentBody.innerHTML = `<textarea id="edit-textarea"
      class="w-full bg-surface2 border border-edge rounded-lg p-3 text-sm font-mono outline-none focus:border-accent resize-y"
      style="min-height:70vh">${escapeHtml(currentFileRaw)}</textarea>`;
  }

  document.getElementById("btn-edit").addEventListener("click", setEditMode);

  document.getElementById("btn-cancel-edit").addEventListener("click", async () => {
    setViewMode();
    const data = await EstudAI.api.get(
      `/api/spaces/${spaceId}/file?path=${encodeURIComponent(currentFilePath)}`
    ).catch(() => ({ raw: currentFileRaw, html: null }));
    renderFileContent(data.raw, data.html);
  });

  document.getElementById("btn-save").addEventListener("click", async () => {
    const textarea = document.getElementById("edit-textarea");
    if (!textarea) return;
    const content = textarea.value;
    try {
      await EstudAI.api.put(`/api/spaces/${spaceId}/file`, { path: currentFilePath, content });
      currentFileRaw = content;
      const data = await EstudAI.api.get(
        `/api/spaces/${spaceId}/file?path=${encodeURIComponent(currentFilePath)}`
      );
      setViewMode();
      renderFileContent(data.raw, data.html);
    } catch (err) {
      alert("Erro ao salvar: " + err.message);
    }
  });

  document.getElementById("btn-delete-file").addEventListener("click", async () => {
    if (!confirm(`Apagar "${currentFilePath}"? Esta ação não pode ser desfeita.`)) return;
    try {
      await EstudAI.api.delete(
        `/api/spaces/${spaceId}/file?path=${encodeURIComponent(currentFilePath)}`
      );
      currentFilePath = null;
      currentFileRaw = null;
      fileActions.classList.add("hidden");
      contentBody.innerHTML = '<div class="text-muted text-sm">Arquivo apagado.</div>';
      await refreshTree();
    } catch (err) {
      alert("Erro ao apagar: " + err.message);
    }
  });

  // ── Nova pasta ────────────────────────────────────────────────────────────────

  document.getElementById("btn-new-folder").addEventListener("click", () => {
    document.getElementById("new-folder-form").classList.remove("hidden");
    document.getElementById("new-file-form").classList.add("hidden");
    document.getElementById("new-folder-name").focus();
  });

  document.getElementById("new-folder-cancel").addEventListener("click", () => {
    document.getElementById("new-folder-form").classList.add("hidden");
    document.getElementById("new-folder-name").value = "";
  });

  document.getElementById("new-folder-confirm").addEventListener("click", async () => {
    const name = document.getElementById("new-folder-name").value.trim();
    if (!name) return;
    try {
      await EstudAI.api.post(`/api/spaces/${spaceId}/folders`, { path: name });
      document.getElementById("new-folder-form").classList.add("hidden");
      document.getElementById("new-folder-name").value = "";
      await refreshTree();
    } catch (err) {
      alert("Erro ao criar pasta: " + err.message);
    }
  });

  document.getElementById("new-folder-name").addEventListener("keydown", (e) => {
    if (e.key === "Enter") document.getElementById("new-folder-confirm").click();
    if (e.key === "Escape") document.getElementById("new-folder-cancel").click();
  });

  // ── Novo arquivo ──────────────────────────────────────────────────────────────

  document.getElementById("btn-new-file").addEventListener("click", () => {
    document.getElementById("new-file-form").classList.remove("hidden");
    document.getElementById("new-folder-form").classList.add("hidden");
    document.getElementById("new-file-name").focus();
  });

  document.getElementById("new-file-cancel").addEventListener("click", () => {
    document.getElementById("new-file-form").classList.add("hidden");
    document.getElementById("new-file-name").value = "";
  });

  document.getElementById("new-file-confirm").addEventListener("click", async () => {
    let name = document.getElementById("new-file-name").value.trim();
    if (!name) return;
    if (!name.includes(".")) name += ".md";
    try {
      await EstudAI.api.post(`/api/spaces/${spaceId}/files`, { path: name });
      document.getElementById("new-file-form").classList.add("hidden");
      document.getElementById("new-file-name").value = "";
      await refreshTree();
      await openFile(name);
    } catch (err) {
      alert("Erro ao criar arquivo: " + err.message);
    }
  });

  document.getElementById("new-file-name").addEventListener("keydown", (e) => {
    if (e.key === "Enter") document.getElementById("new-file-confirm").click();
    if (e.key === "Escape") document.getElementById("new-file-cancel").click();
  });

  // ── Árvore de arquivos ────────────────────────────────────────────────────────

  function highlightActiveFile(path) {
    fileTree.querySelectorAll(".file-link").forEach((btn) => {
      btn.classList.toggle("text-accent", btn.dataset.path === path);
    });
  }

  function bindWikilinks() {
    contentBody.querySelectorAll("a.wikilink").forEach((a) => {
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
    return String(s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderTreeHtml(nodes) {
    const items = nodes.map((node) => {
      if (node.type === "dir") {
        return `<li>
          <details class="tree-node group/dir" open>
            <summary class="text-secondary text-sm py-1 px-1 rounded hover:bg-surface2 flex items-center gap-1">
              <span class="text-muted">📁</span>
              <span class="flex-1 truncate">${escapeHtml(node.name)}</span>
              <a href="/w/${node.space_id}" onclick="event.stopPropagation()"
                 class="opacity-0 group-hover/dir:opacity-100 text-xs text-muted hover:text-accent px-1 shrink-0 transition-opacity"
                 title="Abrir como espaço">↗</a>
            </summary>
            <div class="ml-3 border-l border-edge pl-1">${renderTreeHtml(node.children)}</div>
          </details>
        </li>`;
      }
      return `<li>
        <div class="group/file flex items-center">
          <button type="button" data-path="${escapeHtml(node.path)}"
            class="file-link flex-1 text-left text-sm py-1 px-2 rounded hover:bg-surface2 hover:text-primary text-secondary truncate">
            ${escapeHtml(node.name)}
          </button>
          <button type="button" data-delete-path="${escapeHtml(node.path)}"
            class="opacity-0 group-hover/file:opacity-100 shrink-0 w-5 h-5 flex items-center justify-center text-xs text-muted hover:text-danger rounded mr-1 transition-opacity"
            title="Apagar">×</button>
        </div>
      </li>`;
    });
    return `<ul class="pl-2">${items.join("")}</ul>`;
  }

  async function refreshTree() {
    const { tree } = await EstudAI.api.get(`/api/spaces/${spaceId}/tree`);
    fileTree.innerHTML = renderTreeHtml(tree);
    if (currentFilePath) highlightActiveFile(currentFilePath);
  }
  window.EstudAI.refreshTree = refreshTree;

  fileTree.addEventListener("click", (e) => {
    const deleteBtn = e.target.closest("[data-delete-path]");
    if (deleteBtn) {
      e.stopPropagation();
      const path = deleteBtn.dataset.deletePath;
      if (!confirm(`Apagar "${path}"? Esta ação não pode ser desfeita.`)) return;
      EstudAI.api.delete(
        `/api/spaces/${spaceId}/file?path=${encodeURIComponent(path)}`
      ).then(async () => {
        if (currentFilePath === path) {
          currentFilePath = null;
          currentFileRaw = null;
          fileActions.classList.add("hidden");
          contentBody.innerHTML = '<div class="text-muted text-sm">Arquivo apagado.</div>';
        }
        await refreshTree();
      }).catch(err => alert("Erro: " + err.message));
      return;
    }
    const btn = e.target.closest(".file-link");
    if (btn) openFile(btn.dataset.path);
  });

  // ── Abas do painel direito ────────────────────────────────────────────────────

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
