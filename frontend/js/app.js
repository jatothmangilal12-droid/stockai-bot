/**
 * Angel One Research Auto-Trader AI - Frontend Engine
 * Specialized 100% for Angel One Analyst Research Calls & Instant ₹10,000 Paper Trades.
 */

function getApiBase() {
  let saved = localStorage.getItem('stockai_server_url');
  if (saved) {
    saved = saved.trim().replace(/\/+$/, '');
    if (!saved.startsWith('http://') && !saved.startsWith('https://')) {
      saved = 'http://' + saved;
    }
    return saved;
  }
  if (window.location.protocol === 'capacitor:' || window.location.protocol === 'file:' || (window.location.hostname === 'localhost' && !window.location.port)) {
    return 'http://192.168.29.28:8000';
  }
  return window.location.origin;
}

const API_BASE = getApiBase();
let currentCategory = 'Intraday';
let showPastCalls = false;
let pollingTimer = null;
let isConnected = false;

// Fallback Angel One Calls (Displayed immediately even before backend responds)
const FALLBACK_CALLS = [
  {
    call_id: "CALL_ETERNAL_001",
    symbol: "ETERNAL",
    company_name: "Zomato / Eternal Ltd",
    call_type: "Analyst call",
    category: "Intraday",
    action: "BUY",
    entry_price: 326.30,
    stop_loss: 323.00,
    target_price: 331.50,
    current_price: 326.85,
    potential_pct: 1.42,
    achieved_pct: 0.17,
    status: "ACTIVE",
    quantity: 30
  },
  {
    call_id: "CALL_PRESTIGE_002",
    symbol: "PRESTIGE",
    company_name: "Prestige Estates Projects Ltd",
    call_type: "Analyst call",
    category: "Intraday",
    action: "BUY",
    entry_price: 1395.00,
    stop_loss: 1380.00,
    target_price: 1410.00,
    current_price: 1398.90,
    potential_pct: 0.79,
    achieved_pct: 0.42,
    status: "TARGET_ACHIEVED",
    quantity: 7
  },
  {
    call_id: "CALL_KAYNES_003",
    symbol: "KAYNES",
    company_name: "Kaynes Technology India Ltd",
    call_type: "Analyst call",
    category: "Intraday",
    action: "BUY",
    entry_price: 3125.00,
    stop_loss: 3080.00,
    target_price: 3165.00,
    current_price: 3160.50,
    potential_pct: 0.14,
    achieved_pct: 1.19,
    status: "TARGET_ACHIEVED",
    quantity: 3
  }
];

const DEFAULT_PORTFOLIO = {
  total_equity: 100161.00,
  cash_balance: 90211.00,
  total_invested: 9789.00,
  unrealized_pnl: 16.50,
  open_positions: [
    {
      id: 1,
      symbol: "ETERNAL.NS",
      quantity: 30,
      entry_price: 326.30,
      current_price: 326.85,
      stop_loss: 323.00,
      target_price: 331.50,
      unrealized_pnl: 16.50,
      unrealized_pnl_pct: 0.17
    }
  ],
  closed_positions: [
    {
      id: 101,
      symbol: "KAYNES.NS",
      quantity: 3,
      entry_price: 3125.00,
      close_price: 3162.20,
      realized_pnl: 111.60,
      gain_loss_pct: 1.19,
      is_profit: true,
      close_reason: "TARGET_ACHIEVED",
      close_time: "2026-10-28 11:30:00"
    },
    {
      id: 102,
      symbol: "PRESTIGE.NS",
      quantity: 7,
      entry_price: 1395.00,
      close_price: 1400.85,
      realized_pnl: 40.95,
      gain_loss_pct: 0.42,
      is_profit: true,
      close_reason: "BOOK_PROFIT",
      close_time: "2026-10-27 14:47:00"
    }
  ]
};

function showToast(msg, isSuccess = true) {
  const t = document.getElementById('toast-container');
  if (!t) return;
  t.innerText = msg;
  t.style.borderColor = isSuccess ? '#00f59b' : '#ff3366';
  t.style.display = 'block';
  setTimeout(() => {
    t.style.display = 'none';
  }, 3500);
}

