"""Finalize native links, panes and chart axes after Artifact Tool export."""
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET
from add_internal_index_links import NS_MAIN, sheet_target

C='http://schemas.openxmlformats.org/drawingml/2006/chart'


def patch(files, layout):
    def links(sheet, entries):
        target=sheet_target(files,sheet)
        root=ET.fromstring(files[target])
        old=root.find(f'{{{NS_MAIN}}}hyperlinks')
        if old is not None:
            root.remove(old)
        element=ET.Element(f'{{{NS_MAIN}}}hyperlinks')
        for address,location in entries:
            ET.SubElement(element,f'{{{NS_MAIN}}}hyperlink',dict(ref=address,location=location))
        # OOXML ordering: hyperlinks precede printing and drawing nodes.
        after={'sheetPr','dimension','sheetViews','sheetFormatPr','cols','sheetData','sheetCalcPr','sheetProtection','protectedRanges','scenarios','autoFilter','sortState','dataConsolidate','customSheetViews','mergeCells','phoneticPr','conditionalFormatting','dataValidations'}
        position=0
        for i,child in enumerate(root):
            if child.tag.split('}')[-1] in after:
                position=i+1
        root.insert(position,element)
        if sheet in layout['sheets']:
            view=root.find(f'.//{{{NS_MAIN}}}sheetView')
            pane=view.find(f'{{{NS_MAIN}}}pane')
            if pane is None:
                pane=ET.Element(f'{{{NS_MAIN}}}pane');view.insert(0,pane)
            pane.attrib=dict(xSplit='2',ySplit='4',topLeftCell='C5',activePane='bottomRight',state='frozen')
            for selection in view.findall(f'{{{NS_MAIN}}}selection'):
                selection.set('pane','bottomRight')
        files[target]=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    entries=layout['sheets']['体验问卷大表']['entries']
    index_links=[]
    for sheet,column in [('体验问卷大表','A'),('体验问卷显著性检验','B')]:
        targets=layout['sheets'][sheet]['entries']
        index_links.extend((f'{column}{i+2}',f"'{sheet}'!A{e['title_row']}") for i,e in enumerate(targets))
        links(sheet,[(f"B{e['return_row']}",f"'Index'!A{i+2}") for i,e in enumerate(targets)])
    links('Index',index_links)
    chart_paths=sorted([p for p in files if '/charts/chart' in p and p.endswith('.xml')],key=lambda p:int(Path(p).stem.replace('chart','')))
    if len(chart_paths)!=len(layout['charts']):
        raise ValueError('Native chart count differs from build layout')
    for target,rule in zip(chart_paths,layout['charts']):
        root=ET.fromstring(files[target])
        bar=root.find(f'.//{{{C}}}barChart')
        if bar is None:
            raise ValueError('Expected native bar chart')
        direction=bar.find(f'{{{C}}}barDir')
        if direction is None:
            direction=ET.SubElement(bar,f'{{{C}}}barDir')
        direction.set('val','bar')
        grouping=bar.find(f'{{{C}}}grouping')
        if grouping is None:
            grouping=ET.SubElement(bar,f'{{{C}}}grouping')
        grouping.set('val','percentStacked' if rule.get('distribution') else 'clustered')
        if rule.get('nps'):
            for series in bar.findall(f'{{{C}}}ser'):
                inverse=series.find(f'{{{C}}}invertIfNegative')
                if inverse is None:
                    inverse=ET.Element(f'{{{C}}}invertIfNegative')
                    at=next((i+1 for i,e in enumerate(series) if e.tag==f'{{{C}}}spPr'),2)
                    series.insert(at,inverse)
                inverse.set('val','0')
            labels=bar.find(f'{{{C}}}dLbls')
            if labels is None:
                labels=ET.Element(f'{{{C}}}dLbls')
                position=max(i for i,e in enumerate(bar) if e.tag==f'{{{C}}}ser')+1
                bar.insert(position,labels)
            for child in list(labels):labels.remove(child)
            ET.SubElement(labels,f'{{{C}}}numFmt',dict(formatCode='0',sourceLinked='0'))
            ET.SubElement(labels,f'{{{C}}}dLblPos',dict(val='outEnd'))
            for name in ('showLegendKey','showVal','showCatName','showSerName','showPercent','showBubbleSize'):
                ET.SubElement(labels,f'{{{C}}}{name}',dict(val='1' if name=='showVal' else '0'))
        if rule.get('distribution'):
            overlap=bar.find(f'{{{C}}}overlap')
            if overlap is None:
                overlap=ET.SubElement(bar,f'{{{C}}}overlap')
            overlap.set('val','100')
        for axis in root.findall(f'.//{{{C}}}valAx'):
            scaling=axis.find(f'{{{C}}}scaling')
            if scaling is None:
                scaling=ET.Element(f'{{{C}}}scaling');axis.insert(1,scaling)
            for name,value in [('max',100 if rule.get('nps') else 1),('min',-100 if rule.get('nps') else 0)]:
                old=scaling.find(f'{{{C}}}{name}')
                if old is not None:scaling.remove(old)
                ET.SubElement(scaling,f'{{{C}}}{name}',{'val':str(value)})
            position=axis.find(f'{{{C}}}axPos')
            if position is not None:position.set('val','b')
            if rule.get('nps'):
                for name in ('crosses','crossesAt'):
                    old=axis.find(f'{{{C}}}{name}')
                    if old is not None:axis.remove(old)
                cross=ET.Element(f'{{{C}}}crossesAt',dict(val='-100'))
                at=next((i+1 for i,e in enumerate(axis) if e.tag==f'{{{C}}}crossAx'),len(axis))
                axis.insert(at,cross)
            unit=axis.find(f'{{{C}}}majorUnit')
            if unit is None:unit=ET.SubElement(axis,f'{{{C}}}majorUnit')
            unit.set('val','20' if rule.get('nps') else '0.2')
        for axis in root.findall(f'.//{{{C}}}catAx'):
            position=axis.find(f'{{{C}}}axPos')
            if position is not None:position.set('val','l')
            tick=axis.find(f'{{{C}}}tickLblPos')
            if tick is None:
                tick=ET.Element(f'{{{C}}}tickLblPos')
                later={'spPr','txPr','crossAx','crosses','crossesAt','auto','lblAlgn','lblOffset','tickLblSkip','tickMarkSkip','noMultiLvlLbl','extLst'}
                at=next((i for i,e in enumerate(axis) if e.tag.split('}')[-1] in later),len(axis))
                axis.insert(at,tick)
            tick.set('val','low')
        files[target]=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    return files


def main(analysis, workbook):
    target=Path(workbook)
    layout=json.loads(Path(workbook+'.layout.json').read_text())
    with zipfile.ZipFile(target) as archive:
        files=patch({name:archive.read(name) for name in archive.namelist()},layout)
    fd,name=tempfile.mkstemp(suffix='.xlsx',dir=target.parent);os.close(fd)
    try:
        with zipfile.ZipFile(name,'w',zipfile.ZIP_DEFLATED) as archive:
            for path,content in files.items():archive.writestr(path,content)
        os.replace(name,target)
    finally:
        if os.path.exists(name):os.unlink(name)


if __name__=='__main__':main(*sys.argv[1:])
