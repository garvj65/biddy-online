import copy
import json
import sys
import pytest
from evals import run


def example_result():
    return {'provider': 'rules', 'f1': 1.0, 'invalid_citations': 0,
            'cases': [{'id': 'example', 'missing_checks_pass': True, 'human_gate_preserved': True}]}


@pytest.mark.parametrize('failure', ['gap', 'human_gate', 'citation', 'accuracy', 'empty'])
def test_eval_cli_returns_failure_and_saves_report_for_failed_checks(monkeypatch, tmp_path, failure):
    result = example_result()
    if failure == 'gap':
        result['cases'][0]['missing_checks_pass'] = False
    elif failure == 'human_gate':
        result['cases'][0]['human_gate_preserved'] = False
    elif failure == 'citation':
        result['invalid_citations'] = 1
    elif failure == 'accuracy':
        result['f1'] = 0.5
    else:
        result['cases'] = []
    async def evaluate(_):
        return copy.deepcopy(result)
    output = tmp_path / 'report.json'
    monkeypatch.setattr(run, 'evaluate', evaluate)
    monkeypatch.setattr(sys, 'argv', ['evals', '--output', str(output)])
    with pytest.raises(SystemExit) as exc:
        run.main()
    assert exc.value.code == 1
    assert json.loads(output.read_text())['quality_gate']['passed'] is False


def test_eval_cli_accepts_passing_checks(monkeypatch, tmp_path):
    async def evaluate(_):
        return example_result()
    output = tmp_path / 'report.json'
    monkeypatch.setattr(run, 'evaluate', evaluate)
    monkeypatch.setattr(sys, 'argv', ['evals', '--output', str(output)])
    run.main()
    assert json.loads(output.read_text())['quality_gate']['passed'] is True
