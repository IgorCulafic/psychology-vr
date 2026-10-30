'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {test}=require('node:test');

// Exercise conversation changes and actual export data without loading AI models.
function browser() {
  const elements=new Map(), calls=[], downloads=[], blobs=[];
  const state={failSession:false};
  class Element {
    constructor(tag='div') {
      this.tag=tag;this.children=[];this.value='';this.textContent='';this.hidden=false;
      this.listeners=[];this.classList={toggle(){}};
    }
    append(...children){this.children.push(...children);}
    replaceChildren(...children){this.children=children;}
    setAttribute(){}
    scrollIntoView(){}
    focus(){}
    select(){}
    setCustomValidity(value){this.validityMessage=value;}
    reportValidity(){return !this.validityMessage;}
    addEventListener(type,fn,options){this.listeners.push({type,fn,once:options?.once});}
    showModal(){this.open=true;}
    close(){
      this.open=false;
      const closing=this.listeners.filter(item=>item.type==='close');
      this.listeners=this.listeners.filter(item=>!(item.type==='close'&&item.once));
      closing.forEach(item=>item.fn());
    }
    click(){if(this.tag==='a')downloads.push(this);else this.onclick?.();}
  }
  const get=id=>{
    if(!elements.has(id))elements.set(id,new Element());
    return elements.get(id);
  };
  const catalog={default_scenario_id:'alex-earthquake',default_language:'en',scenarios:[
    {id:'alex-earthquake',character_name:'Alex',age:25},
    {id:'nikola-bereavement',character_name:'Nikola',age:42}
  ]};
  const context=vm.createContext({
    document:{getElementById:get,createElement:tag=>new Element(tag),querySelectorAll:()=>get('characters').children,body:new Element()},
    fetch:async(url,options)=>{
      const data=options ? JSON.parse(options.body) : null;
      calls.push({url,data});
      if(url==='/catalog')return {ok:true,json:async()=>catalog};
      if(url==='/session'){
        if(state.failSession)return {ok:false,json:async()=>({error:'Session unavailable'})};
        return {ok:true,json:async()=>({session_id:`session-${calls.length}`,student_name:data.student_name,
          character_name:catalog.scenarios.find(item=>item.id===data.scenario_id).character_name})};
      }
      return {ok:true,json:async()=>({segments:[{text:'Hello.'}],generation_ms:0})};
    },
    Blob,AbortController,Date,URL:{createObjectURL(blob){blobs.push(blob);return 'blob:transcript';},revokeObjectURL(){}},
    setTimeout(fn){fn();}
  });
  vm.runInContext(fs.readFileSync(path.join(__dirname,'chat.js'),'utf8'),context);
  return {get,calls,downloads,blobs,state,read:expression=>vm.runInContext(expression,context)};
}
async function flush(){await new Promise(resolve=>setImmediate(resolve));}
function submitName(ui,value){ui.get('student-name').value=value;ui.get('student-form').onsubmit({preventDefault(){}});}

test('initial conversation waits for a valid name and exports its normalized identity',async()=>{
  const ui=browser();await flush();
  assert.equal(ui.get('student-dialog').open,true);
  assert.equal(ui.calls.filter(call=>call.url==='/session').length,0);
  submitName(ui,'  A\u0301na Đurović  ');await flush();
  assert.equal(ui.calls.find(call=>call.url==='/session').data.student_name,'Ána Đurović');
  assert.equal(ui.calls.find(call=>call.url==='/session').data.language,'en');
  assert.equal(ui.get('student-label').textContent,'Student: Ána Đurović');
  assert.equal(ui.get('student-label').hidden,false);
  assert.equal(ui.read('transcript.length'),1);
  ui.get('export').onclick();
  const exported=JSON.parse(await ui.blobs[0].text());
  assert.equal(exported.student_name,'Ána Đurović');
  assert.equal(exported.character,'Alex');
  assert.match(ui.downloads[0].download,/^conversation-ána-đurović-alex-\d+\.json$/);
});

test('cancelling initial input generates no session or opening',async()=>{
  const ui=browser();await flush();ui.get('student-cancel').click();await flush();
  assert.equal(ui.calls.filter(call=>call.url!=='/catalog').length,0);
  assert.equal(ui.get('patient').textContent,'Choose a patient');
  assert.equal(ui.get('send').disabled,true);
  assert.equal(ui.get('restart').disabled,false);
});

test('cancelled language switch preserves the old conversation and export identity',async()=>{
  const ui=browser();await flush();submitName(ui,'Ana');await flush();
  const originalSession=ui.read('session'), originalCalls=ui.calls.length;
  ui.get('language').value='cnr';
  const switching=ui.get('language').onchange();
  ui.get('student-name').value='Another student';ui.get('student-cancel').click();
  await switching;
  assert.equal(ui.calls.length,originalCalls);
  assert.equal(ui.read('session'),originalSession);
  assert.equal(ui.read('studentName'),'Ana');
  assert.equal(ui.read('transcript.length'),1);
  assert.equal(ui.get('language').value,'en');
  assert.equal(ui.get('patient').textContent,'Alex');
});

test('failed session creation preserves the old transcript, student and language',async()=>{
  const ui=browser();await flush();submitName(ui,'Ana');await flush();
  const originalSession=ui.read('session');ui.state.failSession=true;
  ui.get('language').value='cnr';const switching=ui.get('language').onchange();
  submitName(ui,'Petar');await switching;
  assert.equal(ui.read('session'),originalSession);
  assert.equal(ui.read('studentName'),'Ana');
  assert.equal(ui.read('transcript.length'),1);
  assert.equal(ui.get('language').value,'en');
  assert.equal(ui.get('status').textContent,'Session unavailable');
  assert.equal(ui.get('student-label').textContent,'Student: Ana');
});

test('restart asks again and a successful new patient receives its own student',async()=>{
  const ui=browser();await flush();submitName(ui,'Ana');await flush();
  const restarting=ui.get('restart').onclick();
  assert.equal(ui.get('student-dialog').open,true);
  ui.get('student-cancel').click();await restarting;
  const selecting=ui.get('characters').children[1].onclick();
  submitName(ui,'Petar');await selecting;
  assert.equal(ui.read('studentName'),'Petar');
  assert.equal(ui.get('patient').textContent,'Nikola');
  ui.get('export').onclick();
  assert.equal(JSON.parse(await ui.blobs[0].text()).student_name,'Petar');
});

test('invalid names keep the dialog open without sending requests',async()=>{
  const ui=browser();await flush();
  for(const value of ['   ','Ana\nPetar','Ana\u200bPetar','x'.repeat(81)]){
    submitName(ui,value);
    assert.equal(ui.get('student-dialog').open,true);
    assert.ok(ui.get('student-name').validityMessage);
  }
  assert.equal(ui.calls.length,1);
  assert.equal(ui.read('filenamePart("../Ana: Petar\\\\test", "student")'),'ana-petar-test');
  assert.equal(ui.read('filenamePart("💛", "student")'),'student');
});
