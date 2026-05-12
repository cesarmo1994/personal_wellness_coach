const STORAGE_KEY = "pichudos-app-state-v4";
const USERS = ["David", "Pri", "Ana", "César"];

const emptyUser = () => ({
  plans: {
    nutrition: null,
    training: null,
    wellness: null,
  },
  checkins: [],
  messages: [
    {
      role: "coach",
      text: "Bienvenido. Carga tus planes o creemos uno por conversacion y yo lo convierto en acciones diarias simples.",
      at: new Date().toISOString(),
    },
  ],
});

const defaultState = {
  activeUser: "César",
  activeView: "onboarding",
  users: Object.fromEntries(USERS.map((name) => [name, emptyUser()])),
  updatedAt: Date.now(),
  groupMessages: [
    {
      role: "system",
      sender: "Sistema",
      text: "Chat grupal listo. David, Pri, Ana y César pueden escribir aqui. El coach solo responde si lo etiquetan con @coach.",
      at: new Date().toISOString(),
    },
  ],
};

let state = loadState();
let saveTimer = null;
let isHydrating = false;
let lastSeenGroupMessageCount = state.groupMessages.length;

const subtitles = {
  onboarding: "Wellness coach privado",
  plan: "Plan activo",
  coach: "Coach personal",
  checkin: "Evidencia diaria",
  group: "Chat grupal",
  admin: "Fundador",
};

const planNames = {
  nutrition: "nutricion",
  training: "entrenamiento",
  wellness: "wellness",
};

const planBuilderLabels = {
  nutrition: "Contame tu objetivo nutricional, preferencias, restricciones y horarios.",
  training: "Contame tu objetivo de entrenamiento, dias disponibles, nivel y equipo.",
  wellness: "Contame que actividades holisticas queres incluir y cuanto tiempo tenes.",
};

function loadState() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (!saved) return structuredClone(defaultState);

  try {
    const parsed = JSON.parse(saved);
    const next = { ...structuredClone(defaultState), ...parsed };
    for (const user of USERS) {
      next.users[user] = { ...emptyUser(), ...(next.users?.[user] || {}) };
    }
    if (!USERS.includes(next.activeUser)) next.activeUser = "César";
    return next;
  } catch {
    return structuredClone(defaultState);
  }
}

function saveState() {
  state.updatedAt = Date.now();
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  if (!isHydrating) scheduleServerSave();
}

function scheduleServerSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    fetch("/api/app-state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state }),
    }).catch(() => {});
  }, 350);
}

async function syncFromServer({ notify = false } = {}) {
  try {
    const response = await fetch("/api/app-state");
    if (!response.ok) return;
    const data = await response.json();
    if (!data.state || !data.state.updatedAt) return;
    if ((data.state.updatedAt || 0) <= (state.updatedAt || 0)) return;

    const previousCount = state.groupMessages.length;
    isHydrating = true;
    state = data.state;
    for (const user of USERS) {
      state.users[user] = { ...emptyUser(), ...(state.users?.[user] || {}) };
    }
    if (!USERS.includes(state.activeUser)) state.activeUser = "César";
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    isHydrating = false;

    if (notify) notifyNewGroupMessages(previousCount);
    render();
  } catch {
    isHydrating = false;
  }
}

function notifyNewGroupMessages(previousCount = lastSeenGroupMessageCount) {
  const newer = state.groupMessages.slice(previousCount);
  lastSeenGroupMessageCount = state.groupMessages.length;
  if (typeof Notification === "undefined" || Notification.permission !== "granted") return;
  newer
    .filter((message) => message.role === "user" && message.sender !== state.activeUser)
    .forEach((message) => {
      new Notification(`Los Pichudos · ${message.sender}`, {
        body: message.text,
        tag: `pichudos-${message.at || Date.now()}`,
      });
    });
}

function currentUser() {
  return state.users[state.activeUser];
}

function setView(view) {
  state.activeView = view;
  saveState();
  render();
}

function todayKey() {
  return new Date().toISOString().slice(0, 10);
}

function weeklyCount(userName = state.activeUser) {
  const days = new Set(state.users[userName].checkins.map((checkin) => checkin.date));
  return Math.min(days.size, 7);
}

