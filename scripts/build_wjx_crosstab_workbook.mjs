import fs from 'node:fs/promises';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const [analysisPath, outputPath, previewDir] = process.argv.slice(2);
if (!previewDir) throw new Error('Usage: build_wjx_crosstab_workbook.mjs <analysis.json> <output.xlsx> <previews>');
const data = JSON.parse(await fs.readFile(analysisPath,'utf8'));
const {groups,rows,quality,metadata} = data;
const wb = Workbook.create();
const overview = wb.worksheets.add('指标概览');
const index = wb.worksheets.add('Index');
const table = wb.worksheets.add('体验问卷大表');
const sig = wb.worksheets.add('体验问卷显著性检验');
const info = wb.worksheets.add('说明');
const mapping = wb.worksheets.add('变量映射');
const qa = wb.worksheets.add('数据质量');
const font='Calibri', navy='#24415B', blue='#0070C0', line='#B8C3CD', cyan='#E1F0F4', purple='#7030A0';
const col = n => {let s=''; for(;n;n=Math.floor((n-1)/26))s=String.fromCharCode(65+(n-1)%26)+s; return s;};
const lastCol=col(groups.length+1);
const familyList=[...new Set(groups.map(g=>g.family))];
const familyFill = family => family==='总体'?'#F0F2F4':/分层|满意|意愿|上手/.test(family)?'#E6E1F0':/性别|年龄|人口|消费|时长/.test(family)?'#E6EEDC':/经验|经历|玩家/.test(family)?'#FCE4D6':'#E0EBF2';
const qmeta=q=>data.questions.find(x=>x.q_index===q);
const typeLabel=q=>q.is_nps?'NPS':q.q_type===7?(q.is_rating?'矩阵评分':'矩阵'):q.q_subtype===402?'排序':q.is_rating?'评分':q.q_type===4?'多选':q.q_type===5?'开放题':'单选';
const lowN=metadata.low_base_warning ?? 30;
const legend=`青色/紫色字母：显著高于同族其他列（不代表表现更好）；黄色：低于同族全部可比列。双侧 p < ${metadata.alpha}。† n < ${lowN}；‡ 定义性分组；— 无有效样本。`;
const layout={schema_version:2,sheets:{},cells:{},charts:[],previewRanges:[]};
function style(sheet,range,extra={}){sheet.getRange(range).format={font:{name:font,size:10,color:'#263645'},verticalAlignment:'center',...extra};}
function title(sheet,text,end='K'){
  sheet.mergeCells(`A1:${end}1`);sheet.getRange('A1').values=[[text]];
  style(sheet,`A1:${end}1`,{font:{name:font,size:15,bold:true,color:navy},rowHeight:30});
  sheet.showGridLines=false;
}
function band(sheet,row,question=null){
  sheet.getRange(`A${row}:A${row+1}`).values=[['分组族'],['选项 / 指标']];
  style(sheet,`A${row}:${lastCol}${row+1}`,{horizontalAlignment:'center',wrapText:true,borders:{preset:'all',style:'thin',color:line}});
  for(let start=0;start<groups.length;){
    let end=start;while(end+1<groups.length&&groups[end+1].family===groups[start].family)end++;
    const c1=col(start+2),c2=col(end+2),family=groups[start].family;
    if(c1!==c2)sheet.mergeCells(`${c1}${row}:${c2}${row}`);
    sheet.getRange(`${c1}${row}`).values=[[family==='总体'?'总体':family]];
    sheet.getRange(`${c1}${row}:${c2}${row+1}`).format.fill=familyFill(family);
    start=end+1;
  }
  sheet.getRange(`B${row+1}:${lastCol}${row+1}`).values=[groups.map(g=>(g.family==='总体'?'Total':g.label+(sheet===sig&&g.letter?` (${g.letter})`:''))+(question!=null&&g.source_questions?.includes(question)?' ‡':''))];
  sheet.getRange(`${row}:${row}`).format.rowHeight=22;
  sheet.getRange(`${row+1}:${row+1}`).format.rowHeight=44;
}
function numberFormat(row,cell,significance){
  let fmt=['percent','matrix_percent'].includes(row.kind)?'0.0%':['mean','rank_mean'].includes(row.kind)?'0.0':row.kind==='nps'?'0':'#,##0';
  const suffix=(significance&&cell.sig_high?.length?' '+cell.sig_high.join('、'):'')+(cell.low_base?' †':'')+(cell.definition_based&&significance?' ‡':'');
  return suffix?`${fmt}"${suffix}"`:fmt;
}
function buildMain(sheet,significance){
  const titleEnd=col(Math.min(groups.length+1,10));
  title(sheet,`${metadata.title} ${significance?'显著性检验':'频率表'}`,titleEnd);
  sheet.mergeCells(`A2:${titleEnd}2`);sheet.getRange('A2').values=[[legend]];
  style(sheet,`A2:${titleEnd}2`,{wrapText:true,font:{name:font,size:9,color:'#52616D'},rowHeight:30});
  band(sheet,3);
  let cursor=6;
  const entries=[];
  for(const q of data.questions){
    const block=rows.filter(r=>r.q_index===q.q_index), base=block.find(r=>r.kind==='total');
    const indicator=metadata.indicator_labels?.[String(q.q_index)]||typeLabel(q);
    sheet.getRange(`A${cursor}`).values=[[indicator]];sheet.getRange(`B${cursor}`).values=[['返回目录']];
    style(sheet,`A${cursor}:${lastCol}${cursor}`,{fill:'#F7F9FB',font:{name:font,size:10,bold:true,color:navy},rowHeight:24});
    sheet.getRange(`B${cursor}`).format.font={name:font,size:9,color:blue,underline:true};
    band(sheet,cursor+1,q.q_index);
    sheet.getRange(`A${cursor+3}:${lastCol}${cursor+3}`).values=[['基数（n）：有效回答该题',...base.cells.map(c=>c.value)]];
    style(sheet,`A${cursor+3}:${lastCol}${cursor+3}`,{horizontalAlignment:'center',borders:{preset:'all',style:'thin',color:line}});
    for(let j=0;j<groups.length;j++)sheet.getRange(`${col(j+2)}${cursor+3}`).setNumberFormat(numberFormat(base,base.cells[j],false));
    const questionRow=cursor+4;
    sheet.mergeCells(`A${questionRow}:${titleEnd}${questionRow}`);
    sheet.getRange(`A${questionRow}`).values=[[`[Q${q.q_index}].${q.title}`]];
    style(sheet,`A${questionRow}:${lastCol}${questionRow}`,{font:{name:font,size:10,bold:true,color:blue},wrapText:true,rowHeight:26});
    entries.push({q_index:q.q_index,title_row:questionRow,return_row:cursor});
    let r=questionRow+1;
    for(const row of block.filter(x=>x.kind!=='total')){
      const direction=row.direction==='higher'?' ↑':row.direction==='lower'?' ↓':'';
      let label=row.item||(row.kind==='mean'?'Mean':row.kind==='nps'?'NPS':row.metric);
      if(row.kind==='rank_mean')label+='（平均名次）';
      const key=['mean','nps','rank_mean'].includes(row.kind)||['t2b','b2b'].includes(row.category);
      sheet.getRange(`A${r}:${lastCol}${r}`).values=[[label+direction,...row.cells.map(c=>c.value===null?'—':c.value)]];
      style(sheet,`A${r}:${lastCol}${r}`,{horizontalAlignment:'center',rowHeight:22,borders:{preset:'all',style:'thin',color:line}});
      sheet.getRange(`A${r}`).format.horizontalAlignment='left';
      if(key||row.kind==='base'){
        sheet.getRange(`A${r}:${lastCol}${r}`).format.fill='#F4F7FA';
        sheet.getRange(`A${r}:${lastCol}${r}`).format.font={name:font,size:10,bold:true,color:navy};
      }
      if(key)sheet.getRange(`A${r}:${lastCol}${r}`).format.borders.top={style:'thin',color:'#71879A'};
      sheet.getRange(`B${r}`).format.fill='#F0F2F4';
      for(let j=0;j<groups.length;j++){
        const c=row.cells[j],address=`${col(j+2)}${r}`;
        if(c.value!==null)sheet.getRange(address).setNumberFormat(numberFormat(row,c,significance));
        if(c.sig_high?.length){
          if(significance)sheet.getRange(address).format.font={name:font,size:10,color:purple,bold:true};
          else if(j>0)sheet.getRange(address).format.fill=cyan;
        }else if(significance&&c.sig_low_all){
          sheet.getRange(address).format.fill='#FFF2CC';
          sheet.getRange(address).format.font={name:font,size:10,color:'#9C6500'};
        }
        if(!significance)layout.cells[`${row.id}/${groups[j].id}`]=address;
      }
      r++;
    }
    const options=block.filter(x=>x.kind==='percent'&&!['t2b','b2b'].includes(x.category));
    if(options.length){
      sheet.getRange(`A${r}`).values=[[q.q_type===4?'选择率合计（可超过100%）':'Total']];
      for(let j=0;j<groups.length;j++){
        const refs=options.map(o=>layout.cells[`${o.id}/${groups[j].id}`]);
        const hasData=options.some(o=>o.cells[j].value!==null);
        const cell=sheet.getRange(`${col(j+2)}${r}`);
        if(hasData)cell.formulas=[[`=SUM(${refs.map(ref=>`'体验问卷大表'!${ref}`).join(',')})`]];
        else cell.values=[['—']];
        cell.setNumberFormat('0.0%');
      }
      style(sheet,`A${r}:${lastCol}${r}`,{horizontalAlignment:'center',borders:{top:{style:'medium',color:line}},rowHeight:24});
      r++;
    }
    for(let j=1;j<groups.length;j++)if(groups[j].family!==groups[j-1].family){
      sheet.getRange(`${col(j+2)}${cursor+1}:${col(j+2)}${r-1}`).format.borders.left={style:'medium',color:'#7D91A2'};
    }
    cursor=r+2;
  }
  sheet.getRange('A:A').format.columnWidth=65;sheet.getRange('B:B').format.columnWidth=14;
  if(groups.length>1)sheet.getRange(`C:${lastCol}`).format.columnWidth=15;
  sheet.freezePanes.freezeRows(4);sheet.freezePanes.freezeColumns(2);sheet.tabColor=navy;
  layout.sheets[sheet.name]={entries,end_row:cursor-1};
}
buildMain(table,false);buildMain(sig,true);

