import asyncio
import copy
import hashlib
import json
import logging
import time
from datetime import timedelta
from sqlalchemy import and_, delete, or_, select, update
from .config import settings
from .db import Brief, Job, Requirement, Session, Solicitation, now, uid
from .extraction import analyze, cache_fingerprint
from .providers import ProviderError

log = logging.getLogger('biddy.worker')


def renew_lease(job_id, lease):
    with Session.begin() as db:
        changed = db.execute(update(Job).where(Job.id == job_id, Job.lease_token == lease,
                                              Job.status == 'running').values(claimed_at=now()))
        return changed.rowcount == 1


async def analyze_with_lease(pages, solicitation_id, job_id, lease):
    async def heartbeat():
        while True:
            await asyncio.sleep(max(1, settings().job_lease_seconds / 3))
            if not await asyncio.to_thread(renew_lease, job_id, lease):
                raise RuntimeError('Processing lease was transferred.')
    work = asyncio.create_task(analyze(pages, solicitation_id))
    beat = asyncio.create_task(heartbeat())
    try:
        done, _ = await asyncio.wait({work, beat}, return_when=asyncio.FIRST_COMPLETED)
        if beat in done:
            beat.result()
        return await work
    finally:
        work.cancel()
        beat.cancel()
        await asyncio.gather(work, beat, return_exceptions=True)


def claim_job():
    s = settings()
    cutoff = now() - timedelta(seconds=s.job_lease_seconds)
    with Session.begin() as db:
        # Exhausted leases become visible failures rather than being stuck forever.
        exhausted = db.scalars(select(Job).where(Job.status == 'running', Job.claimed_at < cutoff,
                                                  Job.attempts >= s.job_max_attempts).with_for_update(skip_locked=True)).all()
        for job in exhausted:
            job.status, job.error = 'failed', 'Worker lease expired after maximum attempts.'
            db.get(Solicitation, job.solicitation_id).status = 'failed'
        job = db.scalar(select(Job).where(Job.attempts < s.job_max_attempts, or_(
            and_(Job.status == 'queued', Job.available_at <= now()),
            and_(Job.status == 'running', Job.claimed_at < cutoff))).order_by(Job.available_at)
            .with_for_update(skip_locked=True).limit(1))
        if not job:
            return None
        job.status, job.claimed_at, job.lease_token = 'running', now(), uid()
        job.attempts += 1
        solicitation = db.get(Solicitation, job.solicitation_id)
        solicitation.status = 'processing'
        return job.id, job.lease_token, solicitation.id


def run_once():
    claimed = claim_job()
    if not claimed:
        return False
    job_id, lease, solicitation_id = claimed
    try:
        with Session() as db:
            sol = db.get(Solicitation, solicitation_id)
            pages = sol.pages
            cached = db.scalars(select(Solicitation).where(Solicitation.owner_id == sol.owner_id,
                                Solicitation.content_hash == sol.content_hash, Solicitation.status.in_(['ready', 'reviewed']),
                                Solicitation.id != sol.id).order_by(Solicitation.created_at.desc())).all()
            result = None
            for candidate in cached:
                if (candidate.analysis and candidate.analysis.get('cache_fingerprint') == cache_fingerprint()
                        and candidate.analysis.get('schema_version') == 'biddy-v1'):
                    result = copy.deepcopy(candidate.analysis)
                    for f in result['facts']:
                        f['id'], f['citation']['document_id'] = uid(), solicitation_id
                    result['metrics'] = {**result['metrics'], 'cache_hit': True, 'processing_ms': 0, 'usage': [], 'cost_usd': 0, 'input_tokens': 0, 'output_tokens': 0, 'cost_basis': 'cache hit; no model calls'}
                    break
        if result is None:
            result = asyncio.run(analyze_with_lease(pages, solicitation_id, job_id, lease))
        result.update({'configured_model': settings().llm_model, 'schema_version': 'biddy-v1'})
        result['version'] = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
        with Session.begin() as db:
            job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job.lease_token != lease or job.status != 'running':
                return True  # A new worker owns this lease; stale output cannot overwrite it.
            sol = db.get(Solicitation, solicitation_id)
            sol.analysis, sol.status, sol.updated_at = result, 'ready', now()
            db.execute(delete(Requirement).where(Requirement.solicitation_id == sol.id))
            for fact in result['facts']:
                db.add(Requirement(id=fact['id'], solicitation_id=sol.id, category=fact['category'], claim=fact))
            db.add(Brief(solicitation_id=sol.id, version=result['version'], content=result))
            job.status, job.error = 'done', None
    except Exception as exc:
        with Session.begin() as db:
            job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
            if job.lease_token == lease and job.status == 'running':
                job.error = str(exc) if isinstance(exc, ProviderError) else f'Processing failed ({type(exc).__name__}). Check server logs/configuration.'
                job.status = 'failed' if job.attempts >= settings().job_max_attempts else 'queued'
                job.available_at = now() + timedelta(seconds=2 ** job.attempts)
                db.get(Solicitation, solicitation_id).status = 'failed' if job.status == 'failed' else 'queued'
        log.warning('Job %s failed: %s', job_id, type(exc).__name__)
    return True


def main():
    logging.basicConfig(level=logging.INFO)
    while True:
        if not run_once():
            time.sleep(1)


if __name__ == '__main__':
    main()
