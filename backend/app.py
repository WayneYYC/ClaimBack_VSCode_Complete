"""ClaimBack local full-stack app. This is a fictional sandbox, not payment software."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4
import json
import os
import sqlite3
import time

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .engine import CASES, WorkflowFailure, run_demo, run_live
from . import prism

ROOT=Path(__file__).resolve().parent.parent
load_dotenv(ROOT/'.env')
DB=Path(os.getenv('CLAIMBACK_DB',str(ROOT/'claimback.sqlite3')))
app=FastAPI(title='ClaimBack API',version='2.0',description='Fictional chargeback evidence investigation. No real payments or dispute submission.')
executor=ThreadPoolExecutor(max_workers=4,thread_name_prefix='prism-trace')


def connect():
    conn=sqlite3.connect(DB,timeout=30)
    conn.row_factory=sqlite3.Row
    return conn


def init_db():
    DB.parent.mkdir(parents=True,exist_ok=True)
    with closing(connect()) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS runs (
          run_id TEXT PRIMARY KEY, case_id TEXT NOT NULL, version TEXT NOT NULL, mode TEXT NOT NULL,
          status TEXT NOT NULL, started_at TEXT NOT NULL, output_json TEXT, error TEXT,
          prism_status TEXT DEFAULT 'not_applicable', prism_detail TEXT DEFAULT ''
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS reviews (
          case_id TEXT PRIMARY KEY, reviewer TEXT NOT NULL, decision TEXT NOT NULL, reviewed_at TEXT NOT NULL
        )''')
        conn.execute('''CREATE TABLE IF NOT EXISTS custom_cases (
          case_id TEXT PRIMARY KEY, payload_json TEXT NOT NULL
        )''')
        cols={x[1] for x in conn.execute('PRAGMA table_info(runs)')}
        if 'prism_status' not in cols:conn.execute("ALTER TABLE runs ADD COLUMN prism_status TEXT DEFAULT 'not_applicable'")
        if 'prism_detail' not in cols:conn.execute("ALTER TABLE runs ADD COLUMN prism_detail TEXT DEFAULT ''")
        for row in conn.execute('SELECT case_id,payload_json FROM custom_cases'):
            CASES[row['case_id']]=json.loads(row['payload_json'])
        conn.commit()

init_db()


def configured(key:str)->bool:
    value=os.getenv(key,'').strip()
    return bool(value and not value.startswith(('replace_','YOUR_','your_')))


def latest_runs(limit=500):
    with closing(connect()) as conn:
        return conn.execute('SELECT * FROM runs ORDER BY started_at DESC LIMIT ?', (limit,)).fetchall()


def snapshot():
    statuses={}
    for record in latest_runs():
        if record['case_id'] not in statuses:
            statuses[record['case_id']]='investigated' if record['status']=='success' else 'failed'
    with closing(connect()) as conn:
        reviews={row['case_id']:row['decision'] for row in conn.execute('SELECT * FROM reviews')}
    return statuses,reviews


def case_summary(case:dict,statuses:dict,reviews:dict):
    cid=case['dispute_id']
    return {'dispute_id':cid,'reason':case['reason'],'scenario':case['scenario'],
            'amount_usd':case['amount_usd'],'opened_at':case['opened_at'],'due_date':case['due_date'],
            'product':case['order']['product'],'latest_status':statuses.get(cid,'unreviewed'),
            'review':reviews.get(cid)}


@app.get('/api/health')
def health():
    return {'ok':True,'mode':'fictional_sandbox','nicrron_configured':configured('NICRRON_API_KEY'),
            'prism_configured':prism.ready(),'cases':len(CASES),'live_requires_keys':True}


@app.get('/api/dashboard')
def dashboard():
    statuses,reviews=snapshot()
    rs=latest_runs()
    return {'total_disputes':len(CASES),
            'total_at_risk_usd':round(sum(float(c['amount_usd']) for c in CASES.values()),2),
            'investigated':sum(s=='investigated' for s in statuses.values()),
            'needs_attention':sum(c['scenario']!='delivered' for c in CASES.values()),
            'failed_runs':sum(r['status']=='error' for r in rs),
            'completed_reviews':len(reviews),
            'by_scenario':{key:sum(c['scenario']==key for c in CASES.values()) for key in sorted({c['scenario'] for c in CASES.values()})}}


@app.get('/api/cases')
def list_cases(q:str='',filter:str='all',limit:int=Query(100,ge=1,le=300)):
    statuses,reviews=snapshot()
    records=[case_summary(c,statuses,reviews) for c in CASES.values()]
    if q:
        query=q.casefold()
        records=[c for c in records if any(query in str(c[field]).casefold() for field in ('dispute_id','reason','scenario','product'))]
    if filter!='all':
        records=[c for c in records if filter in (c['latest_status'],c['scenario'],c['review'])]
    return {'cases':records[:limit],'total':len(records)}


@app.get('/api/cases/{case_id}')
def case_details(case_id:str):
    if case_id not in CASES:raise HTTPException(404,'Unknown fictional dispute')
    statuses,reviews=snapshot()
    record=CASES[case_id]
    return {'case':case_summary(record,statuses,reviews),
            'evidence':{k:record[k] for k in ('order','payment','shipping','support')}}


class NewCase(BaseModel):
    fictional: Literal[True]
    reason: str=Field(min_length=3,max_length=120)
    amount_usd:float=Field(gt=0,le=1000000)
    opened_at:str
    due_date:str
    order:dict
    payment:dict
    shipping:dict
    support:list[dict]


@app.post('/api/cases/import',status_code=201)
def import_case(record:NewCase):
    """Import sample JSON records (NOT PDFs); requires explicit fictional:true."""
    payload=record.model_dump()
    try:
        datetime.fromisoformat(payload['opened_at'])
        datetime.fromisoformat(payload['due_date'])
        for section,keys in {
            'order':('record_id','product','total_usd'),
            'payment':('record_id','status','amount_usd','refunded'),
            'shipping':('record_id','status','address_match')}.items():
            if any(k not in payload[section] for k in keys):raise ValueError(f'Missing {section} fields')
        if any('record_id' not in s or 'message' not in s for s in payload['support']):
            raise ValueError('Support messages require record_id and message')
        if len(json.dumps(payload))>100000:raise ValueError('File too large; use a small fictional case')
    except (TypeError,ValueError) as exc:
        raise HTTPException(422,f'Invalid sample case: {exc}')
    case_id='CB-UP-'+uuid4().hex[:8].upper()
    payload.update(dispute_id=case_id,scenario='imported')
    with closing(connect()) as conn:
        conn.execute('INSERT INTO custom_cases(case_id,payload_json) VALUES (?,?)', (case_id,json.dumps(payload)))
        conn.commit()
    CASES[case_id]=payload
    return {'case_id':case_id,'created':True,'fictional':True}


def update_prism_status(run_id:str,status:str,detail:str):
    with closing(connect()) as conn:
        conn.execute('UPDATE runs SET prism_status=?,prism_detail=? WHERE run_id=?',(status,detail,run_id))
        conn.commit()


def queue_prism(run_id:str,case_id:str,version:str,status:str,message:str,steps:list[dict],duration_ms:int):
    if not prism.ready():
        update_prism_status(run_id,'not_configured','PRISM credentials are absent; no trace sent')
        return
    update_prism_status(run_id,'queued','Uploading authentic workflow spans to PRISM')
    executor.submit(prism.send_run,run_id,case_id,version,status,message,steps,duration_ms,
                    lambda code,detail:update_prism_status(run_id,code,detail))


@app.post('/api/investigate/{case_id}')
def investigate(case_id:str,version:Literal['v1','v2']='v2',mode:Literal['demo','live']='demo'):
    if case_id not in CASES:raise HTTPException(404,'Unknown fictional dispute')
    if mode=='live' and not configured('NICRRON_API_KEY'):
        raise HTTPException(503,'Nicrron API key missing. Fill .env or choose Demo (template).')
    run_id=f'{case_id}-{version}-{uuid4().hex[:10]}'
    started_at=datetime.now(timezone.utc).isoformat()
    with closing(connect()) as conn:
        conn.execute('INSERT INTO runs(run_id,case_id,version,mode,status,started_at) VALUES (?,?,?,?,?,?)',
                     (run_id,case_id,version,mode,'running',started_at))
        conn.commit()
    before=time.perf_counter()
    try:
        execution=run_live(case_id,version,run_id) if mode=='live' else run_demo(case_id,version)
        state=execution['state']
        outcome={'run_id':run_id,'case_id':case_id,'mode':mode,'version':version,
                 'status':'draft_for_human_review','recommendation':state['assessment']['recommendation'],
                 'assessment':state['assessment'],'reconciliation':state['reconciliation'],
                 'evidence':{k:state[k] for k in ('order','payment','shipping','support')},
                 'draft':state['draft'],'draft_origin':state['draft_origin'],
                 'steps':execution['steps'],'prism_instrumented':mode=='live' and prism.ready(),
                 'prism_status':'queued' if mode=='live' and prism.ready() else 'not_applicable',
                 'automatically_submitted':False}
        with closing(connect()) as conn:
            conn.execute('UPDATE runs SET status=?,output_json=? WHERE run_id=?',
                         ('success',json.dumps(outcome),run_id))
            conn.commit()
        if mode=='live':queue_prism(run_id,case_id,version,'success',state['assessment']['recommendation'],
                                   execution['steps'],round((time.perf_counter()-before)*1000))
        return outcome
    except Exception as exc:
        # Expected v1 regression and any live API errors are preserved in local history.
        # No secrets are deliberately included in public error content.
        text=f'{type(exc).__name__}: {exc}'
        steps=getattr(exc,'steps',[])
        if isinstance(exc,WorkflowFailure):text=str(exc)
        failure={'run_id':run_id,'case_id':case_id,'version':version,'mode':mode,
                 'status':'error','error':text,'steps':steps,
                 'prism_status':'queued' if mode=='live' and prism.ready() else 'not_applicable'}
        with closing(connect()) as conn:
            conn.execute('UPDATE runs SET status=?,error=?,output_json=? WHERE run_id=?',
                         ('error',text,json.dumps(failure),run_id))
            conn.commit()
        if mode=='live':queue_prism(run_id,case_id,version,'error',text,steps,
                                   round((time.perf_counter()-before)*1000))
        raise HTTPException(422 if mode=='demo' else 502,detail=failure)


@app.get('/api/runs')
def runs(limit:int=Query(100,ge=1,le=500)):
    return {'runs':[{'run_id':r['run_id'],'case_id':r['case_id'],'version':r['version'],
        'mode':r['mode'],'status':r['status'],'started_at':r['started_at'],
        'prism_status':r['prism_status'],'error':r['error']}
        for r in latest_runs(limit)]}


@app.get('/api/runs/{run_id}')
def run_details(run_id:str):
    with closing(connect()) as conn:
        row=conn.execute('SELECT * FROM runs WHERE run_id=?',(run_id,)).fetchone()
    if row is None:raise HTTPException(404,'Unknown run')
    payload=json.loads(row['output_json']) if row['output_json'] else {'run_id':run_id,'status':'running'}
    payload['prism_status']=row['prism_status']
    payload['prism_detail']=row['prism_detail']
    return payload


class Review(BaseModel):
    reviewer:str=Field(min_length=2,max_length=80)
    decision:Literal['approved_for_manual_submission','needs_changes','rejected']


@app.post('/api/reviews/{case_id}')
def save_review(case_id:str,payload:Review):
    if case_id not in CASES:raise HTTPException(404,'Unknown case')
    with closing(connect()) as conn:
        last=conn.execute("SELECT run_id FROM runs WHERE case_id=? AND status='success' ORDER BY started_at DESC LIMIT 1",(case_id,)).fetchone()
        if last is None:raise HTTPException(409,'Investigate before reviewing')
        now=datetime.now(timezone.utc).isoformat()
        conn.execute('''INSERT INTO reviews(case_id,reviewer,decision,reviewed_at) VALUES (?,?,?,?)
                     ON CONFLICT(case_id) DO UPDATE SET reviewer=excluded.reviewer,decision=excluded.decision,reviewed_at=excluded.reviewed_at''',
                     (case_id,payload.reviewer,payload.decision,now))
        conn.commit()
    return {'case_id':case_id,'reviewer':payload.reviewer,'decision':payload.decision,
            'reviewed_at':now,'submitted_to_processor':False}


@app.get('/api/report/{case_id}.md')
def export_report(case_id:str):
    if case_id not in CASES:raise HTTPException(404,'Unknown case')
    with closing(connect()) as conn:
        record=conn.execute("SELECT output_json FROM runs WHERE case_id=? AND status='success' ORDER BY started_at DESC LIMIT 1",(case_id,)).fetchone()
    if record is None:raise HTTPException(404,'Investigate this case before downloading')
    draft=json.loads(record['output_json'])['draft']
    return PlainTextResponse(draft,media_type='text/markdown',headers={
        'Content-Disposition':f'attachment; filename="{case_id}-draft.md"'})


app.mount('/assets',StaticFiles(directory=ROOT/'frontend'),name='assets')
@app.get('/')
def home():return FileResponse(ROOT/'frontend'/'index.html')
