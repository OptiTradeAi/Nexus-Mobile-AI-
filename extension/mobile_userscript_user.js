// ==UserScript==
// @name         Nexus Mobile - Chart Streamer + Auto Switch Pairs
// @version      1.2
// @match        https://app.homebroker.com/*
// @run-at       document-idle
// @grant        none
// @connect      nexus-mobile-ai.onrender.com
// ==/UserScript==

(async function(){
  console.log('[Nexus userScript] iniciando');
  // URL do seu backend (já configurada)
  const BACKEND_URL = 'https://nexus-mobile-ai.onrender.com';
  const POST_ENDPOINT = `${BACKEND_URL}/frame`;

  // CONFIGURAÇÃO PRINCIPAL
  const FPS = 0.8;               // frames por segundo por par (ajuste)
  const MAX_WIDTH = 900;
  const QUALITY = 0.6;
  const AUTO_SWITCH = true;      // true: script alterna pares automaticamente
  const PAIRS = [                // Ajuste conforme rótulos visíveis na UI da sua corretora
    'EURUSD-OTC', 'USDJPY-OTC', 'GBPUSD-OTC'
  ];
  const SWITCH_DELAY_MS = 1800;  // tempo para esperar o gráfico renderizar após trocar o par
  const BETWEEN_PAIRS_DELAY = 200; // tempo adicional entre passos

  function findChartElement() {
    const canvases = Array.from(document.querySelectorAll('canvas'));
    let best = null;
    canvases.forEach(c => {
      const rect = c.getBoundingClientRect();
      if(rect.width > 120 && rect.height > 80 && !c.style.display.includes('none')) {
        if(!best || rect.width*rect.height > best.area) {
          best = {el: c, area: rect.width*rect.height};
        }
      }
    });
    if(best) return best.el;
    const possible = document.querySelector('[data-chart]') || document.querySelector('.chart') || document.querySelector('#chart');
    return possible;
  }

  async function loadHtml2canvas() {
    if(window.html2canvas) return window.html2canvas;
    await new Promise((res, rej) => {
      const s = document.createElement('script');
      s.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
      s.onload = res; s.onerror = rej;
      document.head.appendChild(s);
    });
    return window.html2canvas;
  }

  function canvasToDataURL(canvas, maxW=MAX_WIDTH, quality=QUALITY) {
    const w = canvas.width || canvas.offsetWidth || 800;
    const h = canvas.height || canvas.offsetHeight || Math.round(w*0.6);
    let nw = w, nh = h;
    if(w > maxW) {
      nw = maxW;
      nh = Math.round(h * (maxW / w));
    }
    const tmp = document.createElement('canvas');
    tmp.width = nw; tmp.height = nh;
    const ctx = tmp.getContext('2d');
    try {
      ctx.drawImage(canvas, 0, 0, nw, nh);
    } catch(e) {
      console.warn('[Nexus userScript] drawImage falhou (possível canvas tainted)', e);
      return null;
    }
    return tmp.toDataURL('image/jpeg', quality);
  }

  async function sendFramePOST(pair, b64data) {
    try {
      await fetch(POST_ENDPOINT, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({type:'frame', pair: pair, data: b64data})
      });
    } catch(e) {
      console.warn('[Nexus userScript] Erro envio POST frame', e);
    }
  }

  async function switchToPair(targetPair) {
    const xpathExact = `//button[normalize-space(text())='${targetPair}'] | //a[normalize-space(text())='${targetPair}'] | //span[normalize-space(text())='${targetPair}']`;
    let el = document.evaluate(xpathExact, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
    if(el && el.click) { el.click(); await sleep(50); return true; }

    const selects = Array.from(document.querySelectorAll('select'));
    for(const s of selects){
      const opt = Array.from(s.options).find(o => o.text.trim() === targetPair || o.value.trim() === targetPair);
      if(opt) { s.value = opt.value; s.dispatchEvent(new Event('change',{bubbles:true})); await sleep(50); return true; }
    }

    const all = Array.from(document.querySelectorAll('button, a, span, div, li'));
    for(const candidate of all){
      if(candidate.innerText && candidate.innerText.trim() === targetPair) {
        try { candidate.click(); await sleep(50); return true; } catch(e){}
      }
    }

    for(const candidate of all){
      if(candidate.innerText && candidate.innerText.includes(targetPair)) {
        try { candidate.click(); await sleep(50); return true; } catch(e){}
      }
    }

    console.warn('[Nexus userScript] Não conseguiu trocar para par', targetPair);
    return false;
  }

  function sleep(ms){ return new Promise(res => setTimeout(res, ms)); }

  async function captureForPair(pair) {
    const chartEl = findChartElement();
    let dataUrl = null;
    if(chartEl && chartEl.tagName && chartEl.tagName.toLowerCase() === 'canvas') {
      dataUrl = canvasToDataURL(chartEl);
    } else if(chartEl && chartEl.tagName && chartEl.tagName.toLowerCase() === 'svg') {
      const svg = new XMLSerializer().serializeToString(chartEl);
      const svg64 = btoa(unescape(encodeURIComponent(svg)));
      const b64start = 'data:image/svg+xml;base64,';
      const img = new Image();
      img.src = b64start + svg64;
      await new Promise((res,rej)=>{ img.onload = res; img.onerror = rej; });
      const tmp = document.createElement('canvas');
      tmp.width = Math.min(MAX_WIDTH, img.width);
      tmp.height = Math.round(tmp.width * (img.height/img.width));
      tmp.getContext('2d').drawImage(img, 0, 0, tmp.width, tmp.height);
      dataUrl = tmp.toDataURL('image/jpeg', QUALITY);
    } else {
      const html2canvas = await loadHtml2canvas();
      const canvas = await html2canvas(chartEl || document.body, {scale:1});
      dataUrl = canvasToDataURL(canvas);
    }
    return dataUrl ? dataUrl.split(',')[1] : null;
  }

  async function mainLoop(){
    if(!AUTO_SWITCH){
      while(true){
        const currentPair = 'OTC';
        const payload = await captureForPair(currentPair);
        if(payload) await sendFramePOST(currentPair, payload);
        await sleep(1000 / FPS);
      }
    } else {
      let idx = 0;
      while(true){
        const pair = PAIRS[idx % PAIRS.length];
        console.log('[Nexus userScript] trocar para', pair);
        const switched = await switchToPair(pair);
        if(!switched) {
          console.warn('[Nexus userScript] Switch falhou; tentando capturar mesmo assim para', pair);
        }
        await sleep(SWITCH_DELAY_MS);
        const payload = await captureForPair(pair);
        if(payload) await sendFramePOST(pair, payload);
        await sleep(BETWEEN_PAIRS_DELAY);
        idx++;
      }
    }
  }

  setTimeout(()=> {
    mainLoop().catch(e => console.error('Erro mainLoop', e));
  }, 1500);

})();
