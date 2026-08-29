const $=s=>document.querySelector(s);let current=null,lastUser=null;
async function api(u,o={}){let r=await fetch(u,{headers:{'Content-Type':'application/json',...(o.headers||{})},...o}),d=await r.json();if(!r.ok)throw Error(d.error||'Request failed');return d}
function auth(login=true){$('#form').innerHTML=login?`<form onsubmit="login(event)"><input id="email" type="email" placeholder="Email" required><input id="pass" type="password" placeholder="Password" required><button>Login</button></form><p><a onclick="auth(false)">Create account</a></p>`:`<form onsubmit="signup(event)"><input id="name" placeholder="Name" required><input id="email" type="email" placeholder="Email" required><input id="pass" type="password" minlength="6" placeholder="Password" required><button>Create account</button></form><p><a onclick="auth(true)">Back to login</a></p>`}
async function login(e) {
    e.preventDefault();

    const emailValue = document.getElementById('email').value.trim();
    const passwordValue = document.getElementById('pass').value;

    try {
        await api('/api/login', {
            method: 'POST',
            body: JSON.stringify({
                email: emailValue,
                password: passwordValue
            })
        });

        start();
    } catch (x) {
        alert(x.message);
    }
}

async function signup(e) {
    e.preventDefault();

    const nameValue = document.getElementById('name').value.trim();
    const emailValue = document.getElementById('email').value.trim();
    const passwordValue = document.getElementById('pass').value;

    if (passwordValue.length < 6) {
        alert('Password must be at least 6 characters');
        return;
    }

    try {
        await api('/api/signup', {
            method: 'POST',
            body: JSON.stringify({
                name: nameValue,
                email: emailValue,
                password: passwordValue
            })
        });

        start();
    } catch (x) {
        alert(x.message);
    }
}
async function start(){$('#auth').classList.add('hidden');$('#app').classList.remove('hidden');await history();newChat()}
async function history(){let c=await api('/api/chats');$('#history').innerHTML=c.map(x=>`<div class="chatrow"><div class="chat" onclick="openChat(${x.id})">${esc(x.title)}</div><button title="Rename" onclick="renameChat(${x.id},event)">✎</button><button title="Delete" onclick="deleteChat(${x.id},event)">×</button></div>`).join('')}
async function newChat(){current=null;lastUser=null;$('#messages').innerHTML='<div class="welcome"><div class="big">✦</div><h2>How can I help you?</h2><p>Ask anything. Learn, code, brainstorm, or build.</p><div class="suggest"><button onclick="prompt(\'Explain DBMS in simple language\')">Explain DBMS</button><button onclick="prompt(\'Give me a Python project idea\')">Python project</button><button onclick="prompt(\'Help me prepare for an exam\')">Exam prep</button><button onclick="prompt(\'Write a C++ sorting program\')">Write code</button></div></div>'}
async function openChat(i){current=i;let d=await api('/api/chats/'+i);$('#messages').innerHTML=d.messages.map((x,idx)=>message(x.role,x.content,idx===d.messages.length-1)).join('');scroll()}
function message(r,t,last=false){let actions=r==='assistant'?`<div class="actions"><button onclick="copyText(this)">Copy</button>${last?'<button onclick="regenerate()">Regenerate</button>':''}</div>`:``;return `<div class="msg ${r}"><div class="av">${r==='user'?'U':'✦'}</div><div class="bubblewrap"><div class="bubble">${r==='assistant'?marked.parse(t):esc(t).replace(/\n/g,'<br>')}</div>${actions}</div></div>`}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function prompt(t){$('#input').value=t;send()}
async function send(){let q=$('#input').value.trim();if(!q)return;$('#input').value='';if(!current){let c=await api('/api/chats',{method:'POST',body:JSON.stringify({title:q.slice(0,50)})});current=c.id;await history()}lastUser=q;$('#messages').insertAdjacentHTML('beforeend',message('user',q));let id='typing-'+Date.now();$('#messages').insertAdjacentHTML('beforeend',`<div id="${id}" class="msg assistant"><div class="av">✦</div><div class="bubblewrap"><div class="bubble">Thinking…</div></div></div>`);scroll();$('#send').disabled=true;try{await streamTo(id,'/api/chat',{chat_id:current,message:q});await history()}catch(x){document.getElementById(id)?.remove();$('#messages').insertAdjacentHTML('beforeend',message('assistant','**Error:** '+x.message))}finally{$('#send').disabled=false;scroll()}}
async function streamTo(id,url,data){let r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});if(!r.ok){let d=await r.json().catch(()=>({}));throw Error(d.error||'AI request failed')}let el=document.getElementById(id);let bubble=el.querySelector('.bubble');bubble.innerHTML='';let reader=r.body.getReader(),decoder=new TextDecoder(),answer='';while(true){let {value,done}=await reader.read();if(done)break;answer+=decoder.decode(value,{stream:true});bubble.innerHTML=marked.parse(answer);scroll()}el.outerHTML=message('assistant',answer,true);$('#badge').textContent='OLLAMA AI'}
async function regenerate(){if(!current)return;let id='regen-'+Date.now();$('#messages').insertAdjacentHTML('beforeend',`<div id="${id}" class="msg assistant"><div class="av">✦</div><div class="bubblewrap"><div class="bubble">Regenerating…</div></div></div>`);scroll();try{await streamTo(id,'/api/regenerate',{chat_id:current});await openChat(current)}catch(e){alert(e.message)}}
async function copyText(btn){let text=btn.closest('.bubblewrap').querySelector('.bubble').innerText;await navigator.clipboard.writeText(text);let old=btn.textContent;btn.textContent='Copied!';setTimeout(()=>btn.textContent=old,1000)}
async function renameChat(i,e){e.stopPropagation();let t=window.prompt('New chat name');if(!t)return;try{await api('/api/chats/'+i,{method:'PATCH',body:JSON.stringify({title:t})});history()}catch(x){alert(x.message)}}
async function deleteChat(i,e){e.stopPropagation();if(!confirm('Delete this chat?'))return;await api('/api/chats/'+i,{method:'DELETE'});if(current===i)newChat();history()}
function searchChats(){let q=$('#find').value.toLowerCase();document.querySelectorAll('.chatrow').forEach(x=>x.style.display=x.querySelector('.chat').innerText.toLowerCase().includes(q)?'flex':'none')}
async function uploadFile(){let f=$('#file').files[0];if(!f)return;let fd=new FormData();fd.append('file',f);let r=await fetch('/api/upload',{method:'POST',body:fd});let d=await r.json();if(!r.ok)return alert(d.error);$('#input').value=`Please analyze this file (${d.name}):\n\n${d.text}`;$('#file').value='';$('#input').focus()}
function scroll(){$('#messages').scrollTop=$('#messages').scrollHeight}
async function logout(){await api('/api/logout',{method:'POST'});location.reload()}
function theme(){document.body.classList.toggle('dark');document.documentElement.classList.toggle('dark');localStorage.theme=document.body.classList.contains('dark')?'dark':'light'}
$('#send').onclick=send;$('#input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}});$('#find').addEventListener('input',searchChats);init()
async function init(){try{let d=await api('/api/me');d.user?start():auth()}catch{auth()}if(localStorage.theme==='dark')theme()}
