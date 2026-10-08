'use strict';
const testLabels={new_id:'새 ID',missing:'미검출',reappeared:'같은 ID 재등장',
                  roi_enter:'구역 진입',roi_exit:'구역 이탈',finish_candidate:'결승선 통과 후보'};
const testCases={roi_inside:'1 · 구역 안/먼 거리',roi_outside:'1 · 구역 밖/경계',
  forward:'2 · 지정 방향 통과',reverse:'2 · 반대 방향 통과',extension:'2 · 선 끝 바깥 통과',
  jitter:'2 · 선 주변 정지/흔들림',crossing:'3 · 두 사람 교차',occlusion:'3 · 가림 후 재등장',
  motion:'4 · 움직임/정지',stop_trial:'5 · 정지 지시 중 움직임'};
let latestValidation=null,validationReceivedAt=0,manualRecords=[];

function renderValidation(v) {
  const t=v.validation;
  latestValidation=v;
  validationReceivedAt=performance.now();
  document.getElementById('reset-validation').disabled=v.state!=='running'||gameActive;
  if (!t) return;
  const m=v.motion_trial;
  const pose=v.pose_trial;
  const poseBody=document.getElementById('pose-rows');poseBody.replaceChildren();
  const poseReasons={baseline_missing:'정지 시작 때 기준 없음 · 새 정지 지시 필요',
    pose_unavailable:'관절 모델이 실행 중이 아닙니다',outside_or_finished:'구역 밖 또는 통과 후보',
    tracking_gap:'추적 공백 · 새 정지 지시 필요',low_confidence:'관절 신뢰도 부족',
    partial_pose:'팔 관절 일부 확인 불가',
    motion:'기준 자세에서 변화',below_threshold:'허용 범위',move:'움직임 허용',idle:'시험 대기'};
  const poseStates={hold:'판정 보류',allowed:'이동 허용',idle:'대기',suspect:'움직임 의심',still:'정지'};
  for(const p of pose?.observations||[]) {
    const row=document.createElement('tr');
    for(const value of [p.track_id??'미지정',poseStates[p.status]||p.status,p.score??'—',
      poseReasons[p.reason]||p.reason,p.valid_joints,p.stop_candidate?'움직임 후보 기록됨':'—']) {
      const cell=document.createElement('td');cell.textContent=value;row.append(cell);
    }
    poseBody.append(row);
  }
  rows('pose-events',[...(pose?.events||[])].reverse().map(e=>
    [`ID ${e.track_id} · 관절 움직임 후보`, `정지 후 ${e.after_stop_s}초 · 점수 ${e.score}`]),'관절 시험 후보 없음');
  if(m) {
    put('motion-phase',`시험 상태: ${{idle:'대기',move:'이동 허용',stop:'정지 지시'}[m.phase]} · 유예 ${m.grace_remaining_s}초 · 요청 ${m.version}`);
    rows('motion-events',[...m.events].reverse().map(e=>[`ID ${e.track_id} · 시험용 탈락 후보`,`정지 지시 후 ${e.after_stop_s}초`]),'시험용 탈락 후보 없음');
  }
  document.getElementById('test-session').textContent=
    `시험 ${t.session.number} · ${t.elapsed_s}초 · ${t.frames}회 검출 · 설정 ${t.session.calibration_revision}`;
  put('roi-inside',v.roi_people??'—'); put('roi-outside',v.outside_people??'—');
  put('test-candidates',(v.candidates||[]).length);put('test-gaps',t.missing_ids.length);
  put('test-summary',`관측한 새 ID ${t.new_id_events}회 · 최대 동시 검출 ${t.max_visible}명 · ID 미지정 ${t.untracked}명 · 최근 평균 검출 간격 ${ms(t.mean_interval_ms)}`);
  const body=document.getElementById('observation-rows');body.replaceChildren();
  for (const o of t.observations) {
    const row=document.createElement('tr');
    const side={approach:'접근 쪽',destination:'도착 쪽',line:'선 주변'}[o.line_side]||'미설정';
    const state=o.candidate?'통과 후보':o.pending?'선 넘음 · 여유 폭 확인 중':o.armed?'접근 확인됨':'접근 확인 대기';
    const motion=m?.observations.find(p=>p.track_id===o.track_id);
    for (const value of [o.track_id??'미지정',o.confidence==null?'—':`${Math.round(o.confidence*100)}%`,
       o.in_roi==null?'미설정':o.in_roi?'안':'밖',`${o.foot[0].toFixed(3)}, ${o.foot[1].toFixed(3)}`,side,o.line_side?state:'미설정',
       motion?`${{pending:'판정 대기',moving:'이동',still:'정지'}[motion.status]} (${motion.score??'—'})`:'—',
       motion?.stop_candidate?'시험용 탈락 후보':motion?.stop_baseline_ready?'정지 감시 중':'기준 준비/대기']) {
      const cell=document.createElement('td');cell.textContent=value;row.append(cell);
    }
    body.append(row);
  }
  rows('test-events',[...t.events].reverse().slice(0,30).map(e=>
    [`ID ${e.track_id} · ${testLabels[e.kind]||e.kind}`,`${e.media_s.toFixed(2)}초${e.gap_s==null?'':' · 공백 '+e.gap_s+'초'}`]),'아직 관측 이력이 없습니다.');
  put('test-freshness',v.state==='running'&&v.result_age_ms<=2000?'관측 갱신 중':'이전 관측입니다. 입력 상태를 확인하세요.');
}

