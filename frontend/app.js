const ws = new WebSocket("wss://nexus-mobile-ai.onrender.com/ws");
const log = document.getElementById("signal-log");

ws.onopen = () => {
  log.innerHTML += "<p>✅ Conectado ao servidor WebSocket...</p>";
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === "signal") {
    log.innerHTML += `<p>🚀 Novo sinal detectado: <b>${data.pair}</b> — Confiança: ${(data.confidence * 100).toFixed(1)}%</p>`;
  }
};
