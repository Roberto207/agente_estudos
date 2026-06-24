EstudAI.createSpace = async function () {
  const nome = document.getElementById("create-nome").value.trim();
  const parent = document.getElementById("create-parent").value.trim();
  const errorEl = document.getElementById("create-error");
  errorEl.classList.add("hidden");
  if (!nome) {
    errorEl.textContent = "Informe um nome.";
    errorEl.classList.remove("hidden");
    return;
  }
  try {
    const { space_id } = await EstudAI.api.post("/api/spaces", { nome, parent });
    window.location.href = `/w/${space_id}`;
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  }
};

EstudAI.openSpace = async function () {
  const path = document.getElementById("open-path").value.trim();
  const errorEl = document.getElementById("open-error");
  errorEl.classList.add("hidden");
  if (!path) {
    errorEl.textContent = "Informe um caminho.";
    errorEl.classList.remove("hidden");
    return;
  }
  try {
    const { space_id } = await EstudAI.api.post("/api/spaces/open", { path });
    window.location.href = `/w/${space_id}`;
  } catch (err) {
    errorEl.textContent = err.message;
    errorEl.classList.remove("hidden");
  }
};
