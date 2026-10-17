"""All tests are offline; fake HTTP clients never reach Nicrron or PRISM."""
import json
from pathlib import Path
from fastapi.testclient import TestClient
from backend.app import app
from backend import engine, prism

client=TestClient(app)


def test_seed_cases_and_reliability_lab():
    assert len(engine.CASES)>=60
    markup=client.get('/').text
    for name in ('labView','labV1','labV2','labMode','importButton','disputesView','executionMode'):
        assert f'id="{name}"' in markup
    js=client.get('/assets/app.js')
    assert js.status_code==200 and 'async function runLab' in js.text


def test_custom_fictional_import():
    sample=json.loads((Path(__file__).parent.parent/'sample_data'/'import_example.json').read_text())
    result=client.post('/api/cases/import',json=sample)
    assert result.status_code==201, result.text
    case_id=result.json()['case_id']
    assert case_id.startswith('CB-UP-')
    assert client.get(f'/api/cases/{case_id}').json()['evidence']['order']['product']=='Sample wireless headphones'
    assert client.post(f'/api/investigate/{case_id}?mode=demo&version=v2').json()['recommendation']=='CONTEST_FOR_REVIEW'
    sample['fictional']=False
    assert client.post('/api/cases/import',json=sample).status_code==422


def test_deterministic_policy_avoids_unproven_delivery():
    for case in ['CB-0002','CB-0003','CB-0005']:
        result=client.post(f'/api/investigate/{case}?mode=demo&version=v2').json()
        assert result['recommendation']=='NEEDS_REVIEW'
        assert result['automatically_submitted'] is False
        assert all(s['span_type']=='tool' for s in result['steps'])
    assert len(result['steps'])==8


def test_nicrron_live_call_is_real_compatible_http_request(monkeypatch):
    monkeypatch.setenv('NICRRON_API_KEY','sk-test-fake-not-real')
    monkeypatch.setenv('NICRRON_MODEL','nicrron/auto')
    calls=[]
    class FakeResponse:
        def raise_for_status(self):pass
        def json(self):return {'choices':[{'message':{'content':'## Evidence\nVerified from [SHIP-001].'}}]}
    class FakeClient:
        def __init__(self,timeout):assert timeout>0
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,headers,json):
            calls.append((url,headers,json))
            return FakeResponse()
    monkeypatch.setattr(engine.httpx,'Client',FakeClient)
    result=client.post('/api/investigate/CB-0001?mode=live&version=v2')
    assert result.status_code==200, result.text
    data=result.json()
    assert data['draft_origin']=='nicrron_llm'
    assert data['draft']=='## Evidence\nVerified from [SHIP-001].'
    assert data['steps'][-1]['span_type']=='llm'
    assert calls[0][0]=='https://api.nicrron.ai/v1/chat/completions'
    assert calls[0][2]['model']=='nicrron/auto'
    assert calls[0][1]['Authorization']=='Bearer sk-test-fake-not-real'


def test_prism_http_trace_and_steps_contract(monkeypatch):
    monkeypatch.setenv('PRISMTRACE_API_KEY','pt-sk-fake-test')
    monkeypatch.setenv('PRISMTRACE_PROJECT_ID','00000000-0000-0000-0000-000000000001')
    captures=[]
    class FakeResponse:
        def __init__(self,kind):self.kind=kind
        def raise_for_status(self):pass
        def json(self):return {'id':'abc123'}
    class FakeClient:
        def __init__(self,timeout):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,headers,json):
            captures.append((url,headers,json))
            return FakeResponse(url)
    monkeypatch.setattr(prism.httpx,'Client',FakeClient)
    steps=engine.run_demo('CB-0001','v2')['steps']
    receipts=[]
    prism.send_run('fake-run','CB-0001','v2','success','CONTEST_FOR_REVIEW',steps,12,
                   lambda status,detail:receipts.append((status,detail)))
    assert receipts[0][0]=='sent'
    assert captures[0][0].endswith('/api/traces')
    assert captures[1][0].endswith('/api/spans/ingest')
    assert captures[0][2]['session_id']=='fake-run'
    assert len(captures[1][2]['spans'])==8
    assert captures[0][2]['metadata']['llm_called'] is False
    assert captures[1][2]['spans'][0]['name']=='load_dispute'


def test_error_history_includes_steps():
    result=client.post('/api/investigate/CB-0010?mode=demo&version=v1')
    assert result.status_code==422
    run_id=result.json()['detail']['run_id']
    persisted=client.get(f'/api/runs/{run_id}').json()
    assert persisted['status']=='error'
    assert persisted['steps'][-1]['name']=='lookup_shipping'
    assert persisted['steps'][-1]['status']=='error'
