'use strict';
const $ = id => document.getElementById(id);
let catalog, runList = [], selected = [], loaded = [], active = null, loading = false, reloadPending = false, detectedModel = '';
const aliases = new Map();
const node = (tag, text, className) => {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (className) n.className = className;
  return n;
};
const title = value => value.replaceAll('_', ' ').replace(/^./, c => c.toUpperCase());
function notice(message, error = false) { $('notice').textContent = message; $('notice').className = error ? 'error' : ''; }
async function api(path, data) {
  const r = await fetch(path, data === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
  const v = await r.json(); if (!r.ok) throw Error(v.error || r.statusText); return v;
}
function name(run) {
  if (!$('blind').checked) return run.label || run.metadata.selection.label;
  if (!aliases.has(run.id)) aliases.set(run.id, `Model ${String.fromCharCode(65 + aliases.size)}`);
  return aliases.get(run.id);
}
function choice(parent, value, text, checked, hint) {
  const l = node('label'), box = node('input'); box.type='checkbox'; box.value=value; box.checked=checked;
  l.append(box); const span = node('span', text); if(hint) span.append(node('small', hint));
  l.append(span); parent.append(l); box.addEventListener('change', count);
}
const checked = id => [...$(id).querySelectorAll('input:checked')].map(n => n.value);
function count() {
  const seeds = $('seeds').value.split(',').filter(s=>s.trim());
  $('count').textContent = catalog.cases.filter(c=>checked('cases').includes(c.id)).reduce((n,c)=>n+c.turns.length,0)*checked('languages').length*seeds.length;
}
async function refreshModel() {
  try {
    const m = await api('/api/model');
    detectedModel = `${m.id} · ${m.meta.ftype || 'GGUF'} · ${m.generation_settings?.n_ctx || '?'} context tokens`;
    $('model').textContent = $('blind').checked ? 'Model identity hidden during review.' : detectedModel;
    $('label').placeholder = (m.model_path || m.id).split(/[\\/]/).pop();
  } catch(e) { $('model').textContent = `Start a local llama.cpp model first. ${e.message}`; }
}
async function refreshRuns() {
  const state = await api('/api/runs'); active=state.active; runList=state.runs;
  $('stop').disabled=!active; $('start').disabled=!!active; renderRuns();
  renderActive();
}
function renderActive() {
  const current=runList.find(r=>r.id===active);
  $('active').textContent=current ? `Running ${name(current)} · ${current.current ? `${current.current.case}, ${current.current.language}, turn ${current.current.turn}` : 'preparing'} · ${current.progress.done}/${current.progress.total} turns` : 'No run in progress.';
}
function renderRuns() {
  // Keep each checkbox mounted while progress polls update its neighbouring cells.
  // Replacing the table during a click can discard the user's selection event.
  const existing = new Map([...$('runs').children].map(tr=>[tr.dataset.runId,tr]));
  for (const run of runList) {
    let tr=existing.get(run.id);
    if(!tr){
      tr=node('tr');tr.dataset.runId=run.id;
      const pick=node('input');pick.type='checkbox';
      pick.addEventListener('change',async()=>{
        if(pick.checked && selected.length>=2){pick.checked=false;return notice('Choose at most two runs.',true);}
        selected=pick.checked?[...selected,run.id]:selected.filter(id=>id!==run.id); await loadResults();
      });
      const td=node('td');td.append(pick);tr.append(td);
      for(let n=0;n<4;n++)tr.append(node('td'));
    }
    existing.delete(run.id);
    const pick=tr.querySelector('input');pick.checked=selected.includes(run.id);
    pick.setAttribute('aria-label',`Compare ${name(run)}`);
    const label=tr.children[1];label.textContent=name(run);
    label.append(node('small',`${new Date(run.created_at).toLocaleString()} · ${run.selection.languages.join(', ')} · seeds ${run.selection.seeds.join(', ')}`));
    const progress=tr.children[2];progress.textContent=`${run.progress.done}/${run.progress.total}`;progress.append(node('small',run.status));
    tr.children[3].textContent=String(run.reviewed_groups);
    const out=tr.children[4];out.replaceChildren();const a=node('a','JSON');a.href=`/api/export/${run.id}`;
    a.title='Includes model identity, complete requests, results and reviews';out.append(a);
    const position=runList.indexOf(run);
    if($('runs').children[position]!==tr)$('runs').insertBefore(tr,$('runs').children[position]||null);
  }
  for(const tr of existing.values())tr.remove();
  if(!runList.length){const tr=node('tr'),td=node('td','No runs yet. Choose a model and start a screen.','muted');td.colSpan=5;tr.append(td);$('runs').append(tr);}
}
async function loadResults() {
  if(loading){reloadPending=true;return;} loading=true;
  try {
    loaded=await Promise.all(selected.map(id=>api(`/api/run/${id}`)));
    const previous=$('conversation').value, groups=new Map();
    for(const run of loaded)for(const row of run.rows)groups.set(row.group_id,`${row.title} · ${catalog.languages[row.language]} · seed ${row.seed}`);
    $('conversation').replaceChildren();
    for(const [key,text]of groups){const o=node('option',text);o.value=key;$('conversation').append(o);}
    if(groups.has(previous))$('conversation').value=previous;
    if(loaded.length===2){
      const [a,b]=loaded;
      const compatible=a.metadata.suite_sha256===b.metadata.suite_sha256&&a.metadata.source_sha256===b.metadata.source_sha256;
      $('compatibility').textContent=compatible?'Same scenario set and source snapshot. Compare matching languages/seeds; check hardware and server context before comparing timings.':'Different suites or source snapshots. Read matching conversations, but do not treat aggregate scores/timings as a controlled comparison.';
    } else $('compatibility').textContent='Human ratings: 1 = major failure, 2 = weak, 3 = usable with issues, 4 = good, 5 = convincing. Unreviewed dimensions stay blank.';
    renderConversation();
  } catch(e){notice(e.message,true);} finally{loading=false;if(reloadPending){reloadPending=false;await loadResults();}}
}
function metric(run,rows){
  const relevant=rows.filter(r=>r.status!=='skipped'), complete=relevant.filter(r=>r.status==='completed');
  const exact=relevant.flatMap(r=>r.checks).filter(c=>c.kind==='exact_answer');
  const times=complete.map(r=>r.seconds).sort((a,b)=>a-b);
  const median=times.length?(times[Math.floor((times.length-1)/2)]+times[Math.floor(times.length/2)])/2:null;
  const m=node('div',undefined,'metric');m.append(node('strong',name(run)));
  m.append(node('div',`${complete.length}/${relevant.length} attempted turns completed · ${rows.length-relevant.length} skipped`));
  m.append(node('div',`${median===null?'—':median.toFixed(2)+' s'} median text response${exact.length?` · ${exact.filter(c=>c.passed).length}/${exact.length} exact answers`:''}`));
  m.append(node('small',`Run ${run.status}. Language/character quality requires review.`));return m;
}
function renderConversation(){
  const group=$('conversation').value;$('comparison').replaceChildren();$('metrics').replaceChildren();
  if(!loaded.length){$('comparison').append(node('p','Select a run above to review its conversations.','empty'));return;}
  for(const run of loaded){
    const rows=run.rows.filter(r=>r.group_id===group);$('metrics').append(metric(run,rows));
    const col=node('article',undefined,'column');col.append(node('h3',name(run)));
    if(run.error)col.append(node('p',run.error,'error'));
    if(run.source_changed_during_run)col.append(node('p','Source changed during this run; repeat before comparing.','error'));
    if(!rows.length){col.append(node('p','This conversation has not been recorded in this run.','muted'));$('comparison').append(col);continue;}
    for(const row of rows){
      const t=node('div',undefined,'turn');
      t.append(node('div',`TURN ${row.turn} · ${row.seconds!==undefined?row.seconds.toFixed(2)+' s':row.status}`,'number'));
      t.append(node('div',row.input,'student'));
      if(row.source==='application_policy')t.append(node('span','Application-authored departure, not model speech','tag'));
      t.append(node('div',row.reply||row.error||row.skip_reason||'',row.status==='error'?'patient error':'patient'));
      if(row.response){
        t.append(node('div',row.response.segments.map(x=>`${x.emotion} ${Math.round(x.intensity*100)}% · ${x.gesture} · ${x.voice_style}`).join(' / '),'controls'));
        const rel=row.response.relationship;
        if(rel)t.append(node('div',`Comfort ${rel.comfort} · Trust ${rel.trust} · Distress ${rel.distress} · ${rel.status}`,'hint'));
      }
      t.append(node('div',row.expectation,'expected'));
      for(const check of row.checks.filter(c=>c.kind==='exact_answer'))t.append(node('p',`${check.passed?'Pass':'Fail'} · exact answer expected: ${check.expected}`,check.passed?'pass':'error'));
      if(!$('blind').checked){
        const d=node('details');d.append(node('summary','Requests, raw model replies and context trimming'));
        d.append(node('pre',JSON.stringify({source:row.source,calls:row.model_calls,context:row.context_events,memory:row.response?.memory},null,2)));t.append(d);
      }
      col.append(t);
    }
    col.append(reviewForm(run,group,rows));
    if(!$('blind').checked){
      const details=node('details');details.append(node('summary','Model, hardware and evaluation protocol'));
      details.append(node('pre',JSON.stringify({model:run.metadata.model,hardware:run.metadata.hardware,protocol:run.metadata.protocol,suite_sha256:run.metadata.suite_sha256,source_sha256:run.metadata.source_sha256},null,2)));col.append(details);
    }
    $('comparison').append(col);
  }
}
function reviewForm(run,group,rows){
  const form=node('form',undefined,'review-form');form.append(node('h3','Your assessment'));
  form.append(node('p','Rate the complete exchange. In notes, cite the turn and explain the problem or strength.','hint'));
  const whoLabel=node('label','Reviewer name or initials'), who=node('input');who.maxLength=60;who.required=true;
  who.value=localStorage.getItem('model-lab-reviewer')||'';whoLabel.append(who);form.append(whoLabel);
  const grid=node('div',undefined,'score-grid'), inputs={};
  for(const [key,description]of Object.entries(catalog.rubric)){
    if(rows[0].track==='reasoning'&&['character','emotion'].includes(key))continue;
    const label=node('label',title(key));label.title=description;const select=node('select');
    select.append(node('option','Not assessed'));select.firstChild.value='';
    for(let n=1;n<=5;n++){const o=node('option',`${n} · ${['','Major failure','Weak','Usable with issues','Good','Convincing'][n]}`);o.value=n;select.append(o);}
    label.append(select);grid.append(label);inputs[key]=select;
  }
  form.append(grid);const flags=node('div',undefined,'checks');for(const f of catalog.flags)choice(flags,f,title(f),false);form.append(flags);
  const notesLabel=node('label','Evidence / notes'), notes=node('textarea');notes.maxLength=5000;notesLabel.append(notes);form.append(notesLabel);
  const button=node('button','Save review','primary');button.type='submit';form.append(button);
  const forget=node('button','Forget reviewer name','quiet');forget.type='button';
  forget.addEventListener('click',()=>{
    localStorage.removeItem('model-lab-reviewer');
    for(const input of document.querySelectorAll('.review-form input[required]')){
      input.value='';input.dispatchEvent(new Event('change'));
    }
  });form.append(forget);
  const saved=node('div',undefined,'saved');form.append(saved);const existing=run.reviews[group]||{};
  function populate(){
    const old=existing[who.value.trim()];
    for(const [key,input]of Object.entries(inputs))input.value=old?.scores[key]||'';
    notes.value=old?.notes||'';for(const box of flags.querySelectorAll('input'))box.checked=!!old?.flags.includes(box.value);
    saved.textContent=old?`Saved ${new Date(old.updated_at).toLocaleString()} · ${old.turns_seen} recorded turns at review`:'Not reviewed by this reviewer.';
  }
  who.addEventListener('change',populate);populate();
  if(Object.keys(existing).length){const other=node('details');other.append(node('summary',`${Object.keys(existing).length} saved reviewer(s)`));other.append(node('pre',JSON.stringify(existing,null,2)));form.append(other);}
  form.addEventListener('submit',async e=>{
    e.preventDefault();button.disabled=true;
    try{
      const scores=Object.fromEntries(Object.entries(inputs).filter(([,v])=>v.value).map(([k,v])=>[k,Number(v.value)]));
      const data={group_id:group,reviewer:who.value.trim(),scores,notes:notes.value,flags:[...flags.querySelectorAll('input:checked')].map(n=>n.value)};
      await api(`/api/review/${run.id}`,data);localStorage.setItem('model-lab-reviewer',data.reviewer);
      existing[data.reviewer]={...data,updated_at:new Date().toISOString(),turns_seen:rows.length};saved.textContent='Review saved locally.';await refreshRuns();
    }catch(e){saved.textContent=e.message;}finally{button.disabled=false;}
  });return form;
}
async function start(){
  try{
    const raw=$('seeds').value.split(',').map(s=>s.trim());if(raw.some(s=>!/^\d+$/.test(s)))throw Error('Enter integer seeds separated by commas.');
    const result=await api('/api/start',{label:$('label').value,languages:checked('languages'),seeds:raw.map(Number),case_ids:checked('cases')});
    selected=[result.id];notice(`Started ${result.planned_turns} turns. Results are saved after every turn. Use Refresh replies while the run progresses; review forms are never refreshed automatically.`);
    await refreshRuns();await loadResults();
  }catch(e){notice(e.message,true);}
}
async function init(){
  catalog=await api('/api/catalog');$('version').textContent=catalog.suite_version;
  for(const [key,label]of Object.entries(catalog.languages))choice($('languages'),key,label,key==='bs');
  for(const c of catalog.cases)choice($('cases'),c.id,c.title,c.quick,`${c.track==='patient'?'Patient':'Reasoning'} · ${c.turns.length} turns`);
  $('quick').onclick=()=>{for(const box of $('cases').querySelectorAll('input'))box.checked=catalog.cases.find(c=>c.id===box.value).quick;count();};
  $('full').onclick=()=>{for(const box of $('cases').querySelectorAll('input'))box.checked=true;count();};
  $('seeds').oninput=count;$('refresh-model').onclick=refreshModel;$('start').onclick=start;
  $('stop').onclick=async()=>{try{const r=await api(`/api/cancel/${active}`,{});notice(r.message);}catch(e){notice(e.message,true);}};
  $('reload').onclick=loadResults;$('conversation').onchange=renderConversation;
  $('blind').onchange=()=>{
    $('label').parentElement.hidden=$('blind').checked;
    $('model').textContent=$('blind').checked?'Model identity hidden during review.':detectedModel;
    renderRuns();renderActive();renderConversation();
  };
  count();await refreshModel();await refreshRuns();
  if(runList.length){selected=[runList[0].id];renderRuns();await loadResults();}
  setInterval(()=>refreshRuns().catch(e=>notice(e.message,true)),4000);
}
init().catch(e=>notice(e.message,true));
