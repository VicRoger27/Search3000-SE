// Search3000 Web Client Application

let currentQuery = "";
let currentRawResults = [];
let activeTab = "all";
let spiderPollInterval = null;

document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  loadIndexStats();
  startStatusPolling();

  // Handle URL query parameters (e.g. ?q=yolo+vs+sam)
  const urlParams = new URLSearchParams(window.location.search);
  const q = urlParams.get("q");
  if (q) {
    document.getElementById("query-input-top").value = q;
    document.getElementById("query-input-home").value = q;
    executeSearch(q);
  }
});

function setupEventListeners() {
  const homeInput = document.getElementById("query-input-home");
  const topInput = document.getElementById("query-input-top");
  const homeSearchBtn = document.getElementById("search-btn-home");
  const topSearchBtn = document.getElementById("search-btn-top");
  const luckyBtn = document.getElementById("lucky-btn");
  const clearBtn = document.getElementById("clear-btn");
  const regenAiBtn = document.getElementById("regenerate-ai-btn");

  // Search Inputs
  homeInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") triggerSearch(homeInput.value);
  });

  topInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") triggerSearch(topInput.value);
  });

  homeSearchBtn.addEventListener("click", () => triggerSearch(homeInput.value));
  topSearchBtn.addEventListener("click", () => triggerSearch(topInput.value));
  luckyBtn.addEventListener("click", () => triggerSearch(homeInput.value || "YOLO vs SAM"));

  clearBtn.addEventListener("click", () => {
    topInput.value = "";
    topInput.focus();
    clearBtn.classList.add("hidden");
  });

  topInput.addEventListener("input", () => {
    if (topInput.value.trim()) {
      clearBtn.classList.remove("hidden");
    } else {
      clearBtn.classList.add("hidden");
    }
  });

  regenAiBtn.addEventListener("click", () => startAiOverview(currentQuery, currentRawResults));

  // Search Filter Tabs
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      activeTab = btn.getAttribute("data-tab");
      applyTabFilter();
    });
  });

  // Settings & Spider Modal
  const openModalBtn = document.getElementById("open-indexer-modal");
  const diskBadgeBtn = document.getElementById("disk-badge-btn");
  const closeModalBtn = document.getElementById("close-modal-btn");
  const modal = document.getElementById("settings-modal");

  openModalBtn.addEventListener("click", openSettingsModal);
  diskBadgeBtn.addEventListener("click", openSettingsModal);
  closeModalBtn.addEventListener("click", closeSettingsModal);

  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeSettingsModal();
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !modal.classList.contains("hidden")) {
      closeSettingsModal();
    }
  });

  // Spider Control Buttons
  document.getElementById("toggle-spider-btn").addEventListener("click", toggleSpider);
  document.getElementById("modal-toggle-spider-btn").addEventListener("click", toggleSpider);
  document.getElementById("step-spider-btn").addEventListener("click", stepSpider);
  document.getElementById("modal-step-spider-btn").addEventListener("click", stepSpider);
}

function triggerSearch(query, skipAi = false) {
  const cleanQ = query.trim();
  if (!cleanQ) return;

  const newUrl = `${window.location.pathname}?q=${encodeURIComponent(cleanQ)}`;
  window.history.pushState({ q: cleanQ }, "", newUrl);

  document.getElementById("query-input-top").value = cleanQ;
  document.getElementById("query-input-home").value = cleanQ;
  executeSearch(cleanQ, skipAi);
}

function goHome() {
  window.history.pushState({}, "", window.location.pathname);
  document.getElementById("results-view").classList.add("hidden");
  document.getElementById("home-view").classList.remove("hidden");
  document.getElementById("logo-small").classList.add("hidden");
  document.getElementById("search-bar-container-top").classList.add("hidden");
  document.getElementById("query-input-home").focus();
}

async function executeSearch(query, skipAi = false) {
  currentQuery = query;
  switchToResultsView();

  const metricsEl = document.getElementById("results-metrics");
  const resultsList = document.getElementById("results-list");
  const reformBar = document.getElementById("reformulation-bar");
  reformBar.classList.add("hidden");

  metricsEl.innerText = "Searching local Base128 index and analyzing intent with MiniCPM 5:2B...";
  resultsList.innerHTML = `
    <div class="shimmer-line"></div>
    <div class="shimmer-line short"></div>
    <div class="shimmer-line"></div>
  `;

  try {
    const url = `/api/search?q=${encodeURIComponent(query)}&skip_ai=${skipAi}`;
    const res = await fetch(url);
    const data = await res.json();

    currentRawResults = data.results || [];
    metricsEl.innerText = `About ${data.total_results} results (${(data.time_ms / 1000).toFixed(2)} seconds)`;

    // Handle MiniCPM 5:2B Query Reformulation ("What you meant to say")
    if (data.did_you_mean && !skipAi) {
      reformBar.classList.remove("hidden");
      const correctedLink = document.getElementById("corrected-query-link");
      const originalLink = document.getElementById("original-query-link");
      const reasonEl = document.getElementById("reformulation-reason");

      correctedLink.innerText = data.corrected_query;
      correctedLink.onclick = () => triggerSearch(data.corrected_query, false);

      originalLink.innerText = data.raw_query;
      originalLink.onclick = () => triggerSearch(data.raw_query, true);

      reasonEl.innerText = data.reason ? `(${data.reason})` : "";
    }

    applyTabFilter();
    updateStatsDisplay(data.stats, data.spider);

    // Trigger AI Overview stream
    startAiOverview(data.effective_query || query, currentRawResults);

  } catch (err) {
    metricsEl.innerText = "Error executing search. Verify backend is running.";
    resultsList.innerHTML = `<p style="color:red;">Error: ${err.message}</p>`;
  }
}

