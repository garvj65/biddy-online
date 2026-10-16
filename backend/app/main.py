import asyncio
import hashlib
import hmac
import json
import os
import re
from typing import Annotated
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, literal_column, select, update
from .config import settings
from .db import Job, Review, Session, Solicitation, User
from .documents import parse_document, section_text
from .schemas import LinkImport, ProfileInput, ReviewInput, TextImport
from .urls import fetch_government_document

app = FastAPI(title='Biddy API', version='0.1.0', description='Source-linked solicitation screening with a human review gate.')
app.add_middleware(CORSMiddleware, allow_origins=settings().cors_origins.split(','),
                   allow_methods=['GET', 'POST', 'PUT'], allow_headers=['Authorization', 'Content-Type'])
bearer = HTTPBearer(auto_error=False)


def owner(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    expected = settings().biddy_access_token
    if not credentials or not hmac.compare_digest(credentials.credentials, expected):
        raise HTTPException(401, 'Connect your workspace with its access token.', headers={'WWW-Authenticate': 'Bearer'})
    return settings().biddy_workspace_id


Owner = Annotated[str, Depends(owner)]


def owned(db, solicitation_id, user):
    sol = db.scalar(select(Solicitation).where(Solicitation.id == solicitation_id, Solicitation.owner_id == user))
    if not sol:
        raise HTTPException(404, 'Solicitation not found.')
    return sol


def ensure_user(db, user):
    # Several first imports may arrive together. Let the database resolve this
    # uniqueness race without rolling back the solicitation transaction.
    if db.bind.dialect.name == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    db.execute(insert(User).values(id=user, name='My workspace', profile={}).on_conflict_do_nothing(index_elements=['id']))


def create_solicitation(user, title, filename, pages, source_url=None):
    text = '\n\f\n'.join(p['text'] for p in pages)
    with Session.begin() as db:
        ensure_user(db, user)
        sol = Solicitation(owner_id=user, title=title, filename=filename, pages=pages, content=text,
                           content_hash=hashlib.sha256(text.encode()).hexdigest(), source_url=source_url)
        db.add(sol)
        db.flush()
        job = Job(solicitation_id=sol.id)
        db.add(job)
        db.flush()
        return {'id': sol.id, 'job_id': job.id, 'status': 'queued'}


@app.get('/api/health')
def health():
    return {'status': 'ok', 'version': '0.1.0'}


@app.get('/api/config')
def config(user: Owner):
    s = settings()
    return {'provider': s.llm_provider, 'model': s.llm_model or 'provider-default',
            'configured': s.llm_provider == 'rules' or bool(s.llm_api_key), 'mode': 'single-workspace'}


@app.post('/api/solicitations/text', status_code=202)
def import_text(body: TextImport, user: Owner):
    return create_solicitation(user, body.title, body.title + '.txt', section_text(body.text))


@app.post('/api/solicitations/upload', status_code=202)
async def upload(user: Owner, file: UploadFile = File(...)):
    data = await file.read(settings().max_upload_bytes + 1)
    try:
        pages = await run_in_threadpool(parse_document, data, file.filename or 'document.txt')
    except Exception as exc:
        message = str(exc) if isinstance(exc, (ValueError, UnicodeDecodeError)) else 'Unable to read this file. Upload a valid unlocked document.'
        raise HTTPException(422, message) from None
    return create_solicitation(user, (file.filename or 'Untitled solicitation')[:250], (file.filename or 'document')[:250], pages)


@app.post('/api/solicitations/url', status_code=202)
async def import_url(body: LinkImport, user: Owner):
    try:
        pages, name = await run_in_threadpool(fetch_government_document, body.url)
    except Exception as exc:
        raise HTTPException(422, str(exc) if isinstance(exc, ValueError) else 'Unable to retrieve that government document. Upload its attachment instead.') from None
    return create_solicitation(user, name[:250], name[:250], pages, body.url)


@app.get('/api/solicitations')
def list_solicitations(user: Owner, q: str = Query('', max_length=200), limit: int = Query(50, ge=1, le=100)):
    with Session() as db:
        query = select(Solicitation).where(Solicitation.owner_id == user)
        if q.strip():
            if db.bind.dialect.name == 'postgresql':
                query = query.where(func.to_tsvector(literal_column("'english'"), Solicitation.content).op('@@')(func.websearch_to_tsquery('english', q)))
            else:
                escaped = q.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
                query = query.where(Solicitation.content.ilike(f'%{escaped}%', escape='\\'))
        sols = db.scalars(query.order_by(Solicitation.created_at.desc()).limit(limit)).all()
        return [{'id': s.id, 'title': s.title, 'status': s.status, 'created_at': s.created_at.isoformat(),
                 'facts_count': len(s.analysis['facts']) if s.analysis else 0} for s in sols]


@app.get('/api/solicitations/{solicitation_id}')
def get_solicitation(solicitation_id: str, user: Owner):
    with Session() as db:
        sol = owned(db, solicitation_id, user)
        job = db.scalar(select(Job).where(Job.solicitation_id == sol.id).order_by(Job.available_at.desc()))
        reviews = db.scalars(select(Review).where(Review.solicitation_id == sol.id).order_by(Review.created_at.desc())).all()
        return {'id': sol.id, 'title': sol.title, 'filename': sol.filename, 'status': sol.status,
                'source_url': sol.source_url, 'pages': sol.pages, 'analysis': sol.analysis,
                'error': job.error if job and job.status == 'failed' else None,
                'reviews': [{'id': r.id, 'decision': r.decision, 'notes': r.notes, 'created_at': r.created_at.isoformat(),
                             'brief_version': r.brief_version, 'reviewed_fact_ids': r.reviewed_fact_ids} for r in reviews]}


@app.post('/api/solicitations/{solicitation_id}/retry', status_code=202)
def retry(solicitation_id: str, user: Owner):
    with Session.begin() as db:
        sol = owned(db, solicitation_id, user)
        claimed = db.execute(update(Solicitation).where(
            Solicitation.id == solicitation_id, Solicitation.owner_id == user,
            Solicitation.status == 'failed').values(status='queued'))
        if claimed.rowcount != 1:
            raise HTTPException(409, 'Only failed analyses can be retried.')
        db.add(Job(solicitation_id=sol.id))
    return {'status': 'queued'}


@app.get('/api/solicitations/{solicitation_id}/events')
def events(solicitation_id: str, user: Owner):
    with Session() as db:
        owned(db, solicitation_id, user)

    async def stream():
        for _ in range(120):
            data = await run_in_threadpool(get_solicitation, solicitation_id, user)
            if data['status'] in {'ready', 'reviewed'}:
                # Only validated facts stream. The model's unverified tokens never reach the brief.
                for fact in data['analysis']['facts']:
                    yield 'event: fact\ndata: ' + json.dumps(fact) + '\n\n'
                yield 'event: ready\ndata: ' + json.dumps({'id': solicitation_id}) + '\n\n'
                return
            yield 'event: status\ndata: ' + json.dumps({'status': data['status'], 'error': data['error']}) + '\n\n'
            if data['status'] == 'failed':
                return
            await asyncio.sleep(1)
        yield 'event: reconnect\ndata: {}\n\n'
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.post('/api/solicitations/{solicitation_id}/review')
def review(solicitation_id: str, body: ReviewInput, user: Owner):
    with Session.begin() as db:
        sol = owned(db, solicitation_id, user)
        if not sol.analysis or sol.status not in {'ready', 'reviewed'}:
            raise HTTPException(409, 'Wait for a complete brief before review.')
        if body.brief_version != sol.analysis['version']:
            raise HTTPException(409, 'The brief changed. Review the current version first.')
        ids = {f['id'] for f in sol.analysis['facts']}
        if not ids or set(body.reviewed_fact_ids) != ids or not body.acknowledged_gaps or not body.meaningful_notes():
            raise HTTPException(422, 'Verify every finding and acknowledge the missing information before recording a decision.')
        item = Review(solicitation_id=sol.id, owner_id=user, brief_version=body.brief_version,
                      decision=body.decision, notes=body.notes, reviewed_fact_ids=body.reviewed_fact_ids)
        db.add(item)
        sol.status = 'reviewed'
        db.flush()
        return {'id': item.id, 'decision': item.decision, 'created_at': item.created_at.isoformat()}


@app.get('/api/solicitations/{solicitation_id}/export')
def export(solicitation_id: str, user: Owner):
    with Session() as db:
        sol = owned(db, solicitation_id, user)
        if not sol.analysis:
            raise HTTPException(409, 'Brief is not ready.')
        latest = db.scalar(select(Review).where(Review.solicitation_id == sol.id, Review.brief_version == sol.analysis['version']).order_by(Review.created_at.desc()))
        decision = latest.decision.replace('_', ' ').upper() if latest else 'DRAFT — NOT REVIEWED'
        lines = [f'# {sol.title}', '', f'Status: {decision}', f'Provider: {sol.analysis["provider"]}', '', '## Source-linked findings', '']
        for f in sol.analysis['facts']:
            c = f['citation']
            kind = next(p.get('kind', 'page') for p in sol.pages if p['number'] == c['page'])
            lines += [f'### {f["label"]}', f['value'], '', f'> {c["quote"]}',
                      f'Source: {sol.filename}, {kind} {c["page"]}, characters {c["start"]}–{c["end"]}.', '']
        lines += ['## Missing information / checks', *['- ' + x for x in sol.analysis['missing_information']]]
        if latest:
            lines += ['', '## Human decision', latest.notes, f'Recorded at: {latest.created_at.isoformat()} UTC']
        return Response('\n'.join(lines), media_type='text/markdown', headers={'Content-Disposition': 'attachment; filename="biddy-brief.md"'})


@app.get('/api/profile')
def get_profile(user: Owner):
    with Session() as db:
        u = db.get(User, user)
        return u.profile if u else {}


@app.put('/api/profile')
def put_profile(body: ProfileInput, user: Owner):
    with Session.begin() as db:
        ensure_user(db, user)
        u = db.get(User, user)
        u.name, u.profile = body.name, body.model_dump()
    return body
