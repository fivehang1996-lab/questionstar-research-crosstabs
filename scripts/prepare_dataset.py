"""Keyed linkage, explicit cleaning and ordered business rules."""
import json
from collections import Counter
from pathlib import Path
from research_core import align_labels, keyed, selections, source_value


def rule_questions(rule):
    """Track target-survey dependencies, including nested priority rules."""
    result = {int(rule['question'])} if 'question' in rule else set()
    for operator in ('all', 'any'):
        for child in rule.get(operator, []):
            result.update(rule_questions(child))
    if 'not' in rule:
        result.update(rule_questions(rule['not']))
    return result


def matches(record, rule):
    if 'all' in rule:
        return all(matches(record,r) for r in rule['all'])
    if 'any' in rule:
        return any(matches(record,r) for r in rule['any'])
    if 'not' in rule:
        return not matches(record,rule['not'])
    if 'question' in rule:
        values = selections(record,rule['question'])
        if 'selected_any' in rule:
            return values is not None and bool(values & set(rule['selected_any']))
        if 'selected_all' in rule:
            return values is not None and set(rule['selected_all']).issubset(values)
        value = source_value(record,rule)
    elif 'field' in rule:
        value = record.get(rule['field'])
    else:
        raise ValueError('Rule requires all/any/not/question/field')
    if 'equals' in rule:
        return value == rule['equals']
    if 'values' in rule:
        return value in rule['values']
    if 'min' in rule or 'max' in rule:
        return value is not None and rule.get('min',float('-inf'))<=value<=rule.get('max',float('inf'))
    raise ValueError('Rule requires equals/values/min/max or selection condition')


def prepare(records, config, labels_meta=None, profile_records=None):
    for spec in config.get('business_segments', []):
        if spec.get('source','target') not in ('target','profile'):
            raise ValueError('Business segment source must be target/profile')
        if spec.get('source')=='profile' and profile_records is None:
            raise ValueError('Profile business segments require profile records')
    cleaning = config.get('cleaning',{})
    policy = cleaning.get('duplicates','error')
    if policy not in ('error','first','last'):
        raise ValueError('duplicates must be error/first/last')
    counts, exclusions, unique = Counter(), [], {}
    for record in records:
        key = str(record.get('respondent_id',''))
        if not key or key=='None':
            raise ValueError('respondent_id is required')
        if key in unique:
            if policy=='error':
                raise ValueError('Duplicate respondent_id')
            counts['重复答卷'] += 1
            exclusions.append(dict(respondent_id=key,reasons=['重复答卷']))
            if policy=='first':
                continue
        unique[key] = record
    unique_records = list(unique.values())
    meta = dict(labels_meta or {})
    if labels_meta is None:
        meta.update(labels=[dict(respondent_id=r['respondent_id'],matched=True) for r in unique_records],linkage=False)
    labels = align_labels(unique_records,meta)
    linkage = config.get('linkage',{})
    if linkage.get('unmatched')=='exclude' and profile_records is None and labels_meta is None:
        raise ValueError('Unmatched exclusion requires profile records or keyed labels')
    profiles = {}
    if profile_records is not None:
        field = linkage.get('key','linkage_key')
        profiles = keyed([r for r in profile_records if r.get(field) not in (None,'')],field)
        target_keys = [r.get(field) for r in unique_records if r.get(field) not in (None,'')]
        if len(target_keys)!=len(set(map(str,target_keys))):
            raise ValueError('Target linkage key is not one-to-one; define deduplication upstream')
        meta['linkage'] = True
    kept, kept_labels, matched_count = [], [], 0
    for record,label in zip(unique_records,labels):
        profile = None
        if profile_records is not None:
            profile = profiles.get(str(record.get(linkage.get('key','linkage_key'))))
            label['matched'] = profile is not None
        matched_count += bool(label.get('matched',True))
        reasons = []
        if cleaning.get('valid_field') and record.get(cleaning['valid_field']) not in cleaning.get('valid_values',[True]):
            reasons.append('原始有效标记未通过')
        if linkage.get('unmatched','keep') not in ('keep','exclude'):
            raise ValueError('linkage.unmatched must be keep/exclude')
        if linkage.get('unmatched')=='exclude' and not label.get('matched',True):
            reasons.append('未匹配画像问卷')
        if cleaning.get('min_answer_seconds') is not None:
            duration = record.get('answer_seconds')
            if duration is None or float(duration)<cleaning['min_answer_seconds']:
                reasons.append('答题时长不足或缺失')
        for q in cleaning.get('required_questions',[]):
            if selections(record,int(q)) is None:
                reasons.append(f'Q{q}未有效作答')
        for rule in cleaning.get('exclude_if',[]):
            if matches(record,rule['when']):
                reasons.append(rule['name'])
        if reasons:
            counts.update(reasons)
            exclusions.append(dict(respondent_id=record['respondent_id'],reasons=reasons))
            continue
        for spec in config.get('business_segments',[]):
            source = profile if spec.get('source','target')=='profile' else record
            field = spec.get('field',spec['family'])
            hits = [g['label'] for g in spec['groups'] if source is not None and matches(source,g['when'])]
            if spec.get('mode','exclusive')=='exclusive':
                label[field] = hits[0] if hits else spec.get('fallback','未回答')
            elif spec['mode']=='overlap':
                for group in spec['groups']:
                    label[field+'_'+group['label']] = group['label'] in hits
            else:
                raise ValueError('Business segment mode must be exclusive/overlap')
        kept.append(record)
        kept_labels.append(label)
    meta['labels'] = kept_labels
    label_groups = list(meta.get('label_groups',[]))
    for spec in config.get('business_segments',[]):
        field = spec.get('field',spec['family'])
        external = spec.get('source','target')=='profile'
        dependencies = [] if external else sorted(set().union(*(rule_questions(g['when']) for g in spec['groups'])))
        if spec.get('mode','exclusive')=='exclusive':
            options = [g['label'] for g in spec['groups']]
            if spec.get('fallback') not in (None,'未回答'):
                options.append(spec['fallback'])
            for value in options:
                label_groups.append(dict(family=spec['family'],field=field,label=value,source_questions=dependencies,requires_match=external))
        else:
            # Expand boolean memberships into metadata read by the analyzer.
            meta.setdefault('boolean_groups',[]).extend(dict(family=spec['family'],field=field+'_'+g['label'],label=g['label'],
                source_questions=[] if external else sorted(rule_questions(g['when'])),requires_match=external) for g in spec['groups'])
    meta['label_groups'] = label_groups
    audit = dict(input_n=len(records),retained_n=len(kept),excluded_n=len(records)-len(kept),
                 reasons=dict(counts),exclusions=exclusions,linkage_matched_before_cleaning=matched_count,
                 unmatched_policy=linkage.get('unmatched','keep'),rules=cleaning)
    return kept, meta, audit
