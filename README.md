# MineraDemo RAG — Guía de Implementación

**Sistema de inteligencia operativa conversacional para operaciones mineras**  
Huawei Cloud · MaaS (DeepSeek V3) + CSS (OpenSearch) + RDS (PostgreSQL) + ECS + OBS + FunctionGraph

---


## Arquitectura del sistema {#arquitectura}

```
Analista / Supervisor
        │
        ▼
┌─────────────────┐
│   Streamlit     │  Frontend web (puerto 8501)
│   app.py        │  Chat con streaming token a token
└────────┬────────┘
         │ POST /chat/stream
         ▼
┌─────────────────────────────────────────────────────┐
│              FastAPI Backend (main.py)              │
│                  ECS · puerto 8000                  │
│                                                     │
│  1. MaaS Router ──► decide: RDS / CSS / AMBOS       │
│  2. Consulta paralela (ThreadPoolExecutor)           │
│     ├── RDS PostgreSQL (datos operativos)            │
│     └── CSS OpenSearch (normativa PDF)               │
│  3. MaaS Synthesizer ──► respuesta con streaming    │
└─────────────────────────────────────────────────────┘
         │                          │
         ▼                          ▼
┌─────────────┐           ┌─────────────────┐
│     RDS     │           │      CSS        │
│ PostgreSQL  │           │  OpenSearch     │
│             │           │                 │
│ • equipos   │           │ • Reglamento    │
│ • produccion│           │   Seguridad     │
│ • incidentes│           │ • Procedimientos│
│ • mantenim. │           │   Operación     │
│ • personal  │           │                 │
└─────────────┘           └─────────────────┘

Indexación automática de documentos:
OBS Bucket ──► FunctionGraph (timer 2 min) ──► POST /ingest ──► CSS + RDS
```

---

## ☁️ Infraestructura en Huawei Cloud {#infraestructura}

| Servicio | Nombre | Especificaciones | Función |

| **ECS** | ecs-minera-demo | 4 vCPU / 8 GB RAM / Ubuntu 22.04 | Backend FastAPI + Streamlit |
| **RDS** | rds-minera | PostgreSQL 14 / 2 vCPU / 4 GB | Base de datos operativa |
| **CSS** | css-minera | OpenSearch 2.x / 4 GB | Búsqueda vectorial semántica |
| **OBS** | minera-rag-docs | Standard storage | Almacén de documentos PDF |
| **FunctionGraph** | fg-minera-indexer | Python 3.10 / 512 MB | Indexación automática |
| **MaaS** | — | DeepSeek V3.2 | Router + Sintetizador LLM |

**Red:** Todos los servicios en la misma VPC (`vpc-minera`) y subnet (`subnet-a / 192.168.x.0/24`), comunicación por IP privada.

---

## Requisitos previos {#requisitos}

- Cuenta activa en Huawei Cloud LA-Santiago (o la región de preferencia)
- ECS Ubuntu 22.04 con al menos 4 vCPU y 8 GB RAM
- RDS PostgreSQL creado y accesible desde el ECS
- CSS OpenSearch creado y accesible desde el ECS
- API Key de MaaS con acceso al modelo DeepSeek V3
- Bucket OBS creado con el nombre `minera-rag-docs`
- Access Key (AK) y Secret Key (SK) de Huawei Cloud con permisos sobre OBS

---

## Instalación del backend {#backend}

### 1. Conectarse al ECS

```bash
ssh root@<ECS_IP_PUBLICA>
```

### 2. Crear el directorio de trabajo

```bash
mkdir -p ~/minera_rag/docs
cd ~/minera_rag
```

### 3. Crear el entorno virtual Python

```bash
apt update && apt install -y python3-pip python3-venv postgresql-client
python3 -m venv venv
source venv/bin/activate
```

### 4. Instalar dependencias

```bash
pip install fastapi uvicorn openai psycopg2-binary opensearch-py \
            sentence-transformers pymupdf python-dotenv streamlit requests
```

> **Nota:** La instalación de `sentence-transformers` incluye PyTorch (~2 GB). El tiempo estimado es 5-10 minutos dependiendo del ancho de banda.

### 5. Subir los archivos

Desde tu máquina local:

```bash
scp main.py root@<ECS_IP>:~/minera_rag/
scp app.py  root@<ECS_IP>:~/minera_rag/
```

### 6. Crear el archivo `.env`

