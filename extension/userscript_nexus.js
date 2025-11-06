// ==UserScript==
// @name         Nexus Mobile Capture - Binary WS
// @namespace    nexus.mobile
// @version      1.0
// @description  Captura canvas do gráfico e envia via WebSocket (meta JSON + binary). Aceita comandos do backend.
// @match        *://*/*   // <-- ajuste para o domínio do HomeBroker, ex: https://homebroker.exemplo/*
// @grant        none
// ==/UserScript==

(function(){
  'use strict';
  // CONFIG
  const WS_URL = "wss://nexus-mobile-ai.onrender.com/ws?token=d33144d6cb84fe05bf38bb9f22591683";
  let PAIRS = ["EURUSD","GBPUSD","USDJPY","AUDUSD","BTCUSD"];
  let pairIndex = 0;
  let CURRENT_PAIR = PAIRS[pairIndex];
  const FPS = 1; // 1 frame per second
  const METHOD = "canvas";
  let overlay = null;
  let ws = null;
  let sending = false;

  function createOverlay(){
    overlay = document.createElement('div');
    overlay.style.position = 'fixed';
    overlay.style.right = '8px';
    overlay.style.top = '8px';
    overlay.style.zIndex = 9999999;
    overlay.style.background = 'rgba(0,0,0,0.6)';
    overlay.style.color = '#fff';
    overlay.style.padding = '8px';
    overlay.style.borderRadius = '6px';
    overlay.style.fontSize = '12px';
    overlay.style.fontFamily = 'Arial,Helvetica,sans-serif';
    overlay.innerHTML = `<div id="nexus-status">NEXUS: desconectado</div>
      <div id="nexus-pair">Pair: ${CURRENT_PAIR}</div>
      <div id="nexus-msg"></div>`;
    document.body.appendChild(overlay);
  }

  function setStatus(s){
    const el = document.getElementById('nexus-status');
    if(el) el.textContent = 'NEXUS: ' + s;
  }
  function setPair(p){
    CURRENT_PAIR = p;
    const el = document.getElementById('nexus-pair');
    if(el) el.textContent = 'Pair: ' + p;
  }
  function setMsg(m){
    const el = document.getElementById('nexus-msg');
    if(el) el.textContent = m;
  }

  function connectWS(){
    ws = new WebSocket(WS_URL);
    ws.binaryType = 'arraybuffer';
    ws.onopen = ()=>{ setStatus('conectado'); setMsg('ready'); console.log('WS open'); };
    ws.onmessage = (ev) => {
      if (typeof ev.data === 'string') {
        try {
          const obj = JSON.parse(ev.data);
          if (obj.type === 'command') {
            handleCommand(obj);
          } else {
            console.log('WS msg', obj);
          }
        } catch(e){
          console.log('WS text', e);
        }
      } else {
        // binary messages from backend (frame broadcast)
        console.log('WS binary received (viewer frame)');
      }
    };
    ws.onclose = ()=>{ setStatus('desconectado'); setMsg('reconectando...'); setTimeout(connectWS,2000); };
    ws.onerror = (e)=>{ setStatus('erro'); setMsg('ws error'); console.error(e); };
  }

  function handleCommand(obj){
    if (!obj || obj.cmd === undefined) return;
    if (obj.cmd === 'switch_pair' && obj.pair) {
      setPair(obj.pair);
      // try to set pair in page (best-effort)
      try {
        // exemplo: procurar select/input com name 'pair' ou 'symbol'
        const sel = document.querySelector('select[name*=pair], input[name*=pair], input[name*=symbol], select[id*=pair]');
        if (sel) {
          sel.value = obj.pair;
          sel.dispatchEvent(new Event('change', {bubbles:true}));
        }
      } catch(e){ console.log('switch_pair DOM set fail', e); }
    }
    if (obj.cmd === 'force_analysis') {
      setMsg('Comando: force_analysis');
      // could trigger immediate send
      captureAndSend();
    }
  }

  async function captureAndSend(){
    if (sending) return;
    sending = true;
    setMsg('capturando...');
    try {
      // try to find canvas element (most chart libs use canvas)
      let canvas = document.querySelector('canvas');
      if (!canvas) {
        // fallback: try to find chart container and use html2canvas if available
        setMsg('canvas não encontrado');
        sending = false;
        return;
      }
      // capture blob
      await new Promise((resolve, reject) => {
        canvas.toBlob(async (blob) => {
          if (!blob) { sending = false; setMsg('toBlob falhou'); reject(); return; }
          // prepare meta
          const rid = crypto.randomUUID ? crypto.randomUUID() : (Date.now().toString(36)+Math.random().toString(36).slice(2));
          const meta = { type: "meta", rid: rid, pair: CURRENT_PAIR, method: METHOD, client_ts: Date.now() };
          // send meta then binary
          try {
            if (ws && ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify(meta));
              const ab = await blob.arrayBuffer();
              ws.send(ab);
              setMsg('enviado ' + rid);
            } else {
              setMsg('ws fechado');
            }
          } catch(e){
            console.error('send error', e);
            setMsg('send error');
          }
          resolve();
        }, 'image/jpeg', 0.8);
      });
    } catch(e){
      console.error('capture error', e);
      setMsg('capture error');
    } finally {
      sending = false;
    }
  }

  function startLoop(){
    setInterval(()=> {
      captureAndSend();
    }, 1000 / FPS);
  }

  // init
  createOverlay();
  connectWS();
  startLoop();

})();
