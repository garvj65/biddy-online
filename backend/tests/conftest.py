import os
import tempfile
from pathlib import Path
import pytest

test_database = Path(tempfile.mkdtemp(prefix='biddy-tests-')) / 'tests.db'
os.environ['DATABASE_URL'] = f'sqlite:///{test_database}'
os.environ['LLM_PROVIDER'] = 'rules'
os.environ['BIDDY_ACCESS_TOKEN'] = 'test-workspace-secret'

from app.db import Base, engine


@pytest.fixture(autouse=True)
def fresh_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def headers():
    return {'Authorization': 'Bearer test-workspace-secret'}


@pytest.fixture
def solicitation_text():
    return '''EXAMPLE WEBSITE SUPPORT PROCUREMENT
The contractor shall provide Drupal maintenance and accessibility support.
Proposals are due October 30, 2026 at 5:00 PM Eastern Time.
Questions must be submitted by October 20, 2026 at noon ET.
This is a total small business set-aside under NAICS 541511.
Offerors must maintain an active SAM registration at award.
Submit two separate volumes through the procurement portal.
The technical lead must attend on-site meetings twice each month.
'''