```bash
cat > ~/minera_rag/.env << 'EOF'
# MaaS — Huawei Cloud Model as a Service
MAAS_API_KEY=tu_api_key_de_maas
MAAS_BASE_URL=https://api-ap-southeast-1.modelarts-maas.com/v2
MAAS_MODEL=deepseek-v3.2

# CSS — Cloud Search Service (OpenSearch)
CSS_HOST=192.168.x.xxx        # IP privada del CSS
CSS_PORT=9200
CSS_USER=admin
CSS_PASS=tu_password_css
CSS_INDEX=minera_docs

# RDS — Relational Database Service (PostgreSQL)
RDS_HOST=192.168.x.xxx        # IP privada del RDS
RDS_PORT=5432
RDS_USER=root
RDS_PASS=tu_password_rds
RDS_DB=minera_rag
EOF
```

### 7. Crear la base de datos

```bash
# Crear la base de datos
psql -h <RDS_HOST> -U root -d postgres -c "CREATE DATABASE minera_rag;"

# Cargar el schema con datos de ejemplo
psql -h <RDS_HOST> -U root -d minera_rag -f init_db_minera.sql
```

Verificar que las tablas se crearon correctamente:

```bash
psql -h <RDS_HOST> -U root -d minera_rag -c "\dt"
```

Resultado esperado:

```
           List of relations
 Schema |     Name      | Type  | Owner
--------+---------------+-------+-------
 public | documentos    | table | root
 public | equipos       | table | root
 public | incidentes    | table | root
 public | mantenimiento | table | root
 public | personal      | table | root
 public | produccion    | table | root
```

### 8. Levantar el backend

```bash
cd ~/minera_rag
source venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000 &
```

Verificar que está corriendo:

```bash
curl http://localhost:8000/health
# Respuesta esperada: {"status":"ok","model":"deepseek-v3.2","empresa":"MineraDemo"}
```

---

## 🖥️ Instalación del frontend {#frontend}

### 1. Configurar el tema de Streamlit

```bash
mkdir -p ~/minera_rag/.streamlit
cat > ~/minera_rag/.streamlit/config.toml << 'EOF'
[theme]
base="light"
primaryColor="#5c3a00"
backgroundColor="#f5f0e8"
secondaryBackgroundColor="#ffffff"
textColor="#1a1a1a"

[server]
headless=true
EOF
```

### 2. Levantar el frontend

```bash
cd ~/minera_rag
source venv/bin/activate
streamlit run app.py --server.port 8501 --server.address 0.0.0.0 &
```

### 3. Acceder al sistema

Abrir en el navegador:
```
http://<ECS_IP_PUBLICA>:8501
```

En el sidebar, configurar el **Backend URL**:
```
http://<ECS_IP_PUBLICA>:8000
```

Hacer clic en **🔍 Conectar** — debe mostrar `✅ Online`.

### 4. Configurar arranque automático (opcional)

Para que los servicios se mantengan activos después de cerrar la sesión SSH:

```bash
# Instalar tmux
apt install -y tmux

# Crear sesión del backend
tmux new-session -d -s backend \
  'cd ~/minera_rag && source venv/bin/activate && uvicorn main:app --host 0.0.0.0 --port 8000'

# Crear sesión del frontend
tmux new-session -d -s frontend \
  'cd ~/minera_rag && source venv/bin/activate && streamlit run app.py --server.port 8501 --server.address 0.0.0.0'

# Ver sesiones activas
tmux list-sessions
```

---

## ⚡ Configuración del FunctionGraph {#functiongraph}

El FunctionGraph detecta automáticamente nuevos PDFs en el bucket OBS y los indexa en CSS.

### 1. Crear la función

En la consola de Huawei Cloud → **FunctionGraph → Functions → Create Function**:

| Campo | Valor |
|---|---|
| Function Type | Event Function |
| Function Name | `fg-minera-indexer` |
| Runtime | Python 3.10 |
| Handler | `index.handler` |
| Memory | 512 MB |
| Timeout | 300 segundos |

### 2. Subir el código

Copiar el contenido del archivo `index.py` (handler del FunctionGraph) en el editor inline de la consola.

### 3. Configurar variables de entorno

En **Configuration → Environment Variables**:

| Clave | Valor |
|---|---|
| `ECS_INGEST_URL` | `http://<ECS_IP>:8000/ingest` |
| `ECS_DOCS_URL` | `http://<ECS_IP>:8000/documents` |
| `OBS_BUCKET` | `minera-rag-docs` |
| `OBS_ENDPOINT` | `obs.la-south-2.myhuaweicloud.com` |
| `OBS_AK` | `<tu_access_key>` |
| `OBS_SK` | `<tu_secret_key>` |

