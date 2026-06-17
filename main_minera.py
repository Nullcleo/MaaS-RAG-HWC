import os, json, logging, decimal, concurrent.futures
from typing import Optional
import psycopg2, psycopg2.extras
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from opensearchpy import OpenSearch, RequestsHttpConnection
from openai import OpenAI
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="MineraAndes RAG", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

MAAS_API_KEY  = os.environ["MAAS_API_KEY"]
MAAS_BASE_URL = os.environ["MAAS_BASE_URL"]
MAAS_MODEL    = os.environ.get("MAAS_MODEL", "deepseek-v3.2")
CSS_INDEX     = os.environ.get("CSS_INDEX", "minera_docs")
TOP_K         = int(os.environ.get("TOP_K", 5))

_maas=None; _css=None; _embed=None

def get_maas():
    global _maas
    if not _maas: _maas = OpenAI(api_key=MAAS_API_KEY, base_url=MAAS_BASE_URL)
    return _maas

def get_css():
    global _css
    if not _css:
        _css = OpenSearch(
            hosts=[{"host": os.environ["CSS_HOST"], "port": int(os.environ.get("CSS_PORT",9200))}],
            http_auth=(os.environ.get("CSS_USER","admin"), os.environ.get("CSS_PASS","")),
            use_ssl=True, verify_certs=False, connection_class=RequestsHttpConnection)
    return _css

def get_embed():
    global _embed
    if not _embed:
        _embed = SentenceTransformer("all-MiniLM-L6-v2")
    return _embed

def get_rds():
    return psycopg2.connect(
        host=os.environ["RDS_HOST"], port=int(os.environ.get("RDS_PORT",5432)),
        user=os.environ["RDS_USER"], password=os.environ["RDS_PASS"],
        dbname=os.environ["RDS_DB"], cursor_factory=psycopg2.extras.RealDictCursor)

def dec(o):
    return float(o) if isinstance(o, decimal.Decimal) else str(o)

class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = None
    top_k: Optional[int] = TOP_K

