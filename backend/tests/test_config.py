import pytest
from pydantic import ValidationError
from app.config import Settings


@pytest.mark.parametrize('field,value', [
    ('llm_concurrency', 0), ('llm_concurrency', -1),
    ('job_max_attempts', 0), ('job_max_attempts', -1),
    ('job_lease_seconds', 0), ('job_lease_seconds', -1),
])
def test_processing_settings_reject_values_that_stall_or_expire_jobs(field, value):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{field: value})
