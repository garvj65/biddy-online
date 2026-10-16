import uuid
from datetime import datetime, timezone
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .config import settings


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def uid():
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default='My workspace')
    profile: Mapped[dict] = mapped_column(JSON, default=dict)


class Solicitation(Base):
    __tablename__ = 'solicitations'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    title: Mapped[str] = mapped_column(String(250))
    filename: Mapped[str] = mapped_column(String(250))
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    pages: Mapped[list] = mapped_column(JSON)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[str] = mapped_column(String(32), default='queued')
    analysis: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Requirement(Base):
    __tablename__ = 'requirements'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    solicitation_id: Mapped[str] = mapped_column(ForeignKey('solicitations.id'), index=True)
    category: Mapped[str] = mapped_column(String(32), index=True)
    claim: Mapped[dict] = mapped_column(JSON)


class Brief(Base):
    __tablename__ = 'briefs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    solicitation_id: Mapped[str] = mapped_column(ForeignKey('solicitations.id'), index=True)
    version: Mapped[str] = mapped_column(String(64))
    content: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Review(Base):
    __tablename__ = 'review_decisions'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    solicitation_id: Mapped[str] = mapped_column(ForeignKey('solicitations.id'), index=True)
    owner_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    brief_version: Mapped[str] = mapped_column(String(64))
    decision: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str] = mapped_column(Text)
    reviewed_fact_ids: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Job(Base):
    __tablename__ = 'processing_jobs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    solicitation_id: Mapped[str] = mapped_column(ForeignKey('solicitations.id'), index=True)
    status: Mapped[str] = mapped_column(String(20), default='queued')
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lease_token: Mapped[str | None] = mapped_column(String(36), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__ = (Index('ix_jobs_ready', 'status', 'available_at'),)


class EvalResult(Base):
    __tablename__ = 'eval_results'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    provider: Mapped[str] = mapped_column(String(40))
    result: Mapped[dict] = mapped_column(JSON)


engine = create_engine(settings().database_url, pool_pre_ping=True,
                       connect_args={'check_same_thread': False} if settings().database_url.startswith('sqlite') else {})
Session = sessionmaker(engine, expire_on_commit=False)
