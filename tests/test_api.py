from fastapi.testclient import TestClient
from backend.app import app

client=TestClient(app)


def test_health_and_cases():
    assert client.get('/api/health').status_code==200
    c=client.get('/api/cases').json()
    assert c['total']>=60
    assert c['cases'][0]['dispute_id']=='CB-0001'
    assert client.get('/api/cases/not-a-case').status_code==404


def test_good_delivery_may_be_contested_for_review():
    r=client.post('/api/investigate/CB-0001?mode=demo&version=v2')
    assert r.status_code==200
    d=r.json()
    assert d['recommendation']=='CONTEST_FOR_REVIEW'
    assert len(d['steps'])==8
    assert d['draft_origin']=='demo_template'
    assert d['automatically_submitted'] is False
    assert 'SHIP-001' in d['draft']


def test_missing_tracking_safe_v2():
    r=client.post('/api/investigate/CB-0005?mode=demo&version=v2')
    assert r.status_code==200
    d=r.json()
    assert d['recommendation']=='NEEDS_REVIEW'
    assert d['evidence']['shipping']['tracking_number'] is None
    assert 'NOT AVAILABLE' in d['draft']


def test_v1_intentional_error_then_v2_fix():
    r=client.post('/api/investigate/CB-0005?mode=demo&version=v1')
    assert r.status_code==422
    assert 'tracking_number' in r.json()['detail']['error']
    assert client.post('/api/investigate/CB-0005?mode=demo&version=v2').status_code==200


def test_export_and_review_are_local_only():
    client.post('/api/investigate/CB-0001?mode=demo&version=v2')
    report=client.get('/api/report/CB-0001.md')
    assert report.status_code==200
    assert 'Chargeback Investigation' in report.text
    review=client.post('/api/reviews/CB-0001',json={'reviewer':'Demo Reviewer','decision':'approved_for_manual_submission'})
    assert review.status_code==200
    assert review.json()['submitted_to_processor'] is False


def test_live_without_key_returns_error(monkeypatch):
    monkeypatch.delenv('NICRRON_API_KEY',raising=False)
    resp=client.post('/api/investigate/CB-0001?mode=live&version=v2')
    assert resp.status_code==503