ROUTER_PROMPT = """Eres el router de un sistema RAG para MineraAndes S.A., empresa minera peruana.
Analiza la pregunta y devuelve SOLO el JSON sin texto extra:
{"targets":["rds"],"sql_query":"SELECT ...","semantic_query":null,"reasoning":"..."}

Ejemplos:
Q: ¿Qué equipos están parados o en mantenimiento?
A: {"targets":["rds"],"sql_query":"SELECT codigo, nombre, tipo, area, estado, horas_operacion FROM equipos WHERE estado IN ('parado','mantenimiento') ORDER BY estado","semantic_query":null,"reasoning":"estado de equipos en RDS"}

Q: ¿Cuál fue la producción del turno día de hoy?
A: {"targets":["rds"],"sql_query":"SELECT area, turno, toneladas, ley_mineral, rendimiento, observaciones FROM produccion WHERE fecha=CURRENT_DATE AND turno='dia' ORDER BY area","semantic_query":null,"reasoning":"producción diaria en RDS"}

Q: ¿Cuáles son los incidentes críticos o altos pendientes?
A: {"targets":["rds"],"sql_query":"SELECT i.tipo, i.severidad, i.area, i.descripcion, i.estado, i.accion_tomada, i.fecha, p.nombre as personal FROM incidentes i LEFT JOIN personal p ON p.id=i.personal_id WHERE i.severidad IN ('critico','alto') AND i.estado != 'cerrado' ORDER BY i.fecha DESC","semantic_query":null,"reasoning":"incidentes críticos en RDS"}

Q: ¿Qué mantenimientos están urgentes o en proceso?
A: {"targets":["rds"],"sql_query":"SELECT e.codigo, e.nombre, m.tipo, m.descripcion, m.prioridad, m.estado, m.tecnico, m.costo FROM mantenimiento m JOIN equipos e ON e.id=m.equipo_id WHERE m.estado IN ('en_proceso','pendiente') ORDER BY m.prioridad DESC","semantic_query":null,"reasoning":"órdenes de mantenimiento en RDS"}

Q: ¿Cuál es el protocolo de emergencia para un accidente en el tajo?
A: {"targets":["css"],"sql_query":null,"semantic_query":"protocolo emergencia accidente tajo minas procedimiento","reasoning":"procedimiento en documentos normativos"}

Q: ¿Qué dice el reglamento sobre trabajos en altura?
A: {"targets":["css"],"sql_query":null,"semantic_query":"reglamento trabajos altura seguridad minera","reasoning":"normativa en documentos"}

Q: Hay un incidente en el tajo norte, ¿cuál es el protocolo de emergencia?
A: {"targets":["rds","css"],"sql_query":"SELECT tipo, severidad, area, descripcion, estado, accion_tomada FROM incidentes WHERE area='tajo_norte' AND estado != 'cerrado' ORDER BY fecha DESC LIMIT 5","semantic_query":"protocolo emergencia incidente tajo minera respuesta","reasoning":"datos del incidente en RDS + procedimiento en documentos"}

Q: ¿Qué equipos del tajo sur están parados y cuánto tiempo lleva la falla?
A: {"targets":["rds","css"],"sql_query":"SELECT e.codigo, e.nombre, e.estado, m.descripcion, m.fecha_inicio, m.prioridad FROM equipos e LEFT JOIN mantenimiento m ON m.equipo_id=e.id WHERE e.area='tajo_sur' AND e.estado IN ('parado','mantenimiento')","semantic_query":"procedimiento mantenimiento correctivo equipo parado","reasoning":"estado equipos en RDS + procedimiento en documentos"}

Schema RDS: equipos(id,codigo,nombre,tipo,area,estado,horas_operacion,ultima_revision), personal(id,nombre,cargo,area,turno,estado), produccion(id,fecha,turno,area,toneladas,ley_mineral,rendimiento,equipo_id,observaciones), incidentes(id,fecha,tipo,severidad,area,descripcion,personal_id,equipo_id,estado,accion_tomada), mantenimiento(id,equipo_id,tipo,descripcion,fecha_inicio,fecha_fin,tecnico,estado,costo,prioridad).

IMPORTANTE: Valores en minúsculas. estados equipos: operativo/mantenimiento/parado/standby. severidad: bajo/medio/alto/critico. turno: dia/noche. Solo devuelve el JSON."""

SYNTH_PROMPT = """Eres el asistente inteligente de MineraAndes S.A., empresa minera peruana.
Responde en español, de forma clara, profesional y concisa.
Usa solo la información del contexto provisto.
Para datos operativos (toneladas, ley mineral, rendimiento) presenta los resultados con unidades.
Si hay incidentes críticos o equipos parados, resáltalos con énfasis.
Si no hay información suficiente en el contexto, dilo claramente sin inventar datos."""

def route(question):
    r = get_maas().chat.completions.create(
        model=MAAS_MODEL,
        messages=[{"role":"system","content":ROUTER_PROMPT},{"role":"user","content":question}],
        max_tokens=300, temperature=0.0)
    raw = r.choices[0].message.content.strip().strip("```").lstrip("json").strip()
    try: return json.loads(raw)
    except: return {"targets":["css"],"sql_query":None,"semantic_query":question,"reasoning":"fallback"}

def qrds(sql):
    if not sql: return []
    try:
        import re
        sql = re.sub(r'```sql','',sql,flags=re.IGNORECASE)
        sql = re.sub(r'```','',sql).strip()
        match = re.search(r'(SELECT\s+.*)',sql,re.IGNORECASE|re.DOTALL)
        if match: sql = match.group(1).strip()
        conn=get_rds()
        with conn.cursor() as c: c.execute(sql); rows=c.fetchall()
        conn.close()
        return [{k: float(v) if isinstance(v,decimal.Decimal) else str(v) if hasattr(v,'isoformat') else v
                 for k,v in dict(r).items()} for r in rows]
    except Exception as e: return [{"error":str(e)}]

