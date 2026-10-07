'use strict';
const canvas = document.getElementById('calibration-canvas');
const ctx = canvas.getContext('2d');
const status = document.getElementById('calibration-status');
const save = document.getElementById('save-calibration');
let roi = [], line = [], direction = null, mode = 'roi', background = null;
let revision = 0, ready = false, busy = false;

function config() {
  return {schema_version:1, reference_size:[canvas.width,canvas.height],
          roi, finish_line:line, finish_direction_point:direction};
}
function complete() { return ready && roi.length >= 3 && line.length === 2 && direction; }
function draw() {
  ctx.clearRect(0,0,canvas.width,canvas.height);
  if (background) ctx.drawImage(background,0,0,canvas.width,canvas.height);
  const pixel = p => [p[0]*(canvas.width-1),p[1]*(canvas.height-1)];
  function path(points,color,close) {
    if (!points.length) return;
    ctx.strokeStyle=color; ctx.fillStyle=color; ctx.lineWidth=3;
    ctx.beginPath();
    points.forEach((p,i) => i ? ctx.lineTo(...pixel(p)) : ctx.moveTo(...pixel(p)));
    if (close) { ctx.closePath(); ctx.globalAlpha=.12; ctx.fill(); ctx.globalAlpha=1; }
    ctx.stroke();
    points.forEach((p,i) => {
      const [x,y]=pixel(p); ctx.beginPath(); ctx.arc(x,y,5,0,Math.PI*2); ctx.fill();
      ctx.font='16px sans-serif'; ctx.fillText(String(i+1),x+8,y-8);
    });
  }
  path(roi,'#71eea4',roi.length>=3); path(line,'#ffdc70',false);
  if (direction && line.length===2) {
    const mid=[(line[0][0]+line[1][0])/2,(line[0][1]+line[1][1])/2];
    path([mid,direction],'#ffdc70',false);
    const [x,y]=pixel(direction),[mx,my]=pixel(mid),angle=Math.atan2(y-my,x-mx);
    ctx.beginPath(); ctx.moveTo(x,y); ctx.lineTo(x-18*Math.cos(angle-.5),y-18*Math.sin(angle-.5));
    ctx.moveTo(x,y); ctx.lineTo(x-18*Math.cos(angle+.5),y-18*Math.sin(angle+.5)); ctx.stroke();
  }
  save.disabled=busy || !complete();
}
function count() {
  status.textContent=`게임 구역 ${roi.length}점 · 결승선 ${line.length}점 · 방향 ${direction?'지정됨':'미지정'} · ${canvas.width}×${canvas.height}`;
}
async function request(path, options={}) {
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),7000);
  try {
    const response=await fetch(path,{...options,cache:'no-store',signal:controller.signal});
    if (!response.ok) throw Error(await response.text());
    return await response.json();
  } finally { clearTimeout(timer); }
}
async function getFrame(loadConfig=false) {
  busy=true; draw();
  try {
    const settings=await request('/api/calibration');
    const image=new Image();
    await new Promise((resolve,reject)=>{
      image.onload=resolve; image.onerror=()=>reject(Error('웹캠 준비 중이거나 연결이 끊겼습니다. 잠시 후 다시 가져오세요.'));
      image.src='/camera.jpg?t='+Date.now();
    });
    if (loadConfig) {
      revision=settings.revision;
      if (settings.config) {
        roi=settings.config.roi; line=settings.config.finish_line; direction=settings.config.finish_direction_point;
      }
      document.getElementById('remove-calibration').disabled=!settings.config;
    }
    if (background && (canvas.width!==image.naturalWidth || canvas.height!==image.naturalHeight)) {
      roi=[]; line=[]; direction=null;
    }
    background=image; canvas.width=image.naturalWidth; canvas.height=image.naturalHeight; ready=true;
    count();
  } catch(error) { status.textContent=error.message; }
  finally { busy=false; draw(); }
}
document.querySelectorAll('[data-mode]').forEach(button=>{
  button.onclick=()=>{
    mode=button.dataset.mode;
    document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('selected',b===button));
    document.getElementById('hint').textContent={roi:'게임 구역 가장자리를 순서대로 3점 이상 클릭하세요.',
      line:'결승선 양 끝을 두 번 클릭하세요.',direction:'결승선 너머, 통과 후 도착할 쪽을 한 번 클릭하세요.'}[mode];
  };
});
canvas.onclick=event=>{
  if (!ready || busy) return;
  const rect=canvas.getBoundingClientRect();
  const point=[Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),
               Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))];
  if (mode==='roi') { if (roi.length===32) return; roi.push(point); }
  else if (mode==='line') { if (line.length===2) { line=[]; direction=null; } line.push(point); }
  else { if (line.length!==2) { status.textContent='결승선을 먼저 지정하세요.'; return; } direction=point; }
  count(); draw();
};
document.getElementById('undo').onclick=()=>{
  if (mode==='roi') roi.pop(); else if (mode==='line') { line.pop(); direction=null; } else direction=null;
  count(); draw();
};
document.getElementById('clear').onclick=()=>{roi=[];line=[];direction=null;count();draw();};
document.getElementById('refresh-frame').onclick=()=>getFrame();
async function apply(value) {
  busy=true; draw();
  try {
    await request('/api/calibration',{method:'POST',headers:{'Content-Type':'application/json',
      'X-Mugunghwa-Calibration':'1'},body:JSON.stringify({config:value,expected_revision:revision})});
    window.location.assign('/');
  } catch(error) { status.textContent=error.message; }
  finally { busy=false; draw(); }
}
save.onclick=()=>apply(config());
document.getElementById('remove-calibration').onclick=()=>apply(null);
getFrame(true);
