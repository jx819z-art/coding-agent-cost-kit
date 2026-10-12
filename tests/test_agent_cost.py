import datetime
import json
import os
import sys
import tomllib
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, 'tests', 'fixtures')
sys.path.insert(0, os.path.join(ROOT, 'tools'))
import agent_cost as ac  # noqa: E402

CLAUDE_RATES = {
    'opus-5-5': {'input': 4, 'cache_write_5m': 5, 'cache_write_1h': 8, 'cache_read': 0.2, 'output': 20},
    'sonnet-5-5': {'input': 2, 'cache_write_5m': 2.5, 'cache_write_1h': 4, 'cache_read': 0.2, 'output': 10},
}
CODEX_RATES = {'model-a': {'input': 1, 'cached_input': 0.1, 'cache_write': 1.25, 'output': 10}}


class ClaudeLogs(unittest.TestCase):
    def setUp(self):
        records = ac.claude_records(os.path.join(FIX, 'claude'), since='2026-10-01')
        self.s = ac.summarise(records, CLAUDE_RATES, ac.PARTS['claude'])

    def test_dedupes_blocks_and_splits_cache_ttl(self):
        # msg_a counted once with its final output count; 600 5-min + 400 1-hour writes.
        opus = self.s['cost']['claude-opus-5-5']
        self.assertAlmostEqual(opus['cache_write_5m'], 600 * 5 / 1e6)
        self.assertAlmostEqual(opus['cache_write_1h'], 400 * 8 / 1e6)
        self.assertAlmostEqual(opus['output'], 50 * 20 / 1e6)
        self.assertAlmostEqual(sum(opus.values()), 0.008)

    def test_bedrock_id_matches_and_since_filters(self):
        self.assertAlmostEqual(sum(self.s['cost']['us.anthropic.claude-sonnet-5-5'].values()), 0.004)
        self.assertEqual(sorted(self.s['day']), ['2026-10-02', '2026-10-03'])

    def test_unknown_model_reported_as_unpriced(self):
        self.assertIn('<synthetic>', self.s['unpriced'])


class CodexLogs(unittest.TestCase):
    def setUp(self):
        records = ac.codex_records(os.path.join(FIX, 'codex'), since='2026-10-01')
        self.s = ac.summarise(records, CODEX_RATES, ac.PARTS['codex'])

    def test_per_response_records_and_old_format_fallback(self):
        # r1 (deduped): 400 uncached + 600 cached + 100 output; old file: last cumulative count.
        a = self.s['cost']['model-a']
        self.assertAlmostEqual(sum(a.values()), (400 + 60 + 1000 + 400 + 40 + 600) / 1e6)
        self.assertEqual(set(self.s['session']), {'sess-new', 'sess-old'})

    def test_model_comes_from_turn_context_even_when_logged_after(self):
        self.assertEqual(self.s['unpriced']['model-b'], {'input': 500, 'cached_input': 0, 'cache_write': 0, 'output': 50})


class Budget(unittest.TestCase):
    def test_pace(self):
        lines = ac.budget_lines({'2026-09-30': 999, '2026-10-01': 100, '2026-10-12': 1000},
                                2000, datetime.date(2026, 10, 12))
        text = '\n'.join(lines)
        self.assertIn('$1,100.00 of $2,000', text)
        self.assertIn('projected month end $2,841.67', text)
        self.assertIn('$47.37/day for the last 19 days', text)


class Templates(unittest.TestCase):
    def test_claude_settings(self):
        with open(os.path.join(ROOT, 'claude', 'settings.json')) as f:
            cfg = json.load(f)
        self.assertIs(cfg['skipWebFetchPreflight'], True)
        self.assertNotIn('CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS', cfg['env'])
        self.assertTrue(all(isinstance(v, str) for v in cfg['env'].values()))

    def test_codex_config_keys_at_right_level(self):
        with open(os.path.join(ROOT, 'codex', 'config.toml'), 'rb') as f:
            cfg = tomllib.load(f)
        for key in ('model', 'model_reasoning_effort', 'model_verbosity', 'model_auto_compact_token_limit'):
            self.assertIn(key, cfg)
        self.assertEqual(cfg['agents']['max_concurrent_threads_per_session'], 2)
        self.assertEqual(set(cfg['agents']), {'max_concurrent_threads_per_session', 'default_subagent_reasoning_effort'})

    def test_price_rows_complete(self):
        with open(os.path.join(ROOT, 'tools', 'prices.json')) as f:
            prices = json.load(f)
        for tool, parts in ac.PARTS.items():
            for key, row in prices[tool].items():
                if not key.startswith('_'):
                    self.assertEqual(set(row), set(parts), f'{tool}/{key}')


if __name__ == '__main__':
    unittest.main()
