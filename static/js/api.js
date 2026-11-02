/* Shared API adapter: Flask for a real shared site, localStorage for file:// demos. */
(function () {
  'use strict';
  const offline = location.protocol === 'file:' || new URLSearchParams(location.search).get('preview') === '1';
  const STORE_KEY = 'reunite-local-preview-v1';
  const REPORTS_KEY = 'reunite-my-reports-v1';
  let csrf = null;
  const daysAgo = n => { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString(); };
  const dateAgo = n => daysAgo(n).slice(0, 10);
  const sampleData = () => ({
    items: [
      {id:'sample-1',type:'found',title:'Wireless earbuds with case',description:'Found a pair of wireless earbuds inside a light-colored charging case, near the reading area.',category:'Electronics',location:'Main library entrance',item_date:dateAgo(1),reporter_first_name:'Aarav',photo_url:null,color:'White',status:'open',created_at:daysAgo(0),is_demo:true},
      {id:'sample-2',type:'lost',title:'Canvas tote bag',description:'Beige canvas tote bag with a little flower drawing. Had a notebook and water bottle inside.',category:'Bags',location:'Near the food court',item_date:dateAgo(2),reporter_first_name:'Mira',photo_url:null,color:'Brown',status:'open',created_at:daysAgo(1),is_demo:true},
      {id:'sample-3',type:'found',title:'Set of three keys',description:'A small set of keys on a simple metal ring. Tell me what the keychain looks like to verify.',category:'Keys',location:'Sports complex gate',item_date:dateAgo(2),reporter_first_name:'Kabir',photo_url:null,color:'Grey',status:'open',created_at:daysAgo(2),is_demo:true},
      {id:'sample-4',type:'lost',title:'Blue notebook with stickers',description:'A blue spiral notebook full of class notes, with two stickers on the back cover.',category:'Books',location:'Academic building corridor',item_date:dateAgo(3),reporter_first_name:'Zoya',photo_url:null,color:'Blue',status:'open',created_at:daysAgo(3),is_demo:true},
      {id:'sample-5',type:'found',title:'Student ID card',description:'An ID card was picked up near the bus stop. Details are intentionally hidden for privacy.',category:'Documents',location:'North bus stop',item_date:dateAgo(4),reporter_first_name:'Dev',photo_url:null,color:'Other',status:'reunited',created_at:daysAgo(4),is_demo:true},
      {id:'sample-6',type:'lost',title:'Black wristwatch',description:'Lost a minimal black watch with a soft strap sometime around lunchtime.',category:'Accessories',location:'Central plaza',item_date:dateAgo(5),reporter_first_name:'Ishita',photo_url:null,color:'Black',status:'open',created_at:daysAgo(5),is_demo:true}
    ], inquiries: []
  });
  function readStore() { let s; try { s = JSON.parse(localStorage.getItem(STORE_KEY)); } catch (_) {} if (!s || !Array.isArray(s.items)) { s = sampleData(); saveStore(s); } return s; }
  function saveStore(s) { localStorage.setItem(STORE_KEY, JSON.stringify(s)); }
  function myReports() { try { return JSON.parse(localStorage.getItem(REPORTS_KEY)) || []; } catch (_) { return []; } }
  function rememberReport(record) { const all = myReports().filter(x => x.token !== record.token); all.unshift(record); localStorage.setItem(REPORTS_KEY, JSON.stringify(all.slice(0, 100))); }
  function forgetReport(token) { localStorage.setItem(REPORTS_KEY, JSON.stringify(myReports().filter(x => x.token !== token))); }
  async function init() { if (offline) return; const r = await fetch('/api/config', {credentials:'same-origin'}); if (!r.ok) throw new Error('Unable to connect to the Python server.'); csrf = (await r.json()).csrf; }
  async function api(path, opts={}) {
    const headers = opts.headers || {};
    if (opts.method && opts.method !== 'GET') headers['X-CSRF-Token'] = csrf;
    const r = await fetch(path, {...opts, headers, credentials:'same-origin'});
    const data = await r.json().catch(() => ({}));
    if (!r.ok || data.ok === false) throw new Error(data.error || 'Something went wrong. Please try again.');
    return data;
  }
  function offlineMatches(source) {
    const sw = s => new Set(String(s).toLowerCase().match(/[a-z0-9]{3,}/g) || []);
    const data = readStore();
    return data.items.filter(x => x.id !== source.id && x.type !== source.type && x.status === 'open').map(x => {
      let score=0; const reasons=[];
      if (x.category===source.category) {score+=38; reasons.push('Same category');}
      const a=sw(source.title+' '+source.description),b=sw(x.title+' '+x.description);
      const overlap=[...a].filter(y=>b.has(y)).length;
      if (overlap) {score+=Math.round(42*overlap/Math.max(1,new Set([...a,...b]).size));reasons.push('Similar item details');}
      if ([...sw(source.location)].some(y=>sw(x.location).has(y))) {score+=18;reasons.push('Location overlap');}
      if (source.color!=='Unknown' && x.color===source.color){score+=8;reasons.push('Same color');}
      return {...x,match_score:Math.min(score,98),match_reasons:reasons};
    }).filter(x=>x.match_score>=22).sort((a,b)=>b.match_score-a.match_score).slice(0,5);
  }
  async function getStats() { if(!offline)return api('/api/stats'); const list=readStore().items; return {total:list.length,reunited:list.filter(x=>x.status==='reunited').length,lost:list.filter(x=>x.type==='lost'&&x.status==='open').length,found:list.filter(x=>x.type==='found'&&x.status==='open').length}; }
  async function getItems(params={}) { if(!offline)return api('/api/items?'+new URLSearchParams(params)); let items=[...readStore().items]; const {type='all',status='all',category='all',q='',sort='recent',page=1}=params; if(type!=='all')items=items.filter(x=>x.type===type);if(status!=='all')items=items.filter(x=>x.status===status);if(category!=='all')items=items.filter(x=>x.category===category);if(q){const t=q.toLowerCase();items=items.filter(x=>(x.title+' '+x.description+' '+x.location+' '+x.category).toLowerCase().includes(t));}items.sort((a,b)=>(sort==='oldest'?1:-1)*(a.created_at.localeCompare(b.created_at)));const total=items.length;const start=(Number(page)-1)*12;return {items:items.slice(start,start+12),total,has_more:start+12<total,page:Number(page)}; }
  function fileAsDataURL(file) { return new Promise((resolve,reject)=>{if(!file || !file.name || file.size===0){resolve(null);return;}if(file.size>5*1024*1024){reject(new Error('Photo must be 5 MB or smaller.'));return;}const read=new FileReader();read.onerror=()=>reject(new Error('Could not read photo.'));read.onload=()=>{const img=new Image();img.onerror=()=>reject(new Error('Invalid image.'));img.onload=()=>{const scale=Math.min(1,1100/img.width,1100/img.height);const canvas=document.createElement('canvas');canvas.width=Math.round(img.width*scale);canvas.height=Math.round(img.height*scale);const ctx=canvas.getContext('2d');ctx.fillStyle='white';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.drawImage(img,0,0,canvas.width,canvas.height);resolve(canvas.toDataURL('image/jpeg',0.75));};img.src=read.result;};read.readAsDataURL(file);}); }
  async function createItem(form) {
    if (!offline) return api('/api/items', {method:'POST',body:form});
    const id='local-'+Date.now()+'-'+Math.floor(Math.random()*100000);
    const token=Date.now().toString(36)+'-'+Math.random().toString(36).slice(2)+Math.random().toString(36).slice(2);
    const item={id,type:form.get('type'),title:form.get('title').trim(),description:form.get('description').trim(),category:form.get('category'),location:form.get('location').trim(),item_date:form.get('item_date'),reporter_name:form.get('reporter_name').trim(),reporter_email:form.get('reporter_email').trim(),reporter_phone:form.get('reporter_phone').trim(),reporter_first_name:form.get('reporter_name').trim().split(' ')[0],photo_url:await fileAsDataURL(form.get('photo')),color:form.get('color')||'Unknown',status:'open',created_at:new Date().toISOString(),token,is_demo:false};
    const store=readStore();store.items.unshift(item);try{saveStore(store);}catch(e){throw new Error('Browser storage is full. Try posting with a smaller photo, or use the Python server.');}
    return {ok:true,item,manage_url:'manage.html?token='+encodeURIComponent(token)+(location.protocol==='file:'?'':'&preview=1'),matches:offlineMatches(item)};
  }
  async function getMatches(id) {if(!offline)return api('/api/items/'+id+'/matches');const item=readStore().items.find(x=>x.id===id);return {matches:item?offlineMatches(item):[]};}
  async function sendInquiry(itemId,fields) {if(!offline)return api('/api/items/'+itemId+'/inquiries',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(fields)});const store=readStore();const item=store.items.find(x=>x.id===itemId);if(!item)throw new Error('Report not found.');if(item.is_demo)throw new Error('This is an example report. Create a real post to try messages.');if(item.status!=='open')throw new Error('This report has been marked reunited.');store.inquiries.push({id:Date.now(),item_id:itemId,...fields,created_at:new Date().toISOString()});saveStore(store);return {ok:true,message:'Private message saved. The report owner can read it from their dashboard on this browser.'}; }
  async function getManage(token) {if(!offline)return api('/api/manage/'+encodeURIComponent(token));const store=readStore();const item=store.items.find(x=>x.token===token&&!x.is_demo);if(!item)throw new Error('This private link was not found in this browser.');return {ok:true,item,inquiries:store.inquiries.filter(x=>x.item_id===item.id).sort((a,b)=>b.created_at.localeCompare(a.created_at))};}
  async function updateStatus(token,status) {if(!offline)return api('/api/manage/'+encodeURIComponent(token),{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({status})});const store=readStore();const item=store.items.find(x=>x.token===token);if(!item)throw new Error('Report not found.');item.status=status;saveStore(store);return {ok:true,status};}
  async function deleteReport(token) {if(!offline)return api('/api/manage/'+encodeURIComponent(token),{method:'DELETE'});const store=readStore();const item=store.items.find(x=>x.token===token);if(!item)throw new Error('Report not found.');store.items=store.items.filter(x=>x.token!==token);store.inquiries=store.inquiries.filter(x=>x.item_id!==item.id);saveStore(store);return {ok:true};}
  window.ReuniteAPI={offline,init,getItems,getStats,createItem,getMatches,sendInquiry,getManage,updateStatus,deleteReport,rememberReport,myReports,forgetReport};
})();
