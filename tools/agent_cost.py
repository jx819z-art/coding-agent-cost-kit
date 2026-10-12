#!/usr/bin/env python3
"""Estimate Claude Code and Codex CLI spend from their local session logs.

Reads local files only: no network, standard library only. Prices come from
prices.json next to this script (USD per 1M tokens). Replace the defaults with
your provider's rates; the output is an estimate, not a bill.

  python3 agent_cost.py claude [--since 2026-10-01] [--budget 2000]
  python3 agent_cost.py codex  [--since 2026-10-01] [--budget 2000]
"""
import argparse
import calendar
import collections
import datetime
import glob
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = {'claude': '~/.claude/projects', 'codex': '~/.codex/sessions'}
PARTS = {
    'claude': ('input', 'cache_write_5m', 'cache_write_1h', 'cache_read', 'output'),
    'codex': ('input', 'cached_input', 'cache_write', 'output'),
}


def jsonl(path):
    with open(path, errors='ignore') as f:
        for line in f:
            try:
                yield json.loads(line)
            except ValueError:
                continue


def logs(root):
    return glob.glob(os.path.join(os.path.expanduser(root), '**', '*.jsonl'), recursive=True)


def claude_records(root, since=''):
    """One (session, day, model, tokens) record per API response."""
    raw = {}
    for path in logs(root):
        for e in jsonl(path):
            m = e.get('message') or {}
            u = m.get('usage')
            if e.get('type') != 'assistant' or not u or not m.get('id'):
                continue
            day = (e.get('timestamp') or '')[:10]
            if day < since:
                continue
            tok = {'input': u.get('input_tokens', 0),
                   'cache_write': u.get('cache_creation_input_tokens', 0),
                   'cache_write_1h': (u.get('cache_creation') or {}).get('ephemeral_1h_input_tokens', 0),
                   'cache_read': u.get('cache_read_input_tokens', 0),
                   'output': u.get('output_tokens', 0)}
            # A response is logged once per content block: keep the largest count of each field.
            old = raw.get(m['id'])
            if old:
                tok = {k: max(v, old[3][k]) for k, v in tok.items()}
            raw[m['id']] = (e.get('sessionId', '?'), day, m.get('model', '?'), tok)
    records = []
    for session, day, model, t in raw.values():
        records.append((session, day, model, {
            'input': t['input'],
            'cache_write_5m': t['cache_write'] - t['cache_write_1h'],
            'cache_write_1h': t['cache_write_1h'],
            'cache_read': t['cache_read'],
            'output': t['output']}))
    return records


def codex_tokens(u):
    # input_tokens includes the cached and cache-write tokens; output_tokens includes reasoning.
    cached = u.get('cached_input_tokens', 0)
    written = u.get('cache_write_input_tokens', 0)
    return {'input': max(u.get('input_tokens', 0) - cached - written, 0),
            'cached_input': cached,
            'cache_write': written,
            'output': u.get('output_tokens', 0)}


def codex_records(root, since=''):
    """Per-response records from token_usage_record; older logs fall back to the
    last cumulative token_count of each session file."""
    records = {}
    for path in logs(root):
        session, turn_model, last_model = os.path.basename(path), {}, '?'
        for e in jsonl(path):
            p = e.get('payload') or {}
            if e.get('type') == 'session_meta':
                session = p.get('id', session)
            elif e.get('type') == 'turn_context':
                last_model = p.get('model') or last_model
                turn_model[p.get('turn_id')] = last_model
        found, cumulative = False, None
        for e in jsonl(path):
            p = e.get('payload') or {}
            day = (e.get('timestamp') or '')[:10]
            if e.get('type') == 'token_usage_record':
                found = True
                if day >= since:
                    key = p.get('response_id') or (path, e.get('ordinal'))
                    model = turn_model.get(p.get('turn_id'), last_model)
                    records[key] = (session, day, model, codex_tokens(p.get('usage') or {}))
            elif e.get('type') == 'event_msg' and p.get('type') == 'token_count' and p.get('info'):
                cumulative = (day, p['info'].get('total_token_usage') or {})
        if not found and cumulative and cumulative[0] >= since:
            records[path] = (session, cumulative[0], last_model, codex_tokens(cumulative[1]))
    return list(records.values())


