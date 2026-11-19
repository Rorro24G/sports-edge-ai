// Execute animation and component protocol against a minimal DOM test double.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('web/brain_portal/index.html','utf8');
const code=html.split('<script>')[1].split('</script>')[0];
const pages=['picks','parlays','noticias','simulaciones','historial','calendario'];

// Regression checks: looping neon effects must preserve the six navigation targets.
for(const keyframe of ['brand-breathe','node-drift','neuron-heartbeat','neuron-aura','label-float']){
 assert(html.includes('@keyframes '+keyframe),'missing animation '+keyframe);
}
assert(html.includes('.reduced #stage .brand'),'motion-reduction CSS missing');
assert(code.includes('const motion=(reduced||paused)?0:t'),'motion and pause behavior missing');
assert(code.includes('if(!reduced&&i%4===0'),'travelling wire highlights missing');
assert(code.includes('.map(project)'),'wire geometry projection missing');
assert(code.includes('rotCa=Math.cos(angle)'),'angle trigonometry must be reused per frame');
assert(code.includes('const frameInterval=lowPower?33:18'),'adaptive frame pacing missing');
assert(code.includes('function drawBrainMass()'),'cerebro volumétrico sin masa no permitido');
assert(code.includes('drawBrainMass();'),'se debe pintar volumen antes de líneas');
assert(html.includes('Cerebro tridimensional volumétrico'),'descripción accesible del cerebro falta');
assert(code.includes('const d=lowPower?1:Math.min(devicePixelRatio||1,1.35)'),
  'pixel budget must be capped for high-DPI devices');
assert(!code.includes('zoom=1+Math.pow(ease,2)*20'),
  'old 20x dive zoom causes expensive offscreen Canvas work');
assert(html.includes('animation:fast-heart'),'neon motion should survive reduced paint');
assert(html.includes('MOVIMIENTO ON'),'motion control must be visible');
assert(html.includes('rgba(5,5,6,.24)'),'intro must reveal moving brain');
assert(code.includes('ctx.globalAlpha=.38;drawBrain(t)'),'intro canvas must be visible');
assert(code.includes("state==='intro'"),'ambient brain on entry screen missing');
assert(!code.includes("angle+=dt*.00035"),'el cerebro no debe girar en 360 grados');
assert(!code.includes("angle+=dt*.00025"),'el cerebro no debe girar solo en portada');
assert(code.includes('floatY=0;'),
  'falta flotación lenta de cerebro y nodos');
assert(code.includes('Math.max(-.30,Math.min(.30,angle+'),
  'no permitir giro manual completo de 360');
assert(code.includes('flightBlend=ease'),'node-directed transition missing');
assert(html.includes('@keyframes portal-depth-launch'),'entry depth animation missing');
assert(html.includes('@keyframes portal-title-launch'),'page title animation missing');
assert(code.includes("stage.classList.add('portal-diving')"),'section launch class missing');
assert(html.includes('neuron-heartbeat 1.75s'),'always-on node beat missing');

function run(reduced,page){
 const messages=[],listeners={},arcs=[];let callback;
 const element=()=>({style:{},classList:{add(){},toggle(){}},setAttribute(){},focus(){},inert:false,clientWidth:1000,clientHeight:760});
 const elements=Object.fromEntries(['scene','stage','intro','brain-ui','flight-label','enter','rotate','reset','motion-toggle'].map(n=>[n,element()]));
 elements.scene.getContext=()=>new Proxy({},{get:(_,key)=>key==='arc'?((...args)=>arcs.push(args)):(key==='createRadialGradient'?(()=>({addColorStop(){}})):(()=>{}))});
 const nodes=pages.map(page=>Object.assign(element(),{dataset:{page},innerText:page.toUpperCase()}));
 const parent={postMessage:v=>messages.push(v)};
 const window={parent};
 const context={console,Math,Date,window,performance:{now:()=>0},devicePixelRatio:1,
 document:{body:element(),getElementById:id=>elements[id],querySelectorAll:()=>nodes},
 matchMedia:()=>({matches:reduced}),addEventListener:(n,f)=>listeners[n]=f,
 requestAnimationFrame:f=>callback=f,setTimeout};
 vm.runInNewContext(code,context);
 assert(messages.some(m=>m.type==='streamlit:componentReady'));
 listeners.message({source:parent,data:{type:'streamlit:render',args:{}}});
 assert(elements['motion-toggle'].textContent.includes('ON'),'motion starts enabled even when OS prefers reduced motion');
  elements.enter.onclick();callback(1800);
 assert.equal(elements['brain-ui'].inert,false);
 callback(1850);
 const before=nodes.map(n=>[n.style.left,n.style.top]);
 const firstHalo=arcs[arcs.length-1][2];
 const firstSignal=arcs[0].slice(0,2);
 arcs.length=0;
 callback(2250);
 const after=nodes.map(n=>[n.style.left,n.style.top]);
 assert.deepEqual(before,after,'brain and labels must remain fixed while signals move');
 assert.notDeepEqual(firstSignal,arcs[0].slice(0,2),'signal must travel along the fixed mesh');
 assert.notEqual(firstHalo,arcs[arcs.length-1][2],'canvas aura must pulse');
 nodes[0].onpointerenter?.();
 const oldAngle=vm.runInNewContext('angle',context);
 callback(60000);
 assert.equal(vm.runInNewContext('angle',context),oldAngle,
   'front-facing brain must not turn even after a minute');
 const minute=nodes.map(n=>[n.style.left,n.style.top]);
 callback(120000);
 assert.deepEqual(minute,nodes.map(n=>[n.style.left,n.style.top]),
   'brain must stay fixed while signals continue');
 elements['motion-toggle'].onclick();
 assert(elements['motion-toggle'].textContent.includes('ACTIVAR'));
 callback(120100);
 const still=nodes.map(n=>[n.style.left,n.style.top]);
 callback(120500);
 assert.deepEqual(still,nodes.map(n=>[n.style.left,n.style.top]),'explicit pause must work');
 elements['motion-toggle'].onclick();
 assert(elements['motion-toggle'].textContent.includes('ON'));
 nodes[pages.indexOf(page)].onclick();callback(122000);
 const selected=messages.find(m=>m.type==='streamlit:setComponentValue');
 assert.equal(selected.value.page,page);assert.equal(selected.dataType,'json');
 assert.equal(selected.isStreamlitMessage,true);
}
for(const page of pages){run(false,page);run(true,page)}
console.log('PORTAL_TRANSITIONS_AND_SIX_ROUTES_OK');

