const startBtn = document.querySelector("#startBtn");
const recommendBtn = document.querySelector("#recommendBtn");
const jsonUpload = document.querySelector("#jsonUpload");
const progressArea = document.querySelector("#progressArea");
const progressLabel = document.querySelector("#progressLabel");
const progressPercent = document.querySelector("#progressPercent");
const progressBar = document.querySelector("#progressBar");
const resultArea = document.querySelector("#resultArea");
const recommendArea = document.querySelector("#recommendArea");
const errorArea = document.querySelector("#errorArea");
const gameList = document.querySelector("#gameList");
const recommendMeta = document.querySelector("#recommendMeta");

let lastDiagnostic = null;
let progressTimer = null;

const steps = [
  [10, "Preparando diagnostico"],
  [30, "Coletando processador"],
  [50, "Coletando placa de video"],
  [70, "Coletando memoria e discos"],
  [90, "Gerando analise gamer"],
];

function setProgress(percent, label) {
  progressPercent.textContent = `${percent}%`;
  progressLabel.textContent = label;
  progressBar.style.width = `${percent}%`;
}

function showError(message) {
  errorArea.textContent = message;
  errorArea.classList.remove("hidden");
}

function clearError() {
  errorArea.textContent = "";
  errorArea.classList.add("hidden");
}

function listItems(target, values, emptyText) {
  target.innerHTML = "";
  const items = values && values.length ? values : [emptyText];
  items.forEach((value) => {
    const li = document.createElement("li");
    li.textContent = value;
    target.appendChild(li);
  });
}

function renderDiagnostic(payload) {
  const summary = payload.summary || {};
  const cpu = summary.processor || {};
  const gpu = summary.gpu || {};
  const ram = summary.ram || {};
  const storage = summary.storage || {};
  const profile = summary.profile || {};

  document.querySelector("#cpuName").textContent = cpu.name || "N/D";
  document.querySelector("#cpuMeta").textContent = `${cpu.cores || "N/D"} nucleos, ${cpu.threads || "N/D"} threads, tier ${cpu.tier || "N/D"}`;

  document.querySelector("#gpuName").textContent = gpu.name || "N/D";
  document.querySelector("#gpuMeta").textContent = `${gpu.type || "N/D"} | VRAM ${gpu.vram_gb ?? "N/D"} GB`;

  document.querySelector("#ramTotal").textContent = `${ram.total_gb ?? "N/D"} GB`;
  document.querySelector("#ramMeta").textContent = `${ram.modules || 0} modulo(s) detectado(s)`;

  document.querySelector("#storageMain").textContent = `${storage.physical_count || 0} disco(s) fisico(s)`;
  document.querySelector("#storageMeta").textContent = `SSD: ${storage.has_ssd ? "sim" : "nao"} | HDD: ${storage.has_hdd ? "sim" : "nao"}`;

  document.querySelector("#directx").textContent = summary.directx || "N/D";
  document.querySelector("#profileLevel").textContent = profile.nivel || "N/D";
  document.querySelector("#profilePreset").textContent = profile.preset_geral || "N/D";

  listItems(document.querySelector("#bottlenecks"), summary.bottlenecks, "Nada critico detectado.");
  listItems(document.querySelector("#upgrades"), summary.upgrades, "A configuracao parece equilibrada.");

  resultArea.classList.remove("hidden");
}

function startProgressLoop() {
  let index = 0;
  setProgress(0, "Preparando diagnostico");
  progressArea.classList.remove("hidden");
  progressTimer = window.setInterval(() => {
    const step = steps[Math.min(index, steps.length - 1)];
    setProgress(step[0], step[1]);
    index += 1;
    if (index >= steps.length) {
      window.clearInterval(progressTimer);
    }
  }, 650);
}

async function runDiagnostic() {
  clearError();
  resultArea.classList.add("hidden");
  recommendArea.classList.add("hidden");
  startBtn.disabled = true;
  startProgressLoop();

  try {
    const response = await fetch("/api/diagnostico", { method: "POST" });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Falha ao executar diagnostico.");
    }
    lastDiagnostic = payload;
    window.clearInterval(progressTimer);
    setProgress(100, "Diagnostico concluido");
    renderDiagnostic(payload);
  } catch (error) {
    showError(error.message);
  } finally {
    startBtn.disabled = false;
  }
}

function renderRecommendations(payload) {
  const recommendations = payload.recommendations || [];
  recommendMeta.textContent = `Pontuacao da maquina: ${payload.machine_score || "N/D"} | Gargalo provavel: ${payload.probable_bottleneck || "N/D"}`;
  gameList.innerHTML = "";

  recommendations.forEach((game) => {
    const item = document.createElement("article");
    item.className = "game-item";
    item.innerHTML = `
      <span>Jogo recomendado</span>
      <strong>${game.title}</strong>
      <div class="game-stats">
        <b>${game.quality}</b>
        <b>${game.fps} FPS</b>
        <b>${game.bottleneck}</b>
      </div>
      <small>${game.note}</small>
    `;
    gameList.appendChild(item);
  });

  if (!recommendations.length) {
    gameList.innerHTML = '<article class="game-item"><strong>Nenhuma recomendacao gerada</strong><small>Gere um diagnostico mais completo e tente novamente.</small></article>';
  }

  recommendArea.classList.remove("hidden");
}

async function requestRecommendations(payload = lastDiagnostic) {
  clearError();
  try {
    const response = await fetch("/api/recomendar-jogos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload || {}),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Nao foi possivel recomendar jogos.");
    }
    renderRecommendations(data);
  } catch (error) {
    showError(error.message);
  }
}

async function uploadJson(file) {
  clearError();
  const form = new FormData();
  form.append("file", file);
  try {
    const response = await fetch("/api/upload-json", {
      method: "POST",
      body: form,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "Nao foi possivel ler o JSON.");
    }
    renderRecommendations(data);
  } catch (error) {
    showError(error.message);
  }
}

startBtn.addEventListener("click", runDiagnostic);
recommendBtn.addEventListener("click", () => requestRecommendations());
jsonUpload.addEventListener("change", (event) => {
  const [file] = event.target.files;
  if (file) {
    uploadJson(file);
  }
});

