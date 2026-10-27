/**
 * Interactive 15-Minute Candlestick & RSI Canvas Chart Renderer
 * Optimized for mobile touch, high DPI rendering, EMA overlays, and pattern markers.
 */

class StockChartRenderer {
  constructor(candleCanvasId, rsiCanvasId) {
    this.candleCanvas = document.getElementById(candleCanvasId);
    this.rsiCanvas = document.getElementById(rsiCanvasId);
    this.candleCtx = this.candleCanvas.getContext('2d');
    this.rsiCtx = this.rsiCanvas.getContext('2d');
    
    this.data = [];
    this.patterns = [];
    this.hoverIndex = -1;

    this.initEvents();
  }

  setData(candles, patterns = []) {
    this.data = candles || [];
    this.patterns = patterns || [];
    this.render();
  }

  resizeCanvas(canvas, ctx) {
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const w = (rect.width > 10 ? rect.width : (canvas.clientWidth > 10 ? canvas.clientWidth : (window.innerWidth ? window.innerWidth - 32 : 360)));
    const isRsi = canvas.id && canvas.id.includes('rsi');
    const h = (rect.height > 10 ? rect.height : (canvas.clientHeight > 10 ? canvas.clientHeight : (isRsi ? 120 : 360)));
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    ctx.scale(dpr, dpr);
    return { width: w, height: h };
  }


  render() {
    if (!this.data || this.data.length === 0) return;

    this.renderCandlesticks();
    this.renderRSI();
  }

  renderCandlesticks() {
    const { width, height } = this.resizeCanvas(this.candleCanvas, this.candleCtx);
    const ctx = this.candleCtx;
    ctx.clearRect(0, 0, width, height);

    // Padding
    const padTop = 30;
    const padBottom = 30;
    const padRight = 60;
    const chartW = width - padRight;
    const chartH = height - padTop - padBottom;

    // View latest N candles (e.g. 50 bars)
    const visibleCount = Math.min(this.data.length, Math.floor(chartW / 8));
    const startIndex = Math.max(0, this.data.length - visibleCount);
    const visibleData = this.data.slice(startIndex);

    // Find Min and Max Price
    let minPrice = Infinity;
    let maxPrice = -Infinity;

    visibleData.forEach(c => {
      if (c.low < minPrice) minPrice = c.low;
      if (c.high > maxPrice) maxPrice = c.high;
      if (c.ema_9 && c.ema_9 < minPrice) minPrice = c.ema_9;
      if (c.ema_9 && c.ema_9 > maxPrice) maxPrice = c.ema_9;
      if (c.ema_21 && c.ema_21 < minPrice) minPrice = c.ema_21;
      if (c.ema_21 && c.ema_21 > maxPrice) maxPrice = c.ema_21;
    });

    const priceRange = maxPrice - minPrice || 1;
    const paddingVal = priceRange * 0.05;
    minPrice -= paddingVal;
    maxPrice += paddingVal;
    const effectiveRange = maxPrice - minPrice;

    const getY = (p) => padTop + chartH - ((p - minPrice) / effectiveRange) * chartH;
    const barSpacing = chartW / visibleData.length;
    const candleWidth = Math.max(2, barSpacing * 0.7);

    // Draw Price Grid lines
    ctx.strokeStyle = '#1e293b';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#64748b';
    ctx.font = '10px monospace';
    ctx.textAlign = 'left';

    const gridSteps = 5;
    for (let i = 0; i <= gridSteps; i++) {
      const p = minPrice + (effectiveRange * i) / gridSteps;
      const y = getY(p);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(chartW, y);
      ctx.stroke();
      ctx.fillText(p.toFixed(2), chartW + 5, y + 3);
    }

    // Draw Candlesticks
    visibleData.forEach((c, idx) => {
      const x = idx * barSpacing + barSpacing / 2;
      const openY = getY(c.open);
      const closeY = getY(c.close);
      const highY = getY(c.high);
      const lowY = getY(c.low);

      const isBull = c.close >= c.open;
      const color = isBull ? '#10b981' : '#f43f5e';
      ctx.fillStyle = color;
      ctx.strokeStyle = color;

      // Wick
      ctx.beginPath();
      ctx.moveTo(x, highY);
      ctx.lineTo(x, lowY);
      ctx.stroke();

      // Body
      const bodyY = Math.min(openY, closeY);
      const bodyH = Math.max(Math.abs(closeY - openY), 1.5);
      ctx.fillRect(x - candleWidth / 2, bodyY, candleWidth, bodyH);

      // Check if a pattern is detected on this candle
      const fullIndex = startIndex + idx;
      const matchPattern = this.patterns.find(p => p.candle_index === fullIndex);
      if (matchPattern) {
        ctx.fillStyle = matchPattern.bias === 'BULLISH' ? '#34d399' : '#fb7185';
        ctx.font = 'bold 9px sans-serif';
        ctx.textAlign = 'center';
        const labelY = matchPattern.bias === 'BULLISH' ? lowY + 14 : highY - 8;
        ctx.fillText(matchPattern.pattern, x, labelY);
        // Draw small dot
        ctx.beginPath();
        ctx.arc(x, matchPattern.bias === 'BULLISH' ? lowY + 4 : highY - 3, 2.5, 0, Math.PI * 2);
        ctx.fill();
      }
    });

    // Draw EMA 9 (Cyan)
    ctx.beginPath();
    ctx.strokeStyle = '#06b6d4';
    ctx.lineWidth = 1.5;
    let started = false;
    visibleData.forEach((c, idx) => {
      if (c.ema_9) {
        const x = idx * barSpacing + barSpacing / 2;
        const y = getY(c.ema_9);
        if (!started) { ctx.moveTo(x, y); started = true; }
        else { ctx.lineTo(x, y); }
      }
    });
    ctx.stroke();

    // Draw EMA 21 (Amber)
    ctx.beginPath();
    ctx.strokeStyle = '#f59e0b';
    ctx.lineWidth = 1.5;
    started = false;
    visibleData.forEach((c, idx) => {
      if (c.ema_21) {
        const x = idx * barSpacing + barSpacing / 2;
        const y = getY(c.ema_21);
        if (!started) { ctx.moveTo(x, y); started = true; }
        else { ctx.lineTo(x, y); }
      }
    });
    ctx.stroke();

    // Legend on Top Left
    ctx.font = '10px sans-serif';
    ctx.fillStyle = '#06b6d4';
    ctx.fillText('■ EMA 9', 10, 18);
    ctx.fillStyle = '#f59e0b';
    ctx.fillText('■ EMA 21', 75, 18);
  }