function switchMainTab(tab) {
  const tabs = ['calls', 'trades', 'ingest', 'settings'];
  tabs.forEach(t => {
    const el = document.getElementById(`view-${t}`);
    const btn = document.getElementById(`tab-btn-${t}`);
    if (el) el.style.display = t === tab ? 'block' : 'none';
    if (btn) {
      if (t === tab) btn.classList.add('active');
      else btn.classList.remove('active');
    }
  });

  if (tab === 'calls' || tab === 'trades') {
    loadCallsAndPortfolio();
  } else if (tab === 'settings') {
    checkAngelStatus();
  }
}

function filterCategory(cat, btn) {
  currentCategory = cat;
  document.querySelectorAll('#view-calls button[id^="sub-cat-"]').forEach(b => {
    b.className = 'btn btn-outline btn-sm';
  });
  if (btn) btn.className = 'btn btn-primary btn-sm';
  loadCallsAndPortfolio();
}

function togglePastCalls() {
  showPastCalls = !showPastCalls;
  const container = document.getElementById('past-calls-container');
  const btn = document.getElementById('btn-toggle-past');
  if (container) container.style.display = showPastCalls ? 'block' : 'none';
  if (btn) btn.innerText = showPastCalls ? 'Hide ▲' : 'View All ▼';
}

async function loadCallsAndPortfolio() {
  const banner = document.getElementById('server-status-banner');

  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 3000);

    // 1. Fetch Angel One calls
    const callsResp = await fetch(`${API_BASE}/api/angel-research/calls?category=${currentCategory}`, {
      signal: controller.signal
    });
    clearTimeout(timeoutId);

    const callsData = await callsResp.json();
    const calls = callsData.calls || [];

    // 2. Fetch paper trading portfolio
    const portResp = await fetch(`${API_BASE}/api/angel-research/portfolio`);
    const port = await portResp.json();

    if (banner) banner.style.display = 'none';
    isConnected = true;

    renderCalls(calls, port);
    renderPortfolio(port);
  } catch (err) {
    console.warn('Backend not reachable, rendering fallback calls:', err);
    if (banner) banner.style.display = 'flex';
    isConnected = false;

    // Filter fallback calls by category
    const filteredFallback = currentCategory === 'ALL'
      ? FALLBACK_CALLS
      : FALLBACK_CALLS.filter(c => c.category.toUpperCase() === currentCategory.toUpperCase());

    renderCalls(filteredFallback, DEFAULT_PORTFOLIO);
    renderPortfolio(DEFAULT_PORTFOLIO);
  }
}

function renderCalls(calls, port) {
  const activeContainer = document.getElementById('active-calls-container');
  const pastContainer = document.getElementById('past-calls-container');
  const countBadge = document.getElementById('calls-badge-count');

  if (!activeContainer) return;

  const activeCalls = calls.filter(c => c.status === 'ACTIVE');
  const pastCalls = calls.filter(c => c.status !== 'ACTIVE');

  if (countBadge) countBadge.innerText = activeCalls.length;

  // Render Active Today's Calls
  if (activeCalls.length === 0) {
    activeContainer.innerHTML = `
      <div style="text-align:center; padding:35px 20px; background:rgba(15, 23, 42, 0.5); border:1px dashed rgba(255, 255, 255, 0.1); border-radius:14px;">
        <span style="font-size:2rem;">📡</span>
        <div style="font-weight:700; color:#ffffff; margin-top:8px;">Listening for Angel One ${currentCategory} Calls...</div>
        <div style="font-size:0.75rem; color:var(--text-muted); margin-top:4px;">Angel One రీసెర్చ్ కాల్ ఇవ్వగానే AI వెంటనే క్యాచ్ చేసి ₹10,000 ఆటో-ట్రేడ్ చేస్తుంది!</div>
        <button class="btn btn-primary btn-sm" onclick="triggerTestCall()" style="margin-top:14px; border-radius:8px;">
          🚀 Test Sample Call Now
        </button>
      </div>
    `;
  } else {
    activeContainer.innerHTML = activeCalls.map(c => generateCallCardHtml(c)).join('');
  }

  // Render Past Calls
  if (pastContainer) {
    if (pastCalls.length === 0) {
      pastContainer.innerHTML = `<div style="text-align:center; padding:15px; color:var(--text-muted); font-size:0.8rem;">No past calls in this category.</div>`;
    } else {
      pastContainer.innerHTML = pastCalls.map(c => generateCallCardHtml(c, true)).join('');
    }
  }
}

