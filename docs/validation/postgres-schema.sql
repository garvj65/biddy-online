BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> e6ae75c83725

CREATE TABLE eval_results (
    id VARCHAR(36) NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    provider VARCHAR(40) NOT NULL, 
    result JSON NOT NULL, 
    PRIMARY KEY (id)
);

CREATE TABLE users (
    id VARCHAR(64) NOT NULL, 
    name VARCHAR(120) NOT NULL, 
    profile JSON NOT NULL, 
    PRIMARY KEY (id)
);

CREATE TABLE solicitations (
    id VARCHAR(36) NOT NULL, 
    owner_id VARCHAR(64) NOT NULL, 
    title VARCHAR(250) NOT NULL, 
    filename VARCHAR(250) NOT NULL, 
    source_url TEXT, 
    content TEXT NOT NULL, 
    pages JSON NOT NULL, 
    content_hash VARCHAR(64) NOT NULL, 
    status VARCHAR(32) NOT NULL, 
    analysis JSON, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(owner_id) REFERENCES users (id)
);

CREATE INDEX ix_solicitations_content_hash ON solicitations (content_hash);

CREATE INDEX ix_solicitations_created_at ON solicitations (created_at);

CREATE INDEX ix_solicitations_owner_id ON solicitations (owner_id);

CREATE INDEX ix_solicitations_fts ON solicitations USING gin(to_tsvector('english', content));

CREATE TABLE briefs (
    id VARCHAR(36) NOT NULL, 
    solicitation_id VARCHAR(36) NOT NULL, 
    version VARCHAR(64) NOT NULL, 
    content JSON NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(solicitation_id) REFERENCES solicitations (id)
);

CREATE INDEX ix_briefs_solicitation_id ON briefs (solicitation_id);

CREATE TABLE processing_jobs (
    id VARCHAR(36) NOT NULL, 
    solicitation_id VARCHAR(36) NOT NULL, 
    status VARCHAR(20) NOT NULL, 
    attempts INTEGER NOT NULL, 
    available_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    claimed_at TIMESTAMP WITHOUT TIME ZONE, 
    lease_token VARCHAR(36), 
    error TEXT, 
    PRIMARY KEY (id), 
    FOREIGN KEY(solicitation_id) REFERENCES solicitations (id)
);

CREATE INDEX ix_jobs_ready ON processing_jobs (status, available_at);

CREATE INDEX ix_processing_jobs_solicitation_id ON processing_jobs (solicitation_id);

CREATE TABLE requirements (
    id VARCHAR(36) NOT NULL, 
    solicitation_id VARCHAR(36) NOT NULL, 
    category VARCHAR(32) NOT NULL, 
    claim JSON NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(solicitation_id) REFERENCES solicitations (id)
);

CREATE INDEX ix_requirements_category ON requirements (category);

CREATE INDEX ix_requirements_solicitation_id ON requirements (solicitation_id);

CREATE TABLE review_decisions (
    id VARCHAR(36) NOT NULL, 
    solicitation_id VARCHAR(36) NOT NULL, 
    owner_id VARCHAR(64) NOT NULL, 
    brief_version VARCHAR(64) NOT NULL, 
    decision VARCHAR(20) NOT NULL, 
    notes TEXT NOT NULL, 
    reviewed_fact_ids JSON NOT NULL, 
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(owner_id) REFERENCES users (id), 
    FOREIGN KEY(solicitation_id) REFERENCES solicitations (id)
);

CREATE INDEX ix_review_decisions_solicitation_id ON review_decisions (solicitation_id);

INSERT INTO alembic_version (version_num) VALUES ('e6ae75c83725') RETURNING alembic_version.version_num;

COMMIT;

