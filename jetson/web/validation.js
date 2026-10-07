'use strict';
const testLabels={new_id:'새 ID',missing:'미검출',reappeared:'같은 ID 재등장',
                  roi_enter:'구역 진입',roi_exit:'구역 이탈',finish_candidate:'결승선 통과 후보'};
const testCases={roi_inside:'1 · 구역 안/먼 거리',roi_outside:'1 · 구역 밖/경계',
  forward:'2 · 지정 방향 통과',reverse:'2 · 반대 방향 통과',extension:'2 · 선 끝 바깥 통과',
  jitter:'2 · 선 주변 정지/흔들림',crossing:'3 · 두 사람 교차',occlusion:'3 · 가림 후 재등장'};
let latestValidation=null,validationReceivedAt=0,manualRecords=[];

function renderValidation(v) {
  const t=v.validation;
  latestValidation=v;
  validationReceivedAt=performance.now();
  document.getElementById('reset-validation').disabled=v.state!=='running';
  if (!t) return;
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
    for (const value of [o.track_id??'미지정',o.confidence==null?'—':`${Math.round(o.confidence*100)}%`,
       o.in_roi==null?'미설정':o.in_roi?'안':'밖',`${o.foot[0].toFixed(3)}, ${o.foot[1].toFixed(3)}`,side,o.line_side?state:'미설정']) {
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
