'use strict';
const $ = id => document.getElementById(id);
let catalog, scenario, session, language = 'cnr', busy = false, switching = false, revision = 0;
let transcript = [], sessions = {}, controller;
let relationship=null;
function showRelationship(value) {
  relationship=value || null;
  $('rapport').hidden=!relationship;
  if(!relationship) return;
  $('comfort').value=relationship.comfort;
  $('comfort-value').textContent=`${relationship.comfort}/100`;
  $('openness').textContent=` · ${relationship.openness} · ${relationship.status==='ended'?'session ended':relationship.status==='boundary'?'boundary set':'conversation open'}`;
  $('rapport-detail').textContent=`Trust ${relationship.trust}/100 · Distress ${relationship.distress}/100 · Reply budget up to ${relationship.word_limit} words when relevant`;
}
const status = (text, error=false) => { $('status').textContent=text; $('status').classList.toggle('error',error); };
async function api(path, data, signal) {
  const response = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data), signal});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Request failed');
  return result;
}
function controls() {
  const ended=relationship?.status==='ended';
  $('message').disabled = !session || busy || switching || ended;
  $('send').disabled = !session || busy || switching || ended;
  $('stop').disabled = !busy || switching;
  $('restart').disabled = !catalog || switching;
  $('language').disabled = switching;
  $('export').disabled = !transcript.length;
  document.querySelectorAll('nav button').forEach(button => button.disabled = switching);
}
function renderCharacters() {
  $('characters').replaceChildren();
  for (const item of catalog.scenarios) {
    const button=document.createElement('button');
    button.classList.toggle('active',item.id===scenario);
    button.setAttribute('aria-pressed',String(item.id===scenario));
    const name=document.createElement('strong'); name.textContent=`${item.character_name} · ${item.age}`; button.append(name);
    if ($('descriptions').checked) {const info=document.createElement('small'); info.textContent=item.summary; button.append(info);}
    button.onclick=()=>start(item.id,$('language').value);
    $('characters').append(button);
  }
  controls();
}
function message(role, segments, response) {
  const entry={role,segments, ...(response ? {generation_ms:response.generation_ms, relationship:response.relationship, memory:response.memory} : {})};
  transcript.push(entry);
  const bubble=document.createElement('article'); bubble.className=`message ${role}`;
  const speaker=document.createElement('div'); speaker.className='speaker'; speaker.textContent=role==='user'?'You':$('patient').textContent; bubble.append(speaker);
  for(const segment of segments) {
    const text=document.createElement('p'); text.textContent=segment.text; bubble.append(text);
    if(segment.emotion) {const cue=document.createElement('div'); cue.className='cue'; cue.textContent=`${segment.emotion} · intensity ${Math.round(segment.intensity*100)}% · ${segment.gesture.replaceAll('_',' ')} · ${segment.voice_style} voice · ${segment.gaze} gaze`; bubble.append(cue);}
  }
  if(response && response.generation_ms>0) {const time=document.createElement('div'); time.className='time'; time.textContent=`Reply generated in ${(response.generation_ms/1000).toFixed(1)} s`; bubble.append(time);}
  if(response?.relationship) {const record=document.createElement('div');record.className='relationship-note';record.textContent=`Comfort ${response.relationship.comfort}/100 · ${response.relationship.openness}${response.relationship.status==='ended'?' · session ended':response.relationship.status==='boundary'?' · boundary set':''}`;bubble.append(record);}
  $('messages').append(bubble); bubble.scrollIntoView({block:'nearest'}); controls();
  return entry;
}
async function cancel() {
  if(!busy || !session) return;
  ++revision; controller?.abort();
  status('Stopping reply…');
  try {
    await api('/interrupt',{language,session_id:session});
    const last=transcript.at(-1); if(last?.role==='user') last.interrupted=true;
    status('Reply stopped. The model may need a moment to finish its current computation.');
  } catch(error) {status(error.message,true);}
  finally {busy=false; controls();}
}
async function start(id, nextLanguage) {
  if(switching) return;
  switching=true; controls();
  try {
    await cancel(); ++revision;
    const result=await api('/session',{language:nextLanguage,scenario_id:id,session_id:sessions[nextLanguage]});
    language=nextLanguage; scenario=id; session=result.session_id; sessions[language]=session;
    showRelationship(result.relationship);
    transcript=[]; $('messages').replaceChildren(); $('message').value=''; $('patient').textContent=result.character_name;
    $('language').value=language; renderCharacters(); status('Opening the conversation…');
    const opening=await api('/turn',{language,session_id:session,opening:true});
    showRelationship(opening.relationship); message('assistant',opening.segments,opening); status('Ready · speak naturally, one question at a time.');
  } catch(error) {status(error.message,true);}
  finally {switching=false; controls(); $('message').focus();}
}
$('composer').onsubmit=async event=>{
  event.preventDefault(); const text=$('message').value.trim(); if(!text || busy || switching || !session || relationship?.status==='ended') return;
  const ticket=++revision; controller=new AbortController(); busy=true;
  const entry=message('user',[{text}]); $('message').value=''; controls(); status(`${$('patient').textContent} is responding…`);
  try {
    const result=await api('/turn',{language,session_id:session,text},controller.signal);
    if(ticket!==revision) return;
    showRelationship(result.relationship); message('assistant',result.segments,result);
    status(relationship?.status==='ended'?'The patient ended the session. Choose New conversation to try again.':'Ready');
  } catch(error) {if(ticket===revision) {entry.failed=true; status(error.message,true); $('message').value=text;}}
  finally {if(ticket===revision) {busy=false; controls(); $('message').focus();}}
};
$('message').onkeydown=event=>{if(event.key==='Enter'&&!event.shiftKey&&!event.isComposing){event.preventDefault();$('composer').requestSubmit();}};
$('stop').onclick=cancel;
$('restart').onclick=()=>start(scenario,$('language').value);
$('language').onchange=()=>start(scenario,$('language').value);
$('descriptions').onchange=renderCharacters;
$('emotions').onchange=()=>document.body.classList.toggle('show-emotions',$('emotions').checked);
$('export').onclick=()=>{
  const value={character:$('patient').textContent,language,exported_at:new Date().toISOString(),messages:transcript};
  const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));
  const link=document.createElement('a'); link.href=url; link.download=`conversation-${$('patient').textContent.toLowerCase()}-${Date.now()}.json`; link.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
};
(async()=>{try{const response=await fetch('/catalog'); if(!response.ok)throw new Error('Local chat service unavailable');catalog=await response.json();scenario=catalog.default_scenario_id;renderCharacters();await start(scenario,language);}catch(error){status(error.message,true);}})();
