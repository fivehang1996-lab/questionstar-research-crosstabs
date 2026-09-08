#!/usr/bin/env python3
"""Idempotent score-aware box metrics, including every configured matrix row."""
import json
import sys
from pathlib import Path
from research_core import add_significance


def apply(data, config):
    specs = {int(s['question']): s for s in config.get('box_metrics', [])}
    if config.get('box_metrics_all_ratings', True):
        for q in data['questions']:
            if q.get('is_rating'):
                specs.setdefault(q['q_index'], {'question': q['q_index']})
    rows = [r for r in data['rows'] if r.get('category') not in ('t2b','b2b') and not str(r.get('item','')).startswith('【指标】')]
    output, applied = [], set()
    for row in rows:
        output.append(row)
        q, ri = row['q_index'], row.get('matrix_row')
        if row['kind'] != 'mean' or q not in specs:
            continue
        spec = specs[q]
        if spec.get('enabled') is False:
            continue
        options = [r for r in rows if r['q_index']==q and r.get('matrix_row')==ri and r.get('option_id') is not None and r.get('score') is not None]
        scores = sorted({r['score'] for r in options})
        tn, bn = int(spec.get('top_n',2)), int(spec.get('bottom_n',2))
        if tn<1 or bn<1 or (not spec.get('top_items') and tn>len(scores)) or (not spec.get('bottom_items') and bn>len(scores)):
            raise ValueError(f'Q{q}: invalid top/bottom band size')
        selections = []
        for category, size, chosen_scores, names in [('t2b',tn,scores[-tn:],spec.get('top_items')), ('b2b',bn,scores[:bn],spec.get('bottom_items'))]:
            if names:
                selected = [r for r in options if r['item'] in names or r['item'].split('｜')[-1] in names]
                if len(selected) != len(names):
                    raise ValueError(f'Q{q}: box option labels missing or duplicated')
            else:
                selected = [r for r in options if r['score'] in chosen_scores]
            selections.append(selected)
            cells = []
            for i, g in enumerate(data['groups']):
                n = row['cells'][i]['base_n']
                numerator = sum(r['cells'][i]['numerator'] for r in selected)
                cells.append(dict(value=numerator/n if n else None, numerator=numerator, denominator=n, raw=[], base_n=n,
                                  low_base=row['cells'][i].get('low_base',False), definition_based=row['cells'][i].get('definition_based',False)))
            chosen = sorted({r['score'] for r in selected})
            score_label = f'{chosen[0]:g}–{chosen[-1]:g}' if len(chosen)>1 and all(b-a==1 for a,b in zip(chosen,chosen[1:])) else ' + '.join(f'{v:g}' for v in chosen)
            label = spec.get('top_label' if category=='t2b' else 'bottom_label') or f"{category.upper()}（{score_label}分）"
            prefix = row['item'].rsplit('｜',1)[0]+'｜' if ri is not None else ''
            direction = row.get('direction','neutral')
            if category=='b2b':
                direction = {'higher':'lower','lower':'higher'}.get(direction,'neutral')
            result = dict(id=f'q{q}:r{ri or 0}:{category}:', q_index=q, question=row['question'], matrix_row=ri, option_id=None,
                          item='【指标】'+prefix+label, kind='percent', test='proportion', metric='二档合计', category=category,
                          direction=direction, source_row_ids=[r['id'] for r in selected], cells=cells)
            add_significance(result, data['groups'], data['metadata'].get('alpha',.10), data['metadata'].get('minimum_test_base',0))
            output.append(result)
        if {r['id'] for r in selections[0]} & {r['id'] for r in selections[1]}:
            raise ValueError(f'Q{q}: top/bottom option overlap')
        applied.add(q)
    unknown = set(specs)-{q['q_index'] for q in data['questions'] if q.get('is_rating')}
    if unknown:
        raise ValueError(f'Box metrics require declared rating questions: {sorted(unknown)}')
    data['rows'] = output
    data['metadata']['box_metrics'] = dict(enabled=bool(applied), questions=sorted(applied), placement='after_mean', base='valid_scoring_answers')
    data['quality']['output_row_count'] = len(output)
    return data


def main(source, config, output):
    data = apply(json.loads(Path(source).read_text()), json.loads(Path(config).read_text()))
    Path(output).write_text(json.dumps(data,ensure_ascii=False,allow_nan=False))
    print(json.dumps(dict(rows=len(data['rows']),output=str(output))))


if __name__=='__main__':
    main(*sys.argv[1:])