function generateCallCardHtml(c, isPast = false) {
  const sym = c.symbol.replace('.NS', '');
  const ltp = c.current_price || c.entry_price;
  const isBuy = c.action.toUpperCase() === 'BUY';
  const entry = c.entry_price;
  const sl = c.stop_loss;
  const tgt = c.target_price;
  
  const achieved = c.achieved_pct || 0.0;
  const potential = c.potential_pct || 0.0;
  
  const changePct = entry > 0 ? (((ltp - entry) / entry) * 100).toFixed(2) : 0.0;
  const isPos = parseFloat(changePct) >= 0;

  let statusBadge = '';
  if (c.status === 'TARGET_ACHIEVED') {
    statusBadge = `<span style="background:rgba(0, 245, 155, 0.2); color:#00f59b; border:1px solid #00f59b; padding:3px 8px; border-radius:6px; font-weight:800; font-size:0.7rem;">🎯 TARGET ACHIEVED (+${achieved}%)</span>`;
  } else if (c.status === 'SL_HIT') {
    statusBadge = `<span style="background:rgba(255, 51, 102, 0.2); color:#ff3366; border:1px solid #ff3366; padding:3px 8px; border-radius:6px; font-weight:800; font-size:0.7rem;">🛑 STOP LOSS HIT</span>`;
  } else {
    statusBadge = `
      <div class="auto-trade-pill">
        <span>⚡ Auto Paper Traded: ${c.quantity || Math.max(1, Math.floor(10000 / entry))} Qty (~₹10,000)</span>
      </div>
    `;
  }

  return `
    <div class="call-card">
      <div class="analyst-badge">
        <span>🟢 ${c.call_type || 'Analyst call'}</span>
        <span style="color:var(--text-muted); font-weight:500;">• Updated live</span>
      </div>

      <div class="call-card-top">
        <div class="stock-badge-wrap">
          <div class="stock-avatar" style="${sym === 'ETERNAL' ? 'background:#e11d48;' : 'background:linear-gradient(135deg, #3b82f6 0%, #1d4ed8 100%);'}">
            ${sym.substring(0, 3)}
          </div>
          <div>
            <div class="stock-name-title">
              <span>${sym}</span>
              <span class="exchange-tag">NSE</span>
            </div>
            <div style="font-size:0.72rem; color:var(--text-muted);">${c.company_name || sym}</div>
          </div>
        </div>

        <div class="cmp-display">
          <div class="cmp-price">₹${ltp.toFixed(2)}</div>
          <div class="cmp-change" style="color:${isPos ? '#00f59b' : '#ff3366'};">
            ${isPos ? '▲ +' : '▼ '}${changePct}%
          </div>
        </div>
      </div>

      <!-- SL - Entry - Target Road Map -->
      <div class="price-road-map">
        <div class="progress-road-line"></div>

        <div class="price-node">
          <div class="price-node-badge sl">SL</div>
          <div class="price-node-label">Stop Loss</div>
          <div class="price-node-val">₹${sl.toFixed(2)}</div>
        </div>

        <div class="price-node">
          <div class="price-node-badge entry">${isBuy ? 'B' : 'S'}</div>
          <div class="price-node-label">Entry</div>
          <div class="price-node-val">₹${entry.toFixed(2)}</div>
        </div>

        <div class="price-node">
          <div class="price-node-badge target">${isBuy ? 'S' : 'B'}</div>
          <div class="price-node-label">Target</div>
          <div class="price-node-val">₹${tgt.toFixed(2)}</div>
        </div>
      </div>

      <div class="call-footer">
        <div class="potential-stats">
          <span>• Achieved: <strong style="color:${achieved > 0 ? '#00f59b' : '#ffffff'};">${achieved}%</strong></span>
          <span>• Potential Left: <strong style="color:#00e5ff;">${potential}%</strong></span>
        </div>

        <div style="display:flex; align-items:center; gap:8px;">
          ${statusBadge}
          <button class="btn-buy-action" style="${isPast ? 'background:#334155; color:#94a3b8; box-shadow:none;' : ''}">
            ${isPast ? 'CLOSED' : (isBuy ? 'BUY' : 'SELL')}
          </button>
        </div>
      </div>
    </div>
  `;
}

