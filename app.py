from flask import Flask, render_template_string, redirect, request, jsonify
import os, time, threading

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
  fill.style.width=val+'%'; level.textContent=val; peakEl.textContent=peak; publishVoiceLevel(val);
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


lock = threading.Lock()
game = {"participants":[],"current":-1,"phase":"idle","started":None,"peak":0,"live":0}
PREP=3
ROUND=5

def update_game():
    if game["phase"]=="prep" and time.time()-game["started"]>=PREP:
        game["phase"]="play"; game["started"]=time.time(); game["peak"]=0
    elif game["phase"]=="play" and time.time()-game["started"]>=ROUND:
        i=game["current"]
        if 0<=i<len(game["participants"]):
            game["participants"][i]["score"]=round(game["peak"])
            game["participants"][i]["done"]=True
        game["phase"]="timeup"

def game_data():
    update_game()
    rem=0
    if game["phase"]=="prep": rem=max(0,PREP-(time.time()-game["started"]))
    elif game["phase"]=="play": rem=max(0,ROUND-(time.time()-game["started"]))
    return {**game,"participants":[dict(x) for x in game["participants"]],"remaining":rem}

CONTROL_HTML = """<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Voice Meter — ведущий</title><style>
body{margin:0;background:#020b07;color:#f4f5ef;font-family:Arial,sans-serif}.wrap{max-width:950px;margin:auto;padding:25px}.top{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px}.brand{font-size:25px;font-weight:900}.m{border:2px solid #20ee78;padding:7px 10px}.w{color:#747d78}.a{color:#20ee78}.p{border:1px solid #174b30;background:#081810;border-radius:22px;padding:22px;margin:16px 0}.label{color:#84968c;font-size:13px;font-weight:900;letter-spacing:2px}button,a{border:0;border-radius:14px;padding:15px 22px;font-size:16px;font-weight:900;text-decoration:none;display:inline-block;cursor:pointer}.g{background:#20eb72;color:#001b0d}.d{background:#18231d;color:#d5ded9}.r{background:#3b171d;color:#ff9da9}input{background:#07110c;border:1px solid #22543a;border-radius:14px;color:#fff;padding:14px;font-size:18px}.row{display:flex;gap:12px;align-items:end;flex-wrap:wrap}.name{font-size:38px;font-weight:900}.big{font-size:75px;color:#20ee78;font-weight:900}.res{display:flex;justify-content:space-between;border-bottom:1px solid #12301f;padding:11px 2px}.res b{color:#20ee78}.sep{margin-top:28px;padding-top:20px;border-top:1px solid #174b30}
</style></head><body><div class="wrap"><div class="top"><div class="brand"><span class="m">МУЖСКОЕ</span> <span class="a">/</span> <span class="w">ЖЕНСКОЕ</span></div><b class="a">VOICE METER</b></div>
<div class="p"><div class="label">СТРАНИЦА ВЕДУЩЕГО</div><div class="row" style="margin-top:12px"><div><div class="label">КОЛИЧЕСТВО УЧАСТНИКОВ</div><input id="n" type="number" min="1" max="10" value="4"></div><button class="g" onclick="init()">НАЧАТЬ КОНКУРС</button><button class="r" onclick="post('/api/reset')">СБРОСИТЬ</button><a class="d" href="/screen" target="_blank">ГОСТЕВОЙ ЭКРАН</a></div></div><div class="p" id="game">ОЖИДАНИЕ</div></div>
<script>
async function post(u,b={}){return fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b)}).then(r=>r.json())}function init(){post('/api/init',{count:+n.value})}
function draw(s){let e=document.getElementById('game');if(!s.participants.length){e.innerHTML='ОЖИДАНИЕ';return}let p=s.participants[s.current],t=s.phase==='prep'?'ОТСЧЁТ: '+Math.max(1,Math.ceil(s.remaining)):s.phase==='play'?'ЗАМЕР · '+Math.ceil(s.remaining)+' СЕК.':s.phase==='timeup'?'ВРЕМЯ!':s.phase==='finished'?'КОНКУРС ЗАВЕРШЁН':'ГОТОВ';let b=s.phase==='ready'?'<button class="g" onclick="post(\\'/api/start\\')">СТАРТ</button>':s.phase==='timeup'?'<button class="d" onclick="post(\\'/api/next\\')">СЛЕДУЮЩИЙ УЧАСТНИК →</button>':'';let rs=s.participants.filter(x=>x.done).map(x=>`<div class="res"><span>${x.name}</span><b>${x.score}</b></div>`).join('');e.innerHTML=`<div class="label">СЕЙЧАС ИГРАЕТ</div><div class="name">${p?p.name:''}</div><h2>${t}</h2><div class="big">${s.peak}</div>${b}<div class="sep"><div class="label">РЕЗУЛЬТАТЫ</div>${rs}</div>`}
async function poll(){try{draw(await fetch('/api/state?_='+Date.now(),{cache:'no-store',headers:{'Cache-Control':'no-cache'}}).then(r=>r.json()))}catch(e){}setTimeout(poll,150)}poll()
</script></body></html>"""