def rate_for(table, model):
    """Price row whose key is the longest substring of the model id, or None."""
    keys = [k for k in table if not k.startswith('_') and k in (model or '')]
    return table[max(keys, key=len)] if keys else None


def summarise(records, table, parts):
    s = {'cost': collections.defaultdict(collections.Counter),
         'unpriced': collections.defaultdict(collections.Counter),
         'session': collections.Counter(), 'day': collections.Counter()}
    for session, day, model, tok in records:
        rate = rate_for(table, model)
        if rate is None or any(rate.get(p) is None for p in parts):
            s['unpriced'][model].update(tok)
            continue
        cost = {p: tok[p] * rate[p] / 1e6 for p in parts}
        s['cost'][model].update(cost)
        s['session'][session] += sum(cost.values())
        s['day'][day] += sum(cost.values())
    return s


def budget_lines(by_day, budget, today):
    month_start = today.replace(day=1).isoformat()
    spent = sum(v for d, v in by_day.items() if d >= month_start)
    days = calendar.monthrange(today.year, today.month)[1]
    left = days - today.day
    lines = [f"Month to date:  ${spent:,.2f} of ${budget:,.0f} ({100 * spent / budget:.0f} %)",
             f"Average/day:    ${spent / today.day:,.2f}  ->  projected month end ${spent / today.day * days:,.2f}"]
    if left:
        lines.append(f"To finish on budget: at most ${(budget - spent) / left:,.2f}/day for the last {left} days")
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('tool', choices=sorted(PARTS))
    ap.add_argument('--since', help='first day to include, YYYY-MM-DD (default: start of this month)')
    ap.add_argument('--budget', type=float, help='monthly budget in USD, for a pace check')
    ap.add_argument('--root', help='log folder (default: %s)' % DEFAULT_ROOT)
    ap.add_argument('--prices', default=os.path.join(HERE, 'prices.json'))
    a = ap.parse_args()

    today = datetime.date.today()
    since = a.since or today.replace(day=1).isoformat()
    with open(a.prices) as f:
        table = json.load(f)[a.tool]
    parts = PARTS[a.tool]
    read = claude_records if a.tool == 'claude' else codex_records
    records = read(a.root or DEFAULT_ROOT[a.tool], since)
    s = summarise(records, table, parts)

    total = sum(sum(c.values()) for c in s['cost'].values())
    print(f"{a.tool}: estimated ${total:,.2f} since {since} ({len(records)} API responses)\n")
    print(f"{'model':32}" + ''.join(f'{p:>16}' for p in parts) + f"{'total':>12}")
    for model, c in sorted(s['cost'].items(), key=lambda kv: -sum(kv[1].values())):
        print(f"{model[:32]:32}" + ''.join(f"{'$' + format(c[p], ',.2f'):>16}" for p in parts)
              + f"{'$' + format(sum(c.values()), ',.2f'):>12}")
    if total:
        both = collections.Counter()
        for c in s['cost'].values():
            both.update(c)
        print(f"{'share':32}" + ''.join(f'{100 * both[p] / total:>15.0f}%' for p in parts))
    for model, t in s['unpriced'].items():
        print(f"{model[:32]:32}" + ''.join(f'{t[p]:>16,}' for p in parts) + '   tokens - no price in prices.json')
    print('\nTop sessions:')
    for session, c in s['session'].most_common(8):
        print(f"  {session[:12]:12}  ${c:,.2f}")
    print('\nPer day:')
    for day in sorted(s['day']):
        print(f"  {day}  ${s['day'][day]:,.2f}")
    if a.budget:
        if since > today.replace(day=1).isoformat():
            print('\n(--since is after the 1st, so month-to-date below is understated)')
        print('\nBudget pace (this machine only - check your cloud bill for the authoritative figure):')
        for line in budget_lines(s['day'], a.budget, today):
            print('  ' + line)


if __name__ == '__main__':
    main()
