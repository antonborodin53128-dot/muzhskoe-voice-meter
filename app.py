from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML = r"""
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Voice Meter — тест аудиовхода</title>
<style>
*{box-sizing:border-box}
html,body{margin:0;min-height:100%;background:#020b07;color:#f4f5ef;font-family:Arial,sans-serif}
body:before{content:"";position:fixed;inset:0;background:radial-gradient(circle at 0 25%,rgba(0,255,115,.15),transparent 36%);pointer-events:none}
.wrap{max-width:1000px;margin:auto;padding:28px}
.top{display:flex;justify-content:space-between;align-items:center;gap:20px;margin-bottom:24px}
.brand{font-size:25px;font-weight:900}.m{border:2px solid #20ee78;padding:7px 10px}.slash,.accent{color:#20ee78}.w{color:#747d78}
.panel{border:1px solid #174b30;background:rgba(8,24,16,.92);border-radius:22px;padding:24px;margin-bottom:18px}
h1{margin:0 0 8px;font-size:38px}.sub{color:#8ba095;margin-bottom:24px}
.label{color:#84968c;font-size:13px;font-weight:900;letter-spacing:2px;margin-bottom:8px}
select,button{width:100%;border-radius:14px;padding:14px 16px;font-size:17px}
select{background:#07110c;border:1px solid #22543a;color:#fff;margin-bottom:14px}
button{border:0;background:#20eb72;color:#001b0d;font-weight:900;cursor:pointer}
button.secondary{margin-top:10px;background:#18231d;color:#d6e0da;border:1px solid #405047}
.meter{height:58px;background:#06110b;border:1px solid #205239;border-radius:16px;overflow:hidden;margin-top:18px;position:relative}
.fill{height:100%;width:0%;background:linear-gradient(90deg,#16d965 0%,#9fea3b 65%,#f2dc36 82%,#ff5353 100%);transition:width .05s linear}
.scale{display:flex;justify-content:space-between;color:#73877b;font-size:12px;margin-top:7px}
.readout{display:flex;gap:18px;margin-top:22px;flex-wrap:wrap}.card{flex:1;min-width:180px;background:#06140c;border:1px solid #16452c;border-radius:18px;padding:18px}
.value{font-size:46px;font-weight:900;color:#20ee78;margin-top:4px}
.status{margin-top:15px;color:#9caf9f}.warn{color:#ffcf65}
.small{font-size:13px;color:#82958a;line-height:1.45;margin-top:16px}
</style>
</head>
<body><div class="wrap">
<div class="top"><div class="brand"><span class="m">МУЖСКОЕ</span> <span class="slash">/</span> <span class="w">ЖЕНСКОЕ</span></div><b class="accent">VOICE METER</b></div>
<div class="panel">
<h1>ТЕСТ АУДИОВХОДА</h1>
<div class="sub">Сначала проверяем, что браузер видит нужную звуковую карту и корректно измеряет уровень микрофона.</div>
<div class="label">АУДИОВХОД / МИКРОФОН</div>
<select id="devices"><option>Нажмите «Разрешить микрофон»</option></select>
<button id="permission">РАЗРЕШИТЬ МИКРОФОН</button>
<button class="secondary" id="refresh">ОБНОВИТЬ СПИСОК УСТРОЙСТВ</button>
<div class="meter"><div class="fill" id="fill"></div></div>
<div class="scale"><span>ТИХО</span><span>ГРОМКО</span></div>
<div class="readout">
<div class="card"><div class="label">ТЕКУЩИЙ УРОВЕНЬ</div><div class="value" id="level">0</div></div>
<div class="card"><div class="label">ПИК</div><div class="value" id="peak">0</div></div>
</div>
<div class="status" id="status">Микрофон ещё не подключён.</div>
<div class="small">Выбранное устройство запоминается в этом браузере. При смене входа браузер переподключится к выбранному устройству. Для работы микрофона страница должна быть открыта по HTTPS или на localhost.</div>
</div></div>
<script>
let ctx=null, analyser=null, stream=null, raf=null, peak=0;
const devices=document.getElementById('devices'), status=document.getElementById('status'),
fill=document.getElementById('fill'), level=document.getElementById('level'), peakEl=document.getElementById('peak');

async function enumerate(){
  const list=await navigator.mediaDevices.enumerateDevices();
  const ins=list.filter(d=>d.kind==='audioinput');
  const saved=localStorage.getItem('voiceMeterDevice');
  devices.innerHTML='';
  ins.forEach((d,i)=>{
    const o=document.createElement('option');
    o.value=d.deviceId; o.textContent=d.label || ('Аудиовход '+(i+1));
    if(saved && saved===d.deviceId)o.selected=true;
    devices.appendChild(o);
  });
  if(!ins.length){devices.innerHTML='<option>Аудиовходы не найдены</option>';}
}

async function connect(deviceId){
  try{
    if(stream)stream.getTracks().forEach(t=>t.stop());
    if(raf)cancelAnimationFrame(raf);
    const constraints={audio:{
      deviceId:deviceId?{exact:deviceId}:undefined,
      echoCancellation:false, noiseSuppression:false, autoGainControl:false
    }};
    stream=await navigator.mediaDevices.getUserMedia(constraints);
    if(!ctx)ctx=new (window.AudioContext||window.webkitAudioContext)();
    if(ctx.state==='suspended')await ctx.resume();
    analyser=ctx.createAnalyser(); analyser.fftSize=2048; analyser.smoothingTimeConstant=.2;
    ctx.createMediaStreamSource(stream).connect(analyser);
    await enumerate();
    const track=stream.getAudioTracks()[0];
    const settings=track.getSettings();
    if(settings.deviceId){devices.value=settings.deviceId;localStorage.setItem('voiceMeterDevice',settings.deviceId);}
    status.textContent='Подключено: '+(track.label||'аудиовход');
    peak=0; draw();
  }catch(e){
    status.textContent='Не удалось открыть микрофон: '+e.message;
    status.className='status warn';
  }
}

function draw(){
  const a=new Float32Array(analyser.fftSize); analyser.getFloatTimeDomainData(a);
  let sum=0,max=0;
  for(let i=0;i<a.length;i++){sum+=a[i]*a[i];max=Math.max(max,Math.abs(a[i]));}
  const rms=Math.sqrt(sum/a.length);
  // visual 0..100 scale, intentionally sensitive enough for speech/shouting
  const val=Math.max(0,Math.min(100,Math.round((20*Math.log10(Math.max(rms,0.00001))+60)*1.67)));
  peak=Math.max(peak,val);
  fill.style.width=val+'%'; level.textContent=val; peakEl.textContent=peak;
  raf=requestAnimationFrame(draw);
}

document.getElementById('permission').onclick=async()=>{
  await connect(localStorage.getItem('voiceMeterDevice')||'');
};
document.getElementById('refresh').onclick=enumerate;
devices.onchange=()=>{localStorage.setItem('voiceMeterDevice',devices.value);connect(devices.value);}
navigator.mediaDevices?.addEventListener?.('devicechange',enumerate);
if(!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia){
  status.textContent='Этот браузер не поддерживает доступ к микрофону.'; status.className='status warn';
}else enumerate();
</script></body></html>
"""

@app.get("/")
def index():
    return render_template_string(HTML)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
