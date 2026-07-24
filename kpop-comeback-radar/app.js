(function () {
  "use strict";

  const STORAGE = {
    artist: "radar.selectedArtist",
    chat: "radar.chatHistory"
  };

  const els = {
    artistSelect: document.getElementById("artistSelect"),
    artistTitle: document.getElementById("artistTitle"),
    heroWatermark: document.getElementById("heroWatermark"),
    typeBadge: document.getElementById("typeBadge"),
    memberCount: document.getElementById("memberCount"),
    timelineList: document.getElementById("timelineList"),
    timelineRange: document.getElementById("timelineRange"),
    connList: document.getElementById("connList"),
    genre: document.getElementById("genre"),
    catalogAlbums: document.getElementById("catalogAlbums"),
    releaseCover: document.getElementById("releaseCover"),
    releaseTitle: document.getElementById("releaseTitle"),
    releaseSub: document.getElementById("releaseSub"),
    videoTitle: document.getElementById("videoTitle"),
    videoMeta: document.getElementById("videoMeta"),
    scoreNum: document.getElementById("scoreNum"),
    scoreStatus: document.getElementById("scoreStatus"),
    sparkline: document.getElementById("sparkline"),
    radarChart: document.getElementById("radarChart"),
    signalBars: document.getElementById("signalBars"),
    chatLog: document.getElementById("chatLog"),
    chatInput: document.getElementById("chatInput"),
    chatSend: document.getElementById("chatSend"),
    resetBtn: document.getElementById("resetBtn"),
    clearAllBtn: document.getElementById("clearAllBtn"),
    toast: document.getElementById("toast"),
    freqAvg: document.getElementById("freqAvg"),
    freqLastYear: document.getElementById("freqLastYear"),
    freqShortest: document.getElementById("freqShortest"),
    formatChart: document.getElementById("formatChart"),
    timelineDetail: document.getElementById("timelineDetail"),
    salesLow: document.getElementById("salesLow"),
    salesMedian: document.getElementById("salesMedian"),
    salesHigh: document.getElementById("salesHigh"),
    revLow: document.getElementById("revLow"),
    revMedian: document.getElementById("revMedian"),
    revHigh: document.getElementById("revHigh"),
    physRatioSlider: document.getElementById("physRatioSlider"),
    physRatioVal: document.getElementById("physRatioVal"),
    streamMultSlider: document.getElementById("streamMultSlider"),
    streamMultVal: document.getElementById("streamMultVal"),
    tabGlobal: document.getElementById("tabGlobal"),
    tabKorean: document.getElementById("tabKorean"),
    newsSourceNote: document.getElementById("newsSourceNote"),
    newsList: document.getElementById("newsList")
  };

  let currentArtist = null;
  let chatHistory = [];
  let toastTimer = null;
  let activeNewsTab = "global";

  // ---------- helpers ----------
  function findArtist(id) {
    return RADAR_DATA.artists.find((a) => a.id === id) || RADAR_DATA.artists[0];
  }

  function showToast(msg) {
    els.toast.textContent = msg;
    els.toast.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => els.toast.classList.remove("show"), 2200);
  }

  function animateNumber(el, to, duration, format) {
    const fmt = format || ((v) => String(Math.round(v)));
    const start = performance.now();
    function tick(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      el.textContent = fmt(to * eased);
      if (t < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
  }

  const won = (v) => `₩${Math.round(v).toLocaleString("ko-KR")}`;
  const sheets = (v) => `${Math.round(v).toLocaleString("ko-KR")}장`;

  // ---------- populate selector ----------
  function populateSelect() {
    els.artistSelect.innerHTML = RADAR_DATA.artists
      .map((a) => `<option value="${a.id}">${a.emoji} ${a.name}</option>`)
      .join("");
  }

  // ---------- API connections ----------
  function renderConnections() {
    els.connList.innerHTML = RADAR_DATA.apiConnections
      .map(
        (c) => `
        <div class="conn-row">
          <span class="dot ${c.status}"></span>
          <span>${c.label}</span>
          <span class="conn-note">${c.note}</span>
        </div>`
      )
      .join("");
  }

  // ---------- timeline ----------
  function renderTimeline(artist) {
    els.timelineRange.textContent = artist.timeline.length
      ? `${artist.timeline[artist.timeline.length - 1].date} — ${artist.timeline[0].date}`
      : "—";
    els.timelineList.innerHTML = artist.timeline
      .map((t) => {
        const [y, m, d] = t.date.split("-");
        const isNow = t.tag === "now";
        return `
        <div class="timeline-row">
          <div class="timeline-date">${isNow ? '<span class="now">now</span>' : `${m}<br>${d}`}</div>
          <div class="timeline-label">${t.label}</div>
          <div class="timeline-play">${isNow ? "▶" : ""}</div>
        </div>`;
      })
      .join("");
  }

  // ---------- profile / video ----------
  function renderProfile(artist) {
    els.genre.textContent = artist.genre;
    els.catalogAlbums.textContent = artist.catalogAlbums;
    els.releaseCover.textContent = artist.emoji;
    els.releaseTitle.textContent = artist.latestRelease.title;
    els.releaseSub.textContent = `${artist.latestRelease.date} · ${artist.latestRelease.kind}`;
    els.videoTitle.textContent = artist.latestVideo.title;
    els.videoMeta.textContent = `${artist.latestVideo.channel} · 조회수 ${artist.latestVideo.views} · ${artist.latestVideo.date}`;
  }

  // ---------- score + sparkline ----------
  function renderScore(artist) {
    animateNumber(els.scoreNum, artist.score, 900);
    els.scoreStatus.textContent = artist.status.label;
    els.scoreStatus.className = `score-status tier-${artist.status.tier}`;
    drawSparkline(artist.history);
  }

  function drawSparkline(history) {
    const w = 220, h = 52, pad = 4;
    const max = Math.max(...history.map((p) => p.score), 10);
    const min = Math.min(...history.map((p) => p.score), 0);
    const step = (w - pad * 2) / (history.length - 1 || 1);
    const points = history.map((p, i) => {
      const x = pad + i * step;
      const y = h - pad - ((p.score - min) / (max - min || 1)) * (h - pad * 2);
      return [x, y];
    });
    const path = points.map((p, i) => (i === 0 ? `M${p[0]},${p[1]}` : `L${p[0]},${p[1]}`)).join(" ");
    const areaPath = `${path} L${points[points.length - 1][0]},${h} L${points[0][0]},${h} Z`;

    els.sparkline.innerHTML = `
      <defs>
        <linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--accent)" stop-opacity="0.25"/>
          <stop offset="100%" stop-color="var(--accent)" stop-opacity="0"/>
        </linearGradient>
      </defs>
      <path d="${areaPath}" fill="url(#sparkFill)" stroke="none"></path>
      <path id="sparkLine" d="${path}" fill="none" stroke="var(--accent-dark)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"></path>
      ${points
        .map((p, i) => `<circle cx="${p[0]}" cy="${p[1]}" r="${i === points.length - 1 ? 3.2 : 2}" fill="var(--accent-dark)"></circle>`)
        .join("")}
    `;
    const lineEl = document.getElementById("sparkLine");
    const len = lineEl.getTotalLength();
    lineEl.style.strokeDasharray = len;
    lineEl.style.strokeDashoffset = len;
    lineEl.getBoundingClientRect();
    lineEl.style.transition = "stroke-dashoffset 1.1s cubic-bezier(.2,.8,.2,1)";
    lineEl.style.strokeDashoffset = "0";
  }

  // ---------- radar chart ----------
  function drawRadar(artist) {
    const labels = RADAR_DATA.signalLabels;
    const keys = Object.keys(labels);
    const cx = 160, cy = 130, radius = 92;
    const angleStep = (Math.PI * 2) / keys.length;
    const rings = [0.25, 0.5, 0.75, 1];

    function pt(i, valueRatio) {
      const angle = -Math.PI / 2 + i * angleStep;
      return [cx + Math.cos(angle) * radius * valueRatio, cy + Math.sin(angle) * radius * valueRatio];
    }

    let svg = "";

    // grid rings
    rings.forEach((r) => {
      const ringPts = keys.map((_, i) => pt(i, r).join(",")).join(" ");
      svg += `<polygon points="${ringPts}" fill="none" stroke="var(--line)" stroke-width="1"></polygon>`;
    });

    // spokes + labels
    keys.forEach((k, i) => {
      const [x, y] = pt(i, 1);
      svg += `<line x1="${cx}" y1="${cy}" x2="${x}" y2="${y}" stroke="var(--line)" stroke-width="1"></line>`;
      const [lx, ly] = pt(i, 1.18);
      svg += `<text x="${lx}" y="${ly}" text-anchor="middle" dominant-baseline="middle" font-size="10" fill="var(--text-muted)">${labels[k]}</text>`;
    });

    // data polygon (animated scale-in via transform)
    const dataPts = keys.map((k, i) => pt(i, artist.signals[k] / 100).join(",")).join(" ");
    svg += `
      <polygon id="radarPoly" points="${dataPts}" fill="var(--accent)" fill-opacity="0.18" stroke="var(--accent-dark)" stroke-width="2" stroke-linejoin="round"
        style="transform-origin:${cx}px ${cy}px; transform:scale(0); transition:transform 1s cubic-bezier(.2,.8,.2,1);"></polygon>`;
    keys.forEach((k, i) => {
      const [x, y] = pt(i, artist.signals[k] / 100);
      svg += `<circle cx="${x}" cy="${y}" r="3" fill="var(--accent-dark)"></circle>`;
    });

    els.radarChart.innerHTML = svg;
    const poly = document.getElementById("radarPoly");
    requestAnimationFrame(() => {
      poly.getBoundingClientRect();
      poly.style.transform = "scale(1)";
    });
  }

  function renderSignalBars(artist) {
    const labels = RADAR_DATA.signalLabels;
    els.signalBars.innerHTML = Object.keys(labels)
      .map(
        (k) => `
        <div class="signal-bar-row">
          <div class="label-row"><span>${labels[k]}</span><b>${artist.signals[k]}</b></div>
          <div class="bar-track"><div class="bar-fill" data-target="${artist.signals[k]}"></div></div>
        </div>`
      )
      .join("");
    requestAnimationFrame(() => {
      els.signalBars.querySelectorAll(".bar-fill").forEach((el) => {
        el.style.width = el.dataset.target + "%";
      });
    });
  }

  // ---------- release frequency ----------
  function renderReleaseFrequency(artist) {
    const f = artist.releaseFrequency;
    els.freqAvg.textContent = `${f.avgIntervalDays}일`;
    els.freqLastYear.textContent = `${f.releasesLastYear}회`;
    els.freqShortest.textContent = `${f.shortestIntervalDays}일`;
    drawFormatChart(f.byFormat);
    renderTimelineDetail(artist.timeline);
  }

  function drawFormatChart(byFormat) {
    const w = 480, h = 200;
    const padL = 30, padR = 10, padT = 24, padB = 30;
    const chartW = w - padL - padR;
    const chartH = h - padT - padB;
    const max = Math.max(...byFormat.map((f) => f.count), 1);
    const gap = 28;
    const barW = (chartW - gap * (byFormat.length - 1)) / byFormat.length;

    let svg = "";
    // gridlines
    const gridSteps = 4;
    for (let i = 0; i <= gridSteps; i++) {
      const y = padT + chartH - (chartH / gridSteps) * i;
      const val = Math.round((max / gridSteps) * i);
      svg += `<line x1="${padL}" y1="${y}" x2="${w - padR}" y2="${y}" stroke="var(--line)" stroke-width="1"></line>`;
      svg += `<text x="${padL - 8}" y="${y + 3}" text-anchor="end" font-size="10" fill="var(--text-muted)">${val}</text>`;
    }

    byFormat.forEach((f, i) => {
      const x = padL + i * (barW + gap);
      const targetH = max ? (f.count / max) * chartH : 0;
      const y = padT + chartH - targetH;
      svg += `<rect x="${x}" y="${padT + chartH}" width="${barW}" height="0" rx="3" fill="var(--accent)" data-y="${y}" data-h="${targetH}" class="fmt-bar"></rect>`;
      svg += `<text x="${x + barW / 2}" y="${y - 8}" text-anchor="middle" font-size="12" font-weight="700" fill="var(--text-primary)" class="fmt-val" data-final="${y - 8}">0</text>`;
      svg += `<text x="${x + barW / 2}" y="${h - 8}" text-anchor="middle" font-size="11" fill="var(--text-secondary)">${f.label}</text>`;
    });

    els.formatChart.innerHTML = svg;

    requestAnimationFrame(() => {
      els.formatChart.querySelectorAll(".fmt-bar").forEach((bar, i) => {
        bar.style.transition = "y 0.9s cubic-bezier(.2,.8,.2,1), height 0.9s cubic-bezier(.2,.8,.2,1)";
        bar.setAttribute("y", bar.dataset.y);
        bar.setAttribute("height", bar.dataset.h);
      });
      const labels = els.formatChart.querySelectorAll(".fmt-val");
      byFormat.forEach((f, i) => animateNumber(labels[i], f.count, 900));
    });
  }

  function renderTimelineDetail(timeline) {
    els.timelineDetail.innerHTML = timeline
      .map(
        (t) => `
        <div class="timeline-row">
          <div class="timeline-date">${t.tag === "now" ? '<span class="now">now</span>' : t.date}</div>
          <div class="timeline-label">${t.label}</div>
          <div></div>
        </div>`
      )
      .join("");
  }

  // ---------- sales / revenue prediction ----------
  function renderSalesPrediction(artist) {
    const a = artist.salesPrediction.assumptions;
    els.physRatioSlider.value = a.physicalRatio;
    els.streamMultSlider.value = Math.round(a.streamMultiplier * 100);
    computeAndRenderPrediction(artist);
  }

  function computeAndRenderPrediction(artist) {
    const base = artist.salesPrediction;
    const baseRatio = base.assumptions.physicalRatio;
    const baseMult = base.assumptions.streamMultiplier;
    const curRatio = Number(els.physRatioSlider.value);
    const curMult = Number(els.streamMultSlider.value) / 100;

    els.physRatioVal.textContent = `${curRatio}%`;
    els.streamMultVal.textContent = `${curMult.toFixed(2)}x`;

    const physFactor = curRatio / baseRatio;
    const revFactor = (curRatio / baseRatio) * 0.5 + (curMult / baseMult) * 0.5;

    animateNumber(els.salesLow, base.firstWeek.low * physFactor, 500, sheets);
    animateNumber(els.salesMedian, base.firstWeek.median * physFactor, 500, sheets);
    animateNumber(els.salesHigh, base.firstWeek.high * physFactor, 500, sheets);

    animateNumber(els.revLow, base.revenue.low * revFactor, 500, won);
    animateNumber(els.revMedian, base.revenue.median * revFactor, 500, won);
    animateNumber(els.revHigh, base.revenue.high * revFactor, 500, won);
  }

  // ---------- news monitor ----------
  const NEWS_NOTES = {
    global: "Mediastack을 통해 수집한 영문권 기사입니다. (데모)",
    korean: "Naver News를 통해 수집한 국내 기사입니다. (데모)"
  };

  function setNewsTab(tab) {
    activeNewsTab = tab;
    els.tabGlobal.classList.toggle("active", tab === "global");
    els.tabKorean.classList.toggle("active", tab === "korean");
    els.newsSourceNote.textContent = NEWS_NOTES[tab];
    renderNews(currentArtist);
  }

  function renderNews(artist) {
    const items = artist.news[activeNewsTab] || [];
    if (!items.length) {
      els.newsList.innerHTML = `<div class="news-empty">표시할 뉴스가 없습니다.</div>`;
      return;
    }
    els.newsList.innerHTML = items
      .map(
        (n) => `
        <div class="news-item">
          <div class="news-title">${n.title}</div>
          <div class="news-meta">${n.source} · ${n.date}</div>
        </div>`
      )
      .join("");
  }

  // ---------- hero / badges ----------
  function renderHero(artist) {
    els.artistTitle.textContent = artist.name;
    els.heroWatermark.textContent = artist.emoji;
    els.typeBadge.textContent = artist.type === "group" ? "GROUP" : "SOLO";
    els.typeBadge.className = `badge ${artist.type}`;
    els.memberCount.textContent = `멤버: ${artist.members}명`;
  }

  // ---------- chat ----------
  function renderChat() {
    els.chatLog.innerHTML = chatHistory
      .map((m) => `<div class="chat-msg ${m.role}"><div class="chat-bubble">${m.text}</div></div>`)
      .join("");
    els.chatLog.scrollTop = els.chatLog.scrollHeight;
  }

  function saveChat() {
    localStorage.setItem(STORAGE.chat, JSON.stringify(chatHistory));
  }

  function demoReply(question, artist) {
    const q = question.toLowerCase();
    if (q.includes("스코어") || q.includes("점수") || q.includes("신호")) {
      return `${artist.name}의 현재 데모 레이더 점수는 ${artist.score}점이며, 상태는 "${artist.status.label}"입니다.`;
    }
    if (q.includes("유튜브") || q.includes("youtube") || q.includes("mv") || q.includes("영상")) {
      return `최신 공식 영상은 "${artist.latestVideo.title}"(${artist.latestVideo.date})이며, YouTube 반응 신호는 ${artist.signals.youtube}/100입니다.`;
    }
    if (q.includes("발매") || q.includes("컴백") || q.includes("앨범") || q.includes("싱글")) {
      return `가장 최근 발매작은 "${artist.latestRelease.title}"(${artist.latestRelease.date}, ${artist.latestRelease.kind})입니다.`;
    }
    if (q.includes("뉴스")) {
      return `뉴스 버즈 신호는 ${artist.signals.news}/100 입니다. (Mediastack·Naver News 데모 값)`;
    }
    return `${artist.name} 데모 데이터 기준: 레이더 점수 ${artist.score}점, 발매 최신성 ${artist.signals.recency}/100, YouTube 반응 ${artist.signals.youtube}/100 입니다. 실제 API 연결 없이 표시되는 데모 응답입니다.`;
  }

  function sendChat() {
    const val = els.chatInput.value.trim();
    if (!val || !currentArtist) return;
    chatHistory.push({ role: "user", text: escapeHtml(val) });
    renderChat();
    els.chatInput.value = "";
    updateSendState();
    setTimeout(() => {
      chatHistory.push({ role: "bot", text: escapeHtml(demoReply(val, currentArtist)) });
      renderChat();
      saveChat();
    }, 420);
  }

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }

  function updateSendState() {
    els.chatSend.classList.toggle("active", els.chatInput.value.trim().length > 0);
  }

  // ---------- artist switch ----------
  function selectArtist(id, { persist = true } = {}) {
    currentArtist = findArtist(id);
    els.artistSelect.value = currentArtist.id;
    renderHero(currentArtist);
    renderTimeline(currentArtist);
    renderProfile(currentArtist);
    renderScore(currentArtist);
    drawRadar(currentArtist);
    renderSignalBars(currentArtist);
    renderReleaseFrequency(currentArtist);
    renderSalesPrediction(currentArtist);
    activeNewsTab = "global";
    setNewsTab("global");
    if (persist) localStorage.setItem(STORAGE.artist, currentArtist.id);
  }

  // ---------- data reset ----------
  function clearAllData() {
    const ok = window.confirm("이 브라우저에 저장된 모든 테스트 데이터(선택 아티스트, 채팅 기록)를 삭제할까요?\n삭제 후에는 기본 상태로 초기화됩니다.");
    if (!ok) return;
    localStorage.removeItem(STORAGE.artist);
    localStorage.removeItem(STORAGE.chat);
    chatHistory = [];
    renderChat();
    selectArtist(RADAR_DATA.artists[0].id, { persist: false });
    showToast("전체 데이터가 초기화되었습니다.");
  }

  // ---------- init ----------
  function init() {
    populateSelect();
    renderConnections();

    try {
      chatHistory = JSON.parse(localStorage.getItem(STORAGE.chat) || "[]");
    } catch (e) {
      chatHistory = [];
    }
    renderChat();

    const savedId = localStorage.getItem(STORAGE.artist);
    selectArtist(savedId && findArtist(savedId) ? savedId : RADAR_DATA.artists[0].id, { persist: false });

    els.artistSelect.addEventListener("change", (e) => selectArtist(e.target.value));
    els.chatInput.addEventListener("input", updateSendState);
    els.chatInput.addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });
    els.chatSend.addEventListener("click", sendChat);
    els.resetBtn.addEventListener("click", clearAllData);
    els.clearAllBtn.addEventListener("click", clearAllData);

    els.physRatioSlider.addEventListener("input", () => computeAndRenderPrediction(currentArtist));
    els.streamMultSlider.addEventListener("input", () => computeAndRenderPrediction(currentArtist));
    els.tabGlobal.addEventListener("click", () => setNewsTab("global"));
    els.tabKorean.addEventListener("click", () => setNewsTab("korean"));
  }

  document.addEventListener("DOMContentLoaded", init);
})();
