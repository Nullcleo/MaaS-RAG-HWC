import os, json, requests
import streamlit as st
from datetime import datetime

st.set_page_config(
    page_title="MineraAndes · Asistente IA",
    page_icon="⛏️", layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"], [data-testid="stMain"] {
    background-color: #f5f0e8 !important; color: #1a1a1a !important;
}
[data-testid="stSidebar"] { background-color: #fff !important; border-right:1px solid #d4c9b0; }
[data-testid="stSidebar"] * { color: #1a1a1a !important; }
.mine-header {
    background: linear-gradient(135deg, #2d1b00 0%, #5c3a00 100%);
    color:white!important; padding:18px 24px; border-radius:14px; margin-bottom:20px;
}
.mine-header h2 { margin:0; font-size:22px; color:white!important; }
.mine-header p  { margin:4px 0 0; font-size:13px; opacity:.8; color:white!important; }
.bubble-user {
    background:#5c3a00; color:white!important;
    padding:12px 16px; border-radius:18px 18px 4px 18px;
    margin:8px 0 4px auto; max-width:72%; font-size:14px;
    line-height:1.6; width:fit-content; margin-left:auto;
}
.bubble-bot {
    background:#fff; color:#1a1a1a!important;
    padding:12px 16px; border-radius:18px 18px 18px 4px;
    margin:8px auto 4px 0; max-width:80%; font-size:14px;
    line-height:1.6; border:1px solid #d4c9b0;
    box-shadow:0 2px 6px rgba(0,0,0,.06); width:fit-content;
}
.meta { font-size:11px; color:#9e9e9e; margin:2px 6px 10px; }
.badge { display:inline-block; padding:2px 10px; border-radius:20px; font-size:11px; font-weight:600; margin:6px 3px 0; }
.badge-rds  { background:#fff3e0; color:#e65100; }
.badge-css  { background:#e8f5e9; color:#2e7d32; }
.badge-both { background:#fce4ec; color:#880e4f; }
.src { display:inline-block; padding:3px 10px; border-radius:20px; font-size:11px; margin:3px; }
.src-doc { background:#e8f5e9; color:#2e7d32; }
.src-rds { background:#fff3e0; color:#e65100; }
.empty { text-align:center; padding:60px 20px; color:#9e9e9e; }
.empty .icon { font-size:48px; }
.empty p { font-size:15px; margin-top:12px; line-height:1.7; }
</style>
""", unsafe_allow_html=True)

if "messages"   not in st.session_state: st.session_state.messages  = []
if "session_id" not in st.session_state:
    st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
if "documents"  not in st.session_state: st.session_state.documents = []

with st.sidebar:
    st.markdown("## ⛏️ MineraAndes IA")
    st.markdown("*Powered by Huawei Cloud*")
    st.divider()

    backend_url = st.text_input("Backend URL",
        value=os.environ.get("ECS_BACKEND_URL","http://localhost:8000"),
        label_visibility="collapsed")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("🔍 Conectar", use_container_width=True):
            try:
                r = requests.get(f"{backend_url}/health", timeout=5)
                st.success("✅ Online") if r.ok else st.error(f"HTTP {r.status_code}")
            except Exception as e: st.error(str(e))
    with c2:
        if st.button("🧹 Limpiar", use_container_width=True):
            st.session_state.messages = []
            st.session_state.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
            st.rerun()

    st.divider()
    st.markdown("**📄 Documentos indexados**")
    if st.button("🔄 Actualizar", use_container_width=True):
        try:
            r = requests.get(f"{backend_url}/documents", timeout=8)
            if r.ok: st.session_state.documents = r.json().get("documents",[])
        except: pass

    for doc in st.session_state.documents:
        name = doc.get("doc_name","").split("/")[-1]
        c1, c2 = st.columns([5,1])
        with c1: st.caption(f"📎 **{name}**\n{doc.get('chunk_count',0)} chunks")
        with c2:
            if st.button("✕", key=f"d_{doc['doc_id']}"):
                try: requests.delete(f"{backend_url}/documents/{doc['doc_id']}", timeout=8); st.rerun()
                except: pass

    if not st.session_state.documents:
        st.caption("Sin documentos.\nSube normativas al bucket OBS.")

    st.divider()
    st.markdown("**💡 Consultas de ejemplo**")
    examples = [
        "¿Qué equipos están parados o en mantenimiento?",
        "¿Cuáles son los incidentes críticos pendientes?",
        "¿Cuál fue la producción del turno día de hoy?",
        "¿Qué mantenimientos están urgentes?",
        "¿Qué equipos tienen más horas de operación?",
        "Incidentes en el tajo norte y protocolo de emergencia",
        "¿Qué dice el reglamento sobre trabajos en altura?",
        "Equipos parados en tajo sur y procedimiento de mantenimiento",
    ]
    for q in examples:
        if st.button(q, use_container_width=True, key=f"e_{q[:18]}"):
            st.session_state._pending = q
            st.rerun()

st.markdown(f"""
<div class="mine-header">
  <h2>⛏️ MineraAndes · Asistente Inteligente</h2>
  <p>Huawei Cloud · MaaS (DeepSeek) + CSS (OpenSearch) + RDS (PostgreSQL)
  · Sesión <b>{st.session_state.session_id}</b></p>
</div>
""", unsafe_allow_html=True)

if not st.session_state.messages:
    st.markdown("""
    <div class="empty">
      <div class="icon">⛏️</div>
      <p>Bienvenido al <b>Asistente Inteligente de MineraAndes</b>.<br>
      Consulto datos de equipos, producción, incidentes, mantenimiento y normativa.<br>
      <span style="font-size:13px">Usa los ejemplos del panel izquierdo o escribe tu consulta.</span>
      </p>
    </div>""", unsafe_allow_html=True)

for msg in st.session_state.messages:
    role=msg["role"]; content=msg["content"]; ts=msg.get("ts","")
    routing=msg.get("routing",{}); sources=msg.get("sources",[])

    if role == "user":
        st.markdown(
            f'<div class="bubble-user">{content}</div>'
            f'<div class="meta" style="text-align:right">{ts}</div>',
            unsafe_allow_html=True)
    else:
        targets=routing.get("targets",[])
        if "rds" in targets and "css" in targets:
            badge='<span class="badge badge-both">🗄️ Datos + 📋 Normativa</span>'
        elif "rds" in targets:
            badge='<span class="badge badge-rds">🗄️ Datos operativos</span>'
        elif "css" in targets:
            badge='<span class="badge badge-css">📋 Normativa</span>'
        else: badge=""

        src_html=""
        for s in sources:
            if s["type"]=="documento":
                name=s.get("name","").split("/")[-1]
                src_html+=f'<span class="src src-doc">📄 {name} ({s.get("score",0):.2f})</span>'
            else:
                src_html+='<span class="src src-rds">🗄️ RDS MineraAndes</span>'

        st.markdown(
            f'<div class="bubble-bot">{content}{badge}</div>'
            f'<div class="meta">🤖 DeepSeek via MaaS · {ts}'
            f'{"&nbsp;" + src_html if src_html else ""}</div>',
            unsafe_allow_html=True)

question = st.chat_input("Consulta sobre equipos, producción, incidentes, mantenimiento o normativa...")
if hasattr(st.session_state,"_pending") and st.session_state._pending:
    question=st.session_state._pending; del st.session_state._pending

if question:
    ts_now=datetime.now().strftime("%H:%M")
    st.session_state.messages.append({"role":"user","content":question,"ts":ts_now})

    st.markdown(
        f'<div class="bubble-user">{question}</div>'
        f'<div class="meta" style="text-align:right">{ts_now}</div>',
        unsafe_allow_html=True)

    answer_placeholder=st.empty()
    full_answer=""; routing_data={}; rds_results=[]; css_results=[]; sources=[]; first_chunk=True

    try:
        with requests.post(f"{backend_url}/chat/stream",
            json={"question":question,"session_id":st.session_state.session_id,"top_k":5},
            stream=True, timeout=120) as resp:
            resp.raise_for_status()
            buffer=""
            for chunk in resp.iter_content(chunk_size=64):
                if not chunk: continue
                text=chunk.decode("utf-8",errors="replace")
                if first_chunk:
                    buffer+=text
                    if "\n" in buffer:
                        first_line,rest=buffer.split("\n",1)
                        try:
                            data=json.loads(first_line)
                            routing_data=data.get("routing",{})
                            rds_results=data.get("rds_results",[])
                            css_results=data.get("css_results",[])
                            sources=data.get("sources",[])
                        except: rest=buffer
                        full_answer+=rest; first_chunk=False; buffer=""
                else: full_answer+=text
                answer_placeholder.markdown(
                    f'<div class="bubble-bot">{full_answer}▌</div>',
                    unsafe_allow_html=True)
        answer_placeholder.empty()
    except requests.exceptions.ConnectionError:
        st.error("❌ No se puede conectar al backend.")
        st.stop()
    except Exception as e:
        st.error(f"❌ Error: {e}"); st.stop()

    ts_ans=datetime.now().strftime("%H:%M")
    st.session_state.messages.append({
        "role":"assistant","content":full_answer,"ts":ts_ans,
        "routing":routing_data,"sources":sources,
        "rds_results":rds_results,"css_results":css_results})
    st.rerun()
