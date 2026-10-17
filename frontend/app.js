(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const API_BASE = "https://gi-ai-novel-studio-api.onrender.com";
const STORE = "gi-novel-settings-v1";
  let novels = [];
  let currentNovel = null;
  let toastTimer;

  const defaults = {
    provider: "openai_compatible",
    baseUrl: "https://api.groq.com/openai/v1",
    model: "openai/gpt-oss-120b"
  };

  function getSettings() {
    try {
      return { ...defaults, ...JSON.parse(sessionStorage.getItem(STORE) || "{}") };
    } catch {
      return { ...defaults };
    }
  }

  function saveSettings(value) {
    sessionStorage.setItem(STORE, JSON.stringify(value));
  }

  function headers(extra = {}) {
    const s = getSettings();
    const h = { ...extra };
    // Send available credentials; the backend selects the one matching
    // the provider saved with the novel.
    if (s.apiKey) h["X-AI-API-Key"] = s.apiKey;
    if (s.geminiKey) h["X-Gemini-API-Key"] = s.geminiKey;
    if (s.baseUrl) h["X-AI-Base-URL"] = s.baseUrl;
    return h;
  }

  async function api(path, options = {}) {
    const response = await fetch(new URL(path, API_BASE), {
      ...options,
      headers: headers(options.headers || {})
    });
    const type = response.headers.get("content-type") || "";
    const data = type.includes("application/json")
      ? await response.json()
      : await response.text();

    if (!response.ok) {
      let detail = typeof data === "string" ? data : data.detail || data.message || JSON.stringify(data);
      if (typeof detail !== "string") detail = JSON.stringify(detail);
      throw new Error(detail);
    }
    return data;
  }

  function esc(value) {
    return String(value ?? "").replace(/[&<>"']/g, (c) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[c]);
  }

  function toast(message) {
    const el = $("toast");
    el.textContent = message;
    el.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove("show"), 3000);
  }

  function setMessage(id, message, error = false) {
    const el = $(id);
    if (!el) return;
    el.textContent = message || "";
    el.classList.toggle("error", error);
  }

  function statusText(status) {
    return ({
      draft: "Draft",
      ready: "ဆက်ရေးရန်",
      generating: "ရေးသားနေသည်",
      completed: "ပြီးစီး",
      paused_quota: "Credit လိုအပ်",
      paused_error: "ပြန်စစ်ရန်"
    })[status] || status || "Ready";
  }

  function chapterCount(novel) {
    return Number(novel.completed_chapters ?? novel.chapters?.length ?? 0);
  }

  function progress(novel) {
    const target = Math.max(1, Number(novel.target_chapters || 1));
    return Math.min(100, Math.round(chapterCount(novel) / target * 100));
  }

  function coverSymbol(genre) {
    return ({
      horror: "☽", mystery: "◉", detective: "⌕", fantasy: "✧",
      romance: "❦", adventure: "➶", "sci-fi": "⌘", drama: "❖"
    })[genre] || "✧";
  }

  function novelCard(novel) {
    const id = esc(novel.id);
    const count = chapterCount(novel);
    const pct = progress(novel);
    return `
      <article class="novel-card">
        <div class="cover-art">
          <div class="cover-noise"></div>
          <span class="cover-symbol">${coverSymbol(novel.genre)}</span>
        </div>
        <div class="novel-card-body">
          <h3>${esc(novel.title)}</h3>
          <p>${esc(novel.idea || "")}</p>
          <div class="card-meta">
            <span>${count}/${Number(novel.target_chapters || 0)} အခန်း</span>
            <span class="status-chip">${esc(statusText(novel.status))}</span>
          </div>
          <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
          <div class="card-meta"><span>${pct}% complete</span><span>${esc(novel.genre || "Novel")}</span></div>
          <div class="card-actions">
            <button class="secondary-btn" data-open="${id}">ဖွင့်ရန် ↗</button>
            <button class="secondary-btn" data-pdf="${id}" ${count ? "" : "disabled"}>PDF ↓</button>
          </div>
        </div>
      </article>`;
  }

  function showPage(name) {
    document.querySelectorAll(".page").forEach((p) => p.classList.remove("active"));
    const page = $("page-" + name);
    if (page) page.classList.add("active");
    document.querySelectorAll(".nav-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.page === name);
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
    if (name === "library") renderLibrary();
    if (name === "settings") populateSettings();
  }

  async function loadNovels() {
    try {
      const data = await api("/api/novels");
      novels = Array.isArray(data) ? data : [];
      renderNovels();
      return novels;
    } catch (error) {
      $("recentNovels").innerHTML = `<div class="empty-state">ဝတ္ထုစာရင်း မရရှိပါ။ ${esc(error.message)}</div>`;
      $("allNovels").innerHTML = `<div class="empty-state">Backend ချိတ်ဆက်မှုကို Settings မှာ စစ်ဆေးပါ။</div>`;
      setMessage("libraryMessage", error.message, true);
      return [];
    }
  }

  function renderNovels() {
    const totalChapters = novels.reduce((sum, n) => sum + chapterCount(n), 0);
    $("statNovels").textContent = novels.length;
    $("statChapters").textContent = totalChapters;
    $("statProvider").textContent = getSettings().provider === "gemini" ? "Gemini" : "OpenAI API";
    const recent = novels.slice(0, 4);
    $("recentNovels").innerHTML = recent.length
      ? recent.map(novelCard).join("")
      : `<div class="empty-state">သင့်ရဲ့ ပထမဆုံးဝတ္ထုကို ဖန်တီးလိုက်ပါ။</div>`;
    renderLibrary();
  }

  function renderLibrary() {
    const query = ($("novelSearch")?.value || "").trim().toLowerCase();
    const list = novels.filter(n => String(n.title || "").toLowerCase().includes(query));
    $("allNovels").innerHTML = list.length
      ? list.map(novelCard).join("")
      : `<div class="empty-state">${query ? "ရှာဖွေမှုနဲ့ ကိုက်ညီတဲ့ဝတ္ထု မတွေ့ပါ။" : "ဝတ္ထုမရှိသေးပါ။ Home မှာ ဝတ္ထုအသစ်ဖန်တီးပါ။"}</div>`;
  }

  async function openNovel(id) {
    showPage("editor");
    $("editorContent").innerHTML = `<div class="empty-state">ဝတ္ထုကို ဖွင့်နေသည်…</div>`;
    try {
      currentNovel = await api(`/api/novels/${encodeURIComponent(id)}`);
      renderEditor();
    } catch (error) {
      $("editorContent").innerHTML = `<div class="empty-state">${esc(error.message)}</div>`;
    }
  }

  function renderEditor() {
    if (!currentNovel) return;
    const n = currentNovel;
    const chapters = Array.isArray(n.chapters) ? n.chapters : [];
    const count = chapters.length;
    const pct = progress(n);
    $("editorContent").innerHTML = `
      <section class="editor-head">
        <span class="eyebrow">YOUR STORY · ${esc(n.genre || "NOVEL")}</span>
        <h1>${esc(n.title)}</h1>
        <p>${esc(n.idea || "")}</p>
        <div class="card-meta"><span>${count}/${Number(n.target_chapters || 0)} chapters</span><span class="status-chip">${esc(statusText(n.status))}</span></div>
        <div class="progress-track"><div class="progress-fill" style="width:${pct}%"></div></div>
        <div class="editor-actions">
          <button class="primary-btn" id="generateOne" ${n.status === "generating" || count >= Number(n.target_chapters) ? "disabled" : ""}>✦ နောက်အခန်းရေးမည်</button>
          <button class="secondary-btn" id="resumeNovel" ${count >= Number(n.target_chapters) ? "disabled" : ""}>↻ ဆက်ရေးမည်</button>
          <button class="secondary-btn" id="exportPdf" ${count ? "" : "disabled"}>PDF ထုတ်ရန် ↓</button>
          <button class="secondary-btn" id="deleteNovel">ဖျက်ရန်</button>
        </div>
        <p id="editorMessage" class="message" role="status">${esc(n.last_error || "")}</p>
      </section>
      <section class="section-heading"><div><span class="eyebrow">MANUSCRIPT</span><h2>ဝတ္ထုအခန်းများ (${count})</h2></div></section>
      <div class="chapter-list">
        ${chapters.length ? chapters.map((ch, i) => `
          <article class="chapter-panel">
            <div class="chapter-number">CHAPTER ${String(ch.chapter_no ?? i + 1).padStart(2, "0")}</div>
            <h3>${esc(ch.title || `အခန်း ${i + 1}`)}</h3>
            <div class="chapter-content">${esc(ch.content || "")}</div>
          </article>`).join("") : `<div class="empty-state">အခန်းမရေးရသေးပါ။ “နောက်အခန်းရေးမည်” ကိုနှိပ်ပါ။</div>`}
      </div>`;
    $("generateOne")?.addEventListener("click", () => generateChapter(false));
    $("resumeNovel")?.addEventListener("click", () => generateChapter(true));
    $("exportPdf")?.addEventListener("click", () => downloadPdf(n.id));
    $("deleteNovel")?.addEventListener("click", () => deleteNovel(n.id));
  }

  async function generateChapter(resume) {
    if (!currentNovel) return;
    const n = currentNovel;
    const button = $(resume ? "resumeNovel" : "generateOne");
    const messageId = "editorMessage";
    if (!getSettings().model.trim()) {
      showPage("settings");
      setMessage("settingsMessage", "Model Name ကို အရင်သတ်မှတ်ပါ။", true);
      return;
    }
    if (getSettings().provider === "gemini" && !getSettings().geminiKey) {
      showPage("settings");
      setMessage("settingsMessage", "Gemini API Key ကို အရင်ထည့်ပါ။", true);
      return;
    }
    if (getSettings().provider !== "gemini" && !getSettings().apiKey) {
      showPage("settings");
      setMessage("settingsMessage", "AI API Key ကို အရင်ထည့်ပါ။", true);
      return;
    }
    if (button) button.disabled = true;
    setMessage(messageId, "AI က အခန်းရေးနေပါတယ်။ ခဏစောင့်ပါ…");
    try {
      const payload = { chapters: 1 };
      const path = `/api/novels/${encodeURIComponent(n.id)}/${resume ? "resume" : "generate"}`;
      const result = await api(path, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Idempotency-Key": crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) },
        body: JSON.stringify(payload)
      });
      currentNovel = result;
      await loadNovels();
      renderEditor();
      toast("အခန်းအသစ်ကို သိမ်းဆည်းပြီးပါပြီ။");
    } catch (error) {
      setMessage(messageId, error.message, true);
      toast("Generation မအောင်မြင်ပါ။ Error ကိုစစ်ပါ။");
      try {
        currentNovel = await api(`/api/novels/${encodeURIComponent(n.id)}`);
        renderEditor();
        setMessage("editorMessage", error.message, true);
      } catch {}
    } finally {
      if (button) button.disabled = false;
    }
  }

  function downloadPdf(id) {
    const url = `/api/novels/${encodeURIComponent(id)}/export/pdf`;
    window.open(url, "_blank", "noopener");
  }

  async function deleteNovel(id) {
    if (!confirm("ဒီဝတ္ထုနဲ့ အခန်းအားလုံးကို ဖျက်မှာ သေချာပါသလား။")) return;
    try {
      await api(`/api/novels/${encodeURIComponent(id)}`, { method: "DELETE" });
      currentNovel = null;
      await loadNovels();
      showPage("library");
      toast("ဝတ္ထုကို ဖျက်ပြီးပါပြီ။");
    } catch (error) {
      toast("ဖျက်မရပါ: " + error.message);
    }
  }

  function populateSettings() {
    const s = getSettings();
    $("provider").value = s.provider;
    $("baseUrl").value = s.baseUrl || defaults.baseUrl;
    $("model").value = s.model || defaults.model;
    $("apiKey").value = s.apiKey || "";
    $("geminiKey").value = s.geminiKey || "";
    toggleProviderFields();
  }

  function toggleProviderFields() {
    const gemini = $("provider").value === "gemini";
    $("compatibleFields").hidden = gemini;
    $("geminiFields").hidden = !gemini;
    if (gemini && !$("model").value) $("model").value = "gemini-2.5-flash";
    if (!gemini && !$("model").value) $("model").value = defaults.model;
  }

  async function checkHealth() {
    $("healthLight").classList.remove("ok", "bad");
    $("healthMessage").textContent = "Backend ကို စစ်ဆေးနေသည်…";
    try {
      const data = await api("/api/health");
      $("healthLight").classList.add("ok");
      $("healthMessage").textContent = `Connected · ${data.service || "API"} · ${data.version || ""}`;
    } catch (error) {
      $("healthLight").classList.add("bad");
      $("healthMessage").textContent = "မချိတ်ဆက်နိုင်ပါ — " + error.message;
    }
  }

  document.addEventListener("click", (event) => {
    const nav = event.target.closest("[data-page]");
    if (nav) {
      showPage(nav.dataset.page);
      return;
    }
    const open = event.target.closest("[data-open]");
    if (open) openNovel(open.dataset.open);
    const pdf = event.target.closest("[data-pdf]");
    if (pdf) downloadPdf(pdf.dataset.pdf);
  });

  $("settingsShortcut").addEventListener("click", () => showPage("settings"));
  $("startWriting").addEventListener("click", () => {
    $("novelTitle").focus();
    $("createForm").scrollIntoView({ behavior: "smooth", block: "start" });
  });
  $("backToLibrary").addEventListener("click", () => showPage("library"));
  $("refreshNovels").addEventListener("click", loadNovels);
  $("novelSearch").addEventListener("input", renderLibrary);
  $("provider").addEventListener("change", toggleProviderFields);
  $("checkHealth").addEventListener("click", checkHealth);

  $("settingsForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const provider = $("provider").value;
    const model = $("model").value.trim();
    if (!model) return setMessage("settingsMessage", "Model Name ထည့်ပါ။", true);
    if (provider === "gemini" && !$("geminiKey").value.trim()) {
      return setMessage("settingsMessage", "Gemini API Key ထည့်ပါ။", true);
    }
    if (provider !== "gemini" && !$("apiKey").value.trim()) {
      return setMessage("settingsMessage", "API Key ထည့်ပါ။", true);
    }
    const baseUrl = $("baseUrl").value.trim().replace(/\/+$/, "");
    if (provider !== "gemini" && !/^https:\/\/.+/i.test(baseUrl)) {
      return setMessage("settingsMessage", "HTTPS Base URL မှန်ကန်စွာထည့်ပါ။", true);
    }
    saveSettings({
      provider, model, baseUrl,
      apiKey: $("apiKey").value.trim(),
      geminiKey: $("geminiKey").value.trim()
    });
    setMessage("settingsMessage", "Settings ကို ဒီ Browser Session အတွက် သိမ်းပြီးပါပြီ။");
    $("statProvider").textContent = provider === "gemini" ? "Gemini" : "OpenAI API";
    toast("AI Settings သိမ်းပြီးပါပြီ။");
  });

  $("clearSettings").addEventListener("click", () => {
    sessionStorage.removeItem(STORE);
    populateSettings();
    setMessage("settingsMessage", "Session ထဲက API Key များကို ရှင်းပြီးပါပြီ။");
    toast("Key များ ရှင်းပြီးပါပြီ။");
  });

  $("createForm").addEventListener("submit", async (event) => {
    event.preventDefault();
    const s = getSettings();
    if (!s.model || (s.provider === "gemini" ? !s.geminiKey : !s.apiKey)) {
      showPage("settings");
      setMessage("settingsMessage", "ဝတ္ထုမဖန်တီးခင် AI Provider၊ Model နဲ့ API Key ကို သတ်မှတ်ပါ။", true);
      return;
    }
    const title = $("novelTitle").value.trim();
    const idea = $("novelIdea").value.trim();
    const style = $("writingStyle").value.trim();
    const genre = $("genre").value;
    const target = Number($("targetChapters").value);
    if (!title || idea.length < 5 || target < 1 || target > 200) {
      return setMessage("createMessage", "ဝတ္ထုအမည်၊ အိုင်ဒီယာနဲ့ အခန်းအရေအတွက်ကို ပြန်စစ်ပါ။", true);
    }
    const btn = $("createBtn");
    btn.disabled = true;
    setMessage("createMessage", "ဝတ္ထုကို သိမ်းဆည်းနေသည်…");
    try {
      const fullIdea = style
        ? `${idea}\n\nစာရေးသူ၏ ကိုယ်ပိုင်ရေးဟန်နှင့် အထူးညွှန်ကြားချက်များ:\n${style}`
        : idea;
      const created = await api("/api/novels", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title, idea: fullIdea, genre, target_chapters: target,
          provider: s.provider, model: s.model
        })
      });
      $("createForm").reset();
      $("targetChapters").value = 10;
      await loadNovels();
      toast("ဝတ္ထုအသစ်ကို ဖန်တီးပြီးပါပြီ။");
      await openNovel(created.id);
    } catch (error) {
      setMessage("createMessage", error.message, true);
    } finally {
      btn.disabled = false;
    }
  });

  populateSettings();
  loadNovels();
  checkHealth();
})();
