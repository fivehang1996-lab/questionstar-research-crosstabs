#!/usr/bin/env python3
"""Explicit display-only sorting; questionnaire metadata takes precedence."""
import json
import re
import sys
from pathlib import Path

ORDERED = re.compile(r'评分|满意|评价|意愿|难度|推荐|频率|年龄|时长|消费|程度|多大')
STRUCTURAL = re.compile(r'^(其他|其它|以上都没有|以上均无|不适用|不知道|不愿透露|未体验|无$|没有$)')


def apply(data):
    output, sorted_q, kept = [], [], []
    total = next(i for i,g in enumerate(data['groups']) if g['family']=='总体')
    for meta in data['questions']:
        q = meta['q_index']
        rows = [r for r in data['rows'] if r['q_index']==q]
        mode = data['metadata'].get('sort_overrides',{}).get(str(q))
        ordered = meta.get('ordered') or meta.get('is_nps') or any(r['kind'] in ('mean','nps','matrix_percent','rank_mean') for r in rows)
        if mode is None and meta.get('q_type')==3 and ORDERED.search(meta.get('title','')):
            ordered = True
        if mode=='source':
            ordered = True
        candidates = [r for r in rows if r['kind']=='percent' and r.get('category') not in ('t2b','b2b')]
        if candidates and not ordered and meta.get('q_type') in (3,4):
            def key(row):
                value = row['cells'][total]['value']
                structural = bool(STRUCTURAL.search(row['item'])) and mode!='total_all'
                return structural, value is None, -(value if value is not None else 0)
            sorted_rows = iter(sorted(candidates,key=key))
            candidate_ids = {id(r) for r in candidates}
            rows = [next(sorted_rows) if id(r) in candidate_ids else r for r in rows]
            sorted_q.append(q)
        else:
            kept.append(q)
        output.extend(rows)
    data['rows'] = output
    data['metadata']['sort_mode'] = 'explicit_total_descending'
    data['quality']['sorting'] = dict(enabled=True,field='Total原始比例',sorted_questions=sorted_q,ordered_questions=kept,
                                     tie_break='并列保留原序',structural_options_last=True)
    return data


def main(source, output):
    data = apply(json.loads(Path(source).read_text()))
    Path(output).write_text(json.dumps(data,ensure_ascii=False))
    print(json.dumps(data['quality']['sorting'],ensure_ascii=False))


if __name__=='__main__':
    main(*sys.argv[1:])
