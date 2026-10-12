const el=id=>document.getElementById(id);
const put=(id,value)=>{if(el(id))el(id).textContent=value};
const gameView=document.body.dataset.view==='game';
const ms=v=>v==null?'—':`${Math.round(v)} ms`;
const labels={move:'이동 허용',stop:'정지 판정',move_preparing:'이동 준비',front_wait:'앞보기 대기',aborted:'중단',playing:'진행 중',passed:'통과',failed:'탈락',waiting:'대기',running:'진행 중',stopped:'정지',finished:'종료'};
let visionConnected=false,gameConnected=false,gameActive=false;
function connection(){put('connection',visionConnected?(gameConnected?'서버 연결됨':'영상 연결됨 · DB 확인 필요'):'영상 연결 확인 필요')}
function rows(id,items,empty){
  const box=el(id);if(!box)return;box.replaceChildren();box.className=items.length?'':'empty';
  if(!items.length){box.textContent=empty;return}
  for(const [left,right,status] of items){
    const row=document.createElement('div'),a=document.createElement('span'),b=document.createElement('span');
    row.className='row';a.textContent=left;b.textContent=right;b.className=status||'';row.append(a,b);box.append(row);
  }
}
function deviceStatus(id,label,state,detail){
  put('link-'+id,label);put('detail-'+id,detail);
  if(el('link-'+id))el('link-'+id).dataset.state=state;
}
function boardStatus(id,devices){
  const board=devices.find(d=>d.id===id.toUpperCase());
  const age=board?.age_seconds;
  const recent=Number.isFinite(age)&&age>=0&&age<=10;
  let detail='아직 응답 기록이 없습니다.';
  if(board?.last_seen_at){
    const date=new Date(board.last_seen_at);
    detail='최근 응답 '+(Number.isNaN(date.getTime())?'시각 확인 불가':date.toLocaleString('ko-KR',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit',second:'2-digit'}));
  }
  deviceStatus(id,recent?'최근 응답 확인':board?.last_seen_at?'최근 응답 오래됨':'응답 기록 없음',recent?'ok':'unknown',detail);
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
    const stale=v.state==='running'&&(v.result_age_ms==null||v.result_age_ms>2000);
    deviceStatus('vision',v.state==='running'&&!stale?'검출 중':v.state==='preparing'?'준비 중':'확인 필요',v.state==='running'&&!stale?'ok':'unknown',v.state==='running'&&!stale?'카메라 영상 수신 정상':'카메라 · 검출 상태를 확인해 주세요.');
    if(Number.isFinite(v.width)&&Number.isFinite(v.height)&&v.width>0&&v.height>0)
      document.querySelector('.preview').style.setProperty('--camera-ratio',v.width+'/'+v.height);
    put('source',v.source==='video'?'영상 테스트 · 1×':'웹캠 · 실시간');
    put('vision-state',stale?'관측 지연':({preparing:'엔진 준비 중',running:'검출 중',ended:'영상 종료',error:'입력 오류'}[v.state]||v.state));
    put('people',v.people??'—');put('processing',ms(v.processing_ms));put('interval',ms(v.interval_ms));put('age',ms(v.result_age_ms));
    el('overlay').hidden=v.state==='running'&&!stale;
    el('overlay').textContent=v.error||(stale?'관측이 지연되었습니다. 마지막 검출 화면입니다.':v.state==='ended'?'영상 재생이 종료되었습니다.':'추론 엔진을 준비하고 있습니다');
    put('tracks',`임시 추적 ID: ${(v.track_ids||[]).join(', ')||'—'}`);
    rows('candidates',(v.candidates||[]).map(c=>[`추적 ID ${c.track_id}`,`통과 후보 · ${c.crossed_at.toFixed(2)}초`]),'결승선 통과 후보 없음');
    put('calibration-info',gameView?(v.calibrated?'구역 안 '+(v.roi_people??0)+'명':'경기 구역을 설정해 주세요'):v.calibrated?'구역 적용됨 · 구역 안 인원 '+v.roi_people+' · 설정 버전 '+v.calibration_revision:'구역 미설정 · 구역 설정 버튼으로 시작하세요.');
    if(document.querySelector('.preview-note'))document.querySelector('.preview-note').textContent=`미리보기 최대 ${v.preview_hz||5} FPS · 추론 속도와 별개입니다.`+
      (v.pose?.enabled?` 관절 검출 비교 · 보이는 관절 수 ${v.pose.visible_keypoints.join(', ')||'—'}/17 · 정지 판정은 관절 기준입니다.`:'');
    if(el('stream').dataset.retry==='1'){el('stream').src='/stream.mjpg?retry='+Date.now();el('stream').dataset.retry='0'}
  }catch(error){
    deviceStatus('vision','연결 확인 필요','unknown','웹 서버의 응답이 없습니다.');
    visionConnected=false;put('vision-state','서버 연결 끊김');el('overlay').hidden=false;el('overlay').textContent='서버 연결을 확인해 주세요';el('stream').dataset.retry='1';
    put('test-freshness','서버 연결이 끊겼습니다. 이전 관측입니다.');
  }finally{connection();setTimeout(refreshVision,1000)}
}
let clearedGameId=null;
try{clearedGameId=localStorage.getItem('mugunghwa.clearedGameId');}catch(error){}
async function refreshGame(schedule=true){
  try{
    const g=await get('/api/game');gameConnected=g.connected!==false;
    deviceStatus('db',gameConnected?'조회 정상':'연결 확인 필요',gameConnected?'ok':'unknown',gameConnected?'경기 기록 조회 정상':'DB 연결을 확인해 주세요.');
    for(const id of ['stm','ard'])boardStatus(id,g.devices||[]);
    const terminal=g.game&&['finished','aborted'].includes(g.game.phase);
    const cleared=gameView&&terminal&&g.game.id===clearedGameId;
    if(el('reset-game-display'))el('reset-game-display').disabled=!terminal||cleared;
    if(cleared){g.game=null;g.participants=[];g.events=[];}
    put('reset-game-note',cleared?'표시를 초기화했습니다. 지난 경기 기록은 보존됩니다.':'지난 경기 기록은 보존됩니다. 경기 종료 후 사용할 수 있습니다.');
    if(g.game){
      const active=!['finished','aborted'].includes(g.game.phase);gameActive=active;
      const stale=active&&Date.now()-Date.parse(g.game.updated_at)>5000;
      for(const id of ['phase-move','phase-stop','phase-idle','reset-validation'])if(el(id))el(id).disabled=active;
      if(el('calibration-link')){el('calibration-link').hidden=active;}
      put('game-state',(stale?'상태 지연 · 마지막 기록 · ':'')+(g.game.is_test?'시험 데이터 · ':'')+(labels[g.game.phase]||g.game.phase));
      const t=g.game.remaining_seconds;put('remaining',t==null?'— : —':`${Math.floor(t/60)} : ${String(t%60).padStart(2,'0')}`);
      const reasons={timeout:'제한 시간이 끝났습니다.',all_resolved:'모든 참가자의 결과가 확정되었습니다.',operator_stop:'경기가 중단되었습니다.',communication_error:'연결 문제로 경기가 중단되었습니다.',audio_error:'음원을 재생할 수 없어 경기가 중단되었습니다.',audio_timeout:'음원 응답이 없어 경기가 중단되었습니다.',source_changed:'카메라 설정이 변경되어 경기가 중단되었습니다.',controller_disconnected:'제어 연결이 종료되어 경기가 중단되었습니다.'};
      put('game-meta',gameView?(stale?'경기 정보가 지연되고 있습니다. 마지막 수신값입니다.':active?'제한 시간 '+(g.game.duration_seconds||180)+'초':'최근 경기 · '+(reasons[g.game.end_reason]||'경기가 종료되었습니다.')):`게임 ${g.game.id} · ${g.game.duration_seconds||180}초 · 종료 사유 ${g.game.end_reason||"—"} · DB 갱신 ${g.game.updated_at}`);put('total',g.participants.length);
      put('passed',g.participants.filter(p=>p.status==='passed').length);put('failed',g.participants.filter(p=>p.status==='failed').length);
    }else{
      gameActive=false;
      for(const id of ['phase-move','phase-stop','phase-idle'])if(el(id))el(id).disabled=false;
      if(el('calibration-link'))el('calibration-link').hidden=false;
      put('game-state','경기 대기');put('remaining',cleared?'0 : 00':'— : —');
      put('game-meta','구역 안에 선 뒤 시작 버튼을 눌러주세요.');for(const id of ['total','passed','failed'])put(id,cleared?'0':'—');
    }
    rows('participants',g.participants.map((p,i)=>[p.name||(gameView?'참가자 '+(i+1):p.id),g.game?.phase==="aborted"&&p.status==="playing"?"미완료":labels[p.status]||p.status,p.status]),'경기가 시작되면 표시됩니다.');
    rows('devices',(g.devices||[]).map(d=>[d.id,d.connection_state+' · '+(d.last_ack||'—')+' · '+(d.last_seen_at||'수신 기록 없음')]),'아직 보드 상태 수집이 연결되지 않았습니다.');
    rows('events',g.events.map(e=>[`${e.kind}${e.participant_id?' · '+e.participant_id:''}`,e.occurred_at]),'아직 저장된 이벤트가 없습니다.');
  }catch(error){if(el('reset-game-display'))el('reset-game-display').disabled=true;deviceStatus('db','연결 확인 필요','unknown','경기 기록을 조회할 수 없습니다.');for(const id of ['stm','ard'])deviceStatus(id,'응답 조회 불가','unknown','보드 응답 기록 조회 불가');gameConnected=false;put('game-state','게임 상태 조회 실패');put('game-meta','마지막 표시값일 수 있습니다. 서버 상태를 확인해 주세요.')}
  finally{connection();if(schedule)setTimeout(refreshGame,2000)}
}
el('stream').addEventListener('error',()=>{el('stream').dataset.retry='1'});
refreshVision();refreshGame();

async function refreshConnections(){
  try{
    const data=await get('/api/connections');
    for(const id of ['stm','ard','pi','jetson']){
      const node=el('session-'+id);if(!node)continue;
      const connected=data.fresh&&data.ids.includes(id.toUpperCase());
      node.textContent=!data.fresh?'서버 접속 조회 지연':connected?(id==='ard'?'중계기 서버 접속 중':'서버 접속 중'):'서버 미접속';
      node.dataset.state=!data.fresh?'unknown':connected?'ok':'offline';
    }
  }catch(error){for(const id of ['stm','ard','pi','jetson']){put('session-'+id,'서버 접속 조회 불가');if(el('session-'+id))el('session-'+id).dataset.state='unknown';}}
  finally{setTimeout(refreshConnections,2000);}
}
if(gameView)refreshConnections();

if(el('reset-game-display'))el('reset-game-display').addEventListener('click',async()=>{
  el('reset-game-display').disabled=true;
  try{
    const data=await get('/api/game');
    if(!data.game||!['finished','aborted'].includes(data.game.phase)){
      put('reset-game-note','진행 중인 경기는 초기화할 수 없습니다. 먼저 경기를 중지해 주세요.');return;
    }
    clearedGameId=data.game.id;
    try{localStorage.setItem('mugunghwa.clearedGameId',clearedGameId);}catch(error){}
    await refreshGame(false);
  }catch(error){put('reset-game-note','경기 상태를 확인할 수 없습니다. 연결 복구 후 다시 시도해 주세요.');}
});