index.getRange('A1:D1').values=[['体验问卷大表','体验问卷显著性检验','题型','指标分类']];
style(index,'A1:D1',{fill:'#FCE4D6',font:{name:font,size:10,bold:true,color:navy},rowHeight:26});
index.getRange(`A2:D${data.questions.length+1}`).values=data.questions.map(q=>[`[Q${q.q_index}].${q.title}`,`[Q${q.q_index}].${q.title}`,typeLabel(q),metadata.indicator_labels?.[q.q_index]||typeLabel(q)]);
style(index,`A2:D${data.questions.length+1}`,{wrapText:true,rowHeight:32,borders:{preset:'all',style:'thin',color:line}});
index.getRange(`A2:B${data.questions.length+1}`).format.font={name:font,size:10,color:blue,underline:true};
index.getRange('A:B').format.columnWidth=65;index.getRange('C:D').format.columnWidth=18;index.freezePanes.freezeRows(1);index.showGridLines=false;

function support(sheet,heading,headers,values,widths){
  const end=col(headers.length);title(sheet,heading,end);sheet.getRange(`A3:${end}3`).values=[headers];
  style(sheet,`A3:${end}3`,{fill:'#E1EAF1',font:{name:font,size:10,bold:true,color:navy},rowHeight:26});
  if(values.length){sheet.getRange(`A4:${end}${values.length+3}`).values=values;style(sheet,`A4:${end}${values.length+3}`,{wrapText:true,rowHeight:34,borders:{preset:'all',style:'thin',color:line}});
    values.forEach((values,i)=>{const lines=Math.max(...values.map((v,j)=>Math.ceil(String(v).length/(widths[j]*.65))));if(lines>2)sheet.getRange(`${i+4}:${i+4}`).format.rowHeight=Math.min(160,lines*16);});}
  widths.forEach((w,i)=>sheet.getRange(`${col(i+1)}:${col(i+1)}`).format.columnWidth=w);
  sheet.freezePanes.freezeRows(3);
}
support(info,'本次数表口径',['项目','本次采用的规则'],[
  ['问卷',metadata.title],['版本',`${metadata.engine_version} / ${metadata.run_version||'本次生成'}`],
  ['来源',quality.source_receipt?.source_note||'问卷结构与已去标识化答卷'],
  ['样本',`清洗前 ${quality.cleaning?.input_n??quality.answer_valid}，剔除 ${quality.cleaning?.excluded_n??0}，保留 ${quality.answer_valid}`],
  ['关联规则',!quality.linkage?'本次未使用外部画像关联':quality.cleaning?.unmatched_policy==='exclude'?'未匹配画像问卷的答卷剔除':'未匹配画像问卷的答卷保留在 Total，排除于对应画像分组'],
  ['显著性',`同族比较；双侧 p < ${metadata.alpha}；比例原始人数检验；Mean / NPS / 平均名次使用 Welch 检验`],
  ['颜色含义','青色、紫色字母表示显著更高，不等于更好；黄色表示显著低于同族全部可比组'],
  ['指标方向','↑ 越高越好；↓ 越低越好。未标方向的指标不预设好坏'],
  ['低基数',`† 有效 n < ${lowN}，仅提示；检验最低 n = ${metadata.minimum_test_base||0}（0表示不额外限制）`],
  ['定义性分组','‡ 表示该题参与了分组定义；其自交叉差异不作为新的研究发现'],
  ['重叠分组',quality.overlaps?.length?`发现 ${quality.overlaps.length} 对同族重叠，详情见数据质量；独立样本检验仅作探索性解释`:'按实际成员检查，未发现同族人群重叠'],
  ['评分和箱体指标','Mean、T2B/B2B 使用有效评分样本；非评分选项保留在分布，排除于评分指标分母。矩阵每个子题独立计算'],
  ['NPS',metadata.nps_question?quality.nps_encoding+'；批评者0–6、中立者7–8、推荐者9–10；推荐者减批评者，范围−100～100':'本问卷未配置 NPS，不生成该指标'],
  ['排序',quality.sorting?.enabled?'无序选项按 Total 降序；有序题、矩阵、NPS、指标行保持原序':'未启用排序，保留问卷选项顺序'],
  ['数据更新','更换源答卷或口径后重新运行；概览下拉只切换已计算的分群，不能替代重跑统计'],
  ['开放题','按实际题型仅保留是否作答，不输出正文'],
],[23,108]);
function ruleText(r){
  if(r.all)return r.all.map(x=>'（'+ruleText(x)+'）').join(' 且 ');
  if(r.any)return r.any.map(x=>'（'+ruleText(x)+'）').join(' 或 ');
  if(r.not)return '不满足：'+ruleText(r.not);
  const origin=r.question?'Q'+r.question:r.field||'';
  if(r.selected_any)return origin+' 选中任一 '+r.selected_any.join('、');
  if(r.selected_all)return origin+' 全部选中 '+r.selected_all.join('、');
  if(r.values)return origin+' 取值 '+r.values.join('、');
  if('equals' in r)return origin+' = '+r.equals;
  return origin+' '+[r.min!=null?'≥ '+r.min:'',r.max!=null?'≤ '+r.max:''].filter(Boolean).join(' 且 ');
}
support(mapping,'变量与分群定义',['题号/分组','名称','类型/取值','口径'],[
  ...data.questions.map(q=>[`Q${q.q_index}`,q.title,typeLabel(q),q.score_map?Object.entries(q.score_map).map(([id,score])=>`选项${id} → ${score==null?'不计分':score+'分'}`).join('；'):'按问卷原选项统计']),
  ...(metadata.native_segments||[]).map(s=>[s.family,`Q${s.question}`,'问卷原生分群','按原始选项分别入组；多选可重叠']),
  ...(metadata.derived_segments||[]).map(s=>[s.family,`Q${s.question}`,s.source==='item_value'?'原始数值':'选项编码',s.groups.map(g=>g.label+'：'+ruleText({...g,question:s.question})).join('；')]),
  ...(metadata.business_segments||[]).map(s=>[s.family,s.source==='profile'?'关联画像问卷':'本问卷',s.mode==='overlap'?'允许重叠':'按顺序互斥',s.groups.map((g,i)=>`${i+1}. ${g.label}：${ruleText(g.when)}`).join('；')+(s.fallback?'；其余：'+s.fallback:'')]),
],[22,55,22,70]);
support(qa,'数据质量',['检查项','结果','说明'],[
  ['有效样本',quality.answer_valid,'进入分析的唯一匿名答卷'],
  ['清洗剔除',quality.cleaning?.excluded_n??0,Object.entries(quality.cleaning?.reasons||{}).map(([name,n])=>`${name}：${n}份`).join('；')||'没有剔除答卷'],
  ['关联覆盖',quality.linkage?`${quality.linkage.matched}/${quality.linkage.target_total}`:'未关联','画像分组的有效匹配数'],
  ['低基数阈值',lowN,'每个指标按自身有效样本提示'],
  ['排序',quality.sorting?.enabled?'Total降序':'原序',quality.sorting?.enabled?'无序选项降序；有序题和指标行保留顺序':'默认不排序'],
  ...Object.entries(quality.question_bases).map(([q,n])=>[`Q${q} 基数`,n,'有效回答人数']),
  ...(quality.overlaps||[]).map(o=>[o.family,o.shared_n,`${o.left} / ${o.right} 共同成员`]),
],[25,25,90]);

