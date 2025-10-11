// Salva WSS e solicita que o background inicie a captura
document.getElementById('start').addEventListener('click', async ()=>{
  const wsUrl = document.getElementById('ws').value.trim();
  if(!wsUrl){ alert('Digite o WSS do backend'); return; }
  chrome.storage.local.set({BACKEND_WS_URL: wsUrl}, ()=> {
    chrome.runtime.sendMessage({type:'START_CAPTURE'}, (resp)=>{
      document.getElementById('status').innerText = 'Requisição enviada: ' + JSON.stringify(resp);
    });
  });
});