function switchToResultsView() {
  document.getElementById("home-view").classList.add("hidden");
  document.getElementById("results-view").classList.remove("hidden");
  document.getElementById("logo-small").classList.remove("hidden");
  document.getElementById("search-bar-container-top").classList.remove("hidden");
  window.scrollTo(0, 0);
}

function applyTabFilter() {
  const aiCard = document.getElementById("ai-overview-card");
  const resultsList = document.getElementById("results-list");

  if (activeTab === "ai") {
    // AI Overview Mode
    aiCard.classList.remove("hidden");
    resultsList.classList.add("hidden");
  } else if (activeTab === "live_crawled") {
    // Autonomous Spider Crawled only
    aiCard.classList.remove("hidden");
    resultsList.classList.remove("hidden");
    const spiderResults = currentRawResults.filter(
      (r) => r.source === "autonomous_spider" || r.source === "frontier_spider"
    );
    renderResults(spiderResults);
  } else {
    // "All" Tab
    aiCard.classList.remove("hidden");
    resultsList.classList.remove("hidden");
    renderResults(currentRawResults);
  }
}

function renderResults(results) {
  const container = document.getElementById("results-list");
  if (!results || results.length === 0) {
    container.innerHTML = `
      <div style="padding: 24px 0;">
        <h3 style="font-size: 16px; margin-bottom: 8px;">No matching results in Base128 index yet.</h3>
        <p style="color: var(--text-secondary); font-size: 14px; line-height: 1.5;">
          The autonomous hyperlink spider is continuously exploring links in the background to discover and index pages across the web graph.
        </p>
      </div>
    `;
    return;
  }

  container.innerHTML = results.map((item) => {
    let domain = "web";
    let path = "";
    try {
      const u = new URL(item.url);
      domain = u.hostname;
      path = u.pathname.replace(/^\//, "").replace(/\/$/, "").replace(/\//g, " › ");
    } catch {}

    const breadcrumb = path ? `${domain} › ${path}` : domain;
    const badgeHtml = getDomainBadge(domain);
    const docId = item.doc_id || "";

    return `
      <article class="result-card">
        <div class="result-header">
          ${badgeHtml}
          <div class="result-site-info">
            <span class="result-domain">${escapeHtml(domain)}</span>
            <span class="result-breadcrumb">${escapeHtml(breadcrumb)}</span>
          </div>
        </div>
        <a href="/page/${escapeHtml(docId)}" class="result-title">
          ${escapeHtml(item.title || item.url)}
        </a>
        <div class="result-snippet">${escapeHtml(item.snippet || "No preview snippet available.")}</div>
        <div class="result-actions-bar">
          <a href="/page/${escapeHtml(docId)}" class="action-pill reader-pill">⚡ Read In-Engine</a>
          <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener" class="action-pill visit-pill">🌐 Original Link</a>
          <span class="base128-tag">⚡ Base128</span>
          ${item.score ? `<span class="base128-tag">BM25: ${item.score}</span>` : ""}
          <span class="base128-tag">Source: ${escapeHtml(item.source || 'spider')}</span>
        </div>
      </article>
    `;
  }).join("");
}

function getDomainBadge(domain) {
  const clean = domain.replace(/^www\./, "");
  const letter = (clean[0] || "W").toUpperCase();
  let hash = 0;
  for (let i = 0; i < clean.length; i++) {
    hash = clean.charCodeAt(i) + ((hash << 5) - hash);
  }
  const hue = Math.abs(hash % 360);
  return `<div class="result-favicon-badge" style="background: hsl(${hue}, 60%, 25%); color: hsl(${hue}, 85%, 85%); border-color: hsl(${hue}, 60%, 40%);">${letter}</div>`;
}

function startAiOverview(query, sources) {
  const aiContent = document.getElementById("ai-overview-content");
  const sourcesBar = document.getElementById("ai-overview-sources");

  if (sources && sources.length > 0) {
    sourcesBar.innerHTML = sources.slice(0, 5).map((s, idx) => {
      let domain = "source";
      try { domain = new URL(s.url).hostname.replace("www.", ""); } catch {}
      return `
        <a href="/page/${escapeHtml(s.doc_id || '')}" class="source-pill" title="${escapeHtml(s.title)}">
          <span>[${idx + 1}]</span>
          <span>${escapeHtml(domain)}</span>
        </a>
      `;
    }).join("");
  } else {
    sourcesBar.innerHTML = "";
  }

  aiContent.innerHTML = `
    <div class="ai-loading">
      <div class="shimmer-line"></div>
      <div class="shimmer-line short"></div>
    </div>
  `;

  let accumulatedText = "";
  const sseUrl = `/api/ai/stream?q=${encodeURIComponent(query)}`;

  fetch(sseUrl)
    .then((response) => {
      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      aiContent.innerHTML = "";

      function read() {
        reader.read().then(({ done, value }) => {
          if (done) return;
          const chunk = decoder.decode(value, { stream: true });
          const lines = chunk.split("\n");
          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const text = line.substring(6);
              if (text === "[DONE]") return;
              accumulatedText += text;
              // Clean any leaked <think> tags on the fly
              const cleanText = accumulatedText
                .replace(/<think>[\s\S]*?<\/think>/g, "")
                .replace(/<think>[\s\S]*/g, "")
                .trim();
              if (cleanText) {
                aiContent.innerHTML = formatMarkdown(cleanText);
              }
            }
          }
          read();
        }).catch(() => {
          if (!accumulatedText) {
            aiContent.innerHTML = `<p style="color:var(--text-secondary)">AI Overview generated based on Base128 disk store.</p>`;
          }
        });
      }
      read();
    })
    .catch(() => {
      aiContent.innerHTML = `<p style="color:var(--text-secondary)">AI Overview ready when model is active.</p>`;
    });
}

