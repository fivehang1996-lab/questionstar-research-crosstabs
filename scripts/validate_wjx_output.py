#!/usr/bin/env python3
"""Independent numeric, statistical and structural validation; errors fail closed."""
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from analyze_wjx_crosstabs import proportion_p, welch_p


def validate(data, expected=None):
    expected = expected or {}
    quality,rows,groups = data['quality'],data['rows'],data['groups']
    checks = []
    def check(name, result, detail=''):
        checks.append(dict(name=name,passed=bool(result),detail=detail))
    near = lambda a,b: a is None and b is None or isinstance(a,(float,int)) and isinstance(b,(float,int)) and math.isfinite(a) and math.isfinite(b) and abs(a-b)<1e-8
    check('总体列唯一且在首列',len([g for g in groups if g['family']=='总体'])==1 and groups[0]['family']=='总体')
    check('题目和统计行存在',bool(rows) and bool(data['questions']))
    check('记录ID唯一',quality.get('duplicate_respondent_ids')==0)
    check('输出规模一致',quality['output_row_count']==len(rows) and quality['output_column_count']==len(groups))
    check('统计行宽一致',all(len(r['cells'])==len(groups) for r in rows))
    if not checks[-1]['passed']:
        return dict(passed=False,checks=checks,failed=[c for c in checks if not c['passed']])
    check('统计行ID唯一',len({r['id'] for r in rows})==len(rows))
    check('组ID唯一',len({g['id'] for g in groups})==len(groups))
    check('定义性分组标记与来源题一致',all(bool(c.get('definition_based'))==(r['q_index'] in g.get('source_questions',[]))
          for r in rows for c,g in zip(r['cells'],groups)))
    check('总体样本与载入样本一致',groups[0]['base_n']==quality['records_loaded']==quality['answer_valid'])
    cleaning = quality.get('cleaning')
    receipt = quality.get('source_receipt',{})
    if cleaning:
        check('清洗人数守恒',cleaning['input_n']==cleaning['retained_n']+cleaning['excluded_n'] and cleaning['retained_n']==quality['answer_valid'])
    if receipt.get('api_valid_records') is not None:
        check('拉取回执与分析输入对账',receipt['api_valid_records']==(cleaning['input_n'] if cleaning else quality['records_loaded']))
    if receipt.get('expected_records') is not None:
        check('接口应收实收一致',receipt['expected_records']==receipt['api_valid_records'])
    numeric_ok, sig_ok, details = True, True, []
    alpha,min_test = data['metadata'].get('alpha',.1),data['metadata'].get('minimum_test_base',0)
    for row in rows:
        for i,cell in enumerate(row['cells']):
            value,n = cell['value'],cell['base_n']
            okay = isinstance(n,int) and 0<=n<=groups[i]['base_n']
            if row['kind'] in ('total','base'):
                okay &= value==n
            elif row['test']=='proportion':
                x,d = cell['numerator'],cell['denominator']
                okay &= isinstance(x,int) and isinstance(d,int) and 0<=x<=d and d==n and near(value,x/d if d else None)
            elif row['test']=='welch':
                raw = cell['raw']
                okay &= len(raw)==n and all(isinstance(v,(int,float)) and math.isfinite(v) for v in raw)
                okay &= near(value,sum(raw)/n*(100 if row['kind']=='nps' else 1) if n else None)
                if row['kind']=='nps':
                    okay &= all(v in (-1,0,1) for v in raw)
            if not okay:
                details.append(f"{row['id']}/{groups[i]['id']}")
            numeric_ok &= okay
            high, comparisons, lows = [], [], []
            if row['test']!='none' and groups[i]['family']!='总体' and value is not None:
                for j,g in enumerate(groups):
                    other=row['cells'][j]
                    if i==j or g['family']!=groups[i]['family'] or other['value'] is None or min(n,other['base_n'])<min_test:
                        continue
                    p=proportion_p(cell['numerator'],cell['denominator'],other['numerator'],other['denominator']) if row['test']=='proportion' else welch_p(cell['raw'],other['raw'])
                    if p is None:
                        continue
                    comparisons.append((g['id'],p))
                    if p<alpha and value>other['value']:
                        high.append(g['letter'])
                    lows.append(p<alpha and value<other['value'])
            sig_ok &= set(high)==set(cell.get('sig_high',[])) and bool(lows and all(lows))==bool(cell.get('sig_low_all'))
            saved={c['group_id']:c['p'] for c in cell.get('comparisons',[])}
            sig_ok &= len(saved)==len(comparisons) and all(near(saved.get(k),p) for k,p in comparisons)
    check('人数、分母、比例、均值和NPS逐格复核',numeric_ok,details[:20])
    check('独立重算显著性及比较p值',sig_ok)
    mapping={r['id']:r for r in rows}
    distributions=defaultdict(list)
    box_ok=True
    for row in rows:
        if row.get('category') in ('t2b','b2b'):
            sources=[mapping.get(k) for k in row['source_row_ids']]
            box_ok &= bool(sources) and all(s is not None and s['q_index']==row['q_index'] and s.get('matrix_row')==row.get('matrix_row') for s in sources)
            if all(s is not None for s in sources):
                box_ok &= all(c['numerator']==sum(s['cells'][i]['numerator'] for s in sources) for i,c in enumerate(row['cells']))
        elif row['kind'] in ('percent','matrix_percent'):
            distributions[(row['q_index'],row.get('matrix_row'))].append(row)
    check('T2B/B2B与原始选项人数一致',box_ok)
    dist_ok,means_ok=True,True
    qmap={q['q_index']:q for q in data['questions']}
    for (q,ri),options in distributions.items():
        meta=qmap[q]
        if meta['q_type']==4 and not meta.get('is_nps'):
            continue
        for i in range(len(groups)):
            n=options[0]['cells'][i]['denominator']
            dist_ok &= all(r['cells'][i]['denominator']==n for r in options) and sum(r['cells'][i]['numerator'] for r in options)==n
            if meta.get('is_rating'):
                mean=next(r for r in rows if r['q_index']==q and r.get('matrix_row')==ri and r['kind']=='mean')['cells'][i]
                scoring=[r for r in options if r.get('score') is not None]
                sn=sum(r['cells'][i]['numerator'] for r in scoring)
                weighted=sum(r['score']*r['cells'][i]['numerator'] for r in scoring)
                means_ok &= mean['base_n']==sn and near(mean['value'],weighted/sn if sn else None)
    check('单选、矩阵和NPS分布人数守恒',dist_ok)
    check('评分均值与选项计分加权结果一致',means_ok)
    for q in data['questions']:
        base=next((r for r in rows if r['q_index']==q['q_index'] and r['kind']=='total'),None)
        check(f"Q{q['q_index']}题目基数对账",base is not None and base['cells'][0]['value']==quality['question_bases'].get(str(q['q_index'])))
    if 'answer_valid' in expected:
        check('预期有效样本',quality['answer_valid']==expected['answer_valid'])
    for q,n in expected.get('question_bases',{}).items():
        check(f'Q{q}预期基数',quality['question_bases'].get(str(q))==n)
    for spec in expected.get('cells',[]):
        row=next((r for r in rows if r['q_index']==int(spec['question']) and r['item']==spec.get('item','') and r['kind']==spec['kind']),None)
        value=row['cells'][spec.get('group_index',0)]['value'] if row else None
        check(spec.get('name','预期单元格'),value is not None and abs(value-spec['value'])<=spec.get('tolerance',1e-9),[value,spec['value']])
    failed=[c for c in checks if not c['passed']]
    return dict(passed=not failed,checks=checks,failed=failed)


def main(source, expectations=None):
    result=validate(json.loads(Path(source).read_text()),json.loads(Path(expectations).read_text()) if expectations else {})
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 1)


if __name__=='__main__':
    main(*sys.argv[1:])
