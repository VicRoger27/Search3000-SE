// Search3000 Web Client Application

let currentQuery = "";
let currentResults = [];
let aiEventSource = null;

document.addEventListener("DOMContentLoaded", () => {
  setupEventListeners();
  loadIndexStats();

  // Handle URL query parameters (e.g. ?q=quantum)
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
  const crawlBtn = document.getElementById("crawl-url-btn");
  const regenAiBtn = document.getElementById("regenerate-ai-btn");

  homeInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") triggerSearch(homeInput.value);
  });

  topInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") triggerSearch(topInput.value);
  });

  homeSearchBtn.addEventListener("click", () => triggerSearch(homeInput.value));
  topSearchBtn.addEventListener("click", () => triggerSearch(topInput.value));
  luckyBtn.addEventListener("click", () => triggerSearch(homeInput.value || "Spark-X 2.6 LLM"));

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

  crawlBtn.addEventListener("click", handleCrawlUrl);
  regenAiBtn.addEventListener("click", () => startAiOverview(currentQuery, currentResults));
}

function triggerSearch(query, skipAi = false) {
  const cleanQ = query.trim();
  if (!cleanQ) return;
  
  // Update URL history
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

  metricsEl.innerText = "Searching local Base128 index and analyzing intent with Spark-X...";
  resultsList.innerHTML = `
    <div class="shimmer-line"></div>
    <div class="shimmer-line short"></div>
    <div class="shimmer-line"></div>
  `;

  try {
    const url = `/api/search?q=${encodeURIComponent(query)}&skip_ai=${skipAi}`;
    const res = await fetch(url);
    const data = await res.json();

    currentResults = data.results || [];
    metricsEl.innerText = `About ${data.total_results} results (${(data.time_ms / 1000).toFixed(2)} seconds)`;

    // Handle Spark-X Query Reformulation
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

    renderResults(currentResults);
    updateStatsDisplay(data.stats);

    // Trigger Streaming AI Overview
    startAiOverview(data.effective_query || query, currentResults);

  } catch (err) {
    metricsEl.innerText = "Error executing search. Please verify the backend is running.";
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

function renderResults(results) {
  const container = document.getElementById("results-list");
  if (!results || results.length === 0) {
    container.innerHTML = `
      <div style="padding: 30px 0;">
        <h3>No results found in Base128 index.</h3>
        <p style="color: var(--text-secondary); margin-top: 8px;">
          Try searching for different keywords or use the right-hand panel to index specific websites.
        </p>
      </div>
    `;
    return;
  }

  container.innerHTML = results.map((item, idx) => {
    let domain = "web";
    try {
      const parsed = new URL(item.url);
      domain = parsed.hostname;
    } catch {}

    const faviconUrl = `https://www.google.com/s2/favicons?domain=${domain}&sz=32`;

    return `
      <article class="result-card">
        <div class="result-header">
          <img src="${faviconUrl}" alt="" class="result-favicon" onerror="this.style.display='none'">
          <div class="result-site-info">
            <span class="result-domain">${escapeHtml(domain)}</span>
            <span class="result-url">${escapeHtml(item.url)}</span>
          </div>
        </div>
        <a href="${escapeHtml(item.url)}" target="_blank" rel="noopener" class="result-title">
          ${escapeHtml(item.title || item.url)}
        </a>
        <div class="result-snippet">${item.snippet || "No preview snippet available."}</div>
        <div class="result-meta">
          <span class="base128-tag">⚡ Base128 Cached</span>
          ${item.score ? `<span class="base128-tag">BM25: ${item.score}</span>` : ""}
        </div>
      </article>
    `;
  }).join("");
}

function startAiOverview(query, sources) {
  const aiContent = document.getElementById("ai-overview-content");
  const sourcesBar = document.getElementById("ai-overview-sources");

  // Render Source Pills
  if (sources && sources.length > 0) {
    sourcesBar.innerHTML = sources.slice(0, 5).map((s, idx) => {
      let domain = "source";
      try { domain = new URL(s.url).hostname.replace("www.", ""); } catch {}
      return `
        <a href="${escapeHtml(s.url)}" target="_blank" rel="noopener" class="source-pill" title="${escapeHtml(s.title)}">
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

  // Close prior event source if active
  if (aiEventSource) {
    aiEventSource.close();
    aiEventSource = null;
  }

  let accumulatedText = "";
  const sseUrl = `/api/ai/stream?q=${encodeURIComponent(query)}`;

  // Use fetch with ReadableStream for smooth token delivery
  fetch(sseUrl)
    .then(response => {
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
              aiContent.innerHTML = formatMarkdown(accumulatedText);
            }
          }
          read();
        }).catch(err => {
          aiContent.innerHTML = `<p style="color:var(--text-secondary)">AI Overview stream ended.</p>`;
        });
      }
      read();
    })
    .catch(err => {
      aiContent.innerHTML = `<p style="color:var(--text-secondary)">AI Overview unavailable.</p>`;
    });
}

function formatMarkdown(text) {
  let html = escapeHtml(text);
  // Bold **text**
  html = html.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  // Citations [1], [2] to styled pills
  html = html.replace(/\[([0-9]+)\]/g, '<span class="citation-tag">[$1]</span>');
  // Newlines to paragraphs/breaks
  html = html.replace(/\n\n/g, "</p><p>");
  html = html.replace(/\n/g, "<br>");
  return `<p>${html}</p>`;
}

async function handleCrawlUrl() {
  const input = document.getElementById("crawl-url-input");
  const statusEl = document.getElementById("crawl-status");
  const url = input.value.trim();

  if (!url || !url.startsWith("http")) {
    statusEl.innerHTML = '<span style="color:red;">Please enter a valid HTTP/HTTPS URL.</span>';
    return;
  }

  statusEl.innerHTML = '<span>Crawling & indexing into Base128 disk store...</span>';

  try {
    const res = await fetch("/api/index/crawl_url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url }),
    });
    const data = await res.json();
    if (data.status === "success") {
      statusEl.innerHTML = `<span style="color:#34a853;">Indexed successfully: ${escapeHtml(data.document.title)}</span>`;
      input.value = "";
      updateStatsDisplay(data.stats);
    } else {
      statusEl.innerHTML = `<span style="color:red;">${escapeHtml(data.message)}</span>`;
    }
  } catch (err) {
    statusEl.innerHTML = `<span style="color:red;">Error indexing site: ${err.message}</span>`;
  }
}

async function loadIndexStats() {
  try {
    const res = await fetch("/api/index/stats");
    const data = await res.json();
    updateStatsDisplay(data.storage);
  } catch {}
}

function updateStatsDisplay(stats) {
  if (!stats) return;
  const docsEl = document.getElementById("stat-docs");
  const vocabEl = document.getElementById("stat-vocab");
  const sizeEl = document.getElementById("stat-size");
  const badgeEl = document.getElementById("disk-badge-text");

  if (docsEl) docsEl.innerText = stats.total_documents || 0;
  if (vocabEl) vocabEl.innerText = stats.total_vocabulary_terms || 0;
  if (sizeEl) sizeEl.innerText = stats.base128_disk_formatted || "0 KB";
  if (badgeEl) badgeEl.innerText = `Base128 Store: ${stats.total_documents || 0} sites (${stats.base128_disk_formatted || '0 KB'})`;
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}
