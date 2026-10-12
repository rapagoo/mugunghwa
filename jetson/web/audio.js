(() => {
  const slider=document.getElementById('speaker-volume'),button=document.getElementById('speaker-mute');
  const level=document.getElementById('speaker-level'),status=document.getElementById('speaker-status');
  let current=null,busy=false,revision=0;
  function render(data){
    current=data;
    if(document.activeElement!==slider)slider.value=data.volume;
    level.textContent=data.volume+'%';button.setAttribute('aria-pressed',String(data.muted));
    button.textContent=data.muted?'음소거 해제':'음소거';
    status.textContent=data.muted?'음소거 중':'USB 스피커 · 구호와 효과음에 함께 적용';
    slider.disabled=button.disabled=false;
  }
  async function request(body){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),7000);
    try{
      const response=await fetch('/api/volume',{cache:'no-store',signal:controller.signal,
        ...(body?{method:'POST',headers:{'Content-Type':'application/json','X-Mugunghwa-Calibration':'1'},body:JSON.stringify(body)}:{})});
      if(!response.ok)throw Error('Speaker unavailable');
      return await response.json();
    }finally{clearTimeout(timer);}
  }
  async function refresh(){
    const version=revision;
    if(!busy){try{const data=await request();if(!busy&&version===revision)render(data);}
      catch(error){if(!busy&&version===revision){slider.disabled=button.disabled=true;status.textContent='USB 스피커를 확인해 주세요.';}}}
    setTimeout(refresh,5000);
  }
  async function save(body){
    busy=true;revision++;slider.disabled=button.disabled=true;status.textContent='볼륨 적용 중';
    try{render(await request(body));}catch(error){status.textContent='설정을 적용하지 못했습니다. USB 스피커를 확인해 주세요.';slider.disabled=button.disabled=true;}
    finally{busy=false;}
  }
  slider.addEventListener('input',()=>{level.textContent=slider.value+'%';});
  slider.addEventListener('change',()=>save({volume:Number(slider.value)}));
  button.addEventListener('click',()=>{if(current)save({muted:!current.muted});});
  refresh();
})();