function groupAverage() {
  const total = USERS.reduce((sum, user) => sum + weeklyCount(user), 0);
  return Math.round((total / (USERS.length * 7)) * 100);
}

function fallbackCoachReply(userText) {
  const loadedPlans = Object.values(currentUser().plans).filter(Boolean).length;
  const count = weeklyCount();
  const lower = userText.toLowerCase();

  if (lower.includes("cans") || lower.includes("dolor") || lower.includes("sueno")) {
    return "Gracias por decirlo. Hoy bajemos un poco la intensidad y enfoquemonos en recuperacion: hidratacion, movilidad suave y dormir mejor.";
  }

  if (lower.includes("foto") || lower.includes("comida") || lower.includes("almuerzo")) {
    return "Excelente evidencia. Si queres mejorar energia, cuidemos proteina y agua en la proxima comida. Vas construyendo buen ritmo.";
  }

  if (loadedPlans < 3) {
    return "Buen avance. Para darte recomendaciones mas precisas, terminemos de cargar o crear nutricion, entrenamiento y wellness.";
  }

  if (count >= 5) {
    return "Vas en verde con la meta semanal. Mantengamos el plan simple: cerrar hoy sin perfeccionismo y revisar ajustes manana.";
  }

  return "Buen check-in. Para hoy te recomiendo enfocarte en una victoria concreta: cumplir el entrenamiento o dejar evidencia de nutricion.";
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "No se pudo conectar con el coach IA.");
  }
  return data;
}

async function analyzePlanFile(planType, file) {
  const formData = new FormData();
  formData.append("planType", planType);
  formData.append("file", file);
  formData.append("notes", document.querySelector("#plan-upload-notes")?.value.trim() || "");
  const response = await fetch("/api/analyze-plan", { method: "POST", body: formData });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "No se pudo analizar el archivo.");
  }
  return data;
}

async function uploadEvidenceFile(file) {
  const formData = new FormData();
  formData.append("user", state.activeUser);
  formData.append("file", file);
  const response = await fetch("/api/upload-evidence", { method: "POST", body: formData });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.error || "No se pudo guardar el archivo.");
  }
  return data;
}

function addPersonalMessage(role, text) {
  currentUser().messages.push({ role, text, at: new Date().toISOString() });
  saveState();
}

function addGroupMessage(role, sender, text) {
  state.groupMessages.push({ role, sender, text, at: new Date().toISOString() });
  saveState();
}

function markPlanLoading(key, label) {
  const status = document.querySelector(`[data-plan-status="${key}"]`);
  if (status) status.textContent = label;
}

function submitCheckin(form) {
  const user = currentUser();
  const done = [...form.querySelectorAll('input[name="done"]:checked')].map((input) => input.value);
  const note = document.querySelector("#checkin-note").value.trim();
  const evidenceNode = document.querySelector("#evidence-name");
  const evidence = evidenceNode.textContent;
  const summary = done.length ? done.join(", ") : "Avance registrado";
  const checkin = {
    date: todayKey(),
    at: new Date().toISOString(),
    done,
    note,
    evidence,
    evidenceUrl: evidenceNode.dataset.url || "",
  };

  user.checkins = user.checkins.filter((item) => item.date !== checkin.date);
  user.checkins.push(checkin);

  addPersonalMessage("user", `Check-in: ${summary}${note ? `. ${note}` : ""}`);
  addGroupMessage("user", state.activeUser, `Check-in: ${summary}${note ? `. ${note}` : ""}`);
  form.reset();
  document.querySelector("#evidence-name").textContent = "Foto, audio o texto del dia";
  document.querySelector("#evidence-name").dataset.url = "";
  setView("group");
}

async function askPersonalCoach(text) {
  try {
    const data = await postJson("/api/chat", {
      message: text,
      messages: currentUser().messages,
      plans: currentUser().plans,
      checkins: currentUser().checkins,
      user: state.activeUser,
    });
    addPersonalMessage("coach", data.reply);
  } catch (error) {
    addPersonalMessage("coach", `${fallbackCoachReply(text)}\n\nNota beta: no pude conectar con OpenAI ahora (${error.message}).`);
  }
  render();
}

