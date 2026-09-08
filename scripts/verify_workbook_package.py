"""Read-only native workbook verification against canonical data and layout."""
import json
import math
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from add_internal_index_links import NS_MAIN,sheet_target


def verify(workbook,analysis=None):
    checks=[]
    def check(name,ok):checks.append(dict(name=name,passed=bool(ok)))
    with zipfile.ZipFile(workbook) as z:files={n:z.read(n) for n in z.namelist()}
    required=['指标概览','Index','体验问卷大表','体验问卷显著性检验','说明','变量映射','数据质量']
    roots={name:ET.fromstring(files[sheet_target(files,name)]) for name in required}
    shared=[]
    if 'xl/sharedStrings.xml' in files:
        shared=[''.join(si.itertext()) for si in ET.fromstring(files['xl/sharedStrings.xml'])]
    def value(cell):
        if cell is None:return None
        v=cell.find(f'{{{NS_MAIN}}}v')
        if cell.get('t')=='s':return shared[int(v.text)]
        if cell.get('t')=='inlineStr':return ''.join(cell.find(f'{{{NS_MAIN}}}is').itertext())
        if v is None or v.text is None:return None
        if cell.get('t') in ('str','e'):return v.text
        try:return float(v.text)
        except ValueError:return v.text
    cells={name:{c.get('r'):c for c in root.findall(f'.//{{{NS_MAIN}}}c')} for name,root in roots.items()}
    check('七个页签完整',len(roots)==7)
    check('无公式错误',not any(c.get('t')=='e' for cs in cells.values() for c in cs.values()))
    layout=json.loads(Path(str(workbook)+'.layout.json').read_text())
    for name in ('体验问卷大表','体验问卷显著性检验'):
        pane=roots[name].find(f'.//{{{NS_MAIN}}}pane')
        check(name+'冻结题目/Total及分群导航',pane is not None and pane.get('xSplit')=='2' and pane.get('ySplit')=='4')
        back={e.get('ref'):e.get('location') for e in roots[name].findall(f'.//{{{NS_MAIN}}}hyperlink')}
        check(name+'返回目录链接',all(back.get('B'+str(e['return_row']))==f"'Index'!A{i+2}" for i,e in enumerate(layout['sheets'][name]['entries'])))
    index_links={e.get('ref'):e.get('location') for e in roots['Index'].findall(f'.//{{{NS_MAIN}}}hyperlink')}
    for name,column in [('体验问卷大表','A'),('体验问卷显著性检验','B')]:
        check(name+'目录到实际题目行',all(index_links.get(f'{column}{i+2}')==f"'{name}'!A{e['title_row']}" and str(value(cells[name].get(f"A{e['title_row']}"))).startswith(f"[Q{e['q_index']}].") for i,e in enumerate(layout['sheets'][name]['entries'])))
    if analysis:
        data=json.loads(Path(analysis).read_text())
        consistent=True
        for row in data['rows']:
            if row['kind']=='total':continue
            for i,g in enumerate(data['groups']):
                address=layout['cells'].get(row['id']+'/'+g['id'])
                expected=row['cells'][i]['value']
                for name in ('体验问卷大表','体验问卷显著性检验'):
                    actual=value(cells[name].get(address))
                    consistent &= actual=='—' if expected is None else isinstance(actual,(float,int)) and abs(actual-expected)<1e-8
        check('两张数表全部数据格与统计结果一致',consistent)
    chart_paths=sorted([n for n in files if re.fullmatch(r'xl/(?:drawings/)?charts/chart\d+\.xml',n)],key=lambda n:int(re.search(r'(\d+)\.xml',n).group(1)))
    check('原生可编辑图表数量正确',len(chart_paths)==len(layout['charts']))
    ns={'c':'http://schemas.openxmlformats.org/drawingml/2006/chart','a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
    for chart_path,rule in zip(chart_paths,layout['charts']):
        root=ET.fromstring(files[chart_path]);bar=root.find('.//c:barDir',ns)
        check(rule['title']+'为横向条形图',bar is not None and bar.get('val')=='bar')
        lo=root.find('.//c:valAx/c:scaling/c:min',ns);hi=root.find('.//c:valAx/c:scaling/c:max',ns)
        check(rule['title']+'坐标范围正确',lo is not None and hi is not None and float(lo.get('val'))==(-100 if rule.get('nps') else 0) and float(hi.get('val'))==(100 if rule.get('nps') else 1))
        series=root.findall('.//c:barChart/c:ser',ns)
        if rule.get('nps'):
            check('NPS负值保留填充色',all(s.find('c:invertIfNegative',ns) is not None and s.find('c:invertIfNegative',ns).get('val')=='0' for s in series))
            labels=root.find('.//c:barChart/c:dLbls',ns)
            check('NPS数据标签仅显示分值',labels is not None and all(labels.find('c:'+name,ns) is not None and labels.find('c:'+name,ns).get('val')==expected for name,expected in [('showVal','1'),('showCatName','0'),('showSerName','0'),('showLegendKey','0')]))
        check(rule['title']+'绑定工作表单元格',all(s.find('.//c:numRef/c:f',ns) is not None for s in series))
        colors=[s.find('.//a:solidFill/a:srgbClr',ns) for s in series]
        check(rule['title']+'导出颜色正确',len(colors)==len(rule['colors']) and all(c is not None and c.get('val').upper()==expected.lstrip('#').upper() for c,expected in zip(colors,rule['colors'])))
    check('概览分组选择器已逐项验证',layout['overview'].get('selector_verified'))
    return dict(passed=all(c['passed'] for c in checks),checks=checks,failed=[c for c in checks if not c['passed']])


if __name__=='__main__':
    result=verify(*sys.argv[1:]);print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['passed'] else 1)
