import copy
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from analyze_wjx_dynamic import analyze
from research_core import align_labels,classify,scale_for,welch_p,proportion_p
from prepare_dataset import prepare
from add_box_metrics import apply as boxes
from sort_wjx_analysis import apply as sort_rows
from validate_wjx_output import validate


def question(q,title='测试',n=5,kind=3,subtype=3,**extra):
    return dict(q_index=q,q_title=title,q_type=kind,q_subtype=subtype,
                items=[dict(item_index=i,item_title=str(i)) for i in range(1,n+1)],**extra)


def record(key,values,**extra):
    return dict(respondent_id=key,answer_items={str(q):dict(q_index=q,q_column=0,item_index=v if isinstance(v,list) else [v]) for q,v in values.items()},**extra)


def run(qs,records,config=None,labels=None):
    return analyze(dict(title='测试',answer_total=len(records),questions=qs),records,config,labels)


def cell(data,q,kind,group=0):
    return next(r for r in data['rows'] if r['q_index']==q and r['kind']==kind)['cells'][group]


class ResearchTests(unittest.TestCase):
    def test_seven_point_mean(self):
        d=run([question(1,n=7)],[record(1,{1:6}),record(2,{1:7})],{'rating_questions':[1]})
        self.assertEqual(cell(d,1,'mean')['value'],6.5)
        self.assertTrue(validate(d)['passed'])

    def test_nominal_five_options_no_mean(self):
        d=run([question(1,'角色偏好')],[record(1,{1:2})],{'auto_rating_five_point':True})
        self.assertFalse(any(r['kind']=='mean' for r in d['rows']))

    def test_reverse_scale_and_non_scoring(self):
        config={'scales':{'1':{'scores':{'1':5,'2':4,'3':3,'4':2,'5':1,'6':None}}}}
        d=boxes(run([question(1,n=6)],[record(1,{1:1}),record(2,{1:6}),record(3,{1:5})],config),config)
        self.assertEqual(cell(d,1,'mean')['value'],3)
        self.assertEqual(cell(d,1,'mean')['base_n'],2)
        top=next(r for r in d['rows'] if r.get('category')=='t2b')['cells'][0]
        self.assertEqual(top['value'],.5)
        self.assertEqual(top['denominator'],2)
        self.assertTrue(validate(d)['passed'])

    def test_multi_native_membership_and_overlap(self):
        d=run([question(1,n=3,kind=4,subtype=4)],[record(1,{1:[1,2]}),record(2,{1:[2,3]})],{'native_segments':[{'family':'经历','question':1}]})
        self.assertEqual(d['groups'][2]['base_n'],2)
        self.assertTrue(d['quality']['overlaps'])

    def test_matrix_skip_and_row_specific_base(self):
        q=question(1,n=5,kind=7,item_rows=[dict(item_index=1,item_title='战斗')])
        records=[record(1,{1:[-3]}),record(2,{1:5})]
        for r in records:r['answer_items']['1']['q_row']=1
        config={'rating_questions':[1]}
        d=boxes(run([q],records,config),config)
        self.assertEqual(cell(d,1,'base')['value'],1)
        self.assertEqual(next(r for r in d['rows'] if r['item']=='战斗｜5')['cells'][0]['value'],1)
        self.assertEqual(cell(d,1,'mean')['value'],5)
        self.assertTrue(validate(d)['passed'])

    def test_label_order_uses_keys(self):
        labels=align_labels([record(1,{}),record(2,{})],{'labels':[{'respondent_id':2,'tag':'乙'},{'respondent_id':1,'tag':'甲'}]})
        self.assertEqual([r['tag'] for r in labels],['甲','乙'])

    def test_missing_and_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):align_labels([record(1,{})],{'labels':[{'tag':'甲'}]})
        with self.assertRaises(ValueError):run([question(1)],[record(1,{1:1}),record(1,{1:2})])

    def test_unmatched_labels_keep_total(self):
        d=run([question(1)],[record(1,{1:1}),record(2,{1:2})],{},
              {'labels':[{'respondent_id':1,'tag':'甲'}],'label_groups':[{'family':'标签','field':'tag','label':'甲'}]})
        self.assertEqual(d['groups'][0]['base_n'],2)
        self.assertEqual(d['groups'][1]['base_n'],1)

    def test_unmatched_exclusion_and_audit(self):
        kept,labels,audit=prepare([record(1,{},linkage_key='a'),record(2,{},linkage_key='b')],
            {'linkage':{'unmatched':'exclude'}},profile_records=[record(9,{},linkage_key='b')])
        self.assertEqual([r['respondent_id'] for r in kept],[2])
        self.assertEqual(audit['excluded_n'],1)
        self.assertEqual(audit['reasons']['未匹配画像问卷'],1)

    def test_ambiguous_profile_link_rejected(self):
        with self.assertRaises(ValueError):prepare([record(1,{},linkage_key='a')],{},profile_records=[record(8,{},linkage_key='a'),record(9,{},linkage_key='a')])

    def test_business_priority(self):
        config={'business_segments':[{'family':'玩家','groups':[{'label':'横版','when':{'question':1,'selected_any':[1]}},{'label':'归龙潮','when':{'question':1,'selected_any':[2]}}]}]}
        _,labels,_=prepare([record(1,{1:[1,2]})],config)
        self.assertEqual(labels['labels'][0]['玩家'],'横版')

    def test_business_definition_provenance_both_modes(self):
        for mode in ('exclusive','overlap'):
            config={'business_segments':[{'family':'本题分层','mode':mode,'groups':[
                {'label':'高','when':{'all':[{'question':1,'selected_any':[4,5]}]}}]}]}
            source=[record(1,{1:5}),record(2,{1:2})]
            kept,labels,_=prepare(source,config)
            d=run([question(1)],kept,config,labels)
            self.assertEqual(d['groups'][1]['source_questions'],[1])
            self.assertTrue(cell(d,1,'percent',1)['definition_based'])
            self.assertTrue(validate(d)['passed'])
            cell(d,1,'percent',1)['definition_based']=False
            self.assertFalse(validate(d)['passed'])

    def test_explicit_short_scale_box_bands(self):
        config={'rating_questions':[1],'box_metrics':[{'question':1,'top_items':['3'],'bottom_items':['1']}]}
        d=boxes(run([question(1,n=3)],[record(1,{1:3}),record(2,{1:2})],config),config)
        self.assertEqual(next(r for r in d['rows'] if r.get('category')=='t2b')['cells'][0]['value'],.5)
        self.assertTrue(validate(d)['passed'])

    def test_default_short_scale_overlapping_boxes_rejected(self):
        config={'rating_questions':[1]}
        with self.assertRaises(ValueError):boxes(run([question(1,n=3)],[record(1,{1:3})],config),config)

    def test_cleaning_counts(self):
        kept,_,audit=prepare([record(1,{},answer_seconds=5),record(2,{},answer_seconds=100)],{'cleaning':{'min_answer_seconds':30}})
        self.assertEqual(len(kept),1)
        self.assertEqual(audit['input_n'],audit['excluded_n']+audit['retained_n'])

    def test_overlapping_derived_rules_rejected(self):
        with self.assertRaises(ValueError):classify(4,[{'label':'A','min':1,'max':4},{'label':'B','min':4,'max':5}])

    def test_tampered_proportion_rejected(self):
        d=run([question(1)],[record(1,{1:1}),record(2,{1:2})])
        cell(d,1,'percent')['value']=.123
        self.assertFalse(validate(d)['passed'])

    def test_tampered_significance_rejected(self):
        d=run([question(1)],[record(i,{1:1 if i<40 else 2}) for i in range(80)],{'native_segments':[{'question':1,'family':'分组'}]})
        row=next(r for r in d['rows'] if r['kind']=='percent')
        row['cells'][1]['sig_high']=[]
        self.assertFalse(validate(d)['passed'])

    def test_box_metrics_idempotent(self):
        config={'rating_questions':[1]}
        d=boxes(run([question(1)],[record(1,{1:4}),record(2,{1:5})],config),config)
        self.assertEqual(boxes(copy.deepcopy(d),config),d)

    def test_nps_any_question_retains_order(self):
        records=[record(i,{8:i}) for i in range(11)]
        for i,r in enumerate(records):r['answer_items']['8']['item_value']=i
        d=run([question(8,'向朋友介绍本作的可能性',n=11)],records,{'nps_question':8})
        before=[r['item'] for r in d['rows']]
        self.assertEqual([r['item'] for r in sort_rows(d)['rows']],before)
        self.assertTrue(validate(d)['passed'])

    def test_nominal_sort_and_ties(self):
        d=run([question(1)],[record(1,{1:2}),record(2,{1:3}),record(3,{1:2})])
        self.assertEqual([r['option_id'] for r in sort_rows(d)['rows'] if r['kind']=='percent'],[2,3,1,4,5])

    def test_score_order_and_boxes_not_sorted(self):
        config={'rating_questions':[1]}
        d=boxes(run([question(1)],[record(1,{1:5})],config),config)
        ids=[r['id'] for r in d['rows']]
        self.assertEqual([r['id'] for r in sort_rows(d)['rows']],ids)

    def test_zero_base_preserved(self):
        d=run([question(1)],[record(1,{1:[-3]})])
        self.assertIsNone(cell(d,1,'percent')['value'])
        self.assertTrue(validate(d)['passed'])

    def test_definition_and_small_base_flags(self):
        d=run([question(1)],[record(1,{1:1})],{'native_segments':[{'family':'分组','question':1}]})
        c=cell(d,1,'percent',1)
        self.assertTrue(c['definition_based'] and c['low_base'])

    def test_ranking_duplicate_rejected(self):
        r=record(1,{1:1});r['answer_items']['1']['q_column']=1
        r['answer_items']['b']=dict(q_index=1,q_column=2,item_index=[1])
        with self.assertRaises(ValueError):run([question(1,kind=4,subtype=402)],[r])

    def test_open_text_any_question(self):
        r=record(1,{10:[]});r['answer_items']['10']['answered']=True
        d=run([question(10,kind=5)], [r])
        self.assertEqual(cell(d,10,'total')['value'],1)

    def test_significance_reference_cases(self):
        self.assertAlmostEqual(proportion_p(60,100,40,100),.004677734981047266,places=10)
        self.assertAlmostEqual(welch_p([1,2,3],[1,2,3]),1)
        self.assertEqual(welch_p([1,1],[2,2]),0)


if __name__=='__main__':unittest.main()
