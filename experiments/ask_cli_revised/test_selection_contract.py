"""Selection-only wire isolation and unchanged failure handling, without inference."""
from dataclasses import dataclass
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from app.backend.llm.managed_local import ManagedProviderRuntime
from experiments.ask_cli_revised.qwen import QwenTasks, evidence_selection_schema, _with_output_cap, _CLAIM_SCHEMA
from experiments.ask_cli_revised.calibration.structured_output import schema_config, RESPONSE_FORMAT


@dataclass
class Config:
    provider_runtime: object
    max_output_tokens: int = 4096
    managed_output_contract: object = None


class SelectionContractTests(unittest.TestCase):
    def test_wire_changes_only_response_format(self):
        sent = []
        client = SimpleNamespace(post=lambda url, **kw: sent.append(kw['json']))
        pool = SimpleNamespace(run_http=lambda **kw: kw['operation'](client))
        base = Config(ManagedProviderRuntime(pool, output_cap=4096, contract=None))
        schema = evidence_selection_schema(['e1', 'e2'])
        for config in [_with_output_cap(base, 96), schema_config(base, output_cap=96, json_schema=schema, mode=RESPONSE_FORMAT)]:
            config.provider_runtime.run_http(base_url='http://localhost', timeout=600, trust_env=False,
                operation=lambda c: c.post('/v1/chat/completions', json={
                    'messages': [{'role': 'user', 'content': 'UNCHANGED'}],
                    'model': 'callosum-managed-local', 'temperature': 0, 'seed': 42, 'max_tokens': 4096}))
        treatment = dict(sent[1])
        contract = treatment.pop('response_format')
        self.assertEqual(treatment, sent[0])
        self.assertEqual(contract['json_schema']['schema'], schema)
        self.assertEqual(treatment['max_tokens'], 96)

    def test_selection_uses_schema_and_preserves_empty_and_truncation_policy(self):
        task = QwenTasks(SimpleNamespace(), SimpleNamespace(qwen_call=lambda **kw: None))
        for raw, ok, expected in [('{"span_ids":[]}', True, []), ('{"span_ids":["e1"]}', True, ['e1']),
                                  ('{"span_ids":["e1"]}', False, [])]:
            with patch.object(task, '_call', return_value=SimpleNamespace(raw_text=raw, provider_ok=ok,
                    failure_reason=None if ok else 'truncated_at_output_cap', elapsed_seconds=0, output_cap=96)) as call:
                actual = task.select_evidence(spans=[{'span_id':'e1','text':'A null result.'}],
                                              subquestion='Which results?', obligations=[])
                self.assertEqual(actual, expected)
                self.assertEqual(call.call_args.kwargs['json_schema'], evidence_selection_schema(['e1']))
                self.assertEqual(call.call_args.kwargs['output_cap'], 96)

    def test_other_tasks_remain_unconstrained(self):
        task = QwenTasks(SimpleNamespace(), SimpleNamespace(qwen_call=lambda **kw: None))
        with patch.object(task, '_call', return_value=SimpleNamespace(raw_text='{"action":"accept"}', provider_ok=True,
                failure_reason=None, elapsed_seconds=0, output_cap=48)) as call:
            task.context_gate(packet_text='A null result.', subquestion='Which results?')
            self.assertNotIn('json_schema', call.call_args.kwargs)

    def test_form_claim_now_uses_schema_and_preserves_empty_string_policy(self):
        task = QwenTasks(SimpleNamespace(), SimpleNamespace(qwen_call=lambda **kw: None))
        for raw, ok, expected in [('{"claim":""}', True, None), ('{"claim":"Amygdala finding."}', True, 'Amygdala finding.'),
                                  ('{"claim":"Amygdala finding."}', False, None)]:
            with patch.object(task, '_call', return_value=SimpleNamespace(raw_text=raw, provider_ok=ok,
                    failure_reason=None if ok else 'truncated_at_output_cap', elapsed_seconds=0, output_cap=512)) as call:
                actual = task.form_claim(quote='A null result.', context_text='A null result.', subquestion='Which results?')
                self.assertEqual(actual, expected)
                self.assertEqual(call.call_args.kwargs['json_schema'], _CLAIM_SCHEMA)
                self.assertEqual(call.call_args.kwargs['output_cap'], 512)


if __name__ == '__main__':
    unittest.main()
