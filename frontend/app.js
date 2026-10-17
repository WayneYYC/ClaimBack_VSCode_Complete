/* ClaimBack frontend. No secrets in browser; API keys remain on the server. */
const $ = (id) => document.getElementById(id);
const escapeHtml = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cash = (amount) => new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}).format(amount);
const friendly = (s) => String(s||'').replaceAll('_',' ').replaceAll('-',' ').replace(/\b\w/g,c=>c.toUpperCase());
const dateFmt = (s) => s ? new Date(s.slice(0,10)+'T12:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}) : '—';
let allCases = [], selected = null, lastResult = null, activeTab = 'evidence', view = 'overview', status = null;

async function api(path, options = {}) {
  const r=await fetch(path,{...options,headers:{'Content-Type':'application/json',...(options.headers||{})}});
  let body;
  try{body=await r.json()}catch{body={detail:'Request returned a non-JSON response.'}}
  if(!r.ok){const error=new Error(typeof body.detail==='string'?body.detail:(body.detail?.error||JSON.stringify(body.detail||body))); error.details=body.detail;throw error;}
  return body;
}
function toast(msg){$('toast').textContent=msg;$('toast').classList.remove('hidden');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').classList.add('hidden'),4100);}
function showView(next){view=next;for(const item of ['overview','disputes','activity','lab']){$(item+'View').classList.toggle('hidden',item!==next);}document.querySelectorAll('[data-view]').forEach(el=>el.classList.toggle('active',el.classList.contains('nav-btn')&&el.dataset.view===next));const labels={overview:['Dispute overview','Investigate faster. Respond with evidence. Keep humans in control.','Overview'],disputes:['All disputes','Explore sample cases and run evidence-backed investigations.','Disputes'],activity:['Agent activity','Local trace history and investigation outcomes.','Activity'],lab:['Reliability lab','Reproduce, inspect and repair a controlled workflow defect.','Reliability lab']};$('pageTitle').textContent=labels[next][0];$('pageSubtitle').textContent=labels[next][1];$('breadcrumb').textContent=labels[next][2];if(next==='activity')loadActivity();}
function statusBadge(x){const s=x.latest_status||'unreviewed';const style=s==='investigated'?'success':s==='failed'?'danger':'warning';return `<span class="status-pill ${style}">${escapeHtml(friendly(s))}</span>`}
function caseRow(x, detailed){return `<tr><td><span class="case-id">${escapeHtml(x.dispute_id)}</span></td><td>${escapeHtml(friendly(x.reason))}</td><td class="cell-strong">${cash(x.amount_usd)}</td>${detailed?`<td>${escapeHtml(friendly(x.scenario))}</td>`:''}<td>${statusBadge(x)}</td><td>${escapeHtml(dateFmt(x.due_date))}</td><td><button class="row-btn" data-case="${escapeHtml(x.dispute_id)}">View case ↗</button></td></tr>`}
function renderRows(){const q=$('search').value.trim().toLowerCase(),filter=$('filter').value;const filtered=allCases.filter(c=>(!q||[c.dispute_id,c.reason,c.scenario,c.product].some(v=>String(v||'').toLowerCase().includes(q)))&&(filter==='all'||c.scenario===filter||c.latest_status===filter));$('overviewRows').innerHTML=allCases.slice(0,6).map(c=>caseRow(c,false)).join('')||'<tr><td colspan="6">No cases.</td></tr>';$('disputesRows').innerHTML=filtered.map(c=>caseRow(c,true)).join('')||'<tr><td colspan="7">No matching disputes.</td></tr>';$('resultCount').textContent=`${filtered.length} cases`;}
async function refresh(){try{const [health, dashboard, cases]=await Promise.all([api('/api/health'),api('/api/dashboard'),api('/api/cases')]);status=health;allCases=cases.cases;$('totalDisputes').textContent=dashboard.total_disputes;$('navCount').textContent=dashboard.total_disputes;$('totalAmount').textContent=cash(dashboard.total_at_risk_usd);$('investigated').textContent=dashboard.investigated;$('needsAttention').textContent=dashboard.needs_attention;
  for(const [key,yes] of [['nic',health.nicrron_configured],['prism',health.prism_configured]]){$(key+'Dot').classList.toggle('on',yes);$(key+'Connection').textContent=yes?'Configured':'Needs API key';}
  renderRows();if(view==='activity')await loadActivity();}catch(err){toast('Backend connection failed: '+err.message);}}
async function loadActivity(){try{const data=await api('/api/runs?limit=100');$('runsRows').innerHTML=data.runs.map(r=>`<tr><td><button class="row-btn" data-run="${escapeHtml(r.run_id)}">${escapeHtml(r.run_id.slice(0,23))} ↗</button></td><td>${escapeHtml(r.case_id)}</td><td>${escapeHtml(friendly(r.mode))}</td><td>${escapeHtml(r.version)}</td><td><span class="status-pill ${r.status==='success'?'success':'danger'}">${escapeHtml(friendly(r.status))}</span></td><td>${escapeHtml(friendly(r.prism_status||'not applicable'))}</td><td>${new Date(r.started_at).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'})}</td></tr>`).join('')||'<tr><td colspan="7">No runs yet. Investigate a case to see the history.</td></tr>';}catch(err){toast(err.message)}}

async function openCase(id){try{const result=await api(`/api/cases/${encodeURIComponent(id)}`);selected=result;lastResult=null;$('drawerTitle').textContent=id;$('overlay').classList.remove('hidden');$('overlay').setAttribute('aria-hidden','false');$('caseInfo').innerHTML=`<div class="case-detail-top"><div class="meta-label">DISPUTED AMOUNT</div><div class="case-top-amount">${cash(result.case.amount_usd)}</div><div class="split-meta"><div><span class="meta-label">DISPUTE REASON</span><span class="meta-value">${escapeHtml(friendly(result.case.reason))}</span></div><div><span class="meta-label">RESPONSE DEADLINE</span><span class="meta-value">${escapeHtml(dateFmt(result.case.due_date))}</span></div><div><span class="meta-label">PRODUCT</span><span class="meta-value">${escapeHtml(result.case.product)}</span></div><div><span class="meta-label">CASE STATUS</span><span class="meta-value">${escapeHtml(friendly(result.case.latest_status))}</span></div></div></div>`;renderEvidence();renderReport();renderExecution();switchTab('evidence');$('executionMode').value='demo';$('executionVersion').value='v2';$('footerHint').textContent=status?.nicrron_configured?'Nicrron is configured; choose Live for an AI-generated report.':'Demo uses local report templates. Live needs a Nicrron API key.';}catch(err){toast(err.message);}}
function evidenceCard(icon,title,record){const entries=Object.entries(record||{}).map(([k,v])=>`<div class="detail-item"><span>${escapeHtml(friendly(k))}</span>${escapeHtml(Array.isArray(v)?JSON.stringify(v):v===null?'Not available':String(v))}</div>`).join('');return `<div class="evidence-card"><div class="evidence-head"><span class="evidence-icon">${icon}</span>${escapeHtml(title)}</div><div class="detail-grid">${entries}</div></div>`;}
function renderEvidence(){if(!selected)return;const ev=selected.evidence;$('evidenceTab').innerHTML=[evidenceCard('▣','Order record',ev.order),evidenceCard('＄','Payment record',ev.payment),evidenceCard('⇥','Shipping & delivery',ev.shipping),...ev.support.map((m,i)=>evidenceCard('☏',`Support message ${i+1}`,m))].join('');}
function resultBanner(){if(!lastResult)return '';const rec=lastResult.recommendation;return `<div class="result-banner ${rec==='CONTEST_FOR_REVIEW'?'ok':'warn'}"><strong>${escapeHtml(friendly(rec))}</strong>${escapeHtml(lastResult.assessment.reason)}</div>`;}
function renderReport(){if(!lastResult){$('reportTab').innerHTML='<div class="report-empty"><b>Ready for investigation</b>Run the agent to generate an evidence-backed report with cited record IDs.</div>';return;}
$('reportTab').innerHTML=`${resultBanner()}<div class="note">${lastResult.mode==='live'?'Live Nicrron model output. Review all claims against the source records.':'Deterministic report template. This mode does not call Nicrron or satisfy the model sponsor requirement.'}</div><div class="report-body">${escapeHtml(lastResult.draft)}</div><button class="secondary-button" id="downloadReport">↓ Download .md</button><button class="secondary-button" id="copyReport">Copy report</button><div class="review-block"><strong>Human sign-off</strong><p>Approval means ready for manual submission review. ClaimBack never files disputes with any payment processor.</p><button class="secondary-button" data-review="approved_for_manual_submission">✓ Approve draft</button><button class="secondary-button" data-review="needs_changes">↶ Request changes</button></div>`;
$('downloadReport').addEventListener('click',()=>{window.location.href=`/api/report/${encodeURIComponent(lastResult.case_id)}.md`});$('copyReport').addEventListener('click',async()=>{try{await navigator.clipboard.writeText(lastResult.draft);toast('Report copied');}catch{toast('Copy not supported here; use Download.')}});}
function renderExecution(error){if(!lastResult&&!error){$('executionTab').innerHTML='<div class="report-empty"><b>Execution timeline</b>Each investigation step will appear here after a run. PRISM tracking is only verified in the external PRISM console.</div>';return;}if(error){const details=error.details||{};const steps=details.steps||[];$('executionTab').innerHTML=`<div class="result-banner err"><strong>Run failed</strong>${escapeHtml(error.message)}</div>${renderTimeline(steps)}<div class="note">Use case CB-0005 with v1 to reproduce the deliberate tracking-field regression. Repair is demonstrated with v2 on the same input.</div>`;return;}
$('executionTab').innerHTML=`<div class="result-banner ${lastResult.prism_instrumented?'ok':'warn'}"><strong>${lastResult.prism_instrumented?'PRISM export queued':'Local execution log'}</strong>${lastResult.prism_instrumented?'Authentic steps are sent using the PRISM HTTP trace and span APIs. Verify actual ingest under Agent Runs / Sessions.':'No PRISM proof is implied by this local timeline.'}</div><p class="meta-label">RUN ID: ${escapeHtml(lastResult.run_id)}</p>${lastResult.steps.length?renderTimeline(lastResult.steps):'<div class="note">Live LangGraph steps are recorded by the connected PRISM handler. Open PRISM → Sessions → Steps to inspect actual spans.</div>'}`;}
function renderTimeline(steps){return (steps||[]).map((s,i)=>`<div class="timeline-item ${s.status==='error'?'bad':''}"><div><strong>${i+1}. ${escapeHtml(friendly(s.name))}</strong><small>${escapeHtml(s.status)} · ${s.duration_ms??'?'} ms${s.error?' · '+escapeHtml(s.error):''}</small></div></div>`).join('');}
function switchTab(tab){activeTab=tab;for(const name of ['evidence','report','execution'])$(name+'Tab').classList.toggle('hidden',tab!==name);document.querySelectorAll('[data-tab]').forEach(b=>b.classList.toggle('active',b.dataset.tab===tab));}
function closeCase(){$('overlay').classList.add('hidden');$('overlay').setAttribute('aria-hidden','true');selected=null;}
async function investigate(){if(!selected)return;const id=selected.case.dispute_id,mode=$('executionMode').value,btn=$('investigateButton');let version=$('executionVersion').value;btn.disabled=true;btn.innerHTML='<span class="loading-dot">✦</span> Investigating...';try{lastResult=await api(`/api/investigate/${encodeURIComponent(id)}?mode=${mode}&version=${version}`,{method:'POST'});renderReport();renderExecution();switchTab('report');toast(`${id}: investigation completed (${mode} mode)`);await refresh();}catch(err){lastResult=null;renderExecution(err);switchTab('execution');toast('Investigation failed: '+err.message);await refresh();}finally{btn.disabled=false;btn.textContent='✦  Run investigation';}}
async function review(decision){if(!lastResult)return;const reviewer='Demo Merchant Reviewer';try{await api(`/api/reviews/${encodeURIComponent(lastResult.case_id)}`,{method:'POST',body:JSON.stringify({reviewer,decision})});toast('Review saved locally. Nothing has been submitted.');await refresh();}catch(err){toast(err.message);}}

document.addEventListener('click',e=>{const v=e.target.closest('[data-view]');if(v){showView(v.dataset.view);return;}const run=e.target.closest('[data-run]');if(run){inspectRun(run.dataset.run);return;}const row=e.target.closest('[data-case]');if(row){openCase(row.dataset.case);return;}const tab=e.target.closest('[data-tab]');if(tab){switchTab(tab.dataset.tab);return;}const action=e.target.closest('[data-review]');if(action){review(action.dataset.review);}});
$('closeDrawer').onclick=closeCase;$('overlay').addEventListener('click',e=>{if(e.target===$('overlay'))closeCase()});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&selected)closeCase()});$('search').addEventListener('input',renderRows);$('filter').addEventListener('change',renderRows);$('refreshButton').onclick=refresh;$('activityRefresh').onclick=loadActivity;$('heroInvestigate').onclick=()=>openCase('CB-0001');$('investigateButton').onclick=investigate;$('importButton').onclick=()=>$('importFile').click();$('importFile').addEventListener('change',importSample);$('labV1').onclick=()=>runLab('v1');$('labV2').onclick=()=>runLab('v2');refresh();