const resetButton=document.getElementById('reset-validation');
resetButton.onclick=async()=>{
  resetButton.disabled=true;
  try {
    const response=await fetch('/api/validation/reset',{method:'POST',headers:{'Content-Type':'application/json',
      'X-Mugunghwa-Calibration':'1'},body:'{}'});
    if (!response.ok) throw Error('초기화 요청 실패');
    const request=await response.json();
    put('test-message',`초기화 요청 ${request.requested_reset} · 다음 검출부터 새 시험입니다. 관찰 기록은 유지됩니다.`);
  } catch(error) { put('test-message',error.message); }
};
for(const phase of ['idle','move','stop']) {
  document.getElementById('phase-'+phase).onclick=async()=>{
    try {
      const response=await fetch('/api/validation/phase',{method:'POST',headers:{'Content-Type':'application/json',
        'X-Mugunghwa-Calibration':'1'},body:JSON.stringify({phase})});
      if(!response.ok) throw Error('시험 상태 변경 실패');
      const command=await response.json();
      put('test-message',`시험 상태 요청 ${command.version} · 다음 검출에서 적용됩니다.`);
    } catch(error) {put('test-message',error.message);}
  };
}
document.getElementById('record-validation').onclick=()=>{
  if (!latestValidation?.validation || latestValidation.state!=='running' ||
      latestValidation.result_age_ms+performance.now()-validationReceivedAt>2000) {
    put('test-message','갱신 중인 관측이 필요합니다.');return;
  }
  const expectedInput=document.getElementById('expected-people').value;
  const expected=expectedInput===''?null:Number(expectedInput);
  if (expected!==null&&(!Number.isInteger(expected)||expected<0||expected>50)) {
    put('test-message','예상 인원은 0~50의 정수로 입력하세요.');return;
  }
  const caseId=document.getElementById('test-case').value;
  const record={recorded_at:new Date().toISOString(),case_id:caseId,
    observer_result:document.getElementById('test-result').value,expected_roi_people:expected,
    note:document.getElementById('test-note').value.slice(0,300),observation:latestValidation};
  manualRecords.push(record);
  if (manualRecords.length>30) manualRecords.shift();
  rows('manual-test-records',[...manualRecords].reverse().map(r=>
    [testCases[r.case_id],{pass:'관찰 일치',fail:'문제 관찰',unchecked:'판단 전'}[r.observer_result]]),'관찰 기록 없음');
  put('test-message',`관찰 기록 ${manualRecords.length}개 · JSON 저장 전 새로고침하면 사라집니다.`);
};
document.getElementById('download-validation').onclick=()=>{
  const report={schema_version:1,exported_at:new Date().toISOString(),
    scope:'Manual vision validation; no Pi game verdicts',records:manualRecords,latest:latestValidation};
  const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));
  const link=document.createElement('a');link.href=url;link.download='vision-validation-'+Date.now()+'.json';link.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
};
