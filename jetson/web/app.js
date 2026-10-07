const el=id=>document.getElementById(id);
const put=(id,value)=>{el(id).textContent=value};
const ms=v=>v==null?'—':`${Math.round(v)} ms`;
const labels={playing:'진행 중',passed:'통과',failed:'탈락',waiting:'대기',running:'진행 중',stopped:'정지',finished:'종료'};
let visionConnected=false,gameConnected=false;
function connection(){put('connection',visionConnected?(gameConnected?'서버 연결됨':'영상 연결됨 · DB 확인 필요'):'영상 연결 확인 필요')}
function rows(id,items,empty){
  const box=el(id);box.replaceChildren();box.className=items.length?'':'empty';
  if(!items.length){box.textContent=empty;return}
  for(const [left,right,status] of items){
    const row=document.createElement('div'),a=document.createElement('span'),b=document.createElement('span');
    row.className='row';a.textContent=left;b.textContent=right;b.className=status||'';row.append(a,b);box.append(row);
  }
}
async function get(path){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),5000);
  try{const response=await fetch(path,{cache:'no-store',signal:controller.signal});if(!response.ok)throw Error(response.status);return await response.json()}
  finally{clearTimeout(timer)}
}
async function refreshVision(){
  try{
    const v=await get('/api/vision');visionConnected=true;
    if(typeof renderValidation==='function')renderValidation(v);
    const stale=v.result_age_ms>2000;
    if(Number.isFinite(v.width)&&Number.isFinite(v.height)&&v.width>0&&v.height>0)
      document.querySelector('.preview').style.setProperty('--camera-ratio',v.width+'/'+v.height);
    put('source',v.source==='video'?'영상 테스트 · 1×':'웹캠 · 실시간');
    put('vision-state',stale?'관측 지연':({preparing:'엔진 준비 중',running:'검출 중',ended:'영상 종료',error:'입력 오류'}[v.state]||v.state));
    put('people',v.people??'—');put('processing',ms(v.processing_ms));put('interval',ms(v.interval_ms));put('age',ms(v.result_age_ms));
    el('overlay').hidden=v.state==='running'&&!stale;
    el('overlay').textContent=v.error||(stale?'관측이 지연되었습니다. 마지막 검출 화면입니다.':v.state==='ended'?'영상 재생이 종료되었습니다.':'추론 엔진을 준비하고 있습니다');
    put('tracks',`임시 추적 ID: ${(v.track_ids||[]).join(', ')||'—'}`);
    rows('candidates',(v.candidates||[]).map(c=>[`추적 ID ${c.track_id}`,`통과 후보 · ${c.crossed_at.toFixed(2)}초`]),'결승선 통과 후보 없음');
    put('calibration-info',v.calibrated?'구역 적용됨 · 구역 안 인원 '+v.roi_people+' · 설정 버전 '+v.calibration_revision:'구역 미설정 · 구역 설정 버튼으로 시작하세요.');
    document.querySelector('.preview-note').textContent=`미리보기 최대 ${v.preview_hz||5} FPS · 추론 속도와 별개입니다.`+
      (v.pose?.enabled?` 관절 검출 비교 · 보이는 관절 수 ${v.pose.visible_keypoints.join(', ')||'—'}/17 · 현재 움직임 판정은 박스 중심 기준입니다.`:'');
    if(el('stream').dataset.retry==='1'){el('stream').src='/stream.mjpg?retry='+Date.now();el('stream').dataset.retry='0'}
  }catch(error){
    visionConnected=false;put('vision-state','서버 연결 끊김');el('overlay').hidden=false;el('overlay').textContent='서버 연결을 확인해 주세요';el('stream').dataset.retry='1';
    put('test-freshness','서버 연결이 끊겼습니다. 이전 관측입니다.');
  }finally{connection();setTimeout(refreshVision,1000)}
}
async function refreshGame(){
  try{
    const g=await get('/api/game');gameConnected=true;
    if(g.game){
      put('game-state',(g.game.is_test?'시험 데이터 · ':'')+(labels[g.game.phase]||g.game.phase));
      const t=g.game.remaining_seconds;put('remaining',t==null?'— : —':`${Math.floor(t/60)} : ${String(t%60).padStart(2,'0')}`);
      put('game-meta',`게임 ${g.game.id} · 상태 갱신 ${g.game.updated_at}`);put('total',g.participants.length);
      put('passed',g.participants.filter(p=>p.status==='passed').length);put('failed',g.participants.filter(p=>p.status==='failed').length);
    }else{
      put('game-state',g.backend==='mariadb'?'DB 연결됨 · 게임 대기':'연결 대기');put('remaining','— : —');
      put('game-meta','Pi 게임 상태 저장 기능을 연결하면 표시됩니다.');for(const id of ['total','passed','failed'])put(id,'—');
    }
    rows('participants',g.participants.map(p=>[p.name||p.id,labels[p.status]||p.status,p.status]),'아직 저장된 참가자 정보가 없습니다.');
    rows('devices',(g.devices||[]).map(d=>[d.id,d.connection_state+' · '+(d.last_seen_at||'수신 기록 없음')]),'아직 보드 상태 수집이 연결되지 않았습니다.');
    rows('events',g.events.map(e=>[`${e.kind}${e.participant_id?' · '+e.participant_id:''}`,e.occurred_at]),'아직 저장된 이벤트가 없습니다.');
  }catch(error){gameConnected=false;put('game-state','게임 상태 조회 실패');put('game-meta','마지막 표시값일 수 있습니다. 서버 상태를 확인해 주세요.')}
  finally{connection();setTimeout(refreshGame,2000)}
}
el('stream').addEventListener('error',()=>{el('stream').dataset.retry='1'});
refreshVision();refreshGame();
