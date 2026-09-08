// Deterministic offline API fixture. No network calls or real account details.
const args=process.argv.slice(2);
const page=Number(args[args.indexOf('--page_index')+1]||1);
if(args[0]==='survey'){
  console.log(JSON.stringify({result:true,data:{vid:123,title:'Offline fixture',answer_total:2,answer_valid:2,
    questions:[{q_index:10,q_type:5,q_title:'反馈',items:[]},{q_index:2,q_type:3,q_title:'选择',items:[{item_index:1,item_title:'甲'}]}]}}));
}else{
  const duplicate=process.env.WJX_TEST_MODE==='duplicate';
  const jid=duplicate?1:page;
  console.log(JSON.stringify({result:true,data:{total_count:2,answers:{[String(jid)]:{jid,source_detail:'profile-'+jid,
    answer_items:{a:{q_index:10,item_index:[],answer_text:'TEXT_MUST_NOT_LEAK',item_value:'TEXT_MUST_NOT_LEAK'},b:{q_index:2,item_index:[1],answer_text:'甲'}}}}}}));
}