### 4. Crear el trigger Timer

En **Create Trigger**:

| Campo | Valor |
|---|---|
| Trigger Type | Timer |
| Timer Name | `timer-2min` |
| Cron Expression | `0/2 * * * *` |

### 5. Probar la función

Hacer clic en **Test** — resultado esperado:

```json
{
  "statusCode": 200,
  "body": "[{\"key\": \"documento.pdf\", \"status\": \"ok\", \"chunks\": 5}]"
}
```

---

## 📄 Indexación de documentos {#indexacion}

### Método 1: Automático vía OBS (recomendado)

1. Subir el PDF al bucket `minera-rag-docs` en la consola de OBS
2. El FunctionGraph lo detecta en el siguiente ciclo (máximo 2 minutos)
3. El documento aparece en el panel lateral del Streamlit al hacer clic en **🔄 Actualizar**

### Método 2: Manual desde el ECS

```bash
# Indexar un PDF directamente desde el ECS
python3 << 'EOF'
import base64, json, urllib.request

with open("mi_documento.pdf", "rb") as f:
    content_b64 = base64.b64encode(f.read()).decode()

payload = json.dumps({
    "doc_name": "mi_documento.pdf",
    "bucket": "minera-rag-docs",
    "content_b64": content_b64
}).encode()

req = urllib.request.Request(
    "http://localhost:8000/ingest",
    data=payload,
    headers={"Content-Type": "application/json"},
    method="POST"
)
with urllib.request.urlopen(req, timeout=300) as r:
    print(r.read().decode())
EOF
```

### Verificar documentos indexados

```bash
# Desde el ECS
curl http://localhost:8000/documents

# Conteo en CSS
curl -X GET "https://<CSS_HOST>:9200/minera_docs/_count" \
  -k -u admin:<CSS_PASS>
```

---

## 🔑 Variables de entorno {#variables}

### Backend (`~/minera_rag/.env`)

| Variable | Descripción | Ejemplo |
|---|---|---|
| `MAAS_API_KEY` | API Key de Huawei Cloud MaaS | `TcKYyCIE...` |
| `MAAS_BASE_URL` | URL base del endpoint MaaS | `https://api-ap-southeast-1.modelarts-maas.com/v2` |
| `MAAS_MODEL` | Modelo a usar | `deepseek-v3.2` |
| `CSS_HOST` | IP privada del cluster CSS | `192.168.x.xxx` |
| `CSS_PORT` | Puerto de CSS | `9200` |
| `CSS_USER` | Usuario de CSS | `admin` |
| `CSS_PASS` | Contraseña de CSS | `...` |
| `CSS_INDEX` | Nombre del índice en CSS | `minera_docs` |
| `RDS_HOST` | IP privada del RDS | `192.168.x.xxx` |
| `RDS_PORT` | Puerto de RDS | `5432` |
| `RDS_USER` | Usuario de RDS | `root` |
| `RDS_PASS` | Contraseña de RDS | `...` |
| `RDS_DB` | Nombre de la base de datos | `minera_rag` |

### FunctionGraph (Environment Variables)

| Variable | Descripción |
|---|---|
| `ECS_INGEST_URL` | URL del endpoint /ingest del ECS |
| `ECS_DOCS_URL` | URL del endpoint /documents del ECS |
| `OBS_BUCKET` | Nombre del bucket OBS |
| `OBS_ENDPOINT` | Endpoint regional de OBS |
| `OBS_AK` | Access Key de Huawei Cloud |
| `OBS_SK` | Secret Key de Huawei Cloud |

---

## 💬 Uso del sistema {#uso}

### Endpoints disponibles

| Método | Endpoint | Descripción |
|---|---|---|
| `GET` | `/health` | Estado del servicio |
| `POST` | `/chat/stream` | Chat con streaming (Streamlit) |
| `GET` | `/documents` | Lista documentos indexados |
| `DELETE` | `/documents/{doc_id}` | Elimina un documento |
| `POST` | `/ingest` | Indexa un PDF |
| `POST` | `/sql` | Ejecuta SQL directo (Dify) |
| `POST` | `/css` | Búsqueda semántica directa (Dify) |

### Probar el chat desde curl

```bash
curl -X POST http://localhost:8000/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"question": "¿Qué equipos están parados?"}' \
  --no-buffer
```

### Probar consulta SQL directa

```bash
curl -X POST http://localhost:8000/sql \
  -H "Content-Type: application/json" \
  -d '{"sql": "SELECT codigo, nombre, estado FROM equipos WHERE estado IN ('"'"'parado'"'"','"'"'mantenimiento'"'"')"}'
```