// One family selector; charts and heat table link to the canonical table cells.
title(overview,`${metadata.title} 指标概览`,'K');
const families=familyList.filter(f=>f!=='总体');if(!families.length)families.push('总体');
overview.getRange('A3').values=[['查看分组族']];overview.getRange('B3').values=[[families[0]]];
overview.getRange('B3').dataValidation={rule:{type:'list',values:families}};
style(overview,'A3:B3',{rowHeight:28});overview.getRange('B3').format.fill='#FFF2CC';
overview.mergeCells('C3:K3');overview.getRange('C3').values=[['选择一个分组族；指标后显示有效 n、显著高于的列字母与样本标记。']];
style(overview,'C3:K3',{wrapText:true,font:{name:font,size:10,color:'#596D7B'}});
overview.mergeCells('A5:K5');overview.getRange('A5').values=[[`热力色深浅表示数值高低，不表示显著性或好坏；显著性看相邻字母（同族，p < ${metadata.alpha}）。† n < ${lowN}；‡ 定义性分组。`]];style(overview,'A5:K5',{rowHeight:34,wrapText:true,font:{name:font,size:9,color:'#52616D'}});
const metrics=rows.filter(r=>(r.category==='t2b'&&r.matrix_row===null)||r.kind==='nps');
const metricCols=metrics.length;
const maxGroups=Math.max(...families.map(f=>groups.filter(g=>g.family===f||g.family==='总体').length));
const helperStart=110+maxGroups*2, helper=[];
const satisfaction=rows.find(r=>r.category==='t2b'&&r.matrix_row===null);
const distribution=satisfaction?rows.filter(r=>r.q_index===satisfaction.q_index&&r.kind==='percent'&&r.option_id!==null&&!['t2b','b2b'].includes(r.category)):[];
const helpersWidth=3+metrics.length*2+distribution.length;
const tableEnd=col(1+metrics.length*2);
overview.getRange(`A7:${tableEnd}7`).values=[['人群',...metrics.flatMap(r=>[`${metadata.indicator_labels?.[r.q_index]||'Q'+r.q_index}${r.kind==='nps'?'':' T2B'}`,'有效n / 显著性'])]];
style(overview,`A7:${tableEnd}7`,{fill:'#E1EAF1',wrapText:true,rowHeight:40,font:{name:font,size:10,bold:true,color:navy}});
for(const family of families){
  const selected=groups.filter(g=>g.family==='总体'||g.family===family);
  for(let slot=0;slot<maxGroups;slot++){
    const group=selected[slot], hrow=helperStart+helper.length;
    helper.push({family,slot,group,row:hrow});
    overview.getRange(`A${hrow}:C${hrow}`).values=[[`${family}::${slot}`,group?(group.family==='总体'?'Total':`${group.label} (${group.letter})`):'',group?.base_n??'']];
    if(!group)continue;
    const gi=groups.indexOf(group);
    for(let m=0;m<metrics.length;m++){
      const metric=metrics[m],cell=metric.cells[gi],ref=layout.cells[`${metric.id}/${group.id}`];
      overview.getRange(`${col(4+m*2)}${hrow}`).formulas=[[`=IF(ISNUMBER('体验问卷大表'!${ref}),'体验问卷大表'!${ref},"")`]];
      overview.getRange(`${col(5+m*2)}${hrow}`).values=[[`n=${cell.base_n}${cell.sig_high?.length?'；'+cell.sig_high.join('、'):''}${cell.low_base?' †':''}${cell.definition_based?' ‡':''}`]];
    }
    distribution.forEach((r,i)=>{const ref=layout.cells[`${r.id}/${group.id}`];overview.getRange(`${col(4+metrics.length*2+i)}${hrow}`).formulas=[[`=IF(ISNUMBER('体验问卷大表'!${ref}),'体验问卷大表'!${ref},"")`]];});
  }
}
const helperEnd=helperStart+helper.length-1;
function selectionFormula(slot,sourceColumn){return `=IFERROR(INDEX($${col(sourceColumn)}$${helperStart}:$${col(sourceColumn)}$${helperEnd},MATCH($B$3&"::${slot}",$A$${helperStart}:$A$${helperEnd},0)),"")`;}
for(let slot=0;slot<maxGroups;slot++){
  const r=8+slot;overview.getRange(`A${r}`).formulas=[[selectionFormula(slot,2)]];
  for(let m=0;m<metrics.length;m++){
    overview.getRange(`${col(2+m*2)}${r}`).formulas=[[`=IF($A${r}="","",${selectionFormula(slot,4+m*2).slice(1)})`]];
    overview.getRange(`${col(3+m*2)}${r}`).formulas=[[`=IF($A${r}="","",${selectionFormula(slot,5+m*2).slice(1)})`]];
    overview.getRange(`${col(2+m*2)}${r}`).setNumberFormat(metrics[m].kind==='nps'?'0':'0.0%');
  }
}
style(overview,`A8:${tableEnd}${7+maxGroups}`,{rowHeight:32,horizontalAlignment:'center',borders:{preset:'all',style:'thin',color:line}});
overview.getRange(`A8:A${7+maxGroups}`).format.horizontalAlignment='left';
metrics.forEach((m,i)=>overview.getRange(`${col(2+i*2)}8:${col(2+i*2)}${7+maxGroups}`).conditionalFormats.add('colorScale',{
  colors:['#FFFFFF','#BDD7E7','#4C86AA'],thresholds:[m.kind==='nps'?-100:0,m.kind==='nps'?0:.5,m.kind==='nps'?100:1]}));
