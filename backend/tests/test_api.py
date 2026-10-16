from sqlalchemy import select
from app.db import Job, Review, Session, Solicitation
from app.worker import run_once


def processed(client, headers, text):
    response = client.post('/api/solicitations/text', headers=headers, json={'title': 'Website support', 'text': text})
    assert response.status_code == 202
    item = response.json()
    assert run_once()
    result = client.get('/api/solicitations/' + item['id'], headers=headers)
    assert result.status_code == 200
    assert result.json()['status'] == 'ready'
    return result.json()


def test_auth_and_workspace_isolation(client, headers, solicitation_text):
    assert client.get('/api/health').status_code == 200
    assert client.get('/api/solicitations').status_code == 401
    assert client.get('/api/solicitations', headers={'Authorization': 'Bearer wrong'}).status_code == 401
    doc = processed(client, headers, solicitation_text)
    from app.main import app, owner
    app.dependency_overrides[owner] = lambda: 'another-workspace'
    try:
        assert client.get('/api/solicitations').json() == []
        assert client.get('/api/solicitations/' + doc['id']).status_code == 404
        assert client.get('/api/solicitations/' + doc['id'] + '/export').status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_upload_worker_citations_and_stream(client, headers, solicitation_text):
    r = client.post('/api/solicitations/upload', headers=headers,
                    files={'file': ('solicitation.txt', solicitation_text.encode(), 'text/plain')})
    assert r.status_code == 202
    assert run_once()
    doc = client.get('/api/solicitations/' + r.json()['id'], headers=headers).json()
    assert doc['analysis']['facts']
    for fact in doc['analysis']['facts']:
        c = fact['citation']
        page = next(p for p in doc['pages'] if p['number'] == c['page'])
        assert page['text'][c['start']:c['end']] == c['quote']
        assert c['document_id'] == doc['id']
    stream = client.get(f'/api/solicitations/{doc["id"]}/events', headers=headers)
    assert 'event: fact' in stream.text and 'event: ready' in stream.text
    assert 'text/event-stream' in stream.headers['content-type']
    assert not run_once()


def test_review_gate_version_and_audit_export(client, headers, solicitation_text):
    doc = processed(client, headers, solicitation_text)
    path = f'/api/solicitations/{doc["id"]}'
    body = {'decision': 'hold', 'notes': 'Need to confirm on-site staffing.',
            'brief_version': doc['analysis']['version'], 'reviewed_fact_ids': [], 'acknowledged_gaps': False}
    assert client.post(path + '/review', headers=headers, json=body).status_code == 422
    body.update(reviewed_fact_ids=[f['id'] for f in doc['analysis']['facts']], acknowledged_gaps=True)
    assert client.post(path + '/review', headers=headers, json={**body, 'brief_version': 'old'}).status_code == 409
    assert client.post(path + '/review', headers=headers, json={**body, 'notes': ' ' * 15}).status_code == 422
    draft = client.get(path + '/export', headers=headers)
    assert 'DRAFT' in draft.text
    assert client.post(path + '/review', headers=headers, json=body).status_code == 200
    final = client.get(path, headers=headers).json()
    assert final['status'] == 'reviewed' and final['reviews'][0]['decision'] == 'hold'
    exported = client.get(path + '/export', headers=headers).text
    assert 'Status: HOLD' in exported and 'Need to confirm on-site staffing.' in exported
    assert 'Eastern Time' in exported and 'characters' in exported
    with Session() as db:
        assert len(db.scalars(select(Review)).all()) == 1


def test_cache_rebinds_all_citations_and_versions(client, headers, solicitation_text):
    first = processed(client, headers, solicitation_text)
    second = processed(client, headers, solicitation_text)
    assert second['analysis']['metrics']['cache_hit'] is True
    assert first['analysis']['version'] != second['analysis']['version']
    ids = {f['id'] for f in first['analysis']['facts']}
    for f in second['analysis']['facts']:
        assert f['citation']['document_id'] == second['id']
        assert f['id'] not in ids


def test_validation_search_and_profile(client, headers, solicitation_text):
    assert client.post('/api/solicitations/text', headers=headers, json={'title': 'Short', 'text': 'too short'}).status_code == 422
    assert client.post('/api/solicitations/text', headers=headers, json={'title': 'Blank', 'text': ' ' * 100}).status_code == 422
    assert client.post('/api/solicitations/upload', headers=headers, files={'file': ('file.exe', b'not a solicitation')}).status_code == 422
    doc = processed(client, headers, solicitation_text)
    assert len(client.get('/api/solicitations?q=Drupal', headers=headers).json()) == 1
    assert client.get('/api/solicitations?q=unmatched', headers=headers).json() == []
    profile = {'name': 'Example firm', 'capabilities': 'Drupal', 'certifications': 'SAM active', 'business_status': 'Small business'}
    assert client.put('/api/profile', headers=headers, json=profile).status_code == 200
    assert client.get('/api/profile', headers=headers).json() == profile


def test_rejects_unsafe_import_urls(client, headers):
    for url in ['http://127.0.0.1/private', 'https://localhost/private', 'file:///etc/passwd', 'https://example.com/file.pdf', 'https://agency.gov@127.0.0.1/file.pdf']:
        response = client.post('/api/solicitations/url', headers=headers, json={'url': url})
        assert response.status_code == 422


def test_concurrent_first_import_creates_workspace_idempotently(client, headers, solicitation_text):
    from concurrent.futures import ThreadPoolExecutor
    def submit(i):
        return client.post('/api/solicitations/text', headers=headers,
                           json={'title': f'Concurrent import {i}', 'text': solicitation_text + f'\nReference {i}.'})
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(submit, range(4)))
    assert [r.status_code for r in responses] == [202] * 4
    for _ in responses:
        assert run_once()
    assert len(client.get('/api/solicitations', headers=headers).json()) == 4


def test_concurrent_retries_enqueue_exactly_one_new_job(client, headers, solicitation_text, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from app import main
    item = client.post('/api/solicitations/text', headers=headers,
                       json={'title': 'Retry once', 'text': solicitation_text}).json()
    with Session.begin() as db:
        db.get(Job, item['job_id']).status = 'failed'
        db.get(Solicitation, item['id']).status = 'failed'
    original_owned = main.owned
    same_snapshot = Barrier(4)
    def owned_before_retry(db, solicitation_id, user):
        sol = original_owned(db, solicitation_id, user)
        same_snapshot.wait(timeout=5)
        return sol
    monkeypatch.setattr(main, 'owned', owned_before_retry)
    def retry_once(_):
        return client.post(f'/api/solicitations/{item["id"]}/retry', headers=headers)
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(retry_once, range(4)))
    assert sorted(r.status_code for r in responses) == [202, 409, 409, 409]
    with Session() as db:
        jobs = db.scalars(select(Job).where(Job.solicitation_id == item['id'])).all()
        assert len(jobs) == 2
        assert len([j for j in jobs if j.status == 'queued']) == 1