### Probar búsqueda semántica directa

```bash
curl -X POST http://localhost:8000/css \
  -H "Content-Type: application/json" \
  -d '{"query": "protocolo emergencia accidente tajo", "top_k": 3}'
```

---

## 🎯 Preguntas de demostración {#demo}

### 🗄️ Datos operativos (RDS)

| Pregunta | Resultado esperado |
|---|---|
| `¿Qué equipos están parados o en mantenimiento?` | Lista de equipos con estado parado/mantenimiento |
| `¿Cuáles son los incidentes críticos pendientes?` | Incidentes con severidad alto/crítico sin cerrar |
| `¿Cuál fue la producción del turno día de hoy?` | Toneladas, ley mineral y rendimiento por área |
| `¿Qué mantenimientos están urgentes?` | Órdenes de trabajo con prioridad urgente/alta |
| `¿Qué equipos tienen más de 5000 horas de operación?` | Equipos por horas descendente |

### 📋 Normativa (CSS)

| Pregunta | Resultado esperado |
|---|---|
| `¿Cuál es el protocolo de emergencia ante un accidente en el tajo?` | Pasos del protocolo del Reglamento de Seguridad |
| `¿Qué dice el reglamento sobre trabajos en altura?` | Requisitos EPP, permisos y certificaciones |
| `¿Qué es el procedimiento LOTO?` | Lockout-Tagout para mantenimiento de equipos |
| `¿Cuáles son los EPP obligatorios en área operativa?` | Lista de equipos de protección por zona |
| `¿Cuáles son las reglas de tráfico en el tajo?` | Velocidades máximas y normas de circulación |

### 🔀 Datos + Normativa (AMBOS — más impactantes para la demo)

| Pregunta | Resultado esperado |
|---|---|
| `Hay un incidente en el tajo norte, ¿cuál es el protocolo de emergencia?` | ⭐ Incidentes activos + pasos del protocolo |
| `¿Qué equipos están parados en el tajo sur y cuál es el procedimiento de mantenimiento?` | ⭐ Equipos parados + procedimiento LOTO |
| `¿Cuáles son los incidentes críticos y qué dice el reglamento sobre cómo reportarlos?` | ⭐ Incidentes + normativa de reporte |
| `Un volquete tiene fuga de aceite, ¿qué debo hacer según los procedimientos?` | ⭐ Procedimiento de detención + mantenimiento |

---

## 🔐 Seguridad

- Todos los servicios están en la misma VPC — sin exposición innecesaria a internet
- El puerto 8000 (backend) solo debe abrirse al rango de IPs necesario en el Security Group
- El puerto 8501 (frontend) puede restringirse a IPs corporativas
- Las credenciales se almacenan en variables de entorno, nunca en el código
- CSS usa SSL con autenticación usuario/contraseña
- FunctionGraph accede a OBS con presigned URLs de corta duración (5 minutos)
- El endpoint `/sql` solo permite consultas `SELECT` (sin escritura)

---

## 🛠️ Solución de problemas comunes

### Backend no responde
```bash
# Verificar que uvicorn está corriendo
ps aux | grep uvicorn

# Ver logs en tiempo real
uvicorn main:app --host 0.0.0.0 --port 8000  # sin & para ver logs
```

### CSS no encuentra documentos
```bash
# Verificar chunks indexados
curl -X GET "https://<CSS_HOST>:9200/minera_docs/_count" -k -u admin:<PASS>

# Listar documentos por nombre
curl -X GET "https://<CSS_HOST>:9200/minera_docs/_search" \
  -k -u admin:<PASS> \
  -H "Content-Type: application/json" \
  -d '{"_source":["doc_name"],"size":20,"query":{"match_all":{}}}'
```

### RDS no conecta
```bash
# Probar conexión desde el ECS
psql -h <RDS_HOST> -U root -d minera_rag -c "SELECT COUNT(*) FROM equipos;"
```

### FunctionGraph con error 403 en OBS
- Verificar que `OBS_AK` y `OBS_SK` son correctos y sin espacios
- Verificar que el AK/SK tiene permisos sobre el bucket en IAM
- Verificar que el nombre del bucket coincide exactamente

---

## 📞 Soporte

Para soporte técnico, contactar al equipo de Huawei Cloud a través del portal de soporte.

---

*MineraDemo RAG — Desarrollado con Huawei Cloud MaaS, CSS y RDS*  
*Versión 1.0 — 2026*