def qcss(q, k):
    if not q: return []
    try:
        vec = get_embed().encode(q, normalize_embeddings=True).tolist()
        r = get_css().search(index=CSS_INDEX, body={
            "size":k,"_source":["doc_name","content","chunk_idx"],
            "query":{"knn":{"embedding":{"vector":vec,"k":k}}}})
        return [{"doc_name":h["_source"].get("doc_name",""),"chunk_idx":h["_source"].get("chunk_idx",0),
                 "content":h["_source"].get("content",""),"score":round(h["_score"],4)}
                for h in r["hits"]["hits"]]
    except Exception as e: return [{"error":str(e)}]

def build_ctx(rds, css):
    parts=[]
    if rds and "error" not in (rds[0] if rds else {}):
        parts.append("DATOS OPERATIVOS (RDS):\n"+json.dumps(rds,ensure_ascii=False,default=dec))
    valid=[x for x in css if "error" not in x]
    if valid: parts.append("NORMATIVA Y PROCEDIMIENTOS (CSS):\n"+"---\n".join(
        f"[{x['doc_name']} chunk {x['chunk_idx']}]\n{x['content']}" for x in valid))
    return "\n\n".join(parts) or "Sin contexto disponible."

def stream_answer(question, ctx):
    s = get_maas().chat.completions.create(
        model=MAAS_MODEL,
        messages=[{"role":"system","content":SYNTH_PROMPT},
                  {"role":"user","content":f"CONSULTA: {question}\n\nCONTEXTO:\n{ctx}"}],
        max_tokens=1024, temperature=0.2, stream=True)
    for chunk in s:
        if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content

@app.get("/health")
def health(): return {"status":"ok","model":MAAS_MODEL,"empresa":"MineraAndes"}

@app.post("/chat/stream")
def chat_stream(req: ChatRequest):
    logger.info("STREAM — %s", req.question)
    routing = route(req.question)
    logger.info("Routing: %s", routing)
    targets = routing.get("targets",[])
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
        fr = ex.submit(qrds, routing.get("sql_query")) if "rds" in targets else None
        fc = ex.submit(qcss, routing.get("semantic_query", req.question), req.top_k or TOP_K) if "css" in targets else None
        rds_r = fr.result() if fr else []
        css_r = fc.result() if fc else []
    ctx = build_ctx(rds_r, css_r)
    sources=[]
    if rds_r and "error" not in (rds_r[0] if rds_r else {}): sources.append({"type":"base_de_datos","name":"RDS PostgreSQL"})
    for x in css_r:
        if "error" not in x: sources.append({"type":"documento","name":x.get("doc_name",""),"score":x.get("score",0)})
    def gen():
        yield json.dumps({"type":"routing","routing":routing,"rds_results":rds_r,"css_results":css_r,"sources":sources},
                         ensure_ascii=False,default=dec)+"\n"
        for token in stream_answer(req.question, ctx):
            yield token
    return StreamingResponse(gen(), media_type="text/plain")

@app.get("/documents")
def list_docs():
    try:
        conn=get_rds()
        with conn.cursor() as c: c.execute("SELECT doc_id,doc_name,obs_bucket,chunk_count,indexed_at::text FROM documentos ORDER BY indexed_at DESC LIMIT 50"); docs=[dict(r) for r in c.fetchall()]
        conn.close(); return {"documents":docs}
    except Exception as e: raise HTTPException(500, str(e))

@app.delete("/documents/{doc_id}")
def del_doc(doc_id: str):
    try: get_css().delete_by_query(index=CSS_INDEX, body={"query":{"term":{"doc_id":doc_id}}})
    except: pass
    try:
        conn=get_rds()
        with conn.cursor() as c: c.execute("DELETE FROM documentos WHERE doc_id=%s",(doc_id,))
        conn.commit(); conn.close()
    except Exception as e: raise HTTPException(500, str(e))
    return {"status":"ok","doc_id":doc_id}