async function askGroupCoach(text) {
  const groupContext = USERS.map((user) => ({
    user,
    plans: state.users[user].plans,
    checkins: state.users[user].checkins.slice(-7),
  }));

  try {
    const data = await postJson("/api/chat", {
      message: `Mensaje grupal de ${state.activeUser}: ${text}`,
      messages: state.groupMessages.slice(-16).map((msg) => ({
        role: msg.role === "coach" ? "coach" : "user",
        text: `${msg.sender}: ${msg.text}`,
      })),
      plans: { group: groupContext },
      checkins: groupContext,
    });
    addGroupMessage("coach", "Coach", data.reply);
  } catch (error) {
    addGroupMessage("coach", "Coach", `Puedo ayudar, pero ahora no pude conectar con OpenAI (${error.message}).`);
  }
  render();
}

function render() {
  document.querySelectorAll(".view").forEach((view) => {
    view.classList.toggle("active", view.id === `view-${state.activeView}`);
  });

  document.querySelectorAll("[data-view]").forEach((control) => {
    control.classList.toggle("active", control.dataset.view === state.activeView);
  });

  document.querySelector("#screen-subtitle").textContent = subtitles[state.activeView] || "Wellness coach privado";
  document.querySelectorAll("[data-current-user]").forEach((node) => {
    node.textContent = state.activeUser;
  });

  renderUserSelect();
  renderProgress();
  renderPlans();
  renderPersonalChat();
  renderGroup();
  renderAdmin();
}

function renderUserSelect() {
  const select = document.querySelector("#user-select");
  if (select.options.length !== USERS.length) {
    select.innerHTML = USERS.map((user) => `<option value="${escapeHtml(user)}">${escapeHtml(user)}</option>`).join("");
  }
  select.value = state.activeUser;
}

function renderProgress() {
  const count = weeklyCount();
  document.querySelectorAll("[data-weekly-count]").forEach((node) => {
    node.textContent = count;
  });
  document.querySelectorAll("[data-weekly-progress]").forEach((bar) => {
    bar.style.width = `${Math.round((count / 7) * 100)}%`;
  });
}

function renderPlans() {
  Object.entries(currentUser().plans).forEach(([key, plan]) => {
    const status = document.querySelector(`[data-plan-status="${key}"]`);
    const card = document.querySelector(`[data-plan-card="${key}"]`);
    if (!status || !card) return;

    card.classList.toggle("is-loaded", Boolean(plan));
    status.textContent = plan ? plan.name : key === "wellness" ? "Crear con IA" : "Pendiente";
  });
}

function renderPersonalChat() {
  const thread = document.querySelector("#chat-thread");
  thread.innerHTML = "";

  currentUser().messages.forEach((message) => {
    const article = document.createElement("article");
    article.className = `chat-message ${message.role}`;
    const who = message.role === "coach" ? "Coach" : message.role === "system" ? "Sistema" : state.activeUser;
    article.innerHTML = `<small>${escapeHtml(who)}</small><span>${escapeHtml(message.text)}</span>`;
    thread.appendChild(article);
  });

  thread.scrollTop = thread.scrollHeight;
}

