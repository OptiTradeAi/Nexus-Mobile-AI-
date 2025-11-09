// ==UserScript==
// @name         Nexus Stream - HomeBroker Capture (WS + fallback)
// @namespace    http://nexus-mobile-ai.onrender.com
// @version      1.0
// @description  Captura gráfico HomeBroker: frames + ticks -> envia via WSS para Nexus backend
// @match        https://www.homebroker.com/pt/invest*
// @grant        none
// @run-at       document-idle
// ==/UserScript==

(function(){
  'use strict';

  const WS_URL = "wss://nexus-mobile-ai.onrender.com/ws/stream";
  const POST_URL = "https://nexus-mobile-ai.onrender.com/frame";
  const CAP_MS = 1500; // capture interval (1.5s) -> tradeoff latency/bandwidth
  const JPEG_QUALITY = 0.7;

  let ws = null;
  let connected = false;
  let lastSent = 0;

  function log(...args){ console.log('[nexus-stream]', ...args); }

  function connect(){
    try {
      ws = new WebSocket(WS_URL);
      ws.onopen = () => { connected = true; log('ws open'); showStatus('Conectado (WS)'); };
      ws.onclose = ()=> { connected = false; log('ws closed'); showStatus('Desconectado (WS) - reconectando'); setTimeout(connect, 2000); };
      ws.onerror = (e)=> { connected = false; log('ws error', e); };
      ws.onmessage = (m)=> { /* ignore for now */ };
    } catch(e){ connected=false; setTimeout(connect,2000); }
  }

  // small overlay
  function showStatus(t){ let d=document.getElementById('nexus_status'); if(!d){ d=document.createElement('div'); d.id='nexus_status'; d.style.cssText='position:fixed;bottom:14px;left:14px;background:#0b1220;color:#fff;padding:8px;border-radius:8px;z-index:9999999;font-size:13px'; document.body.appendChild(d);} d.textContent = t; }

  async function captureFrameAndSend(el){
    try {
      if(!el) el = document.querySelector('#chart, .chart, .tv-lightweight-charts, canvas') || document.body;
      // try using html2canvas if present
      if(typeof html2canvas === 'undefined'){
        const s = document.createElement('script');
        s.src = 'https://html2canvas.hertzen.com/dist/html2canvas.min.js';
        document.head.appendChild(s);
        await new Promise(res => s.onload = res);
      }
      const canvas = await html2canvas(el, {useCORS:true, allowTaint:true, backgroundColor:null, scale: 1});
      const dataUrl = canvas.toDataURL('image/jpeg', JPEG_QUALITY);
      const b64 = dataUrl.split(',')[1];

      const payload = { type:'frame', pair: document.title || 'HOME/OTC', data: b64 };
      if(connected && ws && ws.readyState === WebSocket.OPEN){
        ws.send(JSON.stringify(payload));
      } else {
        // fallback to POST
        fetch(POST_URL, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload)});
      }
      lastSent = Date.now();
      showStatus('Enviado frame ' + new Date().toLocaleTimeString());
    } catch(err){
      console.error(err);
      showStatus('Erro captura: ' + (err.message||err));
    }
  }

  // attempt to extract candle/tick data via DOM (best-effort)
  function extractTick() {
    try {
      // selectors: adapt if needed
      const pairEl = document.querySelector('[class*="symbol"], .pair-name, .symbol-name') || document.querySelector('.asset-title');
      const priceEl = document.querySelector('[class*="price"], .last-price, .current-price, .real-price') || document.querySelector('.price-display');
      if(!priceEl) return null;
      const pair = pairEl ? pairEl.textContent.trim() : 'HOME/OTC';
      const price = parseFloat((priceEl.textContent||'').replace(/[^0-9.,-]/g,'').replace(',','.')) || 0;
      const now = new Date();
      // For best results we need open/high/low/close of last candle; fallback: use price as open/close
      return { pair: pair, timestamp: now.toISOString(), open: price, high: price, low: price, close: price, volume: 0, timeframe: 'M5' };
    } catch(e){ return null; }
  }

  async function sendTickIfAny() {
    const tick = extractTick();
    if(tick){
      const payload = { type: 'tick', tick: tick };
      if(connected && ws && ws.readyState === WebSocket.OPEN){
        ws.send(JSON.stringify(payload));
      } else {
        fetch(POST_URL, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({type:'frame', pair: tick.pair, data: ''})}).catch(()=>{});
      }
    }
  }

  // start loops
  (function init(){
    connect();
    showStatus('iniciando...');
    setInterval(()=>{ captureFrameAndSend(); sendTickIfAny(); }, CAP_MS);
    // quick UI indicator
    const btn = document.createElement('div');
    btn.style.cssText='position:fixed;top:10px;right:10px;background:linear-gradient(90deg,#0ea5a4,#0284c7);color:#fff;padding:8px;border-radius:8px;z-index:99999999;font-weight:700';
    btn.textContent = 'Nexus Stream';
    document.body.appendChild(btn);
  })();

})();
