(() => {
  const el = id => document.getElementById(id);
  const stages = {IDLE:'시작 버튼 대기',MOVE_PREP:'Jetson 이동 허용 적용 대기',
    FRONT_WAIT:'인형 앞보기 명령 전송 · 완료 대기',STOP_APPLY:'앞보기 완료 · Jetson 정지 판정 적용 대기',
    HOLD:'정지 판정 중',REAR_WAIT:'인형 뒤보기 명령 전송 · 완료 대기',
    MOVE_APPLY:'뒤보기 완료 · Jetson 이동 허용 적용 대기',DONE:'한 회차 완료',ERROR:'시험 중단',
    RECOVER:'뒤보기 복귀 중 · 새 회차 시작 잠금',RECOVERY_WAIT:'복귀 미확인 · 재접속/재시도 대기',HOME:'초기 상태 복귀 완료 · 시작 버튼 대기'};
  const motors = {UNKNOWN:'방향 확인 전',FRONT_WAIT:'앞보기 회전 요청 · 완료 응답 대기',
    FRONT_OK:'앞보기 완료 응답 수신',REAR_WAIT:'뒤보기 회전 요청 · 완료 응답 대기',REAR_OK:'뒤보기 완료 응답 수신'};
  const errors = {STM_STOP:'STM 중단 요청',OPERATOR_STOP:'운영자 중단',ACK_TIMEOUT:'완료 응답 시간 초과',
    HEARTBEAT_LOST:'Jetson 하트비트 누락',JETSON_ERROR:'Jetson 시험 준비 오류',RECOVERY_TIMEOUT:'복귀 완료 미확인 · 새 회차 시작 금지, 자동 재시도 중'};
  async function refresh() {
    try {
      const response = await fetch('/api/cycle',{cache:'no-store',signal:AbortSignal.timeout(2500)});
      if(!response.ok) throw new Error('조회 실패');
      const data = await response.json(), cycle = data.cycle;
      const healthy = data.healthy && cycle;
      const recovering = cycle && ['RECOVER','RECOVERY_WAIT','HOME'].includes(cycle.stage);
      const phase = healthy && cycle.stage!=='ERROR' && !recovering ? data.applied_phase : 'idle';
      el('cycle-signal').textContent = !healthy ? '연결 확인 · 판정 상태 불명' :
        cycle.stage==='RECOVER' ? '경기 중단 · 뒤보기 복귀 중' :
        cycle.stage==='RECOVERY_WAIT' ? '복귀 미확인 · 시작 금지' :
        cycle.stage==='HOME' ? '복귀 완료 · 경기 대기' :
        phase==='stop' ? '정지 판정 중 · 움직이지 마세요' :
        phase==='move' ? '움직임 허용' : '판정 대기';
      el('cycle-signal').dataset.phase = phase;
      el('cycle-link').textContent = healthy ? 'Pi ↔ Jetson 연결 정상' : '상태 수신 대기/지연';
      el('cycle-stage').textContent = 'Pi: '+(cycle ? stages[cycle.stage] : '시험 상태 미수신');
      el('cycle-motor').textContent = 'STM: '+(cycle ? motors[cycle.motor] : '완료 응답 미수신');
      el('cycle-time').textContent = healthy && ['HOLD','STOP_APPLY'].includes(cycle.stage) ?
        '정지 유지 남은 시간 '+(cycle.remaining_ms/1000).toFixed(1)+'초' : '정지 유지 시간 —';
      el('cycle-warning').textContent = !healthy ? '새 상태가 확인될 때까지 시험을 멈추세요. 이전 방향·단계일 수 있습니다.' :
        cycle.error!=='NONE' ? errors[cycle.error] :
        'STM 시작 버튼으로 한 회차를 시작하세요. 자동 시험 중에는 아래 수동 단계 버튼을 누르지 마세요.';
    } catch(error) {
      el('cycle-signal').textContent='서버 연결 확인 · 판정 상태 불명';
      el('cycle-signal').dataset.phase='idle';
      el('cycle-link').textContent='조회 실패';
      el('cycle-time').textContent='정지 유지 시간 —';
      el('cycle-warning').textContent='이전 표시값일 수 있습니다. 연결 복구 후 시험하세요.';
    } finally {setTimeout(refresh,500);}
  }
  refresh();
})();
