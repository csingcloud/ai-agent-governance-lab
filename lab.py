"""Review synthetic agent activity against declared authority and exact scopes."""
import argparse
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEMO_TIME = '2026-01-15T12:00:00Z'

def timestamp(value):
    if not isinstance(value, str) or 'T' not in value:
        raise ValueError('Expected timestamp with timezone')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None: raise ValueError('Timezone required')
    return result

def nonempty(value):
    return isinstance(value, str) and bool(value.strip())

def review(inventory, activity, at=DEMO_TIME):
    now = timestamp(at)
    for data in (inventory, activity):
        if not isinstance(data, dict) or data.get('synthetic') is not True:
            raise ValueError('Only explicitly synthetic fixtures are accepted')
    agents, events = inventory.get('agents'), activity.get('events')
    if not isinstance(agents, list) or not isinstance(events, list):
        raise ValueError('agents and events must be lists')
    index = {}
    for agent in agents:
        if not isinstance(agent, dict) or not nonempty(agent.get('agent_id')):
            raise ValueError('Each agent requires an ID')
        if agent['agent_id'] in index:
            raise ValueError('Duplicate agent ID; resolve ambiguity before review')
        index[agent['agent_id']] = agent
    results, seen_events = [], set()
    for event in events:
        if not isinstance(event, dict) or not nonempty(event.get('event_id')):
            raise ValueError('Each event requires an ID')
        if event['event_id'] in seen_events:
            raise ValueError('Duplicate event ID; resolve replay or input duplication')
        seen_events.add(event['event_id'])
        row = {'event': dict(event), 'status': 'UNKNOWN', 'reasons': [], 'authority_id': None}
        results.append(row)
        if any(not nonempty(event.get(k)) for k in ('agent_id', 'identity', 'tool', 'resource')):
            row['reasons'].append('Missing event identity or scope')
            continue
        agent = index.get(event['agent_id'])
        if agent is None:
            row['reasons'].append('Agent is absent from the declared inventory')
            continue
        if not nonempty(agent.get('owner')):
            row['reasons'].append('No accountable owner is recorded')
        if not nonempty(agent.get('identity')) or agent['identity'] != event['identity']:
            row['reasons'].append('Identity binding is missing or mismatched')
        authority = agent.get('authority')
        if not isinstance(authority, dict) or not nonempty(authority.get('id')):
            row['reasons'].append('No authority record is present')
            continue
        row['authority_id'] = authority['id']
        try:
            start, end = timestamp(authority.get('valid_from')), timestamp(authority.get('valid_until'))
            observed = timestamp(event.get('observed_at'))
            if end <= start: raise ValueError('Invalid authority interval')
        except (ValueError, TypeError):
            row['reasons'].append('Invalid authority or observation timestamp')
            continue
        if observed > now:
            row['reasons'].append('Observation is in the future')
        if not start <= observed < end:
            row['reasons'].append('Declared authority was not active at observation time')
        permissions = agent.get('permissions')
        if not isinstance(permissions, list) or any(
            not isinstance(p, dict) or not nonempty(p.get('tool'))
            or not isinstance(p.get('resources'), list)
            or any(not nonempty(x) for x in p['resources']) for p in permissions
        ):
            row['reasons'].append('Malformed declared permissions')
        if row['reasons']:
            continue
        allowed = any(p['tool'] == event['tool'] and event['resource'] in p['resources'] for p in permissions)
        row['status'] = 'WITHIN_DECLARED_SCOPE' if allowed else 'OUTSIDE_DECLARED_SCOPE'
        row['reasons'] = ['Exact tool/resource match found' if allowed else 'No matching tool/resource permission']
    return {'synthetic': True, 'reviewed_at': at, 'review_mode': 'historical-event-time',
            'enforcement_performed': False, 'results': results}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path, default=ROOT / 'fixtures/inventory.json')
    parser.add_argument('--events', type=Path, default=ROOT / 'fixtures/events.json')
    parser.add_argument('--at', default=DEMO_TIME)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    try:
        result = review(json.loads(args.inventory.read_text()), json.loads(args.events.read_text()), args.at)
    except (ValueError, OSError, TypeError) as exc:
        parser.error(str(exc))
    text = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text)
    print(text, end='')

if __name__ == '__main__': main()