SCREEN_HTML = """<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Voice Meter</title><style>
body{margin:0;background:#020b07;color:#f4f5ef;font-family:Arial,sans-serif}.wrap{max-width:1200px;margin:auto;padding:25px}.top{display:flex;justify-content:space-between;align-items:center}.brand{font-size:25px;font-weight:900}.m{border:2px solid #20ee78;padding:7px 10px}.w{color:#747d78}.a{color:#20ee78}.stage{text-align:center;min-height:600px;display:flex;flex-direction:column;justify-content:center}.name{font-size:48px;font-weight:900}.peak{font-size:160px;color:#20ee78;font-weight:900}.count{font-size:190px;font-weight:900}.meter{width:150px;height:380px;margin:24px auto;background:#06110b;border:1px solid #205239;border-radius:22px;overflow:hidden;display:flex;align-items:flex-end}.fill{width:100%;height:0;background:linear-gradient(0deg,#19df68 0%,#9be83e 60%,#ffd63e 80%,#ff5656 100%);transition:height .06s linear}.results{border:1px solid #174b30;background:#081810;border-radius:20px;padding:18px}.res{display:flex;justify-content:space-between;border-bottom:1px solid #12301f;padding:10px}.res b{color:#20ee78}
</style></head><body><div class="wrap"><div class="top"><div class="brand"><span class="m">МУЖСКОЕ</span> <span class="a">/</span> <span class="w">ЖЕНСКОЕ</span></div><b class="a">VOICE METER</b></div><div class="stage" id="stage"></div><div class="results" id="results"></div></div>
<script>
function draw(s){let p=s.participants[s.current],h='';if(!s.participants.length)h='<div class="name">ОЖИДАНИЕ</div>';else if(s.phase==='prep')h=`<div class="name">${p.name}</div><div class="count">${Math.max(1,Math.ceil(s.remaining))}</div>`;else if(s.phase==='play')h=`<div class="name">${p.name}</div><div class="peak">${s.peak}</div><div class="meter"><div class="fill" style="height:${s.live}%"></div></div><h2>${Math.ceil(s.remaining)} СЕК.</h2>`;else if(s.phase==='timeup')h=`<div class="name">${p.name}</div><h1>ВРЕМЯ!</h1><div class="peak">${p.score}</div>`;else if(s.phase==='finished')h='<div class="name">КОНКУРС ЗАВЕРШЁН</div>';else h=`<div class="name">${p.name}</div><h1>ПРИГОТОВЬТЕСЬ</h1>`;stage.innerHTML=h;results.innerHTML=s.participants.filter(x=>x.done).map(x=>`<div class="res"><span>${x.name}</span><b>${x.score}</b></div>`).join('')}
async function poll(){try{draw(await fetch('/api/state?_='+Date.now(),{cache:'no-store',headers:{'Cache-Control':'no-cache'}}).then(r=>r.json()))}catch(e){}setTimeout(poll,100)}poll()
</script></body></html>"""

@app.get("/api/state")
def api_state():
    with lock:return jsonify(game_data())

@app.post("/api/init")
def api_init():
    d=request.get_json(silent=True) or {}
    try:n=max(1,min(10,int(d.get("count",4))))
    except:n=4
    with lock:
        game.update(participants=[{"name":f"УЧАСТНИК {i+1}","score":None,"done":False} for i in range(n)],current=0,phase="ready",started=None,peak=0,live=0)
        return jsonify(game_data())

@app.post("/api/start")
def api_start():
    with lock:
        if game["phase"]=="ready":game.update(phase="prep",started=time.time(),peak=0,live=0)
        return jsonify(game_data())

@app.post("/api/level")
def api_level():
    d=request.get_json(silent=True) or {}
    try:v=max(0,min(100,float(d.get("level",0))))
    except:v=0
    with lock:
        update_game();game["live"]=v
        if game["phase"]=="play":game["peak"]=max(game["peak"],v)
        return jsonify(ok=True)

@app.post("/api/next")
def api_next():
    with lock:
        if game["phase"]=="timeup":
            if game["current"]+1<len(game["participants"]):game.update(current=game["current"]+1,phase="ready",started=None,peak=0,live=0)
            else:game.update(current=len(game["participants"]),phase="finished",started=None,peak=0,live=0)
        return jsonify(game_data())

@app.post("/api/reset")
def api_reset():
    with lock:
        game.update(participants=[],current=-1,phase="idle",started=None,peak=0,live=0)
        return jsonify(game_data())

@app.get("/")
def index():
    return redirect("/setup")

@app.get("/setup")
def setup():
    return render_template_string(HTML)

@app.get("/control")
def control():
    return render_template_string(CONTROL_HTML)

@app.get("/screen")
def screen():
    return render_template_string(SCREEN_HTML)

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",10000)))