  renderRSI() {
    const { width, height } = this.resizeCanvas(this.rsiCanvas, this.rsiCtx);
    const ctx = this.rsiCtx;
    ctx.clearRect(0, 0, width, height);

    const padTop = 15;
    const padBottom = 20;
    const padRight = 60;
    const chartW = width - padRight;
    const chartH = height - padTop - padBottom;

    const visibleCount = Math.min(this.data.length, Math.floor(chartW / 8));
    const startIndex = Math.max(0, this.data.length - visibleCount);
    const visibleData = this.data.slice(startIndex);

    const getY = (rsi) => padTop + chartH - (rsi / 100) * chartH;
    const barSpacing = chartW / visibleData.length;

    // Overbought (70) and Oversold (30) lines
    ctx.strokeStyle = '#334155';
    ctx.setLineDash([4, 4]);
    ctx.lineWidth = 1;
    ctx.fillStyle = '#64748b';
    ctx.font = '9px monospace';
    ctx.textAlign = 'left';

    [70, 50, 30].forEach(level => {
      const y = getY(level);
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(chartW, y);
      ctx.stroke();
      ctx.fillText(`RSI ${level}`, chartW + 5, y + 3);
    });
    ctx.setLineDash([]);

    // Draw RSI Line
    ctx.beginPath();
    ctx.strokeStyle = '#a855f7';
    ctx.lineWidth = 1.8;
    let started = false;
    visibleData.forEach((c, idx) => {
      if (c.rsi !== null && c.rsi !== undefined) {
        const x = idx * barSpacing + barSpacing / 2;
        const y = getY(c.rsi);
        if (!started) { ctx.moveTo(x, y); started = true; }
        else { ctx.lineTo(x, y); }
      }
    });
    ctx.stroke();

    // RSI Label
    const latestRSI = visibleData.length ? visibleData[visibleData.length - 1].rsi : 50;
    ctx.fillStyle = '#a855f7';
    ctx.font = 'bold 10px sans-serif';
    ctx.fillText(`RSI (14): ${latestRSI !== null ? latestRSI : 'N/A'}`, 10, 12);
  }

  initEvents() {
    window.addEventListener('resize', () => {
      this.render();
    });
  }
}

window.StockChartRenderer = StockChartRenderer;