// Import only explicitly fictional structured JSON; file content stays in the local sandbox.
async function importSample(event){
  const file=event.target.files?.[0];if(!file)return;
  if(file.size>100000){toast('Please choose a fictional JSON file smaller than 100 KB');return;}
  try{
    const doc=JSON.parse(await file.text());
    if(doc.fictional!==true)throw new Error('The sample must contain "fictional": true. Do not upload private or real customer financial records.');
    const result=await api('/api/cases/import',{method:'POST',body:JSON.stringify(doc)});
    await refresh();$('search').value=result.case_id;renderRows();toast(`Imported ${result.case_id} into local sandbox`);openCase(result.case_id);
  }catch(err){toast('Import rejected: '+err.message)}finally{event.target.value='';}
}

async function inspectRun(runId){
  try{
    const result=await api(`/api/runs/${encodeURIComponent(runId)}`);
    const el=$('activityInspector');el.classList.remove('hidden');
    el.innerHTML=`<h3>Run ${escapeHtml(result.run_id)}</h3><p><strong>PRISM:</strong> ${escapeHtml(result.prism_status||'not applicable')} — ${escapeHtml(result.prism_detail||'No PRISM receipt; Demo mode does not upload.')}</p><p><strong>Mode:</strong> ${escapeHtml(result.mode)} · <strong>Version:</strong> ${escapeHtml(result.version)} · <strong>Status:</strong> ${escapeHtml(result.status)}</p>${result.error?`<div class="note">${escapeHtml(result.error)}</div>`:''}${renderTimeline(result.steps||[])}`;
    el.scrollIntoView({behavior:'smooth',block:'nearest'});
  }catch(err){toast(err.message)}
}

