(function () {
  const root = document.getElementById("workspace");
  const spaceId = root.dataset.spaceId;
  const messagesEl = document.getElementById("chat-messages");
  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");
  const clearBtn = document.getElementById("chat-clear");
  const settingsBtn = document.getElementById("chat-settings");
  const settingsModal = document.getElementById("chat-settings-modal");
  const settingsBackdrop = document.getElementById("chat-settings-backdrop");
  const settingsClose = document.getElementById("chat-settings-close");
  const settingsCancel = document.getElementById("chat-settings-cancel");
  const settingsSave = document.getElementById("chat-settings-save");
  const modelSelect = document.getElementById("chat-model-select");
  const modeBtns = [document.getElementById("chat-mode-qa"), document.getElementById("chat-mode-socratico")];

  let history = [];
  let mode = "qa";
  let selectedModel = "";

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function addBubble(role, text) {
    const div = document.createElement("div");
    const isUser = role === "user";
    div.className = isUser
      ? "ml-6 bg-accent/15 border border-accent/30 rounded-lg px-3 py-2 text-primary"
      : "mr-6 bg-surface2 border border-edge rounded-lg px-3 py-2 text-secondary";
    div.innerHTML = escapeHtml(text).replace(/\n/g, "<br>");
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  modeBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      mode = btn.dataset.mode;
      modeBtns.forEach((b) => {
        const active = b === btn;
        b.classList.toggle("bg-accent", active);
        b.classList.toggle("text-white", active);
        b.classList.toggle("text-secondary", !active);
      });
      history = [];
      messagesEl.innerHTML = "";
    });
  });

  clearBtn.addEventListener("click", () => {
    history = [];
    messagesEl.innerHTML = "";
  });

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const message = input.value.trim();
    if (!message) return;
    input.value = "";
    addBubble("user", message);
    const thinking = addBubble("assistant", "Buscando e pensando...");

    try {
      const { reply } = await EstudAI.api.post(`/api/spaces/${spaceId}/chat`, {
        message, mode, history, model_override: selectedModel,
      });
      thinking.innerHTML = escapeHtml(reply).replace(/\n/g, "<br>");
      history.push({ role: "user", content: message });
      history.push({ role: "assistant", content: reply });
    } catch (err) {
      thinking.textContent = `Erro: ${err.message}`;
      thinking.classList.add("text-danger");
    }
  });

  // ── Configurações de Modelo ───────────────────────────────────────────────────
  async function loadModels() {
    try {
      const { provider, models } = await EstudAI.api.get("/api/models");

      modelSelect.innerHTML = '<option value="">Padrão (config.yaml)</option>';
      for (const [prov, model] of Object.entries(models)) {
        const option = document.createElement("option");
        option.value = model;
        option.textContent = `${prov}: ${model}`;
        if (prov === provider) option.textContent += " (ativo)";
        modelSelect.appendChild(option);
      }

      // Carregar modelo salvo no localStorage
      selectedModel = localStorage.getItem("chat-selected-model") || "";
      modelSelect.value = selectedModel;
    } catch (err) {
      console.error("Erro ao carregar modelos:", err);
    }
  }

  function openSettingsModal() {
    modelSelect.value = selectedModel;
    settingsModal.style.display = "flex";
  }

  function closeSettingsModal() {
    settingsModal.style.display = "none";
  }

  settingsBtn.addEventListener("click", openSettingsModal);
  settingsClose.addEventListener("click", closeSettingsModal);
  settingsCancel.addEventListener("click", closeSettingsModal);
  settingsBackdrop.addEventListener("click", closeSettingsModal);

  settingsSave.addEventListener("click", () => {
    selectedModel = modelSelect.value;
    localStorage.setItem("chat-selected-model", selectedModel);
    closeSettingsModal();
  });

  // Carregar modelos ao inicializar
  loadModels();
})();