function renderGroup() {
  const thread = document.querySelector("#group-chat-thread");
  thread.innerHTML = "";

  state.groupMessages.forEach((message) => {
    const article = document.createElement("article");
    const own = message.sender === state.activeUser && message.role === "user";
    const klass = message.role === "coach" ? "coach" : message.role === "system" ? "system" : own ? "user" : "other";
    article.className = `chat-message ${klass}`;
    article.innerHTML = `<small>${escapeHtml(message.sender)}</small><span>${escapeHtml(message.text)}</span>`;
    thread.appendChild(article);
  });
  thread.scrollTop = thread.scrollHeight;

  const list = document.querySelector("#member-list");
  list.innerHTML = "";

  USERS.forEach((user) => {
    const count = weeklyCount(user);
    const latest = state.users[user].checkins.at(-1);
    const isWarn = count === 0;
    const card = document.createElement("article");
    card.className = `member-card ${isWarn ? "warn" : ""}`;
    card.innerHTML = `
      <div class="member-top">
        <div class="avatar">${escapeHtml(user[0])}</div>
        <div>
          <strong>${escapeHtml(user)}</strong>
          <p>${latest ? "Completo hoy o esta semana" : "Pendiente"}</p>
        </div>
      </div>
      <div class="progress"><i style="width: ${Math.round((count / 7) * 100)}%"></i></div>
      <small>${latest ? escapeHtml(latest.note || latest.done.join(", ") || "Check-in registrado") : "Sin check-in"}</small>
    `;
    list.appendChild(card);
  });

  document.querySelector("#group-progress").style.width = `${groupAverage()}%`;
  const pending = USERS.filter((user) => weeklyCount(user) === 0);
  document.querySelector("#group-note").textContent = pending.length
    ? `Usa @coach para pedir una opinion. Pendientes sin check-in semanal: ${pending.join(", ")}.`
    : "Todos tienen avance esta semana. Usa @coach para pedir ajustes o feedback grupal.";
}

function renderAdmin() {
  document.querySelector("#stat-users").textContent = USERS.length;
  document.querySelector("#stat-today").textContent = USERS.filter((user) =>
    state.users[user].checkins.some((checkin) => checkin.date === todayKey())
  ).length;

  const list = document.querySelector("#admin-list");
  list.innerHTML = "";
  USERS.forEach((user) => {
    const plansLoaded = Object.values(state.users[user].plans).filter(Boolean).length;
    const row = document.createElement("article");
    row.className = "admin-row";
    row.innerHTML = `
      <strong>${escapeHtml(user)}</strong>
      <span>Los Pichudos · ${weeklyCount(user)}/7 · ${plansLoaded}/3 planes cargados</span>
    `;
    list.appendChild(row);
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.addEventListener("click", (event) => {
  const viewTrigger = event.target.closest("[data-view]");
  if (viewTrigger) {
    setView(viewTrigger.dataset.view);
  }
});

document.querySelector("#user-select").addEventListener("change", (event) => {
  state.activeUser = event.target.value;
  saveState();
  render();
});

document.querySelectorAll("[data-plan-input]").forEach((input) => {
  input.addEventListener("change", async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    const key = event.target.dataset.planInput;
    markPlanLoading(key, "Analizando con IA...");

    try {
      const analysis = await analyzePlanFile(key, file);
      currentUser().plans[key] = {
        name: analysis.name || file.name,
        type: file.type || "archivo",
        summary: analysis.summary,
        responseId: analysis.responseId,
        extraction: analysis.extraction,
        fileUrl: analysis.fileUrl,
        notes: analysis.notes,
        updatedAt: new Date().toISOString(),
      };
      addPersonalMessage("system", `Plan de ${planNames[key]} cargado y analizado: ${file.name}`);
      addPersonalMessage("coach", analysis.summary);
      const notes = document.querySelector("#plan-upload-notes");
      if (notes) notes.value = "";
    } catch (error) {
      currentUser().plans[key] = {
        name: file.name,
        type: file.type || "archivo",
        summary: "Archivo guardado localmente, pendiente de analisis IA.",
        updatedAt: new Date().toISOString(),
      };
      addPersonalMessage("system", `Plan cargado localmente: ${file.name}`);
      addPersonalMessage("coach", `No pude analizar el archivo todavia: ${error.message}`);
    }

    saveState();
    render();
  });
});

document.querySelectorAll("[data-create-plan]").forEach((button) => {
  button.addEventListener("click", () => {
    const planType = button.dataset.createPlan;
    document.querySelector("#builder-plan-type").value = planType;
    document.querySelector("#builder-label").textContent = planBuilderLabels[planType] || planBuilderLabels.wellness;
    document.querySelector("#wellness-builder").classList.remove("hidden");
    document.querySelector("#wellness-notes").focus();
  });
});

document.querySelector("#wellness-builder").addEventListener("submit", async (event) => {
  event.preventDefault();
  const notes = document.querySelector("#wellness-notes").value.trim();
  const planType = document.querySelector("#builder-plan-type").value;
  if (!notes) return;

  markPlanLoading(planType, "Creando con IA...");
  addPersonalMessage("user", `Quiero crear mi plan de ${planNames[planType]}: ${notes}`);
  event.target.classList.add("hidden");
  render();

  try {
    const plan = await postJson("/api/create-plan", {
      planType,
      notes,
      messages: currentUser().messages,
      user: state.activeUser,
    });
    currentUser().plans[planType] = {
      name: plan.name,
      notes,
      summary: plan.summary,
      responseId: plan.responseId,
      updatedAt: new Date().toISOString(),
    };
    addPersonalMessage("coach", plan.summary);
  } catch (error) {
    currentUser().plans[planType] = {
      name: `Plan de ${planNames[planType]} creado localmente`,
      notes,
      summary: "Plan pendiente de refinamiento IA.",
      updatedAt: new Date().toISOString(),
    };
    addPersonalMessage("coach", `Guarde tu informacion, pero no pude crear el plan con IA todavia: ${error.message}`);
  }

  event.target.reset();
  saveState();
  render();
});

document.querySelector("#chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.querySelector("#chat-input");
  const text = input.value.trim();
  if (!text) return;

  addPersonalMessage("user", text);
  input.value = "";
  render();
  await askPersonalCoach(text);
});

document.querySelector("#group-chat-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = document.querySelector("#group-chat-input");
  const text = input.value.trim();
  if (!text) return;

  addGroupMessage("user", state.activeUser, text);
  input.value = "";
  render();

  if (text.toLowerCase().includes("@coach")) {
    await askGroupCoach(text);
  }
});

