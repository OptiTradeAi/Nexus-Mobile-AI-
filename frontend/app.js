// frontend/app.js
const wsUrl = `${window.location.origin.replace("http", "ws")}/ws`;
const statusEl = document.getElementById("status");
const signalList = document.getElementById("signal-list");

// setup chart
const ctx = document.getElementById("chart").getContext("2d");
const chart = new Chart(ctx, {
  type: "candlestick",
  data: {
    datasets: [{
      label: "Candle Data",
      data: [],
      borderColor: "rgba(75, 192, 192, 1)",
      borderWidth: 1
    }]
  },
  options: {
    responsive: true,
    scales: {
      x: { type: "linear", display: false },
      y: { beginAtZero: false }
    }
  }
});

// fallback para Chart.js 4 (caso não suporte candlestick nativo)
if (!Chart.registry.controllers.has('candlestick')) {
  chart.config.type = "line";
}

// conectar WebSocket
let ws = new WebSocket(wsUrl);
ws.onopen = () => {
  statusEl.textContent = "🟢 Conectado";
  statusEl.classList.add("ok");
};

ws.onclose = () => {
  statusEl.textContent = "🔴 Desconectado";
  statusEl.classList.remove("ok");
  setTimeout(() => location.reload(), 5000);
};

ws.onmessage = (msg) => {
  const data = JSON.parse(msg.data);
  if (data.type === "candle") {
    addCandle(data.data);
  }
  if (data.type === "signal") {
    showSignal(data.data);
  }
};

function addCandle(candle) {
  chart.data.datasets[0].data.push({
    x: chart.data.datasets[0].data.length,
    o: candle.open,
    h: candle.high,
    l: candle.low,
    c: candle.close
  });
  if (chart.data.datasets[0].data.length > 50)
    chart.data.datasets[0].data.shift();
  chart.update();
}

function showSignal(signal) {
  const li = document.createElement("li");
  li.textContent = `[${signal.timestamp}] ${signal.pair} — Confiança: ${(signal.confidence*100).toFixed(1)}%`;
  signalList.prepend(li);
}