const chartTop=11+maxGroups, chartMid=chartTop+20;
function chart(titleText,ranges,start,end,rule){
  const c=overview.charts.add('bar',ranges);c.title=titleText;c.setPosition(start,end);c.titleTextStyle.fontSize=13;c.titleTextStyle.typeface=font;
  c.legend={position:'top',textStyle:{typeface:font,fontSize:10}};
  c.xAxis={axisType:'textAxis',textStyle:{typeface:font,fontSize:10}};
  c.yAxis={numberFormatCode:rule.nps?'0':'0%',numberFormatSourceLinked:false,textStyle:{typeface:font,fontSize:10}};
  const palette=rule.distribution?['#BF6F68','#DBA29C','#D9DEE4','#92B5CC','#477EA3','#285F8F','#173F63']:['#477EA3','#759B79','#9A87B7'];
  c.series.items.forEach((s,i)=>s.fill=palette[i%palette.length]);
  if(c.series.items.length===1)c.hasLegend=false;
  layout.charts.push({...rule,colors:c.series.items.map((_,i)=>palette[i%palette.length]),title:titleText});
}
const categories=overview.getRange(`A7:A${7+maxGroups}`);
const t2b=metrics.map((r,i)=>({r,i})).filter(x=>x.r.category==='t2b');
if(t2b.length)chart('核心指标 T2B', [categories,...t2b.map(x=>overview.getRange(`${col(2+x.i*2)}7:${col(2+x.i*2)}${7+maxGroups}`))],`A${chartTop}`,`F${chartTop+18}`,{});
const npsIndex=metrics.findIndex(r=>r.kind==='nps');
if(npsIndex>=0)chart('NPS（−100 至 100）',[categories,overview.getRange(`${col(2+npsIndex*2)}7:${col(2+npsIndex*2)}${7+maxGroups}`)],`G${chartTop}`,`L${chartTop+18}`,{nps:true});
const distHead=chartMid+21;
if(distribution.length){
  overview.getRange(`A${distHead}:${col(1+distribution.length)}${distHead}`).values=[['人群',...distribution.map(r=>r.item)]];
  for(let slot=0;slot<maxGroups;slot++){
    const r=distHead+1+slot;overview.getRange(`A${r}`).formulas=[[`=A${8+slot}`]];
    distribution.forEach((d,i)=>overview.getRange(`${col(2+i)}${r}`).formulas=[[`=IF(A${r}="","",${selectionFormula(slot,4+metrics.length*2+i).slice(1)})`]]);
  }
  overview.getRange(`B${distHead+1}:${col(1+distribution.length)}${distHead+maxGroups}`).setNumberFormat('0.0%');
  style(overview,`A${distHead}:${col(1+distribution.length)}${distHead+maxGroups}`,{rowHeight:25});
  chart(`${metadata.indicator_labels?.[satisfaction.q_index]||'评分'}完整分布`,overview.getRange(`A${distHead}:${col(1+distribution.length)}${distHead+maxGroups}`),`A${chartMid}`,`L${chartMid+18}`,{distribution:true});
}
overview.getRange(`A${helperStart-2}`).values=[['分群指标明细（下拉和图表数据源）']];
style(overview,`A${helperStart}:${col(helpersWidth)}${helperEnd}`,{rowHeight:22});
overview.getRange('A:A').format.columnWidth=32;
overview.getRange(`B:${col(Math.max(12,helpersWidth))}`).format.columnWidth=16;
overview.getRange('B3').format.columnWidth=24;
overview.tabColor=navy;
layout.overview={selector:'B3',families,default_family:families[0],max_groups:maxGroups,metric_ids:metrics.map(r=>r.id),helper_start:helperStart,helper_end:helperEnd};
layout.previewRanges=[['指标概览',`A1:L${chartTop+18}`,'00-overview.png'],['指标概览',`A${chartMid}:L${distHead+maxGroups}`,'00-distribution.png'],['Index',`A1:D${Math.min(16,data.questions.length+1)}`,'01-index.png'],['体验问卷大表',`A1:J${Math.min(42,layout.sheets['体验问卷大表'].end_row)}`,'02-table.png'],['体验问卷显著性检验','A1:J42','03-significance.png'],['说明','A1:B19','04-info.png'],['变量映射','A1:D16','05-mapping.png'],['数据质量','A1:C18','06-quality.png']];
const matrixEntry=layout.sheets['体验问卷大表'].entries.find(e=>qmeta(e.q_index).q_type===7);
if(matrixEntry)layout.previewRanges.push(['体验问卷大表',`A${matrixEntry.return_row}:J${Math.min(matrixEntry.title_row+28,layout.sheets['体验问卷大表'].end_row)}`,'07-matrix.png']);
await fs.mkdir(path.dirname(outputPath),{recursive:true});await fs.mkdir(previewDir,{recursive:true});
wb.recalculate();
// Verify selector changes the displayed groups, then restore the default.
for(const family of families){
  overview.getRange('B3').values=[[family]];wb.recalculate();
  const visible=overview.getRange(`A8:A${7+maxGroups}`).values.flat().filter(Boolean);
  const expected=groups.filter(g=>g.family==='总体'||g.family===family).map(g=>g.family==='总体'?'Total':`${g.label} (${g.letter})`);
  if(JSON.stringify(visible)!==JSON.stringify(expected))throw new Error('Overview selector failed for '+family);
}
overview.getRange('B3').values=[[families[0]]];wb.recalculate();
layout.overview.selector_verified=true;
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(outputPath);
await fs.writeFile(outputPath+'.layout.json',JSON.stringify(layout,null,2));
const patchScript=fileURLToPath(new URL('./finalize_workbook.py',import.meta.url));
execFileSync(process.env.WJX_PYTHON_PATH||'python3',[patchScript,analysisPath,outputPath],{encoding:'utf8'});
// Render the finalized package so chart directions and axis limits are visible.
const {FileBlob}=await import('@oai/artifact-tool');
const final=await SpreadsheetFile.importXlsx(await FileBlob.load(outputPath));
for(const [sheetName,range,name] of layout.previewRanges){
  const blob=await final.render({sheetName,range,scale:1.2,format:'png'});
  await fs.writeFile(path.join(previewDir,name),new Uint8Array(await blob.arrayBuffer()));
}
process.stdout.write(JSON.stringify({output:outputPath,sheets:7,charts:layout.charts.length,selector_verified:true,preview_count:layout.previewRanges.length}));