function renderPortfolio(port) {
  const equityVal = document.getElementById('header-equity-val');
  const portEquity = document.getElementById('port-equity-val');
  const portCash = document.getElementById('port-cash-val');
  const portInvested = document.getElementById('port-invested-val');
  const portPnl = document.getElementById('port-unrealized-pnl');
  const openCountBadge = document.getElementById('open-trades-count');
  const openList = document.getElementById('open-positions-list');
  const closedList = document.getElementById('closed-positions-list');

  const eq = port.total_equity || 100000;
  const cash = port.cash_balance || 100000;
  const invested = port.total_invested || 0;
  const uPnl = port.unrealized_pnl || 0;
  const openPositions = port.open_positions || [];
  const closedPositions = port.closed_positions || [];

  if (equityVal) equityVal.innerText = `₹${Math.round(eq).toLocaleString('en-IN')}`;
  if (portEquity) portEquity.innerText = `₹${Math.round(eq).toLocaleString('en-IN')}`;
  if (portCash) portCash.innerText = `₹${Math.round(cash).toLocaleString('en-IN')}`;
  if (portInvested) portInvested.innerText = `₹${Math.round(invested).toLocaleString('en-IN')}`;
  
  if (portPnl) {
    const isPnlPos = uPnl >= 0;
    portPnl.innerText = `${isPnlPos ? '+' : ''}₹${uPnl.toFixed(2)}`;
    portPnl.style.color = isPnlPos ? '#00f59b' : '#ff3366';
  }

  if (openCountBadge) openCountBadge.innerText = openPositions.length;

  // Render Open Positions (With Live Angel One Market Feed)
  if (openList) {
    if (openPositions.length === 0) {
      openList.innerHTML = `
        <div style="text-align:center; padding:30px; background:rgba(15, 23, 42, 0.4); border-radius:12px; color:var(--text-muted); font-size:0.8rem;">
          No active paper positions. New Angel One calls will auto-execute here with ₹10,000 allocation.
        </div>
      `;
    } else {
      openList.innerHTML = openPositions.map(p => {
        const pnl = p.unrealized_pnl || 0.0;
        const pnlPct = p.unrealized_pnl_pct || 0.0;
        const isPos = pnl >= 0;
        const sym = p.symbol.replace('.NS', '');
        const entry = p.entry_price || 0.0;
        const cmp = p.current_price || entry;
        const sl = p.stop_loss || 0.0;
        const tgt = p.target_price || 0.0;

        return `
          <div class="call-card" style="margin-bottom:12px; padding:14px; border-color:${isPos ? 'rgba(0, 245, 155, 0.3)' : 'rgba(255, 51, 102, 0.3)'};">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <div style="display:flex; align-items:center; gap:6px;">
                <span class="pulse-dot" style="${isPos ? '' : 'background:#ff3366; box-shadow:0 0 10px #ff3366;'}"></span>
                <span style="font-size:0.72rem; color:${isPos ? '#00f59b' : '#ff3366'}; font-weight:800; letter-spacing:0.5px;">LIVE ANGEL ONE TRADE</span>
              </div>
              <span class="badge" style="background:rgba(0, 229, 255, 0.15); color:#00e5ff; font-size:0.68rem; font-weight:800;">
                ₹10,000 CAPITAL (${p.quantity} SHARES)
              </span>
            </div>

            <div style="display:flex; justify-content:space-between; align-items:center;">
              <div>
                <div style="font-weight:800; font-size:1.15rem; color:#ffffff; display:flex; align-items:center; gap:6px;">
                  <span>${sym}</span>
                  <span class="exchange-tag">NSE</span>
                  <span style="font-size:0.72rem; background:rgba(0, 245, 155, 0.15); color:#00f59b; padding:1px 6px; border-radius:4px; font-weight:700;">BUY</span>
                </div>
                <div style="font-size:0.75rem; color:var(--text-muted); margin-top:3px;">
                  Entry: <strong>₹${entry.toFixed(2)}</strong> | Target: <strong style="color:#00f59b;">₹${tgt.toFixed(2)}</strong> | SL: <strong style="color:#ff3366;">₹${sl.toFixed(2)}</strong>
                </div>
              </div>

              <div style="text-align:right;">
                <div style="font-weight:800; font-size:1.25rem; font-family:var(--font-mono); color:${isPos ? '#00f59b' : '#ff3366'};">
                  ${isPos ? '+' : ''}₹${pnl.toFixed(2)}
                </div>
                <div style="font-size:0.8rem; font-weight:700; color:${isPos ? '#00f59b' : '#ff3366'};">
                  ${isPos ? '▲ +' : '▼ '}${pnlPct}% P&L
                </div>
                <div style="font-size:0.72rem; color:var(--text-secondary); margin-top:2px;">
                  Live CMP: <strong>₹${cmp.toFixed(2)}</strong>
                </div>
                <button class="btn btn-outline btn-sm" onclick="closePosition(${p.id}, ${cmp})" style="font-size:0.68rem; padding:3px 10px; margin-top:6px; border-color:rgba(255, 255, 255, 0.25);">
                  Exit Trade
                </button>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }
  }

  // Render Closed Positions History (With Clear PROFIT / LOSS Badges & % Gain/Loss)
  if (closedList) {
    if (closedPositions.length === 0) {
      closedList.innerHTML = `<div style="text-align:center; padding:20px; color:var(--text-muted); font-size:0.8rem;">No closed trades yet. Completed trades will display profit/loss and % return here.</div>`;
    } else {
      closedList.innerHTML = closedPositions.map(p => {
        const pnl = parseFloat(p.realized_pnl || 0.0);
        const gainPct = p.gain_loss_pct !== undefined ? parseFloat(p.gain_loss_pct) : (p.entry_price > 0 ? parseFloat((((p.close_price - p.entry_price) / p.entry_price) * 100).toFixed(2)) : 0.0);
        const isProfit = pnl > 0 || gainPct > 0;
        const isLoss = pnl < 0 || gainPct < 0;
        const sym = (p.symbol || 'STOCK').replace('.NS', '');
        const entry = parseFloat(p.entry_price || 0.0);
        const close = parseFloat(p.close_price || entry);
        const qty = p.quantity || 1;
        const invested = p.invested_amount || Math.round(entry * qty);

        let badgeLabel = '⚖️ BREAK-EVEN';
        let badgeBg = 'rgba(255, 255, 255, 0.1)';
        let badgeColor = '#ffffff';

        if (isProfit) {
          badgeLabel = '🟢 PROFIT (WIN)';
          badgeBg = 'rgba(0, 245, 155, 0.18)';
          badgeColor = '#00f59b';
        } else if (isLoss) {
          badgeLabel = '🔴 LOSS';
          badgeBg = 'rgba(255, 51, 102, 0.18)';
          badgeColor = '#ff3366';
        }

        let reasonLabel = p.close_reason || 'CLOSED';
        if (reasonLabel === 'TARGET_HIT' || reasonLabel === 'TARGET_ACHIEVED') reasonLabel = '🎯 Target Hit';
        else if (reasonLabel === 'STOP_LOSS_HIT' || reasonLabel === 'SL_HIT') reasonLabel = '🛑 Stop Loss Hit';
        else if (reasonLabel === 'BOOK_PROFIT') reasonLabel = '✨ Booked Profit';
        else if (reasonLabel === 'MANUAL_EXIT') reasonLabel = '✋ Manual Exit';

        return `
          <div style="background:rgba(15, 23, 42, 0.7); border:1px solid ${isProfit ? 'rgba(0, 245, 155, 0.25)' : (isLoss ? 'rgba(255, 51, 102, 0.25)' : 'rgba(255, 255, 255, 0.08)')}; border-radius:12px; padding:12px 16px; margin-bottom:10px; box-shadow:0 4px 16px rgba(0, 0, 0, 0.25);">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
              <div style="display:flex; align-items:center; gap:8px;">
                <span style="font-weight:800; font-size:1rem; color:#ffffff;">${sym}</span>
                <span style="font-size:0.68rem; background:${badgeBg}; color:${badgeColor}; border:1px solid ${badgeColor}; padding:2px 8px; border-radius:6px; font-weight:800;">
                  ${badgeLabel}
                </span>
              </div>
              <span style="font-size:0.72rem; color:var(--text-muted); font-weight:600;">
                ${reasonLabel}
              </span>
            </div>

            <div style="display:flex; justify-content:space-between; align-items:flex-end;">
              <div>
                <div style="font-size:0.78rem; color:var(--text-secondary);">
                  Entry: <strong>₹${entry.toFixed(2)}</strong> ➔ Exit: <strong>₹${close.toFixed(2)}</strong>
                </div>
                <div style="font-size:0.7rem; color:var(--text-muted); margin-top:2px;">
                  ${qty} Shares | ₹${invested.toLocaleString('en-IN')} Invested
                </div>
              </div>

              <div style="text-align:right;">
                <div style="font-size:1.15rem; font-weight:800; font-family:var(--font-mono); color:${badgeColor};">
                  ${pnl >= 0 ? '+' : ''}₹${pnl.toFixed(2)}
                </div>
                <div style="font-size:0.78rem; font-weight:700; color:${badgeColor};">
                  ${gainPct >= 0 ? '+' : ''}${gainPct.toFixed(2)}% Return
                </div>
              </div>
            </div>
          </div>
        `;
      }).join('');
    }
  }
}

async function connectAngelOne() {
  const btn = document.getElementById('btn-connect-angel');
  const badge = document.getElementById('angel-status-badge');
  const clientCode = document.getElementById('angel-client-code').value.trim();
  const apiKey = document.getElementById('angel-api-key').value.trim();
  const password = document.getElementById('angel-password').value.trim();
  const totp = document.getElementById('angel-totp').value.trim();

  if (!clientCode || !apiKey || !password || !totp) {
    showToast('Please fill all Angel One credentials!', false);
    return;
  }

  if (btn) {
    btn.disabled = true;
    btn.innerText = 'Connecting to SmartAPI...';
  }

  try {
    const resp = await fetch(`${API_BASE}/api/settings/angel-one`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_code: clientCode,
        api_key: apiKey,
        password: password,
        totp_secret: totp
      })
    });
    const res = await resp.json();

    if (res.success || res.authenticated) {
      showToast('🎉 Connected to Angel One SmartAPI successfully!');
      if (badge) {
        badge.innerText = `🟢 Connected (${res.client_code || clientCode})`;
        badge.style.background = 'rgba(0, 245, 155, 0.2)';
        badge.style.color = '#00f59b';
        badge.style.borderColor = '#00f59b';
      }
    } else {
      showToast('Connection failed: ' + (res.message || 'Check credentials'), false);
      if (badge) {
        badge.innerText = '🔴 Auth Failed';
        badge.style.background = 'rgba(255, 51, 102, 0.2)';
        badge.style.color = '#ff3366';
        badge.style.borderColor = '#ff3366';
      }
    }
  } catch (e) {
    showToast('Network error connecting to backend: ' + e, false);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = '🔗 Connect Angel One Account';
    }
  }
}

async function checkAngelStatus() {
  const badge = document.getElementById('angel-status-badge');
  if (!badge) return;

  try {
    const resp = await fetch(`${API_BASE}/api/settings/angel-one`);
    const data = await resp.json();
    if (data.authenticated) {
      badge.innerText = `🟢 Connected (${data.client_code})`;
      badge.style.background = 'rgba(0, 245, 155, 0.2)';
      badge.style.color = '#00f59b';
      badge.style.borderColor = '#00f59b';
    } else if (data.configured) {
      badge.innerText = `🟡 Configured (${data.client_code})`;
      badge.style.background = 'rgba(245, 158, 11, 0.2)';
      badge.style.color = '#f59e0b';
      badge.style.borderColor = '#f59e0b';
    } else {
      badge.innerText = '🔴 Disconnected';
      badge.style.background = 'rgba(255, 51, 102, 0.2)';
      badge.style.color = '#ff3366';
      badge.style.borderColor = '#ff3366';
    }
  } catch (e) {
    // Keep quiet if offline
  }
}

async function triggerTestCall() {
  const btn = document.getElementById('btn-trigger-test');
  if (btn) {
    btn.disabled = true;
    btn.innerText = '⚡ Catching Angel One Call & Trading ₹10k...';
  }

  try {
    const resp = await fetch(`${API_BASE}/api/angel-research/test-call`, { method: 'POST' });
    const data = await resp.json();
    if (data.success) {
      showToast(`🚀 New Angel One Call: ${data.symbol}! Auto-Executed ₹10,000 Paper Trade!`);
      loadCallsAndPortfolio();
      switchMainTab('calls');
    } else {
      showToast('Test failed: ' + (data.message || 'Unknown'), false);
    }
  } catch (err) {
    showToast('Network error triggering call: ' + err, false);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.innerText = '🚀 Trigger Sample Angel One Call (Instant ₹10k Trade)';
    }
  }
}

async function parseAndTradeNotification() {
  const txt = document.getElementById('raw-notification-input').value.trim();
  if (!txt) {
    showToast('Please paste a notification text first!', false);
    return;
  }

  try {
    const resp = await fetch(`${API_BASE}/api/angel-research/parse-text`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: txt })
    });
    const res = await resp.json();
    if (res.success) {
      showToast(`✅ Successfully parsed & executed ₹10,000 trade for ${res.parsed.symbol}!`);
      document.getElementById('raw-notification-input').value = '';
      loadCallsAndPortfolio();
      switchMainTab('calls');
    } else {
      showToast(res.message || 'Could not parse values from text', false);
    }
  } catch (e) {
    showToast('Error parsing text: ' + e, false);
  }
}

async function closePosition(posId, price) {
  try {
    const resp = await fetch(`${API_BASE}/api/paper/close/${posId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ current_price: price, reason: 'MANUAL_EXIT' })
    });
    const data = await resp.json();
    showToast(data.message || 'Position closed');
    loadCallsAndPortfolio();
  } catch (e) {
    showToast('Failed to close position: ' + e, false);
  }
}

async function resetPortfolio() {
  if (!confirm('Are you sure you want to reset virtual paper portfolio to ₹1,00,000?')) return;
  try {
    const resp = await fetch(`${API_BASE}/api/paper/reset`, { method: 'POST' });
    const res = await resp.json();
    showToast(res.message || 'Portfolio reset');
    loadCallsAndPortfolio();
  } catch (e) {
    showToast('Reset failed: ' + e, false);
  }
}

function saveServerUrl() {
  const inp = document.getElementById('setting-server-url');
  if (!inp) return;
  const url = inp.value.trim();
  if (url) {
    localStorage.setItem('stockai_server_url', url);
    showToast('Backend Server URL saved!');
    setTimeout(() => location.reload(), 800);
  }
}

// Initialization & Auto-Polling
window.addEventListener('DOMContentLoaded', () => {
  const savedUrl = localStorage.getItem('stockai_server_url') || '';
  const urlInp = document.getElementById('setting-server-url');
  if (urlInp) urlInp.value = savedUrl;

  loadCallsAndPortfolio();
  checkAngelStatus();

  // Polling every 3.5 seconds to refresh live quotes & SL/TP triggers
  pollingTimer = setInterval(loadCallsAndPortfolio, 3500);
});