@app.post("/ingest")
def ingest(body: dict):
    import base64, hashlib, fitz
    from datetime import datetime
    doc_name    = body.get("doc_name", "unknown.pdf")
    bucket      = body.get("bucket", "")
    content_b64 = body.get("content_b64", "")
    file_bytes  = base64.b64decode(content_b64)
    ext = os.path.splitext(doc_name.lower())[1]
    if ext == ".pdf":
        doc  = fitz.open(stream=file_bytes, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        doc.close()
    else:
        text = file_bytes.decode("utf-8", errors="ignore")
    if not text.strip():
        return {"status": "skipped", "reason": "texto vacío"}
    words=text.split(); chunks=[]; start=0; idx=0
    while start < len(words):
        end=min(start+800,len(words))
        chunks.append({"index":idx,"text":" ".join(words[start:end])})
        idx+=1; start+=700
    vectors = get_embed().encode([c["text"] for c in chunks], normalize_embeddings=True, show_progress_bar=False).tolist()
    css = get_css()
    try:
        css.indices.get(index=CSS_INDEX)
    except Exception:
        css.indices.create(index=CSS_INDEX, body={
            "settings":{"number_of_shards":1,"index.knn":True},
            "mappings":{"properties":{
                "doc_id":{"type":"keyword"},"doc_name":{"type":"text"},
                "chunk_idx":{"type":"integer"},"content":{"type":"text"},
                "embedding":{"type":"knn_vector","dimension":384,
                             "method":{"name":"hnsw","space_type":"cosinesimil","engine":"faiss"}},
                "indexed_at":{"type":"date"}}}})
    doc_id=hashlib.md5(doc_name.encode()).hexdigest()
    now=datetime.utcnow().isoformat()
    actions=[]
    for chunk,vector in zip(chunks,vectors):
        actions.append({"index":{"_index":CSS_INDEX,"_id":f"{doc_id}_{chunk['index']}"}})
        actions.append({"doc_id":doc_id,"doc_name":doc_name,"chunk_idx":chunk["index"],
                        "content":chunk["text"],"embedding":vector,"indexed_at":now})
    if actions: css.bulk(body=actions)
    try:
        conn=get_rds()
        with conn.cursor() as c:
            c.execute("""INSERT INTO documentos (doc_id,doc_name,obs_bucket,chunk_count,indexed_at)
                VALUES (%s,%s,%s,%s,NOW()) ON CONFLICT (doc_id) DO UPDATE
                SET chunk_count=EXCLUDED.chunk_count,indexed_at=NOW()""",(doc_id,doc_name,bucket,len(chunks)))
        conn.commit(); conn.close()
    except Exception as e: logger.warning("RDS error: %s", e)
    return {"status":"ok","doc_id":doc_id,"chunks":len(chunks),"doc_name":doc_name}

@app.post("/sql")
def run_sql(body: dict):
    import re
    sql = body.get("sql", "").strip()
    if not sql: raise HTTPException(400, "SQL vacío")
    sql = re.sub(r'```sql','',sql,flags=re.IGNORECASE)
    sql = re.sub(r'```','',sql).strip()
    match = re.search(r'(SELECT\s+.*)',sql,re.IGNORECASE|re.DOTALL)
    if match: sql = match.group(1).strip()
    if not sql.upper().startswith("SELECT"): raise HTTPException(400, "Solo se permiten consultas SELECT")
    result = qrds(sql)
    return {"data": result, "rows": len(result)}

@app.post("/css")
def run_css(body: dict):
    query = body.get("query", "").strip()
    top_k = int(body.get("top_k", 5))
    if not query: raise HTTPException(400, "Query vacío")
    result = qcss(query, top_k)
    return {"data": result, "chunks": len(result)}
