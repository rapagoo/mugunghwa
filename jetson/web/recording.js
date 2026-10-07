'use strict';
const recordingLabels={idle:'대기',recording:'기록 중',finalizing:'저장 마무리 중',complete:'저장 완료',error:'저장 오류'};
let recordingRequest=false;
async function refreshRecording(){
  try {
    const response=await fetch('/api/recording',{signal:AbortSignal.timeout(5000)});
    if(!response.ok) throw Error('기록 상태 조회 실패');
    const r=await response.json();
    const active=r.state==='recording'||r.state==='finalizing';
    document.getElementById('record-start').disabled=active||recordingRequest;
    document.getElementById('record-stop').disabled=r.state!=='recording'||recordingRequest;
    document.getElementById('record-scenario').disabled=active;
    document.getElementById('record-state').textContent=`${recordingLabels[r.state]||r.state} · ${r.elapsed_s??0}초 · 저장 ${r.written??0} / 접수 ${r.accepted??0} · 누락 ${r.dropped??0} · 이미지 누락 ${r.image_dropped??0}`;
    document.getElementById('record-id').textContent=r.session_id?`시험 ID: ${r.session_id}`:'아직 기록한 시험이 없습니다.';
    if(r.error) document.getElementById('record-message').textContent=r.error;
  }catch(error){
    document.getElementById('record-state').textContent='기록 상태 연결 확인 필요';
    document.getElementById('record-start').disabled=true;
    document.getElementById('record-stop').disabled=true;
  }
}
async function changeRecording(action){
  recordingRequest=true;
  try {
    const body=action==='start'?{scenario:document.getElementById('record-scenario').value}:{};
    const response=await fetch('/api/recording/'+action,{method:'POST',signal:AbortSignal.timeout(10000),
      headers:{'Content-Type':'application/json','X-Mugunghwa-Calibration':'1'},body:JSON.stringify(body)});
    if(!response.ok) throw Error(action==='start'?'시작 실패: 추론 준비와 현재 기록 상태를 확인하세요.':'중지 요청 실패');
    await response.json();
    document.getElementById('record-message').textContent=action==='start'?'기록을 시작했습니다. 선택한 동작을 해주세요.':'중지 요청했습니다. 저장 완료 표시까지 기다려주세요.';
  }catch(error){document.getElementById('record-message').textContent=error.message;}
  finally{recordingRequest=false;await refreshRecording();}
}
document.getElementById('record-start').onclick=()=>changeRecording('start');
document.getElementById('record-stop').onclick=()=>changeRecording('stop');
refreshRecording();setInterval(refreshRecording,1000);