document.querySelector("#enable-notifications").addEventListener("click", async () => {
  if (typeof Notification === "undefined") {
    addGroupMessage("system", "Sistema", "Este navegador no soporta notificaciones.");
    render();
    return;
  }
  const permission = await Notification.requestPermission();
  addGroupMessage(
    "system",
    "Sistema",
    permission === "granted"
      ? "Notificaciones activadas en este dispositivo mientras la app este abierta o en segundo plano."
      : "No se activaron notificaciones. Podes habilitarlas desde permisos del navegador."
  );
  render();
});

document.querySelector("#photo-input").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  let suffix = "";
  try {
    const uploaded = await uploadEvidenceFile(file);
    suffix = ` (${uploaded.url})`;
  } catch {
    suffix = " (pendiente de guardar en servidor)";
  }
  addPersonalMessage("user", `Subi foto: ${file.name}${suffix}`);
  addPersonalMessage("coach", "Foto recibida. En esta beta la registro como evidencia; luego podemos sumar analisis visual del plato, postura o progreso.");
  render();
});

document.querySelector("#audio-button").addEventListener("click", () => {
  addPersonalMessage("system", "Audio simulado agregado. En produccion esto usara grabacion y transcripcion.");
  addPersonalMessage("coach", "Perfecto. Podes dejarme notas rapidas por audio cuando no queras escribir.");
  render();
});

document.querySelector("#evidence-input").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) {
    document.querySelector("#evidence-name").textContent = "Foto, audio o texto del dia";
    return;
  }
  document.querySelector("#evidence-name").textContent = `Guardando ${file.name}...`;
  try {
    const uploaded = await uploadEvidenceFile(file);
    document.querySelector("#evidence-name").textContent = `${uploaded.name} guardado`;
    document.querySelector("#evidence-name").dataset.url = uploaded.url;
  } catch {
    document.querySelector("#evidence-name").textContent = `${file.name} pendiente de guardar`;
  }
});

document.querySelector("#checkin-form").addEventListener("submit", (event) => {
  event.preventDefault();
  submitCheckin(event.target);
});

document.querySelector("#reset-demo").addEventListener("click", () => {
  localStorage.removeItem(STORAGE_KEY);
  state = structuredClone(defaultState);
  render();
});

syncFromServer().finally(() => {
  render();
  lastSeenGroupMessageCount = state.groupMessages.length;
});
setInterval(() => syncFromServer({ notify: true }), 5000);

if ("serviceWorker" in navigator && location.protocol !== "file:") {
  navigator.serviceWorker.register("./sw.js").catch(() => {});
}
