#!/usr/bin/env python3
"""Analyze cleaned, keyed survey records with explicit score mappings."""
import json
import sys
from collections import defaultdict
from pathlib import Path
from research_core import VERSION, add_significance, align_labels, clean, integer, keyed, letters, primary, scale_for, selections, source_value


def analyze(survey, records, config=None, labels_meta=None, receipt=None):
    config, labels_meta, receipt = config or {}, labels_meta or {}, receipt or {}
    keyed(records)
    labels = align_labels(records, labels_meta) if 'labels' in labels_meta else None
    questions = {int(q['q_index']): q for q in survey.get('questions', [])
                 if integer(q.get('q_index')) and q.get('q_title') and integer(q.get('q_type')) not in (1, 2)}
    if not questions:
        raise ValueError('No analyzable questions')
    alpha = float(config.get('alpha', 0.10))
    if not 0 < alpha < 1:
        raise ValueError('alpha must lie between zero and one')
    nps_q = int(config['nps_question']) if config.get('nps_question') else None
    if nps_q is not None and nps_q not in questions:
        raise ValueError('Configured NPS question does not exist')
    low_n, min_test_n = int(config.get('low_base_warning', 30)), int(config.get('minimum_test_base', 0))
    groups = [{'family': '总体', 'label': '总体', 'members': list(range(len(records))), 'source_questions': []}]
    specs = []
    if labels is not None:
        specs += [dict(s, field=s.get('field', 'exclusive_group')) for s in labels_meta.get('exclusive_groups', [])]
        specs += labels_meta.get('label_groups', [])
        for spec in labels_meta.get('boolean_groups', []):
            groups.append(dict(family=spec['family'], label=spec['label'], source_questions=spec.get('source_questions', []),
                               members=[i for i,label in enumerate(labels) if (not spec.get('requires_match',True) or label.get('matched',True)) and label.get(spec['field']) is True]))
        for spec in config.get('categorical_label_fields', []):
            values = spec.get('values') or list(dict.fromkeys(r.get(spec['field']) for r in labels if r.get(spec['field']) not in (None, '', '未回答')))
            specs += [dict(spec, label=v) for v in values]
        for spec in specs:
            field = spec.get('field', spec['family'])
            groups.append(dict(family=spec['family'], label=spec['label'], source_questions=spec.get('source_questions', []),
                               members=[i for i, label in enumerate(labels) if (not spec.get('requires_match',True) or label.get('matched', True)) and label.get(field) == spec['label']]))
        for spec in config.get('boolean_label_prefixes', []):
            fields = list(dict.fromkeys(k for label in labels for k in label if k.startswith(spec['prefix'])))
            for field in fields:
                groups.append(dict(family=spec['family'], label=field[len(spec['prefix']):], source_questions=[],
                                   members=[i for i, label in enumerate(labels) if label.get('matched', True) and label.get(field) is True]))
    for spec in config.get('native_segments', []):
        q = int(spec['question'])
        if q not in questions:
            raise ValueError(f'Native segment Q{q} does not exist')
        meta = questions[q]
        if integer(meta.get('q_type')) not in (3, 4) or integer(meta.get('q_subtype')) == 402:
            raise ValueError(f'Native segment Q{q} must be single or multi choice')
        allowed = {int(o['item_index']) for o in meta.get('items', [])}
        for option in meta.get('items', []):
            key = int(option['item_index'])
            groups.append(dict(family=spec['family'], label=clean(option['item_title']), source_questions=[q],
                               members=[i for i, r in enumerate(records) if key in (selections(r, q, allowed) or set())
                                        and (integer(meta.get('q_type'))==4 or len(selections(r,q,allowed) or set())==1)]))
    counters, identities = defaultdict(int), set()
    for group in groups:
        identity = (group['family'], group['label'])
        if identity in identities:
            raise ValueError(f'Duplicate group {identity}')
        identities.add(identity)
        counters[group['family']] += 1
        group.update(id=f"g{len(identities)}", letter='' if group['family']=='总体' else letters(counters[group['family']]), base_n=len(group['members']))
    overlaps = []
    for i, group in enumerate(groups):
        for other in groups[i+1:]:
            shared = set(group['members']) & set(other['members'])
            if group['family'] != '总体' and group['family'] == other['family'] and shared:
                overlaps.append(dict(family=group['family'], left=group['label'], right=other['label'], shared_n=len(shared)))
    rows, question_meta, bases = [], [], {}

    def append(q, item, kind, test, samples, *, option=None, matrix_row=None, metric=None, direction='neutral', category=None):
        cells = []
        for group in groups:
            values = [samples[i] for i in group['members'] if samples[i] is not None]
            n = len(values)
            cell = dict(value=None, numerator=None, denominator=None, raw=[], base_n=n, low_base=0<n<low_n,
                        definition_based=q in group['source_questions'])
            if kind in ('total', 'base'):
                cell['value'] = n
            elif test == 'proportion':
                cell.update(numerator=sum(values), denominator=n, value=sum(values)/n if n else None)
            else:
                cell.update(raw=values, value=sum(values)/n*(100 if kind=='nps' else 1) if n else None)
            cells.append(cell)
        row = dict(q_index=q, question=f"Q{q}. {clean(questions[q]['q_title'])}", item=item, kind=kind, test=test,
                   metric=metric or {'total':'total', 'base':'有效基数', 'mean':'均值', 'nps':'NPS', 'rank_mean':'平均名次'}.get(kind, '列百分比'),
                   option_id=option, matrix_row=matrix_row, direction=direction, category=category, cells=cells)
        row['id'] = f"q{q}:r{matrix_row or 0}:{category or kind}:{option if option is not None else ''}"
        add_significance(row, groups, alpha, min_test_n)
        rows.append(row)

    for q, meta in sorted(questions.items()):
        qtype, subtype = integer(meta.get('q_type')), integer(meta.get('q_subtype'))
        options = [(int(o['item_index']), clean(o.get('item_title'))) for o in meta.get('items', [])]
        allowed = {k for k, _ in options}
        scale = None if q == nps_q else scale_for(meta, config)
        question_meta.append(dict(q_index=q, title=clean(meta['q_title']), q_type=qtype, q_subtype=subtype, item_count=len(options),
                     row_count=len(meta.get('item_rows', [])), is_rating=scale is not None, is_nps=q==nps_q,
                     ordered=bool(scale or q==nps_q or qtype==7 or q in config.get('ordered_questions', [])),
                     score_map=scale['scores'] if scale else None, direction=scale['direction'] if scale else 'neutral'))
        if q == nps_q:
            values = [source_value(r, {'question':q, 'source':'item_value'}) for r in records]
            values = [v if v is not None and v.is_integer() and 0<=v<=10 else None for v in values]
            append(q, '', 'total', 'none', values)
            append(q, '', 'nps', 'welch', [None if v is None else (1 if v>=9 else -1 if v<=6 else 0) for v in values], direction='higher')
            for index, (label, lo, hi) in enumerate([('批评者（0–6分）',0,6), ('中立者（7–8分）',7,8), ('推荐者（9–10分）',9,10)]):
                append(q, label, 'percent', 'proportion', [None if v is None else int(lo<=v<=hi) for v in values], option=index, category='nps_band')
        elif qtype == 5:
            values = [1 if primary(r,q).get('answered') or clean(primary(r,q).get('answer_text')) not in ('','(空)') else None for r in records]
            append(q, '', 'total', 'none', values)
        elif subtype == 402:
            values = []
            for record in records:
                ranks, used_positions = {}, set()
                for a in record.get('answer_items', {}).values():
                    if integer(a.get('q_index')) != q:
                        continue
                    position = integer(a.get('q_column'))
                    raw = a.get('item_index') or []
                    option = integer(raw[0]) if raw else None
                    if option is None or option < 0:
                        continue
                    if option not in allowed or not position or position<1 or position in used_positions or option in ranks:
                        raise ValueError(f'Q{q}: invalid or duplicate ranking slot')
                    ranks[option] = position
                    used_positions.add(position)
                values.append(ranks or None)
            append(q, '', 'total', 'none', values)
            for option, label in options:
                append(q, label, 'percent', 'proportion', [None if v is None else int(option in v) for v in values], option=option, metric='入选率')
                append(q, label, 'rank_mean', 'welch', [v.get(option) if v else None for v in values], option=option, direction='lower')
        elif qtype in (3, 4, 7):
            matrix = [(int(o['item_index']), clean(o.get('item_title'))) for o in meta.get('item_rows', [])] if qtype==7 else [(None,'')]
            if not matrix:
                raise ValueError(f'Q{q}: matrix row definitions missing')
            samples = {}
            for ri, _ in matrix:
                samples[ri] = [selections(r,q,allowed,ri) for r in records]
                if qtype in (3,7):
                    samples[ri] = [v if v is not None and len(v)==1 else None for v in samples[ri]]
            values = [1 if any(samples[ri][i] is not None for ri,_ in matrix) else None for i in range(len(records))]
            append(q, '', 'total', 'none', values)
            for ri, label in matrix:
                selected = samples[ri]
                prefix = f'{label}｜' if ri is not None else ''
                if ri is not None:
                    append(q, f'{label}｜有效基数', 'base', 'none', selected, matrix_row=ri)
                if scale:
                    scored = [scale['scores'].get(next(iter(v))) if v else None for v in selected]
                    if any(v is not None and score is None for v,score in zip(selected,scored)):
                        append(q, prefix+'有效评分基数', 'base', 'none', scored, matrix_row=ri, category='score_base')
                    append(q, f'{prefix}Mean' if ri is not None else '', 'mean', 'welch', scored, matrix_row=ri, direction=scale['direction'])
                for option, option_label in options:
                    append(q, prefix+option_label, 'matrix_percent' if ri is not None else 'percent', 'proportion',
                           [None if v is None else int(option in v) for v in selected], option=option, matrix_row=ri)
                    rows[-1]['score'] = scale['scores'].get(option) if scale else None
        else:
            raise ValueError(f'Q{q}: unsupported type {qtype}/{subtype}; define an adapter before analysis')
        bases[str(q)] = next(r['cells'][0]['value'] for r in rows if r['q_index']==q and r['kind']=='total')
    quality = dict(survey_title=survey.get('title'), vid=survey.get('vid'), answer_total=survey.get('answer_total'),
                   answer_valid=len(records), records_loaded=len(records), duplicate_respondent_ids=0,
                   question_count=len(questions), output_row_count=len(rows), output_column_count=len(groups),
                   question_bases=bases, nps_encoding='item_value 原生整数 0–10' if nps_q else '不适用',
                   group_scope='；'.join(dict.fromkeys(g['family'] for g in groups[1:])), source_receipt=receipt, overlaps=overlaps,
                   cleaning=receipt.get('cleaning'), low_base_warning=low_n)
    if labels is not None and labels_meta.get('linkage', True):
        matched = sum(bool(r.get('matched',True)) for r in labels)
        quality['linkage'] = dict(matched=matched, target_total=len(records), coverage=matched/len(records) if records else 0)
    metadata = dict(config, title=survey.get('title'), vid=survey.get('vid'), alpha=alpha, nps_question=nps_q,
                    engine_version=VERSION, schema_version=2, overlap_warning=bool(overlaps), low_base_warning=low_n)
    return dict(metadata=metadata, groups=[{k:v for k,v in g.items() if k!='members'} for g in groups], questions=question_meta, rows=rows, quality=quality)


def main(source_dir, output_path, labels_path=None, config_path=None):
    source = Path(source_dir)
    read = lambda p: json.loads(Path(p).read_text())
    result = analyze(read(source/'survey.json'), read(source/'responses.deidentified.json'),
                     read(config_path) if config_path and str(config_path)!='-' else {},
                     read(labels_path) if labels_path and str(labels_path)!='-' else {},
                     read(source/'fetch-receipt.json') if (source/'fetch-receipt.json').exists() else {})
    Path(output_path).write_text(json.dumps(result, ensure_ascii=False, allow_nan=False))
    print(json.dumps(result['quality'], ensure_ascii=False))


if __name__ == '__main__':
    main(*sys.argv[1:])