function formatMarkdown(text) {
  let html = escapeHtml(text);
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\[([0-9]+)\]/g, '<span class="citation-tag">[$1]</span>');
  html = html.replace(/\n\n/g, "</p><p>");
  html = html.replace(/\n/g, "<br>");
  return `<p>${html}</p>`;
}

// Modal & Spider Controls
function openSettingsModal() {
  document.getElementById("settings-modal").classList.remove("hidden");
  loadIndexStats();
}

function closeSettingsModal() {
  document.getElementById("settings-modal").classList.add("hidden");
}

async function toggleSpider() {
  try {
    const res = await fetch("/api/spider/toggle", { method: "POST" });
    const data = await res.json();
    updateSpiderButtonLabels(data.is_running);
    loadIndexStats();
  } catch {}
}

async function stepSpider() {
  try {
    const res = await fetch("/api/spider/crawl_now", { method: "POST" });
    const data = await res.json();
    loadIndexStats();
    if (currentQuery) {
      executeSearch(currentQuery);
    }
  } catch {}
}

function updateSpiderButtonLabels(isRunning) {
  const label = isRunning ? "Pause Spider" : "Resume Spider";
  const modalLabel = isRunning ? "Pause Background Spider" : "Resume Background Spider";
  document.getElementById("toggle-spider-btn").innerText = label;
  document.getElementById("modal-toggle-spider-btn").innerText = modalLabel;

  const badge = document.getElementById("spider-status-badge");
  const modalState = document.getElementById("modal-spider-state");
  if (isRunning) {
    badge.className = "badge-active";
    badge.innerText = "Active";
    modalState.innerText = "Running";
  } else {
    badge.className = "badge-paused";
    badge.innerText = "Paused";
    modalState.innerText = "Paused";
  }
}

function startStatusPolling() {
  if (spiderPollInterval) clearInterval(spiderPollInterval);
  spiderPollInterval = setInterval(loadIndexStats, 4000);
}

async function loadIndexStats() {
  try {
    const res = await fetch("/api/index/stats");
    const data = await res.json();
    updateStatsDisplay(data.storage, data.spider);
  } catch {}
}

function updateStatsDisplay(storage, spider) {
  if (storage) {
    const docsEl = document.getElementById("stat-docs");
    const vocabEl = document.getElementById("stat-vocab");
    const sizeEl = document.getElementById("stat-size");
    const badgeEl = document.getElementById("disk-badge-text");

    if (docsEl) docsEl.innerText = storage.total_documents || 0;
    if (vocabEl) vocabEl.innerText = storage.total_vocabulary_terms || 0;
    if (sizeEl) sizeEl.innerText = storage.base128_disk_formatted || "0 KB";
    if (badgeEl) badgeEl.innerText = `Base128 Store: ${storage.total_documents || 0} sites (${storage.base128_disk_formatted || '0 KB'})`;
  }

  if (spider) {
    const frontierVal = document.getElementById("spider-frontier-val");
    const crawledVal = document.getElementById("spider-crawled-val");
    const modalFrontier = document.getElementById("modal-frontier-size");
    const modalVisited = document.getElementById("modal-visited-count");

    if (frontierVal) frontierVal.innerText = spider.frontier_size || 0;
    if (crawledVal) crawledVal.innerText = spider.pages_crawled_session || 0;
    if (modalFrontier) modalFrontier.innerText = `${spider.frontier_size || 0} links`;
    if (modalVisited) modalVisited.innerText = `${spider.visited_count || 0} URLs`;

    updateSpiderButtonLabels(spider.is_running);
  }
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;")
    .replace(/on\w+\s*=/g, "") // Remove event handlers like onclick=, onerror=
    .replace(/javascript:/gi, "") // Remove javascript: protocol
    .replace(/vbscript:/gi, ""); // Remove vbscript: protocol
}
