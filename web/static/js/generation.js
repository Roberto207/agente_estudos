(function () {
  const root = document.getElementById("workspace");
  const spaceId = root.dataset.spaceId;
  const form = document.getElementById("gen-form");
  const submitBtn = document.getElementById("gen-submit");
  const logEl = document.getElementById("gen-log");

  function appendLog(line) {
    logEl.classList.remove("hidden");
    const div = document.createElement("div");
    div.className = "text-secondary";
    div.textContent = line;
    logEl.appendChild(div);
    logEl.scrollTop = logEl.scrollHeight;
  }

  function describeEvent(ev) {
    const p = ev.payload || {};
    switch (ev.type) {
      case "iteration_start": return `[Iteração ${p.iteration}] LLM pensando...`;
      case "tool_calls": return `→ ${(p.calls || []).map((c) => c.name).join(", ")}`;
      case "agent_finished": return "Agente finalizado.";
      case "postprocessing_start": return "Pós-processamento iniciado...";
      case "postprocessing_step":
        return `  ${p.status === "ok" ? "✓" : "✗"} ${p.name}`;
      default: return `${ev.type}`;
    }
  }

  async function pollJob(jobId) {
    let seen = 0;
    while (true) {
      const job = await EstudAI.api.get(`/api/jobs/${jobId}`);
      for (; seen < job.events.length; seen++) {
        appendLog(describeEvent(job.events[seen]));
      }
      if (job.status === "done") {
        appendLog(`✓ Concluído — ${job.result.arquivos_md.length} arquivo(s) .md`);
        await window.EstudAI.refreshTree();
        submitBtn.disabled = false;
        submitBtn.textContent = "Gerar conteúdo";
        return;
      }
      if (job.status === "error") {
        appendLog(`✗ Erro: ${job.error}`);
        submitBtn.disabled = false;
        submitBtn.textContent = "Gerar conteúdo";
        return;
      }
      await new Promise((r) => setTimeout(r, 1500));
    }
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fd = new FormData(form);
    const fontes = (fd.get("fontes") || "")
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);

    const body = {
      tema: fd.get("tema"),
      foco: fd.get("foco") || "",
      didatica: fd.get("didatica") || "",
      fontes,
      outputs: {
        html: form.output_html.checked,
        canvas: form.output_canvas.checked,
        flashcards: form.output_flashcards.checked,
        quiz: form.output_quiz.checked,
        mapa_mental: form.output_mapa_mental.checked,
        next_steps: form.output_next_steps.checked,
      },
    };

    logEl.innerHTML = "";
    submitBtn.disabled = true;
    submitBtn.textContent = "Gerando...";

    try {
      const { job_id } = await EstudAI.api.post(`/api/spaces/${spaceId}/generate`, body);
      appendLog("Job iniciado...");
      await pollJob(job_id);
    } catch (err) {
      appendLog(`✗ Erro ao iniciar: ${err.message}`);
      submitBtn.disabled = false;
      submitBtn.textContent = "Gerar conteúdo";
    }
  });
})();
