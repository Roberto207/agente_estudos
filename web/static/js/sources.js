(function () {
  const root = document.getElementById("workspace");
  const spaceId = root.dataset.spaceId;
  const form = document.getElementById("sources-form");
  const submitBtn = document.getElementById("sources-submit");
  const logEl = document.getElementById("sources-log");
  const resultsEl = document.getElementById("sources-results");
  const useBtn = document.getElementById("sources-use-selected");

  const CAMADA_LABEL = {
    fundamentos: "📚 Fundamentos",
    moderno: "⚡ Técnicas Modernas",
    pratico: "🔧 Prático",
  };

  function appendLog(line) {
    logEl.classList.remove("hidden");
    const div = document.createElement("div");
    div.className = "text-secondary";
    div.textContent = line;
    logEl.appendChild(div);
  }

  function escapeHtml(s) {
    return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function renderResults(fontes) {
    const byCamada = {};
    for (const f of fontes) {
      (byCamada[f.camada] = byCamada[f.camada] || []).push(f);
    }

    resultsEl.innerHTML = Object.entries(byCamada)
      .map(([camada, items]) => {
        const label = CAMADA_LABEL[camada] || camada;
        const rows = items
          .sort((a, b) => b.score - a.score)
          .map(
            (f) => `<label class="flex items-start gap-2 py-1.5 border-b border-edge/50 text-xs">
              <input type="checkbox" class="source-check mt-0.5 accent-accent" value="${escapeHtml(f.url)}" checked>
              <span>
                <span class="text-primary block">${escapeHtml(f.titulo)} <span class="text-teal">★${f.score.toFixed(1)}</span></span>
                <span class="text-muted block">${escapeHtml(f.motivo)}</span>
              </span>
            </label>`
          )
          .join("");
        return `<div>
          <h4 class="text-secondary text-xs uppercase tracking-wide mb-1">${label}</h4>
          ${rows}
        </div>`;
      })
      .join("");
    resultsEl.classList.remove("hidden");
    useBtn.classList.toggle("hidden", fontes.length === 0);
  }

  async function pollJob(jobId) {
    let seen = 0;
    while (true) {
      const job = await EstudAI.api.get(`/api/jobs/${jobId}`);
      for (; seen < job.events.length; seen++) {
        const ev = job.events[seen];
        if (ev.type === "discover_start") appendLog("Buscando e curando fontes...");
        if (ev.type === "discover_done") appendLog(`✓ ${ev.payload.count} fonte(s) encontrada(s)`);
      }
      if (job.status === "done") {
        renderResults(job.result.fontes || []);
        submitBtn.disabled = false;
        submitBtn.textContent = "Buscar fontes";
        return;
      }
      if (job.status === "error") {
        appendLog(`✗ Erro: ${job.error}`);
        submitBtn.disabled = false;
        submitBtn.textContent = "Buscar fontes";
        return;
      }
      await new Promise((r) => setTimeout(r, 1500));
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const body = {
      tema: fd.get("tema"),
      foco: fd.get("foco") || "",
      max_per_camada: parseInt(fd.get("max_per_camada"), 10) || 5,
    };

    logEl.innerHTML = "";
    resultsEl.classList.add("hidden");
    useBtn.classList.add("hidden");
    submitBtn.disabled = true;
    submitBtn.textContent = "Buscando...";

    try {
      const { job_id } = await EstudAI.api.post(`/api/spaces/${spaceId}/discover-sources`, body);
      appendLog("Job iniciado...");
      await pollJob(job_id);
    } catch (err) {
      appendLog(`✗ Erro ao iniciar: ${err.message}`);
      submitBtn.disabled = false;
      submitBtn.textContent = "Buscar fontes";
    }
  });

  useBtn.addEventListener("click", () => {
    const urls = Array.from(resultsEl.querySelectorAll(".source-check:checked")).map((c) => c.value);
    document.getElementById("gen-fontes").value = urls.join("\n");
    document.querySelector('.tab-btn[data-tab="gerar"]').click();
  });
})();
