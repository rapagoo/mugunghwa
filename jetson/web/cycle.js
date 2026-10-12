(() => {
  const el = id => document.getElementById(id);
  const gameView=document.body.dataset.view==='game';
  const put=(id,value)=>{if(el(id))el(id).textContent=value;};
  const stages = {PLAY_MOVE:'이동 허용 · 다음 회차 대기',IDLE:'시작 버튼 대기',MOVE_PREP:'Jetson 이동 허용 적용 대기',
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
      if(typeof deviceStatus==='function')deviceStatus('control',healthy?'연결 정상':'연결 확인 필요',healthy?'ok':'unknown',healthy?'Pi 경기 상태 수신 정상':data.reason==='Pi heartbeat missing'?'Pi 제어 클라이언트 응답 대기':'Pi 서버 · 제어 클라이언트 연결을 확인해 주세요.');
      const recovering = cycle && ['RECOVER','RECOVERY_WAIT','HOME'].includes(cycle.stage);
      const phase = healthy && cycle.stage!=='ERROR' && !recovering ? data.applied_phase : 'idle';
      el('cycle-signal').textContent = !healthy ? '연결 확인 · 판정 상태 불명' :
        cycle.stage==='RECOVER' ? '경기 중단 · 뒤보기 복귀 중' :
        cycle.stage==='RECOVERY_WAIT' ? '복귀 미확인 · 시작 금지' :
        cycle.stage==='HOME' ? '복귀 완료 · 경기 대기' :
        phase==='stop' ? '정지 판정 중 · 움직이지 마세요' :
        phase==='move' ? '움직임 허용' : '판정 대기';
      el('cycle-signal').dataset.phase = phase;
      el('cycle-link').textContent = healthy ? '연결 정상' : '연결 확인 필요';
      const brief={HOME:'구역 안에 선 뒤 시작 버튼을 눌러주세요.',FRONT_WAIT:'인형이 앞으로 돌아갑니다. 회전 완료를 기다려주세요.',STOP_APPLY:'정지 판정을 준비하고 있습니다.',REAR_WAIT:'인형이 뒤로 돌아갑니다.',MOVE_APPLY:'이동을 준비하고 있습니다.',MOVE_PREP:'경기를 준비하고 있습니다.',RECOVER:'인형의 뒤보기 복귀를 기다리고 있습니다.',RECOVERY_WAIT:'인형 연결을 확인해 주세요.'};
      put('cycle-stage',gameView?(healthy?(brief[cycle.stage]||''):'상태가 갱신될 때까지 기다려주세요.'):'Pi: '+(cycle ? stages[cycle.stage] : '시험 상태 미수신'));
      put('cycle-motor','STM: '+(cycle ? motors[cycle.motor] : '완료 응답 미수신'));
      put('cycle-time',healthy && ['HOLD','STOP_APPLY'].includes(cycle.stage) ?
        '정지 유지 남은 시간 '+(cycle.remaining_ms/1000).toFixed(1)+'초' : '정지 유지 시간 —');
      el('cycle-warning').textContent = !healthy ? '연결이 확인될 때까지 경기를 시작하지 마세요.' :
        cycle.error!=='NONE' ? errors[cycle.error] :
        gameView?'':'STM 시작 버튼으로 경기를 시작하세요. 게임 중에는 구역과 수동 시험 단계를 바꾸지 마세요.';
    } catch(error) {
      if(typeof deviceStatus==='function')deviceStatus('control','연결 확인 필요','unknown','경기 제어 상태를 조회할 수 없습니다.');
      el('cycle-signal').textContent='서버 연결 확인 · 판정 상태 불명';
      el('cycle-signal').dataset.phase='idle';
      el('cycle-link').textContent='조회 실패';
      put('cycle-time','정지 유지 시간 —');
      put('cycle-stage','');
      el('cycle-warning').textContent='이전 표시값일 수 있습니다. 연결 복구 후 시작해 주세요.';
    } finally {setTimeout(refresh,500);}
  }
  refresh();
})();
