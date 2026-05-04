"""MitoFlow AI Web UI v3 — login-first, user-scoped."""

CHAT_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MitoFlow AI</title>
<style>
:root{--bg:#f8fafb;--surface:#fff;--border:#e5e7eb;--text:#1a1a2e;--sub:#6b7280;--accent:#059669;--accent2:#10b981;--nav-w:58px;--drawer-w:260px;--results-w:300px;--green:#10b981;--red:#ef4444;--amber:#f59e0b;--blue:#3b82f6}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','Noto Sans SC',sans-serif;background:var(--bg);color:var(--text);height:100vh;overflow:hidden}
/* Auth page */
#authPage{display:flex;align-items:center;justify-content:center;height:100vh;background:linear-gradient(135deg,#ecfdf5 0%,#d1fae5 50%,#a7f3d0 100%)}
#authPage.hidden{display:none}
.auth-card{background:var(--surface);border-radius:20px;padding:2.5rem;width:100%;max-width:440px;box-shadow:0 20px 60px rgba(0,0,0,.08)}
.auth-logo{text-align:center;margin-bottom:1.5rem}
.auth-logo .icon{font-size:3rem}
.auth-logo h1{font-size:1.4rem;font-weight:700;margin:.3rem 0;background:linear-gradient(135deg,#059669,#10b981);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.auth-logo p{font-size:.8rem;color:var(--sub)}
.auth-tabs{display:flex;gap:0;margin-bottom:1.2rem;border-bottom:2px solid var(--border)}
.auth-tab{flex:1;padding:.6rem;text-align:center;border:none;background:none;font-size:.9rem;font-weight:600;cursor:pointer;color:var(--sub);border-bottom:2px solid transparent;margin-bottom:-2px;transition:.15s}
.auth-tab.on{color:var(--accent);border-bottom-color:var(--accent)}
.auth-field{margin-bottom:.7rem}
.auth-field input{width:100%;padding:.6rem .8rem;border:1px solid var(--border);border-radius:10px;font-size:.9rem;transition:.15s;background:var(--bg)}
.auth-field input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(5,150,105,.1)}
.auth-btn{width:100%;padding:.65rem;background:linear-gradient(135deg,#059669,#10b981);color:#fff;border:none;border-radius:10px;font-size:.9rem;font-weight:600;cursor:pointer;margin-top:.3rem}
.auth-btn:hover{filter:brightness(1.1)}
.auth-error{color:var(--red);font-size:.78rem;text-align:center;margin-top:.5rem;min-height:1.2rem}

/* App (hidden until login) */
#appPage{display:none;height:100vh;overflow:hidden}
#appPage.visible{display:flex;flex-direction:row}
.app-inner{display:flex;flex:1;overflow:hidden;min-width:0}
/* Nav */
.nav{width:var(--nav-w);min-width:var(--nav-w);background:linear-gradient(180deg,#064e3b,#065f46);display:flex;flex-direction:column;align-items:center;padding:.6rem 0;gap:.2rem;z-index:30}
.nav .logo{font-size:1.2rem;margin-bottom:.3rem}
.n-btn{width:38px;height:38px;border:none;border-radius:10px;display:flex;align-items:center;justify-content:center;cursor:pointer;transition:.15s;background:transparent;color:rgba(255,255,255,.5);position:relative;font-size:1.1rem}
.n-btn:hover{background:rgba(255,255,255,.1);color:rgba(255,255,255,.9)}
.n-btn.on{background:rgba(255,255,255,.15);color:#fff;box-shadow:0 2px 8px rgba(0,0,0,.2)}
.n-btn.on::before{content:'';position:absolute;left:0;top:25%;height:50%;width:3px;background:var(--accent2);border-radius:0 3px 3px 0}
.n-sp{flex:1}
.user-btn{width:34px;height:34px;border-radius:50%;background:var(--accent);color:#fff;font-weight:700;font-size:.8rem;border:none;cursor:pointer;display:flex;align-items:center;justify-content:center;margin-bottom:.3rem}
/* Drawer */
.drawer{width:0;overflow:hidden;background:#fafbfc;border-right:1px solid var(--border);display:flex;flex-direction:column;z-index:20;font-size:.82rem;resize:horizontal;min-width:0}
.drawer.open{width:var(--drawer-w);min-width:180px;max-width:400px}
.dr-h{padding:.8rem 1rem;border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
.dr-h h3{font-size:.85rem;font-weight:600}
.dr-search{padding:.4rem 1rem}
.dr-search input{width:100%;padding:.35rem .7rem;border:1px solid var(--border);border-radius:8px;font-size:.78rem;background:var(--surface)}
.dr-list{flex:1;overflow-y:auto;padding:.4rem}
.dr-item{padding:.5rem .7rem;border-radius:8px;cursor:pointer;font-size:.8rem;margin-bottom:1px}
.dr-item:hover{background:#eef2ff}.dr-item.sel{background:#e0e7ff;font-weight:600}
.nw-btn{margin:.4rem 1rem .8rem;padding:.4rem;border:1px dashed var(--border);border-radius:8px;background:transparent;color:var(--accent);font-size:.78rem;cursor:pointer;width:calc(100% - 2rem)}
/* Main */
.main{flex:1;display:flex;flex-direction:column;min-width:0;overflow:hidden}
.tbar{height:44px;border-bottom:1px solid var(--border);display:flex;align-items:center;padding:0 1rem;gap:.6rem;background:var(--surface);flex-shrink:0}
.tbar-title{font-weight:600;font-size:.85rem;flex:1}
.tbar-btn{padding:.3rem .8rem;border:1px solid var(--border);border-radius:8px;background:var(--surface);cursor:pointer;font-size:.75rem;transition:.15s}
.tbar-btn:hover{background:#f0f4f8}
.content-body{flex:1;display:flex;flex-direction:row;overflow:hidden;min-height:0;width:100%}
.center-panel{flex:1;display:flex;flex-direction:column;overflow:hidden;min-width:0;max-width:calc(100% - var(--results-w))}
/* Panels */
.panel{flex:1;overflow-y:auto;padding:1rem;display:none}
.panel.on{display:block}
/* Chat */
.chat-msgs{flex:1;overflow-y:auto;padding:.8rem 1.2rem}
.welcome{text-align:center;margin:auto;max-width:600px;padding:2rem}
.welcome h1{font-size:1.6rem;font-weight:700;margin-bottom:.4rem;background:linear-gradient(135deg,#059669,#10b981);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.welcome p{color:var(--sub);margin-bottom:1rem;line-height:1.6}
.welcome .sugs{display:flex;gap:.3rem;flex-wrap:wrap;justify-content:center}
.sug{padding:.35rem .9rem;border:1px solid var(--border);border-radius:16px;font-size:.78rem;cursor:pointer;background:var(--surface);white-space:nowrap;transition:.15s}
.sug:hover{background:#eef2ff;border-color:var(--accent);transform:translateY(-1px)}
.msg-w{display:flex;margin-bottom:.6rem;animation:fadeIn .2s}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}}
.msg{max-width:82%;padding:.6rem .9rem;border-radius:12px;line-height:1.55;font-size:.85rem}
.msg.u{background:var(--accent);color:#fff;margin-left:auto;border-bottom-right-radius:3px}
.msg.a{background:var(--surface);border:1px solid var(--border);border-bottom-left-radius:3px}
.msg.a h1,.msg.a h2,.msg.a h3{font-size:.95rem;margin:.4rem 0 .2rem}
.msg.a code{background:#f0f0f5;padding:1px 5px;border-radius:4px;font-size:.8rem}
.msg.a table{border-collapse:collapse;width:100%;font-size:.78rem;margin:.3rem 0}
.msg.a th{background:#f0f4f8;font-weight:600}
.msg.a th,.msg.a td{border:1px solid var(--border);padding:.3rem .5rem;text-align:left}
.msg.a ul,.msg.a ol{padding-left:1.2rem;margin:.2rem 0}
.tool-card{margin:.3rem 0;background:#fafbfd;border:1px solid var(--border);border-radius:8px;overflow:hidden}
.tc-h{padding:.35rem .7rem;background:#f0f4f8;font-size:.73rem;font-weight:600;color:var(--accent);cursor:pointer}
.tc-b{padding:.35rem .7rem;font-size:.75rem;color:var(--sub);max-height:150px;overflow:auto;font-family:monospace;white-space:pre-wrap;display:none}
.tool-card.open .tc-b{display:block}
.thk{display:flex;align-items:center;gap:.5rem;padding:.35rem .8rem;border-radius:8px;font-size:.76rem;color:var(--sub);margin:.2rem 0}
.thk-d{width:7px;height:7px;border-radius:50%}
.thk-d.run{background:var(--blue);animation:pulse 1.5s infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
.inp-area{border-top:1px solid var(--border);padding:.6rem 1rem;background:var(--surface);flex-shrink:0}
.inp-row{display:flex;gap:.5rem;align-items:center;max-width:900px;margin:0 auto}
.inp-row textarea{flex:1;padding:.5rem .8rem;border:1px solid var(--border);border-radius:12px;font-size:.85rem;resize:none;height:40px;max-height:140px;font-family:inherit;line-height:1.4;background:var(--bg)}
.inp-row textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(5,150,105,.1)}
.inp-row button{padding:.5rem 1.2rem;height:40px;border:none;border-radius:12px;background:linear-gradient(135deg,#059669,#10b981);color:#fff;font-weight:600;font-size:.82rem;cursor:pointer;white-space:nowrap}
.inp-row .upload-chat{width:36px;height:36px;border:1px solid var(--border);border-radius:10px;background:var(--surface);cursor:pointer;font-size:1.1rem;display:flex;align-items:center;justify-content:center;flex-shrink:0}
/* Results */
.results{width:var(--results-w);min-width:200px;max-width:500px;overflow:hidden;background:var(--surface);border-left:1px solid var(--border);display:flex;flex-direction:column;z-index:10;flex-shrink:0;resize:horizontal}
.results.closed{width:0;min-width:0;max-width:0;flex-shrink:0}
.res-tabs{display:flex;border-bottom:1px solid var(--border);flex-shrink:0}
.res-tab{flex:1;padding:.5rem;text-align:center;font-size:.75rem;cursor:pointer;border:none;background:transparent;border-bottom:2px solid transparent;font-weight:500}
.res-tab.on{border-bottom-color:var(--accent);color:var(--accent)}
.res-content{flex:1;overflow-y:auto;padding:.8rem}
.res-content img{max-width:100%;border-radius:8px;margin:.3rem 0}
.pipeline-step{padding:.5rem .8rem;margin:.3rem 0;border:1px solid var(--border);border-radius:10px;font-size:.8rem;cursor:pointer;display:flex;align-items:center;gap:.6rem}
.pipeline-step:hover{border-color:var(--accent);background:#eef2ff}
.pipeline-step .step-num{width:24px;height:24px;border-radius:50%;background:var(--accent);color:#fff;display:flex;align-items:center;justify-content:center;font-size:.7rem;font-weight:700;flex-shrink:0}
/* Cards */
.cards{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:.6rem}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:.9rem;transition:.15s}
.card:hover{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,.06)}
.card .icon{font-size:1.4rem;margin-bottom:.3rem}
.card .name{font-weight:600;font-size:.85rem;margin-bottom:.15rem}
.card .desc{font-size:.75rem;color:var(--sub);margin-bottom:.5rem}
.card .actions{display:flex;gap:.3rem}
.card .act{padding:.25rem .6rem;border-radius:6px;font-size:.7rem;border:1px solid var(--border);cursor:pointer;background:var(--surface);font-weight:500;transition:.15s}
.card .act:hover{border-color:var(--accent);background:#eef2ff}
.card .act.ai{background:#eef2ff;color:var(--accent);border-color:#a7f3d0}
.card .badge{display:inline-block;font-size:.65rem;padding:1px 6px;border-radius:8px;margin-top:.3rem}
.badge-read{background:#e0f2fe;color:#0369a1}.badge-job{background:#fef3c7;color:#92400e}
/* Settings */
.set-section{margin-bottom:1.2rem}
.set-section h3{font-size:.85rem;margin-bottom:.5rem;padding-bottom:.25rem;border-bottom:1px solid var(--border)}
.pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:.4rem}
.pcard{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:.5rem;cursor:pointer;display:flex;align-items:center;gap:.4rem;font-size:.8rem;transition:.15s}
.pcard:hover,.pcard.sel{border-color:var(--accent);background:#eef2ff}
.set-section input,.set-section select{width:100%;padding:.4rem .6rem;border:1px solid var(--border);border-radius:8px;font-size:.82rem}
.lang-tg{display:flex;background:#e5e7eb;border-radius:6px;padding:1px}
.lang-tg button{flex:1;border:none;background:transparent;padding:.25rem .5rem;border-radius:5px;font-size:.7rem;cursor:pointer}
.lang-tg button.on{background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.1)}
/* Upload */
.upload-zone{border:2px dashed var(--border);border-radius:14px;padding:1.5rem;text-align:center;cursor:pointer;transition:.2s;background:var(--surface);margin-bottom:1rem}
.upload-zone:hover{border-color:var(--accent);background:#fafafe}
.status{display:flex;align-items:center;gap:.4rem;font-size:.75rem;color:var(--sub);padding:.6rem 1rem;border-top:1px solid var(--border);margin-top:auto}
.sdot{width:6px;height:6px;border-radius:50%}.sdot.on{background:var(--green)}.sdot.off{background:var(--red)}
@media(max-width:900px){.results{width:240px;min-width:240px}.drawer.open{width:200px;min-width:200px}}
</style>
</head>
<body>

<!-- Auth Page (shown first) -->
<div id="authPage">
  <div class="auth-card">
    <div class="auth-logo"><img src="/logo.png" alt="MitoFlow" style="width:70px;height:70px;border-radius:16px;margin-bottom:.3rem"><h1>MitoFlow AI</h1><p>Plant Mitochondrial & Chloroplast Genomics</p></div>
    <div class="auth-tabs"><button class="auth-tab on" id="tabLogin" onclick="switchAuthTab('login')">Login</button><button class="auth-tab" id="tabRegister" onclick="switchAuthTab('register')">Register</button></div>
    <div id="authLogin">
      <div class="auth-field"><input id="loginEmail" placeholder="Email" onkeydown="if(event.key==='Enter')doLogin()"></div>
      <div class="auth-field"><input id="loginPass" type="password" placeholder="Password" onkeydown="if(event.key==='Enter')doLogin()"></div>
      <button class="auth-btn" onclick="doLogin()">Login</button>
    </div>
    <div id="authRegister" style="display:none">
      <div class="auth-field"><input id="regEmail" placeholder="Email"></div>
      <div class="auth-field"><input id="regUser" placeholder="Username"></div>
      <div class="auth-field"><input id="regPass" type="password" placeholder="Password (6+ characters)" onkeydown="if(event.key==='Enter')doRegister()"></div>
      <button class="auth-btn" onclick="doRegister()">Register</button>
    </div>
    <div class="auth-error" id="authError"></div>
  </div>
</div>

<!-- App Page (hidden until login) -->
<div id="appPage">
  <div class="nav">
    <img src="/logo.png" alt="MitoFlow" style="width:32px;height:32px;border-radius:8px;margin-bottom:.3rem">
    <button class="n-btn on" onclick="go('chat')" id="nChat">💬</button>
    <button class="n-btn" onclick="go('tools')" id="nTools">🔧</button>
    <button class="n-btn" onclick="go('skills')" id="nSkills">📋</button>
    <button class="n-btn" onclick="go('files')" id="nFiles">📤</button>
    <button class="n-btn" onclick="go('results')" id="nResults" title="Analysis Results">📊</button>
    <div class="n-sp"></div>
    <button class="user-btn" onclick="showUserMenu()" id="userBtn" title="User">?</button>
    <button class="n-btn" onclick="go('settings')" id="nSettings">⚙️</button>
  </div>
  <div class="app-inner">
    <div class="drawer open" id="drawer">
      <div class="dr-h"><h3>Sessions</h3></div>
      <div class="dr-search"><input placeholder="Search..." id="sessionSearch" oninput="renderSessions()"></div>
      <button class="nw-btn" onclick="newSession()">+ New Session</button>
      <div class="dr-list" id="sessionList"></div>
      <div class="status"><span class="sdot on" id="statusDot"></span><span id="statusText">Connected</span></div>
    </div>
    <div class="main">
      <div class="tbar"><button class="tbar-btn" onclick="toggleDrawer()">☰</button><span class="tbar-title" id="tbarTitle">Chat</span></div>
      <div class="content-body"><div class="center-panel">
        <div class="panel on" id="pChat">
          <div class="chat-msgs" id="chatMsgs"><div class="welcome" id="welcomeBlock"><h1>Plant Mitochondrial Genomics AI</h1><p>Upload data, ask questions, run analysis — all in one platform.</p><div class="sugs" id="suggestions"></div></div></div>
          <div class="inp-area"><div class="inp-row"><button class="upload-chat" onclick="quickUpload()" title="Upload files">📎</button><textarea id="chatInput" rows="1" placeholder="Ask about plant mitochondrial genomics..." onkeydown="if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}"></textarea><button onclick="send()" id="sendBtn">Send</button></div></div>
        </div>
        <div class="panel" id="pTools"><div style="max-width:1000px;margin:0 auto"><h2 style="margin-bottom:.3rem">🔧 MitoFlow Modules</h2><p style="color:var(--sub);font-size:.82rem;margin-bottom:.8rem">AI-auto, manual fine-tune, or view results.</p><div class="cards" id="toolsCards"></div></div></div>
        <div class="panel" id="pSkills"><div style="max-width:1000px;margin:0 auto"><h2 style="margin-bottom:.3rem">📋 Workflow Skills</h2><p style="color:var(--sub);font-size:.82rem;margin-bottom:.8rem">Encapsulated multi-step analysis workflows.</p><div class="cards" id="skillsCards"></div></div></div>
        <div class="panel" id="pFiles"><div style="max-width:1000px;margin:0 auto"><h2 style="margin-bottom:.3rem">📤 Upload Files</h2>
          <div class="upload-zone" id="uploadZone" ondragover="this.style.borderColor='var(--accent)';this.style.background='#eef2ff';event.preventDefault()" ondragleave="this.style.borderColor='var(--border)';this.style.background='var(--surface)'" ondrop="handleDrop(event)" onclick="document.getElementById('fileInput').click()">
            <div style="font-size:2rem">📤</div><div style="font-weight:600">Drop FASTA/GenBank/FASTQ files here</div>
            <input type="file" id="fileInput" multiple style="display:none" onchange="uploadFiles(this.files)"><input type="file" id="dirInput" webkitdirectory multiple style="display:none" onchange="uploadFiles(this.files)">
            <div style="margin-top:.6rem;display:flex;gap:.4rem;justify-content:center"><button class="tbar-btn" onclick="event.stopPropagation();document.getElementById('fileInput').click()">📎 Files</button><button class="tbar-btn" onclick="event.stopPropagation();document.getElementById('dirInput').click()">📁 Directory</button></div>
          </div><div id="fileList"></div></div></div>
        <div class="panel" id="pResults"><div style="max-width:1000px;margin:0 auto"><h2 style="margin-bottom:.3rem">📊 Analysis Results</h2><p style="color:var(--sub);font-size:.82rem;margin-bottom:.8rem">Results organized by session. Click to browse analysis outputs.</p><div id="resultsPageContent"></div></div></div>
        <div class="panel" id="pSettings"><div style="max-width:700px;margin:0 auto"><h2 style="margin-bottom:.8rem">⚙️ Settings</h2>
          <div class="set-section"><h3>Language</h3><div class="lang-tg" id="langToggle"><button class="on" onclick="setLang('en')">English</button><button onclick="setLang('zh')">中文</button></div></div>
          <div class="set-section"><h3>Protocol Format</h3><div class="lang-tg" id="protoToggle"><button class="on" onclick="setProto('openai')">OpenAI / Compatible</button><button onclick="setProto('anthropic')">Claude / Anthropic</button></div></div>
          <div class="set-section"><h3>Model Provider</h3><div class="pgrid" id="providerGrid"></div></div>
          <div class="set-section"><h3>Model</h3><select id="modelSelect"></select></div>
          <div class="set-section"><h3>API Key</h3><input type="password" id="apiKeyInput" placeholder="sk-... (per-provider, saved locally)"><p style="font-size:.7rem;color:var(--sub);margin-top:.2rem">Key is saved per provider in your browser. Different providers can have different keys.</p></div>
          <div class="set-section"><h3>Custom Endpoint</h3><input type="text" id="baseUrlInput" placeholder="Auto-filled from provider"></div>
          </div></div>
        </div><!-- /center-panel -->
        <div class="results" id="resultsPanel"><div class="res-tabs"><button class="res-tab on" onclick="switchResTab('files')" id="rtFiles">📁 Files</button><button class="res-tab" onclick="switchResTab('preview')" id="rtPreview">👁 Preview</button><button class="res-tab" onclick="switchResTab('pipeline')" id="rtPipeline">🔗 Pipeline</button></div><div class="res-content" id="resContent"></div></div>
      </div><!-- /content-body -->
    </div><!-- /main -->
  </div><!-- /app-inner -->
</div><!-- /appPage -->

<script>
const API='/api';
let sid=null,lang='en',view='chat',resTab='files',sessions={};
let presetKey='deepseek',provider='openai',model='deepseek-chat',baseUrl='https://api.deepseek.com/v1';
let pipelineSteps=[];
let userToken=localStorage.getItem('mitoflow_token')||'';
let userInfo=null;
try{userInfo=JSON.parse(localStorage.getItem('mitoflow_user')||'null')}catch(e){}

const PRESETS=[
  {k:'deepseek',n:'DeepSeek',i:'🦈',p:'openai',b:'https://api.deepseek.com/v1',m:['deepseek-chat','deepseek-reasoner'],d:'High value'},
  {k:'deepseek_code',n:'DeepSeek Code',i:'💻',p:'anthropic',b:'https://api.deepseek.com/anthropic',m:['deepseek-v4-pro','deepseek-v4-flash'],d:'Anthropic protocol'},
  {k:'kimicode',n:'Kimi Code',i:'🔧',p:'anthropic',b:'https://api.kimi.com/coding/',m:['K2.6'],d:'Coding'},
  {k:'zhipu',n:'GLM Zhipu',i:'🧠',p:'openai',b:'https://open.bigmodel.cn/api/paas/v4',m:['glm-4-plus','glm-4-flash'],d:'Chinese'},
  {k:'moonshot',n:'Kimi',i:'🌙',p:'openai',b:'https://api.moonshot.cn/v1',m:['moonshot-v1-8k','moonshot-v1-32k'],d:'Long ctx'},
  {k:'qwen',n:'Qwen',i:'☁️',p:'openai',b:'https://dashscope.aliyuncs.com/compatible-mode/v1',m:['qwen-plus','qwen-max'],d:'Alibaba'},
  {k:'openai',n:'OpenAI',i:'⚡',p:'openai',b:'https://api.openai.com/v1',m:['gpt-4o','gpt-4o-mini'],d:'All-around'},
  {k:'claude',n:'Claude',i:'🔮',p:'anthropic',b:'',m:['claude-sonnet-4-20250514'],d:'Best reasoning'},
  {k:'openrouter',n:'OpenRouter',i:'🌐',p:'openai',b:'https://openrouter.ai/api/v1',m:['deepseek/deepseek-chat'],d:'200+ models'},
  {k:'ollama',n:'Ollama',i:'🏠',p:'openai',b:'http://localhost:11434/v1',m:['llama3'],d:'Local'},
  {k:'custom',n:'Custom',i:'⚙️',p:'openai',b:'',m:[''],d:'Any endpoint'},
];
const MODULES=[
  {id:'annotate',name:'Annotation',icon:'🧬',desc:'HMM+BLAST gene prediction, tRNA/rRNA, boundary correction',badge:'job'},
  {id:'qc',name:'Quality Check',icon:'✅',desc:'5-D quality assessment, gold standard comparison, F1 scoring',badge:'read'},
  {id:'cms',name:'CMS Detection',icon:'🌾',desc:'Chimeric ORF detection, ML scoring, PPR binding prediction',badge:'job'},
  {id:'rna_edit',name:'RNA Editing',icon:'✏️',desc:'C-to-U site prediction, flanking context, VCF output',badge:'read'},
  {id:'viz',name:'Visualization',icon:'📊',desc:'Circular/linear/OGDraw genome maps, GC profile, synteny visualization',badge:'read',params:['genbank','type']},
  {id:'synteny',name:'Synteny',icon:'🔗',desc:'Gene order comparison, rearrangement detection',badge:'read'},
  {id:'phylo',name:'Phylogenetics',icon:'🌳',desc:'IQ-TREE/MAFFT trees, Ka/Ks analysis',badge:'job'},
  {id:'repeat',name:'Repeats & NUMTs',icon:'🔄',desc:'Repeat detection, NUMT identification',badge:'read'},
  {id:'codon',name:'Codon Usage',icon:'📐',desc:'Codon bias, RSCU tables',badge:'read'},
  {id:'multiconf',name:'Multi-Config',icon:'🔀',desc:'Multi-configuration genome analysis',badge:'read'},
  {id:'mtpt',name:'MTPT Transfer',icon:'↔️',desc:'Mito→chloroplast gene transfer detection',badge:'read'},
  {id:'report',name:'Report',icon:'📄',desc:'HTML report aggregation',badge:'read'},
];
const SKILLS=[
  {id:'assembly',name:'Assembly',icon:'🧩',desc:'Raw reads → circular genome. GetOrganelle/NOVOPlasty/MITObim'},
  {id:'annotation',name:'Annotation',icon:'🧬',desc:'Full annotation pipeline with boundary correction and QC'},
  {id:'qc',name:'Quality Control',icon:'✅',desc:'A/B/C error classification, F1 scoring, gold standard comparison'},
  {id:'erc',name:'ERC Analysis',icon:'📈',desc:'OrthoFinder→MAFFT→IQ-TREE→ERCnet2 coevolution pipeline'},
  {id:'cms',name:'CMS Detection',icon:'🌾',desc:'Chimeric ORF→BLAST→ML scoring→PPR prediction'},
  {id:'comparative',name:'Comparative',icon:'🔗',desc:'Multi-species gene content, synteny, pan-genome'},
];
const T={en:{send:'Send',think:'Analyzing...',placeholder:'Ask about plant mitochondrial genomics...',sugs:["What does cox1 encode?","Which genes are trans-spliced?","What is CMS?","List assembly tools","Explain ERC analysis","How does RNA editing work?"]},zh:{send:'发送',think:'分析中...',placeholder:'询问植物线粒体基因组学问题...',sugs:["cox1 编码什么？","哪些基因需要反式剪接？","什么是CMS？","列出组装工具","解释ERC协进化","RNA编辑如何工作？"]}};

function $(id){return document.getElementById(id)}
function err(msg){$('authError').textContent=msg}
function go(v){view=v;['chat','tools','skills','files','results','settings'].forEach(function(x){var p=$('p'+x[0].toUpperCase()+x.slice(1));if(p)p.classList.toggle('on',x===v);var b=$('n'+x[0].toUpperCase()+x.slice(1));if(b)b.classList.toggle('on',x===v)});$('tbarTitle').textContent={chat:'Chat',tools:'Tools',skills:'Skills',files:'Upload',results:'Results',settings:'Settings'}[v]||v;if(v==='files')refreshFiles();if(v==='results')renderResultsPage();if(v==='tools')renderTools();if(v==='skills')renderSkills()}
function toggleDrawer(){$('drawer').classList.toggle('open')}
function toggleResults(){var rp=$('resultsPanel');if(!rp){console.log('resultsPanel not found');return}rp.classList.toggle('closed');var btn=$('nResults');if(btn){if(rp.classList.contains('closed')){btn.classList.remove('on')}else{btn.classList.add('on')}};if(!rp.classList.contains('closed')){refreshResFiles();renderPipe()}}
function setLang(l){lang=l;localStorage.setItem('mitoflow_lang',l);document.querySelectorAll('#langToggle button').forEach(function(b,i){b.classList.toggle('on',(i===0&&l==='en')||(i===1&&l==='zh'))});$('chatInput').placeholder=T[l].placeholder;$('sendBtn').textContent=T[l].send;renderSugs()}
function setProto(proto){provider=proto;localStorage.setItem('mitoflow_proto',proto);presetKey='';document.querySelectorAll('#protoToggle button').forEach(function(b,i){b.classList.toggle('on',(i===0&&proto==='openai')||(i===1&&proto==='anthropic'))});renderProviders();var first=PRESETS.filter(function(p){return p.p===proto})[0];if(first)selectProvider(first.k)}
function selectProvider(k){presetKey=k;localStorage.setItem('mitoflow_preset',k);var p=PRESETS.find(function(x){return x.k===k});if(p){provider=p.p;model=p.m[0];baseUrl=p.b;$('modelSelect').innerHTML=p.m.filter(function(m){return m}).map(function(m){return'<option>'+m+'</option>'}).join('');$('baseUrlInput').value=p.b;// Load per-provider API key
  var keys=loadApiKeys();var saved=keys[k]||'';$('apiKeyInput').value=saved}renderProviders()}
function renderProviders(){var filtered=PRESETS.filter(function(p){return p.p===provider});$('providerGrid').innerHTML=filtered.map(function(p){return'<div class="pcard'+(p.k===presetKey?' sel':'')+'" onclick="selectProvider(\''+p.k+'\')"><span>'+p.i+'</span><div><div style="font-weight:600">'+p.n+'</div><div style="font-size:.68rem;color:var(--sub)">'+p.d+'</div></div></div>'}).join('');if(!presetKey&&filtered.length)selectProvider(filtered[0].k)}
// Per-provider API key storage
function loadApiKeys(){try{return JSON.parse(localStorage.getItem('mitoflow_apikeys')||'{}')}catch(e){return{}}}
function saveApiKeyForProvider(){if(!presetKey)return;var keys=loadApiKeys();var v=$('apiKeyInput').value.trim();if(v)keys[presetKey]=v;else delete keys[presetKey];localStorage.setItem('mitoflow_apikeys',JSON.stringify(keys));
  // Also save to account if logged in
  if(userToken){try{fetch(API+'/auth/api-key',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+userToken},body:JSON.stringify({api_key:v})})}catch(e){}}}
function switchResTab(t){resTab=t;['files','preview','pipeline'].forEach(x=>{const b=$('rt'+x[0].toUpperCase()+x.slice(1));if(b)b.classList.toggle('on',x===t)});renderResContent()}

// ── Auth ──
function switchAuthTab(tab){
  document.querySelectorAll('#authPage .auth-tab').forEach(b=>b.classList.toggle('on',b.id==='tab'+tab[0].toUpperCase()+tab.slice(1)));
  $('authLogin').style.display=tab==='login'?'':'none';
  $('authRegister').style.display=tab==='login'?'none':'';
  $('authError').textContent='';
}

async function doRegister(){
  const e=$('regEmail').value.trim(),u=$('regUser').value.trim(),p=$('regPass').value;
  if(!e||!u||!p){err('Please fill all fields.');return}
  if(p.length<6){err('Password must be at least 6 characters.');return}
  try{
    const r=await fetch(API+'/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e,username:u,password:p})});
    const d=await r.json();
    if(r.ok){err('');alert('Registration successful! Please login.');switchAuthTab('login');$('loginEmail').value=e}
    else err(d.detail||d.error||'Registration failed');
  }catch(x){err('Network error. Is the server running?')}
}

async function doLogin(){
  const emailEl=$('loginEmail'),passEl=$('loginPass');
  if(!emailEl||!passEl){err('Login form not loaded. Please refresh the page.');return}
  const e=emailEl.value.trim(),p=passEl.value;
  if(!e||!p){err('Enter email and password.');return}
  err('');
  try{
    const r=await fetch(API+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({email:e,password:p})});
    const d=await r.json();
    if(r.ok&&d.token){
      userToken=d.token;userInfo=d.user;
      localStorage.setItem('mitoflow_token',userToken);
      localStorage.setItem('mitoflow_user',JSON.stringify(userInfo));
      // Don't auto-set global API key — per-provider keys are loaded by selectProvider
      $('authPage').classList.add('hidden');
      $('appPage').classList.add('visible');
      const ub=$('userBtn');if(ub&&userInfo){ub.textContent=userInfo.username[0].toUpperCase();ub.title=userInfo.username}
      initApp();
    }else{err(d.detail||d.error||'Login failed: '+JSON.stringify(d).substring(0,100))}
  }catch(x){err('Network error: '+x.message+'. Check server.')}
}

function doLogout(){
  userToken='';userInfo=null;sid=null;sessions={};sessionList=[];
  localStorage.removeItem('mitoflow_token');localStorage.removeItem('mitoflow_user');
  localStorage.removeItem('mitoflow_sid');
  $('appPage').classList.remove('visible');
  $('authPage').classList.remove('hidden');
  $('authLogin').style.display='';$('authRegister').style.display='none';
  $('loginEmail').value='';$('loginPass').value='';
  switchAuthTab('login');
}


function showUserMenu(){
  if(!userInfo)return;
  const html=`<div style="background:var(--surface);border-radius:12px;padding:1rem;min-width:180px;text-align:center"><div style="font-weight:600">${userInfo.username}</div><div style="font-size:.75rem;color:var(--sub)">${userInfo.email}</div><button onclick="closeDialog();doLogout()" style="margin-top:.8rem;padding:.3rem 1rem;border:1px solid var(--red);border-radius:8px;background:transparent;color:var(--red);cursor:pointer;font-size:.8rem">Logout</button></div>`;
  showDialog('',html,false);
}

function showDialog(title,html,closable=true){closeDialog();const overlay=document.createElement('div');overlay.style.cssText='position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.4);z-index:100;display:flex;align-items:center;justify-content:center';overlay.id='dialogOverlay';
  if(closable)overlay.innerHTML=`<div style="background:var(--surface);border-radius:14px;max-width:500px;width:90%;box-shadow:0 20px 60px rgba(0,0,0,.2)"><div style="padding:.8rem 1rem;font-weight:600;border-bottom:1px solid var(--border);display:flex;justify-content:space-between">${title}<button onclick="closeDialog()" style="background:none;border:none;cursor:pointer;font-size:1.2rem">✕</button></div>${html}</div>`;
  else overlay.innerHTML=html;
  document.body.appendChild(overlay)}
function closeDialog(){const o=$('dialogOverlay');if(o)o.remove()}

// ── App Init ──
function initApp(){
  // Restore settings from localStorage
  var savedLang=localStorage.getItem('mitoflow_lang');if(savedLang)setLang(savedLang);
  var savedProto=localStorage.getItem('mitoflow_proto');if(savedProto){provider=savedProto;document.querySelectorAll('#protoToggle button').forEach(function(b,i){b.classList.toggle('on',(i===0&&savedProto==='openai')||(i===1&&savedProto==='anthropic'))})}
  var savedPreset=localStorage.getItem('mitoflow_preset');if(savedPreset)presetKey=savedPreset;
  $('modelSelect').onchange=function(){model=this.value;localStorage.setItem('mitoflow_model',model)};
  $('baseUrlInput').oninput=function(){baseUrl=this.value};
  $('apiKeyInput').addEventListener('blur',function(){saveApiKeyForProvider()});
  $('chatInput').addEventListener('input',function(){this.style.height='40px';this.style.height=Math.min(this.scrollHeight,140)+'px'});
  renderSugs();renderProviders();renderTools();renderSkills();
  if(presetKey){selectProvider(presetKey)}else{var first=PRESETS[0];if(first)selectProvider(first.k)}
  checkHealth();loadSessions();renderResContent();
}

// ── Sessions ──
async function loadSessions(){try{const r=await fetch(API+'/ai/sessions');if(r.ok){const d=await r.json();sessionList=d.sessions||[];renderSessions();// Auto-select last session if none active
  if(!sid&&sessionList.length>0){var lastId=localStorage.getItem('mitoflow_sid');if(lastId&&sessionList.find(function(s){return s.id===lastId})){selectSession(lastId)}}
}}catch(e){}}
let sessionList=[];
async function newSession(){try{const r=await fetch(API+'/ai/sessions',{method:'POST'});if(r.ok){const d=await r.json();sid=d.session_id;localStorage.setItem('mitoflow_sid',sid);sessionList.unshift({id:sid,name:sid.slice(0,8)+'...',first_message:'',pinned:false,created:Date.now()/1000});renderSessions();const m=$('chatMsgs'),w=$('welcomeBlock');if(m){m.innerHTML='';if(w){w.style.display='';m.appendChild(w)}}go('chat')}}catch(e){showErr('Session error: '+e.message)}}
async function selectSession(id){
  sid=id;localStorage.setItem('mitoflow_sid',sid);go('chat');
  const m=$('chatMsgs'),w=$('welcomeBlock');
  if(!m)return;m.innerHTML='<div style="text-align:center;color:var(--sub);padding:1rem">Loading...</div>';
  // Load messages from server
  try{
    const r=await fetch(API+'/ai/sessions/'+id+'/messages');
    if(r.ok){
      const d=await r.json();
      if(d.messages&&d.messages.length){
        if(w)w.style.display='none';m.innerHTML='';
        var userMsgs=[],aiMsgs=[];
        for(var i=0;i<d.messages.length;i++){
          var msg=d.messages[i];
          if(msg.role==='system')continue;
          if(msg.role==='user'){m.appendChild(msgEl('u',esc(msg.content)));userMsgs.push(msg)}
          else if(msg.role==='assistant'&&msg.content){m.appendChild(msgEl('a',md(msg.content)));aiMsgs.push(msg)}
          else if(msg.role==='tool'){
            var div=document.createElement('div');div.className='tool-card';
            div.innerHTML='<div class="tc-h">🔧 '+esc(msg.name||'tool')+'</div><div class="tc-b" style="display:block">'+esc(msg.content||'').substring(0,500)+'</div>';
            m.appendChild(div);
          }
        }
        scrollD();
      }else{if(w){w.style.display='';m.appendChild(w)}}
    }
  }catch(e){if(w){w.style.display='';m.innerHTML='';m.appendChild(w)}}
  renderSessions();refreshResFiles();
  // Load results
  loadResults();
}
async function renameSession(id,name){try{await fetch(API+'/ai/sessions/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({name})});const s=sessionList.find(x=>x.id===id);if(s)s.name=name;renderSessions()}catch(e){}}
async function pinSession(id,pinned){try{await fetch(API+'/ai/sessions/'+id,{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({pinned})});var s=sessionList.find(function(x){return x.id===id});if(s)s.pinned=pinned;renderSessions()}catch(e){}}
async function deleteSession(id){try{await fetch(API+'/ai/sessions/'+id,{method:'DELETE'});sessionList=sessionList.filter(function(x){return x.id!==id});if(sid===id){sid=null;localStorage.removeItem('mitoflow_sid');var m=$('chatMsgs');if(m)m.innerHTML='';var w=$('welcomeBlock');if(w){w.style.display='';if(m)m.appendChild(w)}}renderSessions()}catch(e){}}
function renderSessions(){
  var q=($('sessionSearch').value||'').toLowerCase();
  var f=q?sessionList.filter(function(s){var n=s.name||'';return n.toLowerCase().indexOf(q)>=0||s.id.indexOf(q)>=0}):sessionList;
  var h='';
  for(var i=0;i<f.length;i++){
    var s=f[i],raw=s.name||s.first_message||'',nm=raw?raw.substring(0,30):(s.id||'').slice(0,8)+'...',sel=s.id===sid?' sel':'',pin=s.pinned?'📌 ':'';
    h+='<div class="dr-item'+sel+'" data-sid="'+s.id+'" style="position:relative;padding-right:30px">'+pin+esc(nm);
    h+='<span class="sess-gear" data-sid="'+s.id+'" data-name="'+esc(nm)+'" data-pin="'+(s.pinned?1:0)+'" style="position:absolute;right:4px;top:50%;transform:translateY(-50%);cursor:pointer;font-size:.65rem;opacity:.4" title="Settings">⋯</span></div>';
  }
  $('sessionList').innerHTML=h||'<div style="color:var(--sub);font-size:.78rem;padding:.4rem">No sessions</div>';
  var items=$('sessionList').querySelectorAll('.dr-item');
  for(var j=0;j<items.length;j++){items[j].onclick=function(){selectSession(this.getAttribute('data-sid'))}}
  var gears=$('sessionList').querySelectorAll('.sess-gear');
  for(var k=0;k<gears.length;k++){gears[k].onclick=function(e){e.stopPropagation();showSessionMenu(this.getAttribute('data-sid'),this.getAttribute('data-name'),this.getAttribute('data-pin')==='1')}}
}
function showSessionMenu(id,name,pinned){
  var h='<div style="background:var(--surface);border-radius:12px;padding:1rem;min-width:200px;text-align:left">';
  h+='<div style="font-weight:600;margin-bottom:.8rem;font-size:.85rem">Session Settings</div>';
  h+='<div style="margin-bottom:.6rem"><input id="renameInput" value="'+esc(name)+'" style="width:100%;padding:.4rem;border:1px solid var(--border);border-radius:8px;font-size:.82rem"></div>';
  h+='<div style="display:flex;gap:.4rem;margin-bottom:.4rem">';
  h+='<button onclick="var v=document.getElementById(\'renameInput\').value;renameSession(\''+id+'\',v);closeDialog()" style="flex:1;padding:.4rem;background:var(--accent);color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:.8rem">Rename</button>';
  h+='<button onclick="pinSession(\''+id+'\','+(!pinned)+');closeDialog()" style="flex:1;padding:.4rem;background:'+(pinned?'var(--amber)':'#f0f4f8')+';color:'+(pinned?'#fff':'var(--text)')+';border:1px solid var(--border);border-radius:8px;cursor:pointer;font-size:.8rem">'+(pinned?'📌 Unpin':'📌 Pin')+'</button>';
  h+='</div>';
  h+='<button onclick="if(confirm(\'Delete this session? All chat history will be lost.\')){deleteSession(\''+id+'\');closeDialog()}" style="width:100%;padding:.35rem;background:transparent;color:var(--red);border:1px solid var(--red);border-radius:8px;cursor:pointer;font-size:.75rem">🗑 Delete Session</button>';
  h+='</div>';
  showDialog('',h,false);
}

// ── Chat ──
async function send(){const input=$('chatInput');if(!input)return;const text=input.value.trim();if(!text)return;input.value='';input.style.height='40px';
  if(!sid){try{const r=await fetch(API+'/ai/sessions',{method:'POST'});if(r.ok){const d=await r.json();sid=d.session_id;localStorage.setItem('mitoflow_sid',sid)}}catch(e){showErr('Cannot create session');return}}
  const wb=$('welcomeBlock');if(wb)wb.style.display='none';const ms=$('chatMsgs');if(!ms)return;
  ms.appendChild(msgEl('u',esc(text)));scrollD();
  var thk=document.createElement('div');thk.className='thk';thk.id='thk';
  thk.innerHTML='<span class="thk-d run"></span><span id="thkTxt">'+T[lang].think+'</span>';
  ms.appendChild(thk);scrollD();
  try{var payload={session_id:sid,message:text,provider:provider,model:model};var ak=$('apiKeyInput');if(ak&&ak.value)payload.api_key=ak.value;if(baseUrl)payload.base_url=baseUrl;
    var ctrl=new AbortController();var timer=setTimeout(function(){ctrl.abort()},120000);
    var r;try{r=await fetch(API+'/ai/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal:ctrl.signal})}catch(e){clearTimeout(timer);var tb=$('thk');if(tb)tb.remove();showErr('Request timeout');return}
    clearTimeout(timer);
    // Update thinking bar with tool chain summary
    var tb=$('thk');
    if(r.ok){var d=await r.json();var tools=d.tool_results||[];
      // Update thinking bar: show tool chain
      if(tb){
        if(tools.length){
          var chain=tools.map(function(t){return t.name}).join(' → ');
          tb.innerHTML='<span class="thk-d" style="background:var(--green)"></span><span style="font-size:.72rem;color:var(--accent)">🔗 '+chain+'</span>';
        }else{tb.innerHTML='<span class="thk-d" style="background:var(--green)"></span><span style="font-size:.72rem">Answered directly</span>'}
      }
      var ai=msgEl('a',md(d.final_text||'(empty)'));
      if(tools.length){var tw=document.createElement('div');for(var ti=0;ti<tools.length;ti++){tw.appendChild(tc(tools[ti].name,tools[ti].content))}ai.appendChild(tw)}
      ms.appendChild(ai);
      var toolsUsed=tools.map(function(t){return{name:t.name,content:(t.content||'').substring(0,60)}});
      var detail='';if(tools.length){detail=tools.map(function(t,i){return (i+1)+'. '+t.name+': '+(t.content||'').substring(0,80)}).join('\n')}
      var stepLabel='Q&A';
      if(tools.length){var tnames=tools.map(function(t){return t.name});
        if(tnames.join(' ').indexOf('annotation')>=0||tnames.join(' ').indexOf('run_annotation')>=0)stepLabel='🧬 Annotation';
        else if(tnames.join(' ').indexOf('visual')>=0)stepLabel='📊 Visualization';
        else if(tnames.join(' ').indexOf('upload')>=0||tnames.join(' ').indexOf('workspace')>=0)stepLabel='📤 Data Upload';
        else if(tnames.join(' ').indexOf('qc')>=0)stepLabel='✅ Quality Check';
        else stepLabel='🔍 Analysis';
      }
      addStep(stepLabel,tools.length?tools.length+' tool(s) called':'Direct answer',detail,toolsUsed);
      loadResults();
    }else{var em='Error '+r.status;try{var ed=await r.json();em=ed.detail||em}catch(_){}showErr(em)}
  }catch(e){var tb2=$('thk');if(tb2)tb2.remove();showErr('Network: '+e.message)}
  scrollD();loadSessions()}
function msgEl(role,txt){const w=document.createElement('div');w.className='msg-w';const d=document.createElement('div');d.className='msg '+(role==='u'?'u':'a');d.innerHTML=role==='a'?md(txt):txt;w.appendChild(d);return w}
function tc(name,content){const c=document.createElement('div');c.className='tool-card open';c.innerHTML=`<div class="tc-h" onclick="this.parentElement.classList.toggle('open')">🔧 ${name}</div><div class="tc-b">${esc(content)}</div>`;return c}
function showErr(msg){const d=msgEl('a','❌ '+esc(msg));const inner=d.querySelector('.msg');if(inner){inner.style.background='#fef2f2';inner.style.borderColor='#fecaca';inner.style.color='#dc2626'}const ms=$('chatMsgs');if(ms)ms.appendChild(d);scrollD()}
function scrollD(){const c=$('chatMsgs');if(c)setTimeout(()=>c.scrollTop=c.scrollHeight,50)}
function quickAsk(q){$('chatInput').value=q;send()}
function quickUpload(){const fi=$('fileInput');if(fi)fi.click()}
function esc(s){return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/'/g,'&#39;')}
function md(t){if(!t)return'';let o=t;o=o.replace(/^### (.+)$/gm,'<h3>$1</h3>');o=o.replace(/^## (.+)$/gm,'<h2>$1</h2>');o=o.replace(/^# (.+)$/gm,'<h1>$1</h1>');o=o.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>');o=o.replace(/`([^`\n]+)`/g,'<code>$1</code>');o=o.replace(/\[([^\]]+)\]\(([^)]+)\)/g,'<a href="$2" target="_blank">$1</a>');
  if(/\|.+\|/.test(o)){let rows=o.split('\n'),th='',inTable=false,inHead=false;for(let i=0;i<rows.length;i++){let r=rows[i].trim();if(r.startsWith('|')&&r.endsWith('|')){if(!inTable){inTable=true;inHead=true;th+='<table><thead>'}let cells=r.split('|').filter(c=>c.trim()).map(c=>c.trim());if(/^[\s\-:]+$/.test(cells[0]||'')){inHead=false;th+='</thead><tbody>';continue}let tag=inHead?'th':'td';th+='<tr>'+cells.map(c=>'<'+tag+'>'+c+'</'+tag+'>').join('')+'</tr>'}else{if(inTable){inTable=false;th+='</tbody></table>';rows[i]=th+'\n'+r}}if(i===rows.length-1&&inTable){th+='</tbody></table>';rows.push(th)}}o=rows.join('\n')}
  o=o.replace(/^- (.+)$/gm,'<li>$1</li>');o=o.replace(/((?:<li>.*<\/li>\n?)+)/g,'<ul>$1</ul>');
  if(!/<table/.test(o)&&!/<br>/.test(o)&&!/<a href/.test(o)){o=o.replace(/\n\n/g,'<br><br>');o=o.replace(/\n/g,'<br>')}return o}

// ── Tools & Skills ──
function renderTools(){$('toolsCards').innerHTML=MODULES.map(m=>`<div class="card"><div class="icon">${m.icon}</div><div class="name">${m.name}</div><div class="desc">${m.desc}</div><div class="actions"><button class="act ai" onclick="runAI('${m.id}')">🤖 AI Auto</button><button class="act" onclick="runManual('${m.id}')">🔧 Manual</button><button class="act" onclick="go('results')">📊 Results</button></div><span class="badge badge-${m.badge==='job'?'job':'read'}">${m.badge==='job'?'launches job':'read only'}</span></div>`).join('')}
function renderSkills(){$('skillsCards').innerHTML=SKILLS.map(s=>`<div class="card"><div class="icon">${s.icon}</div><div class="name">${s.name}</div><div class="desc">${s.desc}</div><div class="actions"><button class="act ai" onclick="runAI('${s.id}')">🤖 AI Auto</button><button class="act" onclick="runManual('${s.id}')">🔧 Manual</button><button class="act" onclick="go('results')">📊 Results</button></div></div>`).join('')}
function runAI(id){const m=MODULES.find(x=>x.id===id)||SKILLS.find(x=>x.id===id);if(m){$('chatInput').value=`Run the ${m.name} module on my data.`;go('chat');send()}}
function runManual(id){var m=MODULES.find(function(x){return x.id===id})||SKILLS.find(function(x){return x.id===id});if(!m)return;showDialog(m.name+' Configuration','<div style="padding:.5rem"><p style="font-size:.82rem;color:var(--sub);margin-bottom:.5rem">Configure '+m.name+':</p><button onclick="closeDialog();runAI(\''+id+'\')" style="margin-top:.5rem;padding:.4rem 1rem;background:var(--accent);color:#fff;border:none;border-radius:8px;cursor:pointer">Run with AI</button></div>')}

// ── Files ──
async function uploadFiles(fl){if(!fl||!fl.length)return;if(!sid){try{const r=await fetch(API+'/ai/sessions',{method:'POST'});if(r.ok){const d=await r.json();sid=d.session_id;sessions[sid]={}}}catch(e){showErr('Create session first');return}}
  const fd=new FormData();fd.append('session_id',sid);for(const f of fl)fd.append('files',f);const z=$('uploadZone');if(z)z.style.opacity='0.5';
  try{const r=await fetch(API+'/files/upload',{method:'POST',body:fd});if(r.ok){const d=await r.json();if(d.errors&&d.errors.length)d.errors.forEach(e=>showErr('Upload: '+e));if(d.uploaded&&d.uploaded.length){refreshFiles();refreshResFiles();addStep('📤 Data Upload',d.uploaded.length+' file(s) uploaded',d.uploaded.map(function(f){return f.name}).join(', '))}}}catch(e){showErr('Upload: '+e.message)}
  if(z)z.style.opacity='1';$('fileInput').value='';$('dirInput').value=''}
function handleDrop(e){e.preventDefault();const z=$('uploadZone');if(z){z.style.borderColor='var(--border)';z.style.background='var(--surface)'}if(e.dataTransfer.files.length)uploadFiles(e.dataTransfer.files)}
async function refreshFiles(){
  var fl=$('fileList');if(!fl)return;fl.innerHTML='<div style="text-align:center;color:var(--sub);padding:1rem">Loading...</div>';
  // Show uploaded files organized by session
  try{
    var r=await fetch(API+'/ai/sessions');if(!r.ok){fl.innerHTML='<div style="color:var(--sub);text-align:center;padding:1rem">No sessions</div>';return}
    var d=await r.json();var sessions=d.sessions||[];var h='';var hasFiles=false;
    for(var i=0;i<sessions.length;i++){
      var s=sessions[i];
      try{
        var fr=await fetch(API+'/files/list?session_id='+s.id);
        if(fr.ok){var fd=await fr.json();if(fd.files&&fd.files.length){
          hasFiles=true;var sname=s.name||s.first_message||s.id.slice(0,8)+'...';
          h+='<div style="margin-bottom:.8rem;border:1px solid var(--border);border-radius:10px;overflow:hidden">';
          h+='<div style="padding:.5rem .8rem;background:#f8fafb;font-weight:600;font-size:.8rem;display:flex;align-items:center;gap:.4rem;cursor:pointer" onclick="var el=this.nextElementSibling;if(el)el.style.display=el.style.display===\'none\'?\'\':\'none\'">📤 '+esc(sname)+' <span style="font-weight:400;color:var(--sub);font-size:.7rem">('+fd.files.length+' files)</span></div>';
          h+='<div style="padding:.3rem .6rem">';
          for(var j=0;j<fd.files.length;j++){var f=fd.files[j],icon=fi(f.type),sz=f.size>1048576?(f.size/1048576).toFixed(1)+' MB':(f.size/1024).toFixed(0)+' KB';
            h+='<div style="display:flex;align-items:center;gap:.5rem;padding:.3rem .4rem;cursor:pointer;border-radius:4px;font-size:.75rem" onmouseover="this.style.background=\'#f0f4f8\'" onmouseout="this.style.background=\'transparent\'"><span>'+icon+'</span><span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+esc(f.name)+'</span><span style="font-size:.65rem;color:var(--sub)">'+sz+'</span><button onclick="previewFile(\''+esc(f.name)+'\')" style="background:none;border:none;cursor:pointer;font-size:.7rem">👁</button><button onclick="delFile(\''+esc(f.name)+'\')" style="background:none;border:none;cursor:pointer;font-size:.7rem">🗑</button></div>';
          }
          h+='</div></div>';
        }}
      }catch(e){}
    }
    fl.innerHTML=h||'<div style="color:var(--sub);text-align:center;padding:2rem">No uploaded files. Upload FASTA/GenBank files in a chat session.</div>';
  }catch(e){fl.innerHTML='<div style="color:var(--red);text-align:center;padding:1rem">Error loading files</div>'}
}
async function refreshResFiles(){
  if(resTab!=='files')return;
  var ssid=sid||'default',rc=$('resContent');if(!rc)return;
  rc.innerHTML='<div style="text-align:center;color:var(--sub);padding:.5rem;font-size:.7rem">Loading...</div>';
  var h='',hasAny=false;
  // ── Uploaded files ──
  try{
    var r=await fetch(API+'/files/list?session_id='+ssid);
    if(r.ok){var d=await r.json();if(d.files&&d.files.length){
      h+='<div style="font-weight:600;margin-bottom:.3rem;font-size:.7rem;color:var(--accent)">📤 Uploaded</div>';
      for(var i=0;i<d.files.length;i++){var f=d.files[i],icon=fi(f.type),sz=f.size>1048576?(f.size/1048576).toFixed(1)+' MB':(f.size/1024).toFixed(0)+' KB';
        h+='<div onclick="previewFile(\''+esc(f.name)+'\')" style="padding:.2rem .3rem;cursor:pointer;border-radius:3px;font-size:.65rem;display:flex;align-items:center;gap:.2rem" onmouseover="this.style.background=\'#f0f4f8\'" onmouseout="this.style.background=\'transparent\'"><span>'+icon+'</span>'+esc(f.name)+' <span style="color:var(--sub);font-size:.6rem;margin-left:auto">'+sz+'</span></div>';
      }
      hasAny=true;
    }}
  }catch(e){}
  // ── Analysis Results ──
  try{
    var rr=await fetch(API+'/ai/sessions/'+ssid+'/results');
    if(rr.ok){var rd=await rr.json();window._lastResults=rd.results||[];
      if(rd.results&&rd.results.length){
        var tree={};
        for(var j=0;j<rd.results.length;j++){
          var parts=rd.results[j].path.split('/'),node=tree;
          for(var k=0;k<parts.length;k++){
            if(!node[parts[k]])node[parts[k]]=k===parts.length-1?{_files:rd.results[j].files,_base:rd.results[j].base,_full:rd.results[j].path}:{};
            node=node[parts[k]];
          }
        }
        h+='<div style="font-weight:600;margin:.6rem 0 .2rem;font-size:.7rem;color:var(--accent)">📊 Results</div>';
        _treeId=0;
        try{h+=renderTree(tree,ssid,0)}catch(e2){h+='<div style="color:var(--red);font-size:.6rem">Tree error</div>'}
        hasAny=true;
      }
    }
  }catch(e){}
  rc.innerHTML=h||'<div style="color:var(--sub);text-align:center;padding:1rem;font-size:.7rem">No files or results for this session.</div>';
}

var _treeId=0;
function renderTree(node,ssid,depth){
  var h='',keys=Object.keys(node).filter(function(k){return k[0]!=='_'}).sort();
  for(var i=0;i<keys.length;i++){
    var k=keys[i],v=node[k];
    _treeId++;
    if(v._files){
      var fid='t'+_treeId;
      h+='<div style="cursor:pointer;font-size:.7rem;padding:.15rem 0" onclick="var el=document.getElementById(\''+fid+'\');if(el)el.style.display=el.style.display===\'none\'?\'\':\'none\'">📁 <strong>'+k+'</strong> <span style="color:var(--sub);font-size:.65rem">('+v._files.length+' files)</span></div>';
      h+='<div id="'+fid+'" style="display:none;padding-left:.8rem">';
      for(var fi=0;fi<v._files.length;fi++){
        var f=v._files[fi];
        h+='<div onclick="previewResultFile(\''+esc(v._full)+'/'+esc(f.name)+'\')" style="padding:.15rem .3rem;cursor:pointer;border-radius:3px;font-size:.65rem;display:flex;align-items:center;gap:.2rem;word-break:break-all" onmouseover="this.style.background=\'#f0f4f8\'" onmouseout="this.style.background=\'transparent\'"><span>'+fi(f.type||'')+'</span>'+esc(f.name)+'</div>';
      }
      h+='</div>';
    }else{
      var fid='t'+_treeId;
      h+='<div style="cursor:pointer;font-size:.7rem;padding:.15rem 0" onclick="var el=document.getElementById(\''+fid+'\');if(el)el.style.display=el.style.display===\'none\'?\'\':\'none\'">📁 '+k+'</div>';
      h+='<div id="'+fid+'" style="display:none;padding-left:.8rem">'+renderTree(v,ssid,depth+1)+'</div>';
    }
  }
  return h;
}

async function previewResultFile(fullPath){
  if(!sid)return;switchResTab('preview');
  var rc=$('resContent');if(!rc)return;
  rc.innerHTML='<div style="text-align:center;color:var(--sub);padding:1rem">Loading...</div>';
  try{
    var r=await fetch(API+'/ai/sessions/'+sid+'/results/download?path='+encodeURIComponent(fullPath));
    if(r.ok){
      var t=await r.text();
      var ext=(fullPath.split('.').pop()||'').toLowerCase();
      if(['png','jpg','jpeg','svg','gif'].indexOf(ext)>=0){
        rc.innerHTML='<div style="font-weight:600;margin-bottom:.3rem;font-size:.73rem">🖼️ '+esc(fullPath.split('/').pop())+'</div><button onclick="go(\'results\')" style="margin-bottom:.4rem;padding:.2rem .5rem;font-size:.65rem;border:1px solid var(--border);border-radius:4px;cursor:pointer;background:var(--surface)">📊 Open in Results</button><img src="'+API+'/ai/sessions/'+sid+'/results/download?path='+encodeURIComponent(fullPath)+'" style="max-width:100%;border-radius:6px" onerror="this.parentElement.innerHTML+=\'<div style=color:var(--red)>Failed to load</div>\'">';
      }else{
        rc.innerHTML='<div style="font-weight:600;margin-bottom:.3rem;font-size:.73rem">📄 '+esc(fullPath.split('/').pop())+'</div><button onclick="go(\'results\')" style="margin-bottom:.4rem;padding:.2rem .5rem;font-size:.65rem;border:1px solid var(--border);border-radius:4px;cursor:pointer;background:var(--surface)">📊 Open in Results</button><pre style="background:#f8fafb;padding:.5rem;border-radius:6px;overflow:auto;max-height:65vh;font-size:.68rem;white-space:pre-wrap">'+esc(t.substring(0,10000))+'</pre>';
      }
    }else{rc.innerHTML='<div style="color:var(--red);font-size:.75rem">Failed to load file</div>'}
  }catch(e){rc.innerHTML='<div style="color:var(--red);font-size:.75rem">Error: '+e.message+'</div>'}
}
function fi(ext){const m={'.fasta':'🧬','.fa':'🧬','.fna':'🧬','.gb':'📗','.gbk':'📗','.gff':'📋','.gff3':'📋','.fq':'📊','.fastq':'📊','.vcf':'🧪','.bam':'📦','.csv':'📊','.tsv':'📊','.nwk':'🌳','.treefile':'🌳','.zip':'📦','.png':'🖼️','.jpg':'🖼️','.svg':'🖼️','.pdf':'📄','.txt':'📝'};return m[ext]||'📎'}
async function delFile(name){const ssid=sid||'default';try{await fetch(API+'/files/'+encodeURIComponent(name)+'?session_id='+ssid,{method:'DELETE'});refreshFiles();refreshResFiles()}catch(e){}}
async function previewFile(name){const ssid=sid||'default';const ext=(name.split('.').pop()||'').toLowerCase();switchResTab('preview');const rc=$('resContent');if(!rc)return;
  if(['png','jpg','jpeg','svg','gif','webp'].includes(ext)){rc.innerHTML=`<div style="font-weight:600;margin-bottom:.4rem">🖼️ ${name}</div><img src="${API}/files/download/${encodeURIComponent(name)}?session_id=${ssid}" onerror="this.parentElement.innerHTML+='<div style=color:var(--red)>Failed to load</div>'">`}
  else if(['md','txt','csv','tsv','gff','gff3','vcf','nwk','treefile','json','xml'].includes(ext)){try{const r=await fetch(API+'/files/download/'+encodeURIComponent(name)+'?session_id='+ssid);if(r.ok){const t=await r.text();rc.innerHTML=`<div style="font-weight:600;margin-bottom:.4rem">📄 ${name}</div><pre style="background:#f8fafb;padding:.6rem;border-radius:8px;overflow:auto;max-height:70vh;font-size:.75rem;white-space:pre-wrap">${esc(t)}</pre>`}}catch(e){rc.innerHTML='<div style="color:var(--red)">Preview failed</div>'}}
  else{rc.innerHTML=`<div style="text-align:center;padding:2rem;color:var(--sub)"><div style="font-size:3rem">📎</div><div style="margin:.5rem 0">${name}</div><a href="${API}/files/download/${encodeURIComponent(name)}?session_id=${ssid}" download style="color:var(--accent)">Download</a></div>`}}

async function loadResults(){
  if(!sid)return;
  try{
    var r=await fetch(API+'/ai/sessions/'+sid+'/results');
    if(r.ok){var d=await r.json();window._lastResults=d.results||[];refreshResFiles();renderPipe()}
  }catch(e){}
}

function addStep(module,result,detail,toolsUsed){
  pipelineSteps.push({module,status:'done',output:result,time:new Date().toLocaleTimeString(),detail:detail||'',tools:toolsUsed||[]});
  if(resTab==='pipeline')renderPipe();
}
function renderPipe(){
  var rc=$('resContent');if(!rc)return;
  var h='<div style="font-weight:600;margin-bottom:.5rem;font-size:.73rem;color:var(--accent)">▸ Data Flow</div>';
  if(!pipelineSteps.length){
    h+='<div style="color:var(--sub);text-align:center;padding:1rem;font-size:.7rem;line-height:1.5">Analysis flow appears here as you work.</div>';
  } else {
    for(var i=0;i<pipelineSteps.length;i++){
      var s=pipelineSteps[i];
      h+='<div style="padding:.4rem .5rem;margin:.2rem 0;background:#fff;border:1px solid var(--border);border-radius:8px;border-left:3px solid var(--accent)">';
      h+='<div style="font-weight:600;font-size:.72rem">'+(i+1)+'. '+s.module+'</div>';
      h+='<div style="font-size:.63rem;color:var(--sub);line-height:1.3;margin-top:.1rem">'+s.output+'</div>';
      if(s.tools&&s.tools.length){
        h+='<div style="margin-top:.15rem">';
        for(var ti=0;ti<s.tools.length;ti++){
          h+='<span style="display:inline-block;background:#eef2ff;color:var(--accent);padding:1px 4px;border-radius:3px;margin:1px;font-size:.6rem">'+s.tools[ti].name+'</span>';
        }
        h+='</div>';
      }
      h+='<div style="font-size:.58rem;color:var(--sub);margin-top:.1rem">'+s.time+'</div>';
      h+='</div>';
    }
  }
  rc.innerHTML=h;
}

async function renderResultsPage(){
  var rc=$('resultsPageContent');if(!rc)return;rc.innerHTML='<div style="text-align:center;color:var(--sub);padding:2rem">Loading...</div>';
  // Group results by session
  try{
    var r=await fetch(API+'/ai/sessions');if(!r.ok){rc.innerHTML='<div style="color:var(--sub);text-align:center;padding:2rem">No sessions</div>';return}
    var d=await r.json();var sessions=d.sessions||[];
    var h='';
    for(var i=0;i<sessions.length;i++){
      var s=sessions[i];
      try{
        var rr=await fetch(API+'/ai/sessions/'+s.id+'/results');
        if(rr.ok){var rd=await rr.json();if(rd.results&&rd.results.length){
          var sname=s.name||s.first_message||s.id.slice(0,8)+'...';
          h+='<div style="margin-bottom:1rem;border:1px solid var(--border);border-radius:12px;overflow:hidden">';
          h+='<div style="padding:.6rem 1rem;background:#f0fdf4;font-weight:600;font-size:.85rem;display:flex;align-items:center;gap:.5rem;cursor:pointer" onclick="var el=this.nextElementSibling;if(el)el.style.display=el.style.display===\'none\'?\'\':\'none\'">📊 '+esc(sname)+' <span style="font-weight:400;color:var(--sub);font-size:.72rem">('+rd.results.length+' dirs)</span></div>';
          h+='<div style="padding:.5rem 1rem;display:block">';
          for(var j=0;j<rd.results.length;j++){
            var rd_=rd.results[j],nms=rd_.files.slice(0,5).map(function(f_){return f_.name}).join(', ');
            if(rd_.files.length>5)nms+=', +'+(rd_.files.length-5)+' more';
            h+='<div style="padding:.4rem .6rem;margin:.2rem 0;background:var(--surface);border:1px solid var(--border);border-radius:8px;cursor:pointer" onclick="previewResultFile(\''+esc(rd_.path)+'/'+esc(rd_.files[0]&&rd_.files[0].name||'')+'\')">';
            h+='📁 <strong>'+esc(rd_.path)+'</strong> <span style="color:var(--sub);font-size:.72rem">('+rd_.files.length+' files)</span>';
            h+='<div style="font-size:.7rem;color:var(--sub);margin-top:.15rem">'+esc(nms)+'</div></div>';
          }
          h+='</div></div>';
        }}
      }catch(e){}
    }
    rc.innerHTML=h||'<div style="color:var(--sub);text-align:center;padding:2rem">No analysis results yet. Run annotation or other modules to see outputs here.</div>';
  }catch(e){rc.innerHTML='<div style="color:var(--red);text-align:center;padding:2rem">Error loading results</div>'}
}

function renderResContent(){
  if(resTab==='files')refreshResFiles();
  else if(resTab==='pipeline'){renderPipe();}
  else{$('resContent').innerHTML='<div style="color:var(--sub);text-align:center;padding:2rem">Click a file in 📁 Files to preview</div>'}
}
async function checkHealth(){try{const r=await fetch(API+'/health');const d=$('statusDot');if(d)d.className=r.ok?'sdot on':'sdot off';$('statusText').textContent=r.ok?'Connected':'Offline'}catch(e){const d=$('statusDot');if(d)d.className='sdot off';$('statusText').textContent='Offline'}}
setInterval(checkHealth,30000);
function renderSugs(){$('suggestions').innerHTML=T[lang].sugs.map(s=>`<span class="sug" onclick="quickAsk('${s}')">${s}</span>`).join('')}

// ── Startup ──
(function startup(){
  if(userToken&&userInfo){
    fetch(API+'/auth/me',{method:'POST',headers:{'Authorization':'Bearer '+userToken}}).then(r=>{
      if(r.ok){return r.json().then(u=>{userInfo=u;localStorage.setItem('mitoflow_user',JSON.stringify(u))})}
      else throw new Error('invalid')
    }).then(()=>{
      $('authPage').classList.add('hidden');
      $('appPage').classList.add('visible');
      const ub=$('userBtn');if(ub&&userInfo){ub.textContent=userInfo.username[0].toUpperCase();ub.title=userInfo.username}
      initApp();
    }).catch(()=>{
      localStorage.removeItem('mitoflow_token');localStorage.removeItem('mitoflow_user');
      userToken='';userInfo=null;
    })
  }
  // Auth page is always visible by default if not auto-logged-in
})();
</script>
</body>
</html>"""
