#!/usr/bin/env python3
"""Apply the explicit Total-descending display mode to an analysis JSON."""
import json, re, sys
from pathlib import Path

ORDERED = re.compile(r'评分|满意度|满意|整体评价|继续游玩意愿|上手难度|推荐|频率|年龄|时长|消费|程度|多大')
STRUCTURAL = re.compile(r'其他|以上都没有|不适用|不知道|不愿透露|未体验|无')

def main(src, dst):
    d=json.loads(Path(src).read_text())
    by={}
    for row in d['rows']:
        by.setdefault(row['q_index'], []).append(row)
    sorted_questions=[]; kept_order=[]
    for q, rs in by.items():
        title=rs[0].get('question','')
        # Matrix, NPS and ordered single-choice scales remain in source order.
        qmeta=next((x for x in d.get('questions',[]) if x.get('q_index')==q),{})
        ordered=bool(qmeta.get('q_type')==7 or q==21 or (qmeta.get('q_type')==3 and ORDERED.search(title)))
        candidates=[r for r in rs if r.get('kind') in ('percent','matrix_percent')]
        if candidates and not ordered and qmeta.get('q_type') in (3,4):
            original={id(r):i for i,r in enumerate(candidates)}
            def key(r):
                v=r.get('cells',[{}])[0].get('value')
                return (1 if STRUCTURAL.search(str(r.get('item',''))) else 0, -(v if isinstance(v,(int,float)) else -1), original[id(r)])
            ordered_rows=sorted(candidates,key=key)
            it=iter(ordered_rows)
            rs=[next(it) if r in candidates else r for r in rs]
            sorted_questions.append(q); kept_order.append({'q_index':q,'mode':'Total降序'})
        else:
            kept_order.append({'q_index':q,'mode':'问卷原顺序'})
        by[q]=rs
    d['rows']=[r for q in by for r in by[q]]
    d.setdefault('metadata',{})['sort_mode']='explicit_total_descending'
    d.setdefault('quality',{})['sorting']={'enabled':True,'field':'Total列原始比例','sorted_questions':sorted_questions,'ordered_questions':[x['q_index'] for x in kept_order if x['mode']=='问卷原顺序'],'tie_break':'并列保留问卷原顺序','structural_options_last':True}
    Path(dst).write_text(json.dumps(d,ensure_ascii=False))
    print(json.dumps(d['quality']['sorting'],ensure_ascii=False))
if __name__=='__main__': main(sys.argv[1],sys.argv[2])
