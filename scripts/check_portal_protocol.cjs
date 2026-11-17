// Execute animation and component protocol against a minimal DOM test double.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync('web/brain_portal/index.html','utf8');
const code=html.split('<script>')[1].split('</script>')[0];
const pages=['picks','parlays','noticias','simulaciones','historial','calendario'];
function run(reduced,page){
 const messages=[],listeners={};let callback;
 const element=()=>({style:{},classList:{add(){},toggle(){}},setAttribute(){},focus(){},inert:false,clientWidth:1000,clientHeight:760});
 const elements=Object.fromEntries(['scene','stage','intro','brain-ui','flight-label','enter','rotate','reset'].map(n=>[n,element()]));
 elements.scene.getContext=()=>new Proxy({},{get:()=>()=>{}});
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
 elements.enter.onclick();if(!reduced)callback(1800);
 assert.equal(elements['brain-ui'].inert,false);
 nodes[pages.indexOf(page)].onclick();if(!reduced)callback(2700);
 const selected=messages.find(m=>m.type==='streamlit:setComponentValue');
 assert.equal(selected.value.page,page);assert.equal(selected.dataType,'json');
 assert.equal(selected.isStreamlitMessage,true);
}
for(const page of pages){run(false,page);run(true,page)}
console.log('PORTAL_TRANSITIONS_AND_SIX_ROUTES_OK');
