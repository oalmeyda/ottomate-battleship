/**
 * Ottomate Battleship Client Application
 */

(function () {
  const FLEET_SPECS = {
    carrier: { name: "Carrier", size: 5, symbol: "C" },
    battleship: { name: "Battleship", size: 4, symbol: "B" },
    cruiser: { name: "Cruiser", size: 3, symbol: "R" },
    submarine: { name: "Submarine", size: 3, symbol: "S" },
    destroyer: { name: "Destroyer", size: 2, symbol: "D" },
  };

  const GRID_SIZE = 10;
  const COLUMNS = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"];

  let currentUser = null;
  let activeMatchId = null;
  let currentMatchData = null;
  let pollInterval = null;

  // Deployment Phase State
  let currentOrientation = "horizontal"; // 'horizontal' | 'vertical'
  let selectedShipId = null;
  let deployedShips = {}; // ship_id -> { ship_id, row, col, orientation }

  // --- Auth & Init ---

  async function initApp() {
    setupAuth();
    setupKeybindings();
    setupModalBackdrops();
  }

  function setupModalBackdrops() {
    document.querySelectorAll(".modal-overlay").forEach((overlay) => {
      overlay.addEventListener("click", (e) => {
        if (e.target === overlay) {
          overlay.style.display = "none";
        }
      });
    });
  }

  function setupAuth() {
    if (window.Ottomate && window.Ottomate.people && typeof window.Ottomate.people.init === "function") {
      window.Ottomate.people.init({
        appName: "Ottomate Battleship",
        onError: (msg) => console.warn(msg),
      });
    }

    if (window.Ottomate && typeof window.Ottomate.initHeader === "function") {
      window.Ottomate.initHeader({
        onSignOut: () => logout(),
        onBrandClicked: () => showLobbyView(),
        onProfileClicked: () => showProfileModal(),
        onDirectoryClicked: () => showDirectoryModal(),
      });
    }

    fetch("/api/config")
      .then((res) => res.json())
      .then((config) => {
        if (config && window.Ottomate && typeof window.Ottomate.setupSignIn === "function") {
          window.Ottomate.setupSignIn(config, async (token) => {
            if (token && typeof window.Ottomate.storeAuthToken === "function") {
              window.Ottomate.storeAuthToken(token);
            }
            await onUserSignedIn();
          });
        }
      })
      .catch((err) => console.warn("Failed to load /api/config:", err));

    const token = window.Ottomate && typeof window.Ottomate.getStoredAuthToken === "function"
      ? window.Ottomate.getStoredAuthToken()
      : null;

    if (token) {
      onUserSignedIn();
    } else {
      showSignInPrompt();
    }
  }

  async function onUserSignedIn() {
    try {
      const res = await apiFetch("/api/me");
      if (res && res.email) {
        currentUser = res;
        updateHeaderUser(currentUser);
        loadLobby();
        loadUserDatalist();
      }
    } catch (err) {
      console.error("Auth check failed:", err);
      showSignInPrompt();
    }
  }

  function showSignInPrompt() {
    if (window.Ottomate && typeof window.Ottomate.toggleAuthButtons === "function") {
      window.Ottomate.toggleAuthButtons(false);
    }
    const banner = document.getElementById("status-banner");
    banner.style.display = "flex";
    document.getElementById("turn-dot").className = "status-indicator-dot waiting-turn";
    document.getElementById("status-title").textContent = "Welcome to Ottomate Battleship";
    document.getElementById("status-subtitle").textContent = "Sign in above with your Google account or Dev mode to battle.";
    document.getElementById("lobby-view").style.display = "none";
    document.getElementById("battle-view").style.display = "none";
  }

  function updateHeaderUser(user) {
    if (window.Ottomate) {
      if (typeof window.Ottomate.updateProfilePill === "function") {
        window.Ottomate.updateProfilePill(user);
      }
      if (typeof window.Ottomate.toggleAuthButtons === "function") {
        window.Ottomate.toggleAuthButtons(true);
      }
    }
    const btnDir = document.getElementById("btn-directory");
    if (btnDir && (user.system_role === "super_admin" || user.roles?.battleship === "game_admin")) {
      btnDir.style.display = "inline-block";
    }
  }

  function logout() {
    if (window.Ottomate && typeof window.Ottomate.clearAuthToken === "function") {
      window.Ottomate.clearAuthToken();
    }
    location.reload();
  }

  function showProfileModal() {
    if (window.Ottomate && window.Ottomate.people && typeof window.Ottomate.people.showProfileModal === "function") {
      window.Ottomate.people.showProfileModal();
    }
  }
  window.showProfileModal = showProfileModal;

  function showDirectoryModal() {
    if (window.Ottomate && window.Ottomate.people && typeof window.Ottomate.people.showDirectoryModal === "function") {
      window.Ottomate.people.showDirectoryModal();
    }
  }
  window.showDirectoryModal = showDirectoryModal;

  // --- API Fetch Helper ---

  async function apiFetch(url, options = {}) {
    if (window.Ottomate && typeof window.Ottomate.api === "function") {
      return window.Ottomate.api(url, options);
    }
    const headers = options.headers || {};
    const token = window.Ottomate && typeof window.Ottomate.getStoredAuthToken === "function"
      ? window.Ottomate.getStoredAuthToken()
      : null;

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    if (options.body && typeof options.body === "object") {
      headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(options.body);
    }
    options.headers = headers;

    const res = await fetch(url, options);
    if (!res.ok) {
      let errorMsg = `HTTP ${res.status}`;
      try {
        const errJson = await res.json();
        if (errJson.detail) errorMsg = errJson.detail;
      } catch (e) {}
      throw new Error(errorMsg);
    }
    return res.json();
  }

  async function loadUserDatalist() {
    try {
      const data = await apiFetch("/api/users");
      const datalist = document.getElementById("user-datalist");
      if (datalist && data.users) {
        datalist.innerHTML = data.users
          .map((u) => `<option value="${u.email}">${u.display_name || u.email}</option>`)
          .join("");
      }
    } catch (e) {
      // Ignored if non-admin
    }
  }

  // --- Lobby & Matches ---

  window.showLobbyView = function () {
    stopPolling();
    activeMatchId = null;
    currentMatchData = null;
    document.getElementById("battle-view").style.display = "none";
    document.getElementById("status-banner").style.display = "none";
    document.getElementById("lobby-view").style.display = "block";
    loadLobby();
  };

  async function loadLobby() {
    if (!currentUser) return;
    document.getElementById("lobby-view").style.display = "block";
    const container = document.getElementById("matches-list");
    container.innerHTML = "<div style='color:#94a3b8;'>Loading active battles...</div>";

    try {
      const data = await apiFetch("/api/matches");
      renderMatchesList(data.matches || []);
    } catch (err) {
      container.innerHTML = `<div style="color:#ef4444;">Error loading matches: ${err.message}</div>`;
    }
  }

  function renderMatchesList(matches) {
    const container = document.getElementById("matches-list");
    if (!matches.length) {
      container.innerHTML = `
        <div style="grid-column: 1/-1; text-align: center; padding: 3rem 1rem; color: #94a3b8;">
          <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">⚓</div>
          <div style="font-size: 1.1rem; font-weight: 600; color: #f8fafc;">No active naval battles found</div>
          <div style="margin-top: 0.25rem;">Start a duel against an AI commander or challenge a friend!</div>
          <button class="btn btn-primary" onclick="openNewMatchModal()" style="margin-top: 1rem; background: #0284c7; border-color: #0284c7;">➕ New Battle</button>
        </div>`;
      return;
    }

    container.innerHTML = matches
      .map((m) => {
        const isP1 = m.player1_email === currentUser.email;
        const oppName = isP1 ? (m.player2_name || "Waiting for opponent...") : (m.player1_name || m.player1_email);
        const statusBadge = `<span class="badge-status badge-${m.status}">${m.status.toUpperCase()}</span>`;
        let turnText = "";
        let rematchActionHtml = "";

        if (m.status === "in_progress") {
          turnText = m.turn_player === currentUser.email ? "🟢 Your Turn" : "⏳ Opponent's Turn";
        } else if (m.status === "completed") {
          turnText = m.winner_email === currentUser.email ? "🏆 Victory" : "💥 Defeated";
          if (m.rematch_match_id) {
            rematchActionHtml = `<button class="btn btn-primary btn-sm" onclick="event.stopPropagation(); openMatch('${m.rematch_match_id}')" style="background:#22c55e; border-color:#22c55e; padding: 0.25rem 0.65rem; font-size: 0.75rem; font-weight:700;">🚀 Re-match Ready</button>`;
          } else if (m.can_rematch) {
            rematchActionHtml = `<button class="btn btn-primary btn-sm" onclick="event.stopPropagation(); handleRematch('${m.id}')" style="background:#22c55e; border-color:#22c55e; padding: 0.25rem 0.65rem; font-size: 0.75rem; font-weight:700;">🔄 Re-match</button>`;
          }
        } else {
          turnText = "🛠️ Setup Phase";
        }

        return `
          <div class="match-card" onclick="openMatch('${m.id}')">
            <div class="match-card-top">
              <span style="font-weight: 700; color: #f8fafc;">${escapeHtml(m.title)}</span>
              ${statusBadge}
            </div>
            <div style="font-size: 0.85rem; color: #94a3b8;">
              Opponent: <b style="color: #cbd5e1;">${escapeHtml(oppName)}</b>
            </div>
            <div style="font-size: 0.8rem; margin-top: 0.6rem; display: flex; justify-content: space-between; align-items: center;">
              <span style="font-weight: 600; color: #38bdf8;">${turnText}</span>
              <div style="display: flex; align-items: center; gap: 0.5rem;">
                ${rematchActionHtml}
                <span style="color: #64748b;">${m.mode === "pve" ? "🤖 AI" : "👥 PvP"}</span>
              </div>
            </div>
          </div>
        `;
      })
      .join("");
  }

  // --- Match Creation Modal ---

  window.openNewMatchModal = function () {
    document.getElementById("new-match-modal").style.display = "flex";
  };

  window.closeNewMatchModal = function () {
    document.getElementById("new-match-modal").style.display = "none";
  };

  window.toggleOpponentType = function (mode) {
    const botGroup = document.getElementById("bot-difficulty-group");
    const pvpGroup = document.getElementById("pvp-opponent-group");
    if (mode === "pve") {
      botGroup.style.display = "block";
      pvpGroup.style.display = "none";
    } else {
      botGroup.style.display = "none";
      pvpGroup.style.display = "block";
    }
  };

  window.handleCreateMatch = async function (e) {
    e.preventDefault();
    const title = document.getElementById("match-title").value;
    const mode = document.getElementById("match-mode").value;
    const bot_difficulty = document.getElementById("bot-difficulty").value;
    const opponent_email = document.getElementById("opponent-email").value.trim() || null;

    try {
      const data = await apiFetch("/api/matches", {
        method: "POST",
        body: { title, mode, bot_difficulty, opponent_email },
      });
      closeNewMatchModal();
      openMatch(data.match.id);
    } catch (err) {
      alert(`Failed to create battle: ${err.message}`);
    }
  };

  // --- Active Match Lifecycle ---

  window.openMatch = async function (matchId) {
    activeMatchId = matchId;
    document.getElementById("lobby-view").style.display = "none";
    document.getElementById("battle-view").style.display = "block";
    document.getElementById("status-banner").style.display = "flex";

    deployedShips = {};
    selectedShipId = "carrier";

    await refreshMatchState();
    startPolling();
  };

  function startPolling() {
    stopPolling();
    pollInterval = setInterval(() => {
      if (document.visibilityState === "visible" && activeMatchId) {
        refreshMatchState();
      }
    }, 2200);
  }

  function stopPolling() {
    if (pollInterval) {
      clearInterval(pollInterval);
      pollInterval = null;
    }
  }

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  let isAnimatingBotTurn = false;

  function computeActiveStreak(history, playerEmail) {
    if (!history || !history.length || !playerEmail) return { type: "none", count: 0 };
    const playerShots = history.filter((h) => h.player_email === playerEmail);
    if (!playerShots.length) return { type: "none", count: 0 };
    const lastResult = playerShots[playerShots.length - 1].result; // "hit" or "miss"
    let count = 0;
    for (let i = playerShots.length - 1; i >= 0; i--) {
      if (playerShots[i].result === lastResult) {
        count++;
      } else {
        break;
      }
    }
    return { type: lastResult, count };
  }

  async function refreshMatchState() {
    if (!activeMatchId || isAnimatingBotTurn) return;
    try {
      const data = await apiFetch(`/api/matches/${activeMatchId}`);
      currentMatchData = data;
      renderMatch(data);
    } catch (err) {
      console.error("Match refresh error:", err);
    }
  }

  function renderMatch(match) {
    renderStatusBanner(match);
    renderGridBoards(match);
    renderFleetHealth(match);
    renderHistoryFeed(match);

    const dock = document.getElementById("deployment-dock");
    if (match.status === "setup") {
      dock.style.display = "block";
      renderDeploymentDock();
    } else {
      dock.style.display = "none";
    }

    renderCompletedCard(match);
  }

  function renderStatusBanner(match) {
    const dot = document.getElementById("turn-dot");
    const title = document.getElementById("status-title");
    const subtitle = document.getElementById("status-subtitle");
    const actions = document.getElementById("status-actions");

    actions.innerHTML = "";

    if (match.status === "setup") {
      dot.className = "status-indicator-dot waiting-turn";
      title.textContent = `Setup Phase • ${match.title}`;
      const myReady = match.my_role === "player1" ? match.player1.ready : match.player2.ready;
      const oppReady = match.my_role === "player1" ? match.player2.ready : match.player1.ready;

      if (!myReady) {
        subtitle.textContent = "Deploy your 5 warships on Your Fleet Waters to commence battle.";
      } else if (!oppReady) {
        subtitle.textContent = "Fleet deployed! Waiting for opponent to position their fleet...";
      } else {
        subtitle.textContent = "Both fleets deployed. Starting combat...";
      }
    } else if (match.status === "in_progress") {
      const { lastShot } = getRecentOpponentShots(match);
      if (match.is_my_turn) {
        dot.className = "status-indicator-dot active-turn";
        title.textContent = "🎯 YOUR TURN TO FIRE!";
        if (lastShot) {
          const outcome = lastShot.result === "hit" ? "💥 HIT" : "💦 MISS";
          const sunkDetail = lastShot.sunk ? ` (Sunk your ${lastShot.ship_name}!)` : "";
          subtitle.innerHTML = `Incoming enemy strike landed at <b style="color: #fbbf24; text-decoration: underline;">${lastShot.coordinate}</b> [${outcome}${sunkDetail}]. Target coordinates acquired — launch your strike!`;
        } else {
          subtitle.textContent = "Click any coordinate on the Radar to launch an artillery strike. (Hits grant a bonus shot!)";
        }
      } else {
        dot.className = "status-indicator-dot waiting-turn";
        title.textContent = "⏳ Enemy Admiral's Turn";
        const oppName = match.my_role === "player1" ? match.player2.name : match.player1.name;
        subtitle.textContent = `Waiting for ${oppName} to fire...`;
      }

      actions.innerHTML = `
        <button class="btn btn-secondary" onclick="confirmSurrender()" style="color:#ef4444; border-color:rgba(239,68,68,0.3);">🏳️ Forfeit</button>
      `;

      // Active in-match streaks
      const playerStreak = computeActiveStreak(match.history || [], currentUser ? currentUser.email : "");
      const oppEmail = match.my_role === "player1" ? (match.player2 ? match.player2.email : "") : (match.player1 ? match.player1.email : "");
      const enemyStreak = computeActiveStreak(match.history || [], oppEmail);

      const pBadge = document.getElementById("player-streak-badge");
      if (pBadge) {
        if (playerStreak.type === "hit" && playerStreak.count >= 1) {
          pBadge.style.display = "inline-flex";
          pBadge.textContent = playerStreak.count > 1 ? `🔥 ${playerStreak.count} Streak` : `🎯 Direct Hit`;
        } else {
          pBadge.style.display = "none";
        }
      }

      const eBadge = document.getElementById("enemy-streak-badge");
      if (eBadge) {
        if (enemyStreak.type === "hit" && enemyStreak.count >= 1) {
          eBadge.style.display = "inline-flex";
          eBadge.textContent = enemyStreak.count > 1 ? `⚠️ ${enemyStreak.count} Streak 🔥` : `⚠️ Enemy Hit`;
        } else {
          eBadge.style.display = "none";
        }
      }
    } else {
      const pBadge = document.getElementById("player-streak-badge");
      if (pBadge) pBadge.style.display = "none";
      const eBadge = document.getElementById("enemy-streak-badge");
      if (eBadge) eBadge.style.display = "none";

      if (match.status === "completed") {
      const isWinner = match.winner_email === (currentUser && currentUser.email);
      dot.className = "status-indicator-dot";
      dot.style.background = isWinner ? "#22c55e" : "#ef4444";
      title.textContent = isWinner ? "🏆 NAVAL VICTORY!" : "💥 FLEET DESTROYED";
      subtitle.textContent = isWinner
        ? "All enemy vessels have been sent to the ocean floor. Outstanding command!"
        : "Your fleet has been completely sunk. Honor to the fallen.";

      let rematchBtnHtml = "";
      if (match.rematch_match_id) {
        rematchBtnHtml = `<button class="btn btn-primary" onclick="openMatch('${match.rematch_match_id}')" style="background:#22c55e; border-color:#22c55e; font-weight:750; box-shadow: 0 0 15px rgba(34,197,94,0.4);">🚀 Go to Re-match</button>`;
      } else if (match.can_rematch) {
        rematchBtnHtml = `<button class="btn btn-primary" onclick="handleRematch('${match.id}')" style="background:#22c55e; border-color:#22c55e; font-weight:750; box-shadow: 0 0 15px rgba(34,197,94,0.4);">🔄 Re-match</button>`;
      }

      actions.innerHTML = `
        ${rematchBtnHtml}
        <button class="btn btn-secondary" onclick="showLobbyView()">⚓ Return to Lobby</button>
      `;
    }
    }
  }

  function renderCompletedCard(match) {
    const card = document.getElementById("completed-match-card");
    if (!card) return;

    if (match.status !== "completed") {
      card.style.display = "none";
      return;
    }

    card.style.display = "block";
    const isWinner = match.winner_email === (currentUser && currentUser.email);
    card.className = `completed-match-card ${isWinner ? "victory" : "defeat"}`;

    const badge = document.getElementById("completed-result-badge");
    const title = document.getElementById("completed-result-title");
    const desc = document.getElementById("completed-result-desc");
    const actions = document.getElementById("completed-result-actions");

    if (badge) {
      badge.className = `completed-card-badge ${isWinner ? "victory" : "defeat"}`;
      badge.textContent = isWinner ? "🏆 NAVAL VICTORY" : "💥 FLEET SUNK";
    }

    if (title) {
      title.textContent = isWinner
        ? "All Hostile Warships Sent to the Ocean Floor!"
        : "Your Entire Fleet Has Been Sunk";
    }

    const totalRounds = match.history ? match.history.length : 0;
    if (desc) {
      desc.textContent = isWinner
        ? `Command mastery confirmed! Engagement resolved in ${totalRounds} tactical artillery strikes.`
        : `Tactical defeat recorded after ${totalRounds} incoming strikes. Regroup and fight again!`;
    }

    let rematchBtnHtml = "";
    if (match.rematch_match_id) {
      rematchBtnHtml = `<button class="btn btn-primary" onclick="openMatch('${match.rematch_match_id}')" style="background:#22c55e; border-color:#22c55e; font-weight:750; padding:0.6rem 1.4rem; font-size:1rem; box-shadow: 0 0 15px rgba(34,197,94,0.4);">🚀 Go to Re-match</button>`;
    } else if (match.can_rematch) {
      rematchBtnHtml = `<button class="btn btn-primary" onclick="handleRematch('${match.id}')" style="background:#22c55e; border-color:#22c55e; font-weight:750; padding:0.6rem 1.4rem; font-size:1rem; box-shadow: 0 0 15px rgba(34,197,94,0.4);">🔄 Re-match</button>`;
    }

    if (actions) {
      actions.innerHTML = `
        ${rematchBtnHtml}
        <button class="btn btn-secondary" onclick="showLobbyView()" style="padding:0.6rem 1.2rem; font-size:1rem;">⚓ Return to Lobby</button>
      `;
    }
  }

  // --- Grid Rendering ---

  function renderGridBoards(match) {
    renderRadarBoard(match);
    renderFleetBoard(match);
  }

  function createEmptyGridHtml(prefix) {
    let html = `<div class="grid-header-cell"></div>`;
    for (let c = 0; c < GRID_SIZE; c++) {
      html += `<div class="grid-header-cell">${COLUMNS[c]}</div>`;
    }
    for (let r = 0; r < GRID_SIZE; r++) {
      html += `<div class="grid-header-cell">${r + 1}</div>`;
      for (let c = 0; c < GRID_SIZE; c++) {
        const coord = `${COLUMNS[c]}${r + 1}`;
        html += `<div id="${prefix}-${coord}" data-coord="${coord}" data-r="${r}" data-c="${c}" class="grid-cell"></div>`;
      }
    }
    return html;
  }

  function renderRadarBoard(match) {
    const container = document.getElementById("radar-board");
    if (!container.innerHTML) {
      container.innerHTML = createEmptyGridHtml("radar");
    }

    const radar = match.radar_board || {};
    const shots = radar.shots_received || {};
    const sunkShipCoords = radar.sunk_ships_coords || {};

    const allSunkCells = new Set();
    Object.values(sunkShipCoords).forEach((cells) => cells.forEach((c) => allSunkCells.add(c)));

    const canFire = match.status === "in_progress" && match.is_my_turn;

    for (let r = 0; r < GRID_SIZE; r++) {
      for (let c = 0; c < GRID_SIZE; c++) {
        const coord = `${COLUMNS[c]}${r + 1}`;
        const cell = document.getElementById(`radar-${coord}`);
        if (!cell) continue;

        cell.className = "grid-cell";
        cell.onclick = null;

        const shot = shots[coord];
        if (shot) {
          if (shot.result === "hit") {
            cell.classList.add("hit");
            if (allSunkCells.has(coord)) {
              cell.classList.add("sunk-ship");
            }
          } else {
            cell.classList.add("miss");
          }
        } else if (canFire) {
          cell.onclick = () => handleFireShot(coord);
        } else {
          cell.classList.add("disabled");
        }
      }
    }
  }

  function getRecentOpponentShots(match) {
    const history = match.history || [];
    if (!history.length || !currentUser) return { lastShot: null, recentShots: [] };

    // Find index of the last shot made by the current user
    let lastPlayerShotIdx = -1;
    for (let i = history.length - 1; i >= 0; i--) {
      if (history[i].player_email === currentUser.email) {
        lastPlayerShotIdx = i;
        break;
      }
    }

    // Opponent shots taken since the current user's last action
    const opponentRecentShots = history
      .slice(lastPlayerShotIdx + 1)
      .filter((h) => h.player_email !== currentUser.email);

    let lastShot = null;
    if (opponentRecentShots.length > 0) {
      lastShot = opponentRecentShots[opponentRecentShots.length - 1];
    } else {
      const allOpponentShots = history.filter((h) => h.player_email !== currentUser.email);
      if (allOpponentShots.length > 0) {
        lastShot = allOpponentShots[allOpponentShots.length - 1];
      }
    }

    return { lastShot, recentShots: opponentRecentShots };
  }

  function renderFleetBoard(match) {
    const container = document.getElementById("fleet-board");
    if (!container.innerHTML) {
      container.innerHTML = createEmptyGridHtml("fleet");
    }

    const myBoard = match.my_board || {};
    const ships = match.status === "setup" ? getDeployedCoordinatesMap() : myBoard.ships || {};
    const shots = myBoard.shots_received || {};

    const occupied = {};
    Object.entries(ships).forEach(([shipId, coords]) => {
      coords.forEach((coord) => {
        occupied[coord] = shipId;
      });
    });

    const isSetup = match.status === "setup";
    const { lastShot, recentShots } = getRecentOpponentShots(match);
    const recentCoords = new Set(recentShots.map((s) => s.coordinate));

    // Update fleet header strike chip
    const strikeBadge = document.getElementById("last-strike-badge");
    if (strikeBadge) {
      if (lastShot && !isSetup) {
        strikeBadge.style.display = "inline-flex";
        strikeBadge.className = `last-strike-chip ${lastShot.result === "hit" ? "hit" : ""}`;
        strikeBadge.innerHTML = `${lastShot.result === "hit" ? "💥 Hit" : "💦 Miss"}: <b>${lastShot.coordinate}</b>`;
      } else {
        strikeBadge.style.display = "none";
      }
    }

    for (let r = 0; r < GRID_SIZE; r++) {
      for (let c = 0; c < GRID_SIZE; c++) {
        const coord = `${COLUMNS[c]}${r + 1}`;
        const cell = document.getElementById(`fleet-${coord}`);
        if (!cell) continue;

        cell.className = "grid-cell";
        cell.onclick = null;
        cell.onmouseenter = null;
        cell.onmouseleave = null;

        if (occupied[coord]) {
          cell.classList.add("ship");
        }

        const shot = shots[coord];
        if (shot) {
          if (shot.result === "hit") {
            cell.classList.add("hit");
          } else {
            cell.classList.add("miss");
          }
        }

        // Highlight latest and recent incoming enemy shots
        if (lastShot && coord === lastShot.coordinate) {
          cell.classList.add("last-incoming-shot");
          if (lastShot.result === "hit") {
            cell.classList.add("last-incoming-hit");
          } else {
            cell.classList.add("last-incoming-miss");
          }
        } else if (recentCoords.has(coord)) {
          cell.classList.add("recent-incoming-shot");
        }

        if (isSetup) {
          cell.onclick = () => handlePlaceShipAt(r, c);
          cell.onmouseenter = () => handleCellHover(r, c);
          cell.onmouseleave = () => handleCellLeave();
        }
      }
    }
  }

  function renderFleetHealth(match) {
    const myHealthContainer = document.getElementById("my-fleet-health");
    const enemyHealthContainer = document.getElementById("enemy-fleet-health");

    const mySunk = new Set((match.my_board && match.my_board.sunk_ships) || []);
    const enemySunk = new Set((match.radar_board && match.radar_board.sunk_ships) || []);

    myHealthContainer.innerHTML = Object.entries(FLEET_SPECS)
      .map(([id, spec]) => {
        const isSunk = mySunk.has(id);
        return `<span class="ship-badge ${isSunk ? "sunk" : ""}">${spec.name}</span>`;
      })
      .join("");

    enemyHealthContainer.innerHTML = Object.entries(FLEET_SPECS)
      .map(([id, spec]) => {
        const isSunk = enemySunk.has(id);
        return `<span class="ship-badge ${isSunk ? "sunk" : ""}">${spec.name}</span>`;
      })
      .join("");
  }

  function renderHistoryFeed(match) {
    const feed = document.getElementById("history-feed");
    const container = document.getElementById("feed-entries");
    const history = match.history || [];

    if (!history.length) {
      feed.style.display = "none";
      return;
    }

    feed.style.display = "block";
    container.innerHTML = history
      .slice(-10)
      .reverse()
      .map((entry) => {
        const isMe = entry.player_email === currentUser.email;
        const actorName = isMe ? "You" : "Opponent";
        const badge = entry.result === "hit"
          ? `<span class="feed-badge-hit">HIT at ${entry.coordinate}</span>`
          : `<span class="feed-badge-miss">Miss at ${entry.coordinate}</span>`;
        const sunkMsg = entry.sunk ? ` • 💥 <b>${escapeHtml(entry.ship_name)} Sunk!</b>` : "";
        return `<div class="feed-entry"><span>Turn ${entry.turn}:</span> <b>${actorName}</b> fired — ${badge}${sunkMsg}</div>`;
      })
      .join("");
  }

  // --- Fleet Placement (Setup Phase) ---

  function renderDeploymentDock() {
    const container = document.getElementById("dock-ships");
    container.innerHTML = Object.entries(FLEET_SPECS)
      .map(([id, spec]) => {
        const isPlaced = !!deployedShips[id];
        const isSelected = selectedShipId === id;
        return `
          <div class="dock-ship-item ${isSelected ? "selected" : ""} ${isPlaced ? "placed" : ""}" onclick="selectShipForPlacement('${id}')">
            <b>${spec.name}</b> (${spec.size} cells)
          </div>
        `;
      })
      .join("");

    const deployBtn = document.getElementById("btn-deploy-fleet");
    deployBtn.disabled = Object.keys(deployedShips).length !== 5;
  }

  window.selectShipForPlacement = function (shipId) {
    selectedShipId = shipId;
    renderDeploymentDock();
  };

  window.toggleOrientation = function () {
    currentOrientation = currentOrientation === "horizontal" ? "vertical" : "horizontal";
    const btn = document.getElementById("btn-rotate-ship");
    btn.textContent = `🔄 Rotate (${currentOrientation === "horizontal" ? "Horizontal" : "Vertical"})`;
    renderFleetBoard(currentMatchData);
  };

  function getShipCoordinates(shipId, row, col, orientation) {
    const size = FLEET_SPECS[shipId].size;
    const coords = [];
    for (let i = 0; i < size; i++) {
      const r = row + (orientation === "vertical" ? i : 0);
      const c = col + (orientation === "horizontal" ? i : 0);
      if (r < 0 || r >= GRID_SIZE || c < 0 || c >= GRID_SIZE) {
        return null; // out of bounds
      }
      coords.push(`${COLUMNS[c]}${r + 1}`);
    }
    return coords;
  }

  function getDeployedCoordinatesMap() {
    const map = {};
    Object.entries(deployedShips).forEach(([shipId, placement]) => {
      const coords = getShipCoordinates(
        shipId,
        placement.row,
        placement.col,
        placement.orientation
      );
      if (coords) map[shipId] = coords;
    });
    return map;
  }

  function handleCellHover(r, c) {
    if (!selectedShipId) return;
    const coords = getShipCoordinates(selectedShipId, r, c, currentOrientation);
    const existing = getDeployedCoordinatesMap();

    // Check collision with other ships
    let invalid = !coords;
    if (coords) {
      for (const [shipId, shipCoords] of Object.entries(existing)) {
        if (shipId === selectedShipId) continue;
        if (coords.some((cell) => shipCoords.includes(cell))) {
          invalid = true;
          break;
        }
      }
    }

    if (coords) {
      coords.forEach((coord) => {
        const cell = document.getElementById(`fleet-${coord}`);
        if (cell) cell.classList.add(invalid ? "ship-ghost-invalid" : "ship-ghost");
      });
    }
  }

  function handleCellLeave() {
    document.querySelectorAll(".ship-ghost, .ship-ghost-invalid").forEach((cell) => {
      cell.classList.remove("ship-ghost", "ship-ghost-invalid");
    });
  }

  function handlePlaceShipAt(r, c) {
    if (!selectedShipId) return;
    const coords = getShipCoordinates(selectedShipId, r, c, currentOrientation);
    if (!coords) return;

    // Check overlap
    const existing = getDeployedCoordinatesMap();
    for (const [shipId, shipCoords] of Object.entries(existing)) {
      if (shipId === selectedShipId) continue;
      if (coords.some((cell) => shipCoords.includes(cell))) {
        return; // Overlaps
      }
    }

    deployedShips[selectedShipId] = {
      ship_id: selectedShipId,
      row: r,
      col: c,
      orientation: currentOrientation,
    };

    // Auto-select next unplaced ship
    const unplaced = Object.keys(FLEET_SPECS).find((id) => !deployedShips[id]);
    selectedShipId = unplaced || null;

    handleCellLeave();
    renderFleetBoard(currentMatchData);
    renderDeploymentDock();
  }

  window.randomizeFleet = function () {
    const ships = Object.keys(FLEET_SPECS);
    const newDeployment = {};
    const occupied = new Set();

    for (const shipId of ships) {
      const size = FLEET_SPECS[shipId].size;
      let placed = false;
      let attempts = 0;
      while (!placed && attempts < 1000) {
        attempts++;
        const orientation = Math.random() > 0.5 ? "horizontal" : "vertical";
        const row = Math.floor(Math.random() * (orientation === "vertical" ? GRID_SIZE - size + 1 : GRID_SIZE));
        const col = Math.floor(Math.random() * (orientation === "horizontal" ? GRID_SIZE - size + 1 : GRID_SIZE));

        const coords = [];
        for (let i = 0; i < size; i++) {
          const r = row + (orientation === "vertical" ? i : 0);
          const c = col + (orientation === "horizontal" ? i : 0);
          coords.push(`${r},${c}`);
        }

        if (!coords.some((c) => occupied.has(c))) {
          coords.forEach((c) => occupied.add(c));
          newDeployment[shipId] = { ship_id: shipId, row, col, orientation };
          placed = true;
        }
      }
    }

    deployedShips = newDeployment;
    selectedShipId = null;
    renderFleetBoard(currentMatchData);
    renderDeploymentDock();
  };

  window.confirmDeployment = async function () {
    if (Object.keys(deployedShips).length !== 5) {
      alert("Please place all 5 ships before deploying.");
      return;
    }

    const payload = {
      ships: Object.values(deployedShips),
    };

    try {
      await apiFetch(`/api/matches/${activeMatchId}/deploy`, {
        method: "POST",
        body: payload,
      });
      refreshMatchState();
    } catch (err) {
      alert(`Deployment failed: ${err.message}`);
    }
  };

  // --- Firing Action ---

  async function handleFireShot(coord) {
    if (!activeMatchId || isAnimatingBotTurn) return;
    try {
      isAnimatingBotTurn = true;
      const res = await apiFetch(`/api/matches/${activeMatchId}/fire`, {
        method: "POST",
        body: { coordinate: coord },
      });
      await processTurnAnimation(coord, res);
    } catch (err) {
      alert(`Firing error: ${err.message}`);
    } finally {
      isAnimatingBotTurn = false;
      await refreshMatchState();
    }
  }

  async function processTurnAnimation(playerCoord, res) {
    if (!res || !res.shot) return;

    // 1. Render the player's shot immediately on Radar board
    const radarCell = document.getElementById(`radar-${playerCoord}`);
    if (radarCell) {
      radarCell.classList.add(res.shot.result);
      radarCell.classList.add("incoming-shot-impact");
      setTimeout(() => radarCell.classList.remove("incoming-shot-impact"), 600);
    }

    // Update player hit streak badge if hit
    const playerBadge = document.getElementById("player-streak-badge");
    if (res.shot.result === "hit") {
      const pStreak = computeActiveStreak(res.history || [], currentUser ? currentUser.email : "");
      if (playerBadge) {
        playerBadge.style.display = "inline-flex";
        playerBadge.textContent = pStreak.count > 1 ? `🔥 ${pStreak.count} Streak` : `🎯 Direct Hit`;
      }
      const title = document.getElementById("status-title");
      const subtitle = document.getElementById("status-subtitle");
      if (title && subtitle && res.status !== "completed") {
        title.textContent = pStreak.count > 1 ? `🔥🔥 ${pStreak.count}-HIT STREAK!` : "🎯 DIRECT HIT!";
        const sunkMsg = res.shot.sunk ? ` and SUNK the enemy ${res.shot.ship_name || "warship"}!` : "!";
        subtitle.innerHTML = `You struck enemy waters at <b style="color: #22c55e;">${playerCoord}</b>${sunkMsg} Target locked in — fire your bonus shot!`;
      }
      await sleep(400);
      return; // Player keeps turn!
    }

    // Player missed:
    if (playerBadge) playerBadge.style.display = "none";

    // 2. If bot responded with shots, play them out sequentially with pacing
    const botShots = res.bot_shots || [];
    if (botShots.length > 0) {
      const title = document.getElementById("status-title");
      const subtitle = document.getElementById("status-subtitle");
      const dot = document.getElementById("turn-dot");
      const enemyBadge = document.getElementById("enemy-streak-badge");

      if (dot) dot.className = "status-indicator-dot waiting-turn";
      if (title) title.textContent = "⏳ Enemy Admiral's Turn";
      if (subtitle) subtitle.innerHTML = `Salvo missed at <b style="color:#94a3b8;">${playerCoord}</b>. Enemy Admiral acquiring firing solution...`;

      await sleep(850);

      let currentEnemyStreak = 0;

      for (let i = 0; i < botShots.length; i++) {
        const bShot = botShots[i];
        const fleetCell = document.getElementById(`fleet-${bShot.coordinate}`);

        // A. Aiming phase: crosshair on targeted cell
        if (fleetCell) {
          fleetCell.classList.add("incoming-target-aiming");
        }
        if (subtitle) {
          subtitle.innerHTML = `Enemy targeting coordinates <b style="color:#f59e0b;">${bShot.coordinate}</b>...`;
        }

        await sleep(650);

        // B. Impact phase: remove aiming, apply hit/miss
        if (fleetCell) {
          fleetCell.classList.remove("incoming-target-aiming");
          fleetCell.classList.add("incoming-shot-impact");
          fleetCell.classList.add(bShot.result);
          setTimeout(() => fleetCell.classList.remove("incoming-shot-impact"), 600);
        }

        if (bShot.result === "hit") {
          currentEnemyStreak++;
          if (enemyBadge) {
            enemyBadge.style.display = "inline-flex";
            enemyBadge.textContent = currentEnemyStreak > 1
              ? `⚠️ ${currentEnemyStreak} Streak 🔥`
              : `⚠️ Enemy Hit`;
          }
          if (title) {
            title.textContent = currentEnemyStreak > 1
              ? `💥 ENEMY HIT STREAK: ${currentEnemyStreak}!`
              : `💥 ENEMY ARTILLERY HIT!`;
          }
          if (subtitle) {
            const sunkText = bShot.sunk ? ` and <b style="color:#ef4444;">SUNK your ${bShot.ship_name || "warship"}</b>!` : "!";
            subtitle.innerHTML = `Enemy struck your fleet at <b style="color:#ef4444;">${bShot.coordinate}</b>${sunkText} (🔥 ${currentEnemyStreak} in a row). Enemy fires bonus shot...`;
          }

          // Update last strike badge
          const strikeBadge = document.getElementById("last-strike-badge");
          if (strikeBadge) {
            strikeBadge.style.display = "inline-flex";
            strikeBadge.className = "last-strike-chip hit";
            strikeBadge.innerHTML = `💥 Hit: <b>${bShot.coordinate}</b>`;
          }

          // PAUSE SLOWER when bot gets it right so player can clearly register the hit!
          await sleep(bShot.sunk ? 1600 : 1350);
        } else {
          // Bot missed:
          if (enemyBadge) {
            enemyBadge.style.display = "none";
          }
          if (title) {
            title.textContent = "🎯 YOUR TURN TO FIRE!";
          }
          if (subtitle) {
            subtitle.innerHTML = `Enemy artillery missed at <b style="color:#38bdf8;">${bShot.coordinate}</b>! Enemy streak broken. Command is yours — launch strike!`;
          }

          const strikeBadge = document.getElementById("last-strike-badge");
          if (strikeBadge) {
            strikeBadge.style.display = "inline-flex";
            strikeBadge.className = "last-strike-chip";
            strikeBadge.innerHTML = `💦 Miss: <b>${bShot.coordinate}</b>`;
          }

          await sleep(800);
        }
      }
    }
  }

  window.confirmSurrender = async function () {
    if (!confirm("Are you sure you wish to surrender this naval battle?")) return;
    try {
      await apiFetch(`/api/matches/${activeMatchId}/surrender`, { method: "POST" });
      refreshMatchState();
    } catch (err) {
      alert(`Surrender error: ${err.message}`);
    }
  };

  window.handleRematch = async function (matchId) {
    try {
      const res = await apiFetch(`/api/matches/${matchId}/rematch`, { method: "POST" });
      if (res && res.rematch_match_id) {
        openMatch(res.rematch_match_id);
      }
    } catch (err) {
      alert(`Failed to start rematch: ${err.message}`);
    }
  };

  // --- Stats & Leaderboard ---

  let currentStatsScope = "all";
  let currentLeaderboardScope = "human_only";

  window.openStatsModal = async function () {
    const modal = document.getElementById("stats-modal");
    modal.style.display = "flex";
    loadUserStats();
  };

  window.switchStatsScope = function (scope) {
    currentStatsScope = scope;
    document.getElementById("btn-stats-scope-all").className = `scope-pill ${scope === "all" ? "active" : ""}`;
    document.getElementById("btn-stats-scope-human").className = `scope-pill ${scope === "human_only" ? "active" : ""}`;
    loadUserStats();
  };

  async function loadUserStats() {
    const content = document.getElementById("stats-content");
    content.innerHTML = "<div style='grid-column: 1/-1; text-align: center; color:#94a3b8; padding: 1rem;'>Loading command record...</div>";

    try {
      const stats = await apiFetch(`/api/me/stats?scope=${currentStatsScope}`);
      const rankText = stats.rank ? `#${stats.rank}` : "Unranked";
      content.innerHTML = `
        <div style="background:#1e293b; padding:0.85rem; border-radius:8px; text-align:center;">
          <div style="font-size:1.6rem; font-weight:bold; color:#38bdf8;">${stats.wins} - ${stats.losses}</div>
          <small style="color:#94a3b8;">Record (W - L)</small>
        </div>
        <div style="background:#1e293b; padding:0.85rem; border-radius:8px; text-align:center;">
          <div style="font-size:1.6rem; font-weight:bold; color:#22c55e;">${stats.win_rate}%</div>
          <small style="color:#94a3b8;">Win Rate</small>
        </div>
        <div style="background:#1e293b; padding:0.85rem; border-radius:8px; text-align:center;">
          <div style="font-size:1.6rem; font-weight:bold; color:#f59e0b;">${stats.hits} / ${stats.total_shots}</div>
          <small style="color:#94a3b8;">Artillery Hits (${stats.hit_pct}%)</small>
        </div>
        <div style="background:#1e293b; padding:0.85rem; border-radius:8px; text-align:center;">
          <div style="font-size:1.6rem; font-weight:bold; color:#f87171;">${stats.ships_sunk} / ${stats.ships_lost}</div>
          <small style="color:#94a3b8;">Sunk / Lost</small>
        </div>
        <div style="background:#1e293b; padding:0.85rem; border-radius:8px; text-align:center; border: 1px solid rgba(245, 158, 11, 0.3);">
          <div style="font-size:1.6rem; font-weight:bold; color:#fbbf24;">${stats.current_hit_streak || 0} <span style="font-size:0.9rem; color:#94a3b8;">(Max: ${stats.longest_hit_streak || 0})</span></div>
          <small style="color:#f59e0b;">🔥 Correct Hit Streak</small>
        </div>
        <div style="background:#1e293b; padding:0.85rem; border-radius:8px; text-align:center; border: 1px solid rgba(56, 189, 248, 0.2);">
          <div style="font-size:1.6rem; font-weight:bold; color:#38bdf8;">${stats.current_miss_streak || 0} <span style="font-size:0.9rem; color:#94a3b8;">(Longest: ${stats.longest_miss_streak || 0})</span></div>
          <small style="color:#94a3b8;">❄️ Miss (Cold) Streak</small>
        </div>
        <div style="background:#1e293b; padding:0.85rem; border-radius:8px; text-align:center;">
          <div style="font-size:1.6rem; font-weight:bold; color:#a855f7;">${stats.current_win_streak || 0} <span style="font-size:0.9rem; color:#94a3b8;">(Best: ${stats.max_win_streak || 0})</span></div>
          <small style="color:#94a3b8;">🏆 Match Win Streak</small>
        </div>
        <div style="background:#1e293b; padding:0.85rem; border-radius:8px; text-align:center;">
          <div style="font-size:1.6rem; font-weight:bold; color:#38bdf8;">${rankText}</div>
          <small style="color:#94a3b8;">Leaderboard Standing</small>
        </div>
        <div style="background:#1e293b; padding:0.85rem; border-radius:8px; text-align:center;">
          <div style="font-size:1.6rem; font-weight:bold; color:#eab308;">${stats.flawless_victories}</div>
          <small style="color:#94a3b8;">⭐ Flawless Victories</small>
        </div>
        <div style="background:#1e293b; padding:0.85rem; border-radius:8px; text-align:center;">
          <div style="font-size:1.6rem; font-weight:bold; color:#06b6d4;">${stats.avg_shots_to_win ? stats.avg_shots_to_win : "—"}</div>
          <small style="color:#94a3b8;">Avg Shots to Win</small>
        </div>
      `;
    } catch (err) {
      content.innerHTML = `<div style="grid-column: 1/-1; color:#ef4444; text-align:center;">Error: ${err.message}</div>`;
    }
  }

  window.closeStatsModal = function () {
    document.getElementById("stats-modal").style.display = "none";
  };

  // --- Leaderboard Modal ---

  window.openLeaderboardModal = function () {
    const modal = document.getElementById("leaderboard-modal");
    modal.style.display = "flex";
    loadLeaderboard();
  };

  window.closeLeaderboardModal = function () {
    document.getElementById("leaderboard-modal").style.display = "none";
  };

  window.switchLeaderboardScope = function (scope) {
    currentLeaderboardScope = scope;
    document.getElementById("btn-lb-scope-human").className = `scope-pill ${scope === "human_only" ? "active" : ""}`;
    document.getElementById("btn-lb-scope-all").className = `scope-pill ${scope === "all" ? "active" : ""}`;
    loadLeaderboard();
  };

  async function loadLeaderboard() {
    const container = document.getElementById("leaderboard-content");
    container.innerHTML = "<div style='text-align: center; color: #94a3b8; padding: 2rem;'>Loading fleet standings...</div>";

    try {
      const data = await apiFetch(`/api/leaderboard?scope=${currentLeaderboardScope}`);
      const list = data.leaderboard || [];

      if (!list.length) {
        container.innerHTML = `
          <div style="text-align: center; color: #94a3b8; padding: 3rem 1rem;">
            <div style="font-size: 2rem; margin-bottom: 0.5rem;">⚓</div>
            <div>No completed battles recorded for this filter yet.</div>
          </div>`;
        return;
      }

      container.innerHTML = `
        <table class="tactical-table">
          <thead>
            <tr>
              <th style="width: 44px; text-align: center;">Rank</th>
              <th>Commander</th>
              <th>Record</th>
              <th>Win %</th>
              <th>Hit %</th>
              <th>Sunk / Lost</th>
              <th>Hit Streak</th>
              <th>Win Streak</th>
              <th>Flawless</th>
            </tr>
          </thead>
          <tbody>
            ${list.map((r) => {
              const rankClass = r.rank <= 3 ? `rank-${r.rank}` : "";
              const botBadge = r.is_bot ? `<span class="bot-pill">BOT</span>` : "";
              const isMe = currentUser && r.email === currentUser.email;
              const rowClass = isMe ? "current-user-row" : "";
              return `
                <tr class="${rowClass}">
                  <td style="text-align: center;"><span class="rank-badge ${rankClass}">#${r.rank}</span></td>
                  <td>
                    <div class="commander-name" title="${escapeHtml(r.display_name)}">
                      <span>${escapeHtml(r.display_name)}</span>${botBadge}
                    </div>
                    <div class="commander-email" title="${escapeHtml(r.email)}">${escapeHtml(r.email)}</div>
                  </td>
                  <td><b class="record-val">${r.wins}</b> - <span style="color:#cbd5e1;">${r.losses}</span></td>
                  <td class="${r.win_rate >= 50 ? "win-rate-high" : "win-rate-normal"}">${r.win_rate}%</td>
                  <td class="accuracy-val">${r.hit_pct}%</td>
                  <td><span style="color:#4ade80; font-weight:700;">${r.ships_sunk}</span> <span style="color:#64748b;">/</span> <span style="color:#f87171; font-weight:700;">${r.ships_lost}</span></td>
                  <td><span style="color:#f59e0b; font-weight:700;">${r.longest_hit_streak > 0 ? `🔥 ${r.current_hit_streak || 0} <span style="font-size:0.75rem; color:#94a3b8;">(max ${r.longest_hit_streak})</span>` : "—"}</span></td>
                  <td><span style="color:#a855f7; font-weight:700;">${r.max_win_streak > 0 ? `🏆 ${r.current_win_streak || 0} <span style="font-size:0.75rem; color:#94a3b8;">(max ${r.max_win_streak})</span>` : "—"}</span></td>
                  <td><span style="color:#fbbf24; font-weight:700;">${r.flawless_victories > 0 ? `⭐ ${r.flawless_victories}` : "—"}</span></td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      `;
    } catch (err) {
      container.innerHTML = `<div style="color: #ef4444; text-align: center; padding: 2rem;">Error: ${err.message}</div>`;
    }
  }

  function setupKeybindings() {
    window.addEventListener("keydown", (e) => {
      if ((e.key === "r" || e.key === "R") && currentMatchData?.status === "setup") {
        toggleOrientation();
      }
      if (e.key === "Escape") {
        closeNewMatchModal();
        closeStatsModal();
        closeLeaderboardModal();
      }
    });
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  // Boot
  document.addEventListener("DOMContentLoaded", initApp);
})();

