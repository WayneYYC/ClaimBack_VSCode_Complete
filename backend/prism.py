"""Best-effort PRISM trace + authentic step span delivery via documented HTTP endpoints.

A trace is sent only for a REAL app run in live mode, never for Demo mode.
Network errors never change the investigation outcome. See https://blockconvey.com/docs.
"""
from __future__ import annotations
import logging
import os
import uuid
from typing import Callable
import httpx

logger=logging.getLogger(__name__)


def ready()->bool:
    required=('PRISMTRACE_API_KEY','PRISMTRACE_PROJECT_ID')
    return all(os.getenv(k,'').strip() and not os.getenv(k,'').startswith(('replace_','YOUR_')) for k in required)


def send_run(run_id:str,case_id:str,version:str,status:str,
             message:str,steps:list[dict],latency_ms:int,
             receipt:Callable[[str,str],None])->None:
    """Upload one observed run and its actual executed steps; receipt(status, detail)."""
    if not ready():
        receipt('not_configured','Set PRISMTRACE_API_KEY and PRISMTRACE_PROJECT_ID')
        return
    host=os.getenv('PRISMTRACE_HOST','https://prism.blockconvey.com').rstrip('/')
    key=os.environ['PRISMTRACE_API_KEY']
    project=os.environ['PRISMTRACE_PROJECT_ID']
    # For failed v1 run no Nicrron LLM was called; model field reflects that honestly.
    used_llm=any(x['name']=='write_response' and x['span_type']=='llm' for x in steps)
    model=os.getenv('NICRRON_MODEL','nicrron/auto') if used_llm else 'claimback/deterministic-workflow'
    payload={
        'project_id':project,
        'trace_id':str(uuid.uuid4()),
        'session_id':run_id,
        'agent_id':'claimback-chargeback-investigator',
        'agent_name':'ClaimBack Investigator',
        'model':model,
        'input_messages':[{'role':'user','content':f'Investigate fictional chargeback {case_id}; regression version {version}'}],
        'output_message':message[:2000],
        'latency_ms':max(int(latency_ms),0),
        'metadata':{'case_id':case_id,'workflow_version':version,'run_status':status,
                    'source':'claimback-local-app','synthetic_data':True,'llm_called':used_llm,
                    'run_id':run_id},
    }
    try:
        with httpx.Client(timeout=12) as client:
            response=client.post(host+'/api/traces',json=payload,
                                 headers={'X-PRISMtrace-Key':key,'Content-Type':'application/json'})
            response.raise_for_status()
            remote=response.json()
            trace_id=str(remote.get('id') or payload['trace_id'])
            # Per published contract: observed workflow steps are transmitted as PRISM spans.
            span_data={'trace_id':trace_id,'project_id':project,'session_id':run_id,
                'spans':[
                    {k:v for k,v in step.items() if k in (
                        'name','span_type','start_time','end_time','duration_ms','status',
                        'input_text','output_text','error_message','model')}
                    for step in steps
                ],
                'metadata':{'run_id':run_id,'synthetic_data':True}}
            spans=client.post(host+'/api/spans/ingest',json=span_data,
                              headers={'X-PRISMtrace-Key':key,'Content-Type':'application/json'})
            spans.raise_for_status()
        receipt('sent',f'Trace and {len(steps)} spans accepted by PRISM HTTP endpoints; verify in console')
    except httpx.HTTPStatusError as exc:
        logger.warning('PRISM rejected run %s: HTTP %s',run_id,exc.response.status_code)
        receipt('error',f'PRISM HTTP {exc.response.status_code}; inspect credentials and scopes')
    except (httpx.RequestError,ValueError) as exc:
        logger.warning('PRISM delivery failed for %s: %s',run_id,type(exc).__name__)
        receipt('error',f'PRISM connectivity/response error: {type(exc).__name__}')