let labBusy=false;
async function runLab(version){
  if(labBusy)return;
  const mode=$('labMode').value;
  if(mode==='live'&&!status?.nicrron_configured){toast('Configure NICRRON_API_KEY in .env before Live mode');return;}
  labBusy=true;$('labV1').disabled=true;$('labV2').disabled=true;
  const ids=['CB-0005','CB-0010','CB-0015'];const output=[];
  $('labResults').innerHTML='';
  for(let i=0;i<ids.length;i++){
    $('labProgress').textContent=`Running ${i+1}/3 · ${ids[i]} · ${version}`;
    try{
      const r=await api(`/api/investigate/${ids[i]}?mode=${mode}&version=${version}`,{method:'POST'});
      output.push({id:ids[i],status:'success',detail:r.recommendation,runId:r.run_id});
    }catch(err){output.push({id:ids[i],status:'error',detail:err.message,runId:err.details?.run_id||'—'});}
    $('labResults').innerHTML=output.map(x=>`<div class="lab-result"><span class="status-pill ${x.status==='success'?'success':'danger'}">${escapeHtml(x.status)}</span><strong>${escapeHtml(x.id)}</strong><span>${escapeHtml(x.detail)}</span><small>${escapeHtml(x.runId)}</small></div>`).join('');
  }
  $('labProgress').textContent=`${version} complete · ${output.filter(x=>x.status==='success').length} successes / ${output.length} runs`;
  labBusy=false;$('labV1').disabled=false;$('labV2').disabled=false;
  await refresh();
  toast(`${version} batch finished. ${mode==='live'?'Verify PRISM traces and alerts in the external console.':'Demo runs are local only.'}`);
}
