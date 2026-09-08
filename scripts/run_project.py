#!/usr/bin/env python3
"""One entry point from versioned JSON source to verified research workbook."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from research_core import VERSION
from prepare_dataset import prepare
from apply_derived_segments import main as derive
from analyze_wjx_dynamic import analyze
from add_box_metrics import apply as boxes
from sort_wjx_analysis import apply as sort_rows
from validate_wjx_output import validate


ROOT = Path(__file__).resolve().parents[1]


def run(args):
    read=lambda p: json.loads(Path(p).read_text())
    config=read(args.config)
    source=Path(args.source)
    out=Path(args.output_dir)
    out.mkdir(parents=True,exist_ok=True)
    if any(out.iterdir()):
        raise ValueError('Output directory must be empty; use a new version directory')
    def save(name, value):
        (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False))
    records=read(source/'responses.deidentified.json')
    receipt=read(source/'fetch-receipt.json') if (source/'fetch-receipt.json').exists() else {}
    if receipt.get('api_valid_records') is not None and len(records)!=receipt['api_valid_records']:
        raise ValueError('Source record count differs from fetch receipt')
    profile=read(args.profile_source) if args.profile_source else None
    labels=read(args.labels) if args.labels else None
    records,labels,audit=prepare(records,config,labels,profile)
    save('cleaning-receipt.json',audit)
    save('responses.cleaned.json',records)
    save('labels.prepared.json',labels)
    derive(str(out/'responses.cleaned.json'),str(out/'labels.prepared.json'),str(args.config),str(out/'labels.json'))
    receipt['cleaning']=audit
    data=analyze(read(source/'survey.json'),records,config,read(out/'labels.json'),receipt)
    order=['总体']+[f for f in config.get('family_order',[]) if f!='总体']
    positions=sorted(range(len(data['groups'])),key=lambda i:order.index(data['groups'][i]['family']) if data['groups'][i]['family'] in order else len(order))
    data['groups']=[data['groups'][i] for i in positions]
    for row in data['rows']:
        row['cells']=[row['cells'][i] for i in positions]
    data=boxes(data,config)
    if args.sorted:
        data=sort_rows(data)
    data['metadata']['run_version']=out.name
    save('analysis.json',data)
    save('project-config.json',config)
    expectations=read(args.expectations) if args.expectations else {}
    validation=validate(data,expectations)
    save('validation-receipt.json',validation)
    if not validation['passed']:
        raise ValueError('Analysis validation failed: '+str([c['name'] for c in validation['failed']]))
    inputs={'questionnaire':source/'survey.json','responses':source/'responses.deidentified.json','config':Path(args.config)}
    for role,filename in [('profile',args.profile_source),('labels',args.labels),('expectations',args.expectations)]:
        if filename:inputs[role]=Path(filename)
    if (source/'fetch-receipt.json').exists():inputs['source_receipt']=source/'fetch-receipt.json'
    hashes={role:hashlib.sha256(p.read_bytes()).hexdigest() for role,p in inputs.items()}
    code_hash=hashlib.sha256(b''.join(p.read_bytes() for p in sorted((ROOT/'scripts').glob('*')) if p.is_file())).hexdigest()
    manifest=dict(engine_version=VERSION,created_at=datetime.now(timezone.utc).isoformat(),source_hashes=hashes,code_sha256=code_hash,
                  input_n=audit['input_n'],retained_n=audit['retained_n'],sort_enabled=args.sorted,analysis_validated=True,workbook_validated=False)
    save('run-manifest.json',manifest)
    if not args.analysis_only:
        env=dict(os.environ,WJX_PYTHON_PATH=sys.executable)
        workbook=out/'research-crosstabs.xlsx'
        for script,arguments,receipt_name in [
            ('build_wjx_crosstab_workbook.mjs',[out/'analysis.json',workbook,out/'previews'],'build-receipt.json'),
            ('verify_wjx_workbook.mjs',[workbook,'--compact',out/'analysis.json'],'workbook-verification.json')]:
            result=subprocess.run([args.node,str(ROOT/'scripts'/script),*map(str,arguments)],env=env,text=True,capture_output=True)
            if result.returncode:
                raise RuntimeError(f'{script} failed: {result.stderr[-2000:]}')
            # Artifact Tool may emit one-line export notices before the receipt.
            text=result.stdout
            start=text.find('{')
            save(receipt_name,json.loads(text[start:]))
        manifest.update(workbook_validated=True,workbook_sha256=hashlib.sha256(workbook.read_bytes()).hexdigest())
        save('run-manifest.json',manifest)
    print(json.dumps(dict(output_dir=str(out),checks=len(validation['checks']),workbook=not args.analysis_only),ensure_ascii=False))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',required=True)
    parser.add_argument('--config',required=True)
    parser.add_argument('--labels')
    parser.add_argument('--profile-source',help='Deidentified profile response JSON; linkage.key must be stable in both files')
    parser.add_argument('--output-dir',default=str(ROOT/'outputs'/datetime.now().strftime('%Y%m%d-%H%M%S')))
    parser.add_argument('--expectations')
    parser.add_argument('--sorted',action='store_true',help='Display-only Total sorting; default is source order')
    parser.add_argument('--analysis-only',action='store_true')
    parser.add_argument('--node',default=os.environ.get('WJX_NODE_PATH','node'))
    run(parser.parse_args())
