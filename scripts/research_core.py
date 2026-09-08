"""Shared input contracts and statistics for survey tables."""
import math
import re
from collections import defaultdict
from analyze_wjx_crosstabs import welch_p as reference_welch

VERSION = '2.0.0'


def clean(value):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', str(value or ''))).strip()


def integer(value):
    try:
        result = float(value)
        return int(result) if math.isfinite(result) and result.is_integer() else None
    except (ValueError, TypeError):
        return None


def primary(record, question, matrix_row=None):
    answers = [a for a in record.get('answer_items', {}).values() if integer(a.get('q_index')) == int(question)
               and (matrix_row is None or integer(a.get('q_row')) == matrix_row)]
    return next((a for a in answers if integer(a.get('q_column', 0)) == 0), answers[0] if answers else {})


def selections(record, question, allowed=None, matrix_row=None):
    values = [integer(v) for v in primary(record, question, matrix_row).get('item_index') or []]
    if not values or any(v is None or v < 0 for v in values):
        return None
    if allowed is not None and any(v not in allowed for v in values):
        return None
    return set(values)


def source_value(record, spec):
    answer = primary(record, int(spec['question']))
    if spec.get('source', 'item_index') == 'item_value':
        try:
            value = float(answer.get('item_value'))
            return value if math.isfinite(value) else None
        except (ValueError, TypeError):
            return None
    values = selections(record, spec['question'])
    return next(iter(values)) if values is not None and len(values) == 1 else None


def keyed(rows, field='respondent_id'):
    result = {}
    for row in rows:
        key = str(row.get(field, '')).strip()
        if not key or key == 'None':
            raise ValueError(f'Missing stable {field}; positional label matching is not supported')
        if key in result:
            raise ValueError(f'Duplicate {field}; resolve duplicates before analysis')
        result[key] = row
    return result


def align_labels(records, meta):
    keyed(records)
    lookup = keyed(meta.get('labels', []))
    return [dict(lookup.get(str(r['respondent_id']), {'respondent_id': r['respondent_id'], 'matched': False})) for r in records]


def classify(value, groups):
    if value is None:
        return '未回答'
    hits = [g['label'] for g in groups if ('values' in g and value in g['values']) or
            (('min' in g or 'max' in g) and g.get('min', -math.inf) <= value <= g.get('max', math.inf))]
    if len(hits) > 1:
        raise ValueError('Derived segment definitions overlap; use explicit boolean groups for overlap')
    return hits[0] if hits else '未回答'


def letters(number):
    result = ''
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result


def proportion_p(x1, n1, x2, n2):
    if not n1 or not n2:
        return None
    pooled = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pooled * (1 - pooled) * (1 / n1 + 1 / n2))
    return math.erfc(abs(x1 / n1 - x2 / n2) / se / math.sqrt(2)) if se else 1.0


def welch_p(a, b):
    if len(a) < 2 or len(b) < 2:
        return None
    if len(set(a)) == 1 and len(set(b)) == 1:
        return 1.0 if a[0] == b[0] else 0.0
    result = reference_welch(a, b)
    return result if math.isfinite(result) else None


def add_significance(row, groups, alpha=0.10, min_test_n=0):
    for cell in row['cells']:
        cell['sig_high'], cell['sig_low_all'], cell['comparisons'] = [], False, []
    if row['test'] == 'none':
        return
    families = defaultdict(list)
    for i, group in enumerate(groups):
        if group['family'] != '总体':
            families[group['family']].append(i)
    for indices in families.values():
        for i in indices:
            a = row['cells'][i]
            for j in indices:
                b = row['cells'][j]
                if i == j or a['value'] is None or b['value'] is None:
                    continue
                if min(a.get('base_n', 0), b.get('base_n', 0)) < min_test_n:
                    continue
                p = proportion_p(a['numerator'], a['denominator'], b['numerator'], b['denominator']) if row['test'] == 'proportion' else welch_p(a['raw'], b['raw'])
                if p is None:
                    continue
                a['comparisons'].append({'group_id': groups[j]['id'], 'letter': groups[j]['letter'], 'p': p,
                                         'higher': a['value'] > b['value'], 'lower': a['value'] < b['value']})
                if p < alpha and a['value'] > b['value']:
                    a['sig_high'].append(groups[j]['letter'])
            a['sig_low_all'] = bool(a['comparisons']) and all(c['p'] < alpha and c['lower'] for c in a['comparisons'])


def scale_for(question, config):
    q = int(question['q_index'])
    spec = config.get('scales', {}).get(str(q))
    if spec is None and q not in [int(v) for v in config.get('rating_questions', [])]:
        return None
    spec = dict(spec or {})
    options = {int(o['item_index']): clean(o.get('item_title')) for o in question.get('items', [])}
    mapping = spec.get('scores')
    if mapping is None:
        mapping = {str(i): i for i in options}  # only explicitly declared scales
    if set(map(int, mapping)) != set(options):
        raise ValueError(f'Q{q}: score mapping must cover every option; use null for non-scoring choices')
    scores = {int(k): float(v) if v is not None else None for k, v in mapping.items()}
    if any(v is not None and not math.isfinite(v) for v in scores.values()):
        raise ValueError(f'Q{q}: scores must be finite')
    if len({v for v in scores.values() if v is not None}) < 2:
        raise ValueError(f'Q{q}: scale requires two distinct scores')
    spec.update(scores=scores, direction=spec.get('direction', 'higher'))
    if spec['direction'] not in ('higher', 'lower', 'neutral'):
        raise ValueError('Scale direction must be higher/lower/neutral')
    return spec
