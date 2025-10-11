// Inicia captura via getDisplayMedia (funciona bem em desktop)
// Envia chunks via WebSocket para BACKEND_WSS (configurado no popup)
chrome.runtime.onMessage.addListener(async (msg, sender, sendResponse) => {
  if(msg.type === 'START_CAPTURE'){
    try{
      // abre o seletor de captura (usuário escolhe a aba)
      const stream = await navigator.mediaDevices.getDisplayMedia({video: true, audio: false});
      chrome.storage.local.get('BACKEND_WS_URL', (res)=>{
        const wsUrl = res.BACKEND_WS_URL || 'ws://localhost:8000/ws/stream';
        const ws = new WebSocket(wsUrl);
        ws.binaryType = 'arraybuffer';
        const recorder = new MediaRecorder(stream, {mimeType: 'video/webm;codecs=vp8'});
        recorder.ondataavailable = async (e) => {
          if(e.data && e.data.size>0 && ws.readyState===WebSocket.OPEN){
            const arr = await e.data.arrayBuffer();
            ws.send(arr);
          }
        };
        ws.onopen = ()=> console.log('WS conectado ao backend');
        ws.onclose = ()=> console.log('WS fechado');
        recorder.start(1000); // 1s de chunks
      });
      sendResponse({status:'started'});
    }catch(err){
      console.error('Erro capture', err);
      sendResponse({status:'error', message:String(err)});
    }
    return true;
  }
});
