=============================================================
  MINERADEMO RAG — GUIA DE IMPLEMENTACION
  Sistema de inteligencia operativa conversacional
  Huawei Cloud: MaaS + CSS + RDS + ECS + OBS + FunctionGraph
=============================================================

INDICE
------
1. Arquitectura del sistema
2. Infraestructura en Huawei Cloud
3. Requisitos previos
4. Instalacion del backend
5. Instalacion del frontend
6. Configuracion del FunctionGraph
7. Indexacion de documentos
8. Variables de entorno
9. Uso del sistema
10. Preguntas de demostracion
11. Solucion de problemas

=============================================================
1. ARQUITECTURA DEL SISTEMA
=============================================================

El sistema sigue el patron RAG (Retrieval-Augmented Generation):
el modelo de lenguaje no inventa respuestas, sino que consulta
datos reales antes de responder.

FLUJO COMPLETO:

  Analista / Supervisor
          |
          v
  [Streamlit - Puerto 8501]
  Interfaz de chat con streaming token a token
          |
          | POST /chat/stream
          v
  [FastAPI Backend - Puerto 8000]
          |
          | 1. Llama a DeepSeek (MaaS) como Router
          |    El modelo decide: RDS / CSS / AMBOS
          |
          | 2. Consulta PARALELA (misma velocidad que una sola)
          |    |                    |
          v    v                    v
  [RDS PostgreSQL]        [CSS OpenSearch]
  Datos operativos        Documentos PDF
  - equipos               - Reglamento Seguridad
  - produccion            - Procedimientos Operacion
  - incidentes
  - mantenimiento
  - personal
          |                    |
          v                    v
          |____________________| 3. Combina resultados
                   |
                   | 4. Llama a DeepSeek (MaaS) como Sintetizador
                   |    Genera respuesta profesional con streaming
                   v
          Respuesta con fuentes citadas

INDEXACION AUTOMATICA DE DOCUMENTOS:
  OBS Bucket --[FunctionGraph timer 2min]--> POST /ingest --> CSS + RDS


=============================================================
2. INFRAESTRUCTURA EN HUAWEI CLOUD
=============================================================

Servicio        Nombre              Specs                    Funcion
--------        ------              -----                    -------
ECS             ecs-minera-demo     4 vCPU / 8 GB / Ubuntu   Backend + Frontend
RDS             rds-minera          PostgreSQL 14 / 4 GB     Base de datos
CSS             css-minera          OpenSearch 2.x / 4 GB    Busqueda vectorial
OBS             [nombre-OBS]        Standard storage         PDFs documentos
FunctionGraph   fg-minera-indexer   Python 3.10 / 512 MB     Indexacion auto
MaaS            ---                 DeepSeek V3.2            Router + Sintetizador

NOTA: Todos los servicios deben estar en la misma VPC y subnet
para comunicarse por IP privada sin exponer puertos al exterior.


=============================================================
3. REQUISITOS PREVIOS
=============================================================

- Cuenta activa en Huawei Cloud (region LA-Santiago recomendada)
- ECS Ubuntu 22.04 con al menos 4 vCPU y 8 GB RAM
- RDS PostgreSQL creado y accesible desde el ECS
- CSS OpenSearch creado y accesible desde el ECS
- API Key de MaaS con acceso a DeepSeek V3
- Bucket OBS creado con nombre: [nombre-OBS]
- Access Key (AK) y Secret Key (SK) de Huawei Cloud con
  permisos sobre el bucket OBS


=============================================================
4. INSTALACION DEL BACKEND
=============================================================

PASO 1 - Conectarse al ECS por SSH:

    ssh root@<ECS_IP_PUBLICA>

PASO 2 - Crear el directorio de trabajo:

    mkdir -p ~/minera_rag/docs
    cd ~/minera_rag

PASO 3 - Instalar Python y dependencias del sistema:

    apt update && apt install -y python3-pip python3-venv postgresql-client
    python3 -m venv venv
    source venv/bin/activate

PASO 4 - Instalar librerias Python:

    pip install fastapi uvicorn openai psycopg2-binary opensearch-py \
                sentence-transformers pymupdf python-dotenv streamlit requests

    NOTA: La instalacion de sentence-transformers incluye PyTorch (~2 GB).
    El tiempo estimado es 5-10 minutos segun el ancho de banda.

PASO 5 - Subir los archivos desde tu maquina local:

    scp main_minera.py root@<ECS_IP>:~/minera_rag/
    scp app_minera.py  root@<ECS_IP>:~/minera_rag/

PASO 6 - Crear el archivo de configuracion .env:

    nano ~/minera_rag/.env

    Contenido del archivo:

        # MaaS - Huawei Cloud Model as a Service
        MAAS_API_KEY=tu_api_key_de_maas
        MAAS_BASE_URL=https://api-ap-southeast-1.modelarts-maas.com/v2
        MAAS_MODEL=deepseek-v3.2

        # CSS - Cloud Search Service (OpenSearch)
        CSS_HOST=192.168.x.xxx
        CSS_PORT=9200
        CSS_USER=admin
        CSS_PASS=tu_password_css
        CSS_INDEX=minera_docs

        # RDS - Relational Database Service (PostgreSQL)
        RDS_HOST=192.168.x.xxx
        RDS_PORT=5432
        RDS_USER=root
        RDS_PASS=tu_password_rds
        RDS_DB=minera_rag

PASO 7 - Crear la base de datos y cargar el schema:

    psql -h <RDS_HOST> -U root -d postgres -c "CREATE DATABASE minera_rag;"
    psql -h <RDS_HOST> -U root -d minera_rag -f init_db_minera.sql

    Verificar tablas creadas:
    psql -h <RDS_HOST> -U root -d minera_rag -c "\dt"

    Resultado esperado:
        public | documentos    | table | root
        public | equipos       | table | root
        public | incidentes    | table | root
        public | mantenimiento | table | root
        public | personal      | table | root
        public | produccion    | table | root

PASO 8 - Levantar el backend:

    cd ~/minera_rag
    source venv/bin/activate
    uvicorn main:app --host 0.0.0.0 --port 8000 &

    Verificar que esta corriendo:
    curl http://localhost:8000/health

    Respuesta esperada:
    {"status":"ok","model":"deepseek-v3.2","empresa":"MineraDemo"}


=============================================================
5. INSTALACION DEL FRONTEND
=============================================================

PASO 1 - Configurar el tema visual de Streamlit:

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

PASO 2 - Levantar el frontend:

    cd ~/minera_rag
    source venv/bin/activate
    streamlit run app.py --server.port 8501 --server.address 0.0.0.0 &

PASO 3 - Acceder al sistema en el navegador:

    http://<ECS_IP_PUBLICA>:8501

PASO 4 - En el sidebar de la aplicacion:
    - Backend URL: http://<ECS_IP_PUBLICA>:8000
    - Hacer clic en "Conectar" -> debe mostrar Online
    - Hacer clic en "Actualizar" -> muestra documentos indexados

PASO 5 - Arranque automatico con tmux (para mantener activo):

    apt install -y tmux

    tmux new-session -d -s backend \
      'cd ~/minera_rag && source venv/bin/activate && \
       uvicorn main:app --host 0.0.0.0 --port 8000'

    tmux new-session -d -s frontend \
      'cd ~/minera_rag && source venv/bin/activate && \
       streamlit run app.py --server.port 8501 --server.address 0.0.0.0'

    Verificar sesiones activas:
    tmux list-sessions


=============================================================
6. CONFIGURACION DEL FUNCTIONGRAPH
=============================================================

El FunctionGraph detecta PDFs nuevos en OBS y los indexa
automaticamente en CSS cada 2 minutos.

PASO 1 - Crear la funcion en la consola de Huawei Cloud:
    Ir a: FunctionGraph -> Functions -> Create Function

    Parametros:
        Function Type : Event Function
        Function Name : fg-minera-indexer
        Runtime       : Python 3.10
        Handler       : index.handler
        Memory        : 512 MB
        Timeout       : 300 segundos

PASO 2 - Subir el codigo:
    Copiar el contenido del archivo index.py en el editor
    de la consola de FunctionGraph y hacer clic en Deploy.

PASO 3 - Configurar variables de entorno:
    Ir a: Configuration -> Environment Variables

    Clave              Valor
    -----              -----
    ECS_INGEST_URL     http://<ECS_IP>:8000/ingest
    ECS_DOCS_URL       http://<ECS_IP>:8000/documents
    OBS_BUCKET         [nombre-OBS]
    OBS_ENDPOINT       obs.la-south-2.myhuaweicloud.com
    OBS_AK             <tu_access_key>
    OBS_SK             <tu_secret_key>

PASO 4 - Crear el trigger Timer:
    Ir a: Create Trigger

    Parametros:
        Trigger Type    : Timer
        Timer Name      : timer-2min
        Cron Expression : 0/2 * * * *

PASO 5 - Probar la funcion:
    Hacer clic en "Test".
    Resultado esperado:
    {
        "statusCode": 200,
        "body": "[{\"key\": \"documento.pdf\", \"status\": \"ok\", \"chunks\": 5}]"
    }


=============================================================
7. INDEXACION DE DOCUMENTOS
=============================================================

METODO 1 - Automatico via OBS (recomendado):

    1. Ir a la consola de OBS
    2. Abrir el bucket "[nombre-OBS]" 
    3. Subir el archivo PDF
    4. En menos de 2 minutos el FunctionGraph lo detecta
    5. Hacer clic en "Actualizar" en el sidebar del Streamlit
       -> el documento aparece con el numero de chunks

    IMPORTANTE: Los nombres de archivo no deben contener
    espacios ni caracteres especiales.

METODO 2 - Manual desde el ECS:

    python3 << 'EOF'
    import base64, json, urllib.request

    with open("mi_documento.pdf", "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode()

    payload = json.dumps({
        "doc_name": "mi_documento.pdf",
        "bucket": "[nombre-OBS]",
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

Verificar documentos indexados:

    curl http://localhost:8000/documents

    curl -X GET "https://<CSS_HOST>:9200/minera_docs/_count" \
      -k -u admin:<CSS_PASS>


=============================================================
8. VARIABLES DE ENTORNO
=============================================================

BACKEND (.env):

    Variable        Descripcion                         Ejemplo
    --------        -----------                         -------
    MAAS_API_KEY    API Key de Huawei Cloud MaaS         TcKYyCIE...
    MAAS_BASE_URL   URL base del endpoint MaaS           https://api-ap-southeast-1...
    MAAS_MODEL      Modelo a usar                        deepseek-v3.2
    CSS_HOST        IP privada del cluster CSS           192.168.x.xxx
    CSS_PORT        Puerto de CSS                        9200
    CSS_USER        Usuario de CSS                       admin
    CSS_PASS        Contrasena de CSS                    ...
    CSS_INDEX       Nombre del indice en CSS              minera_docs
    RDS_HOST        IP privada del RDS                   192.168.x.xxx
    RDS_PORT        Puerto de RDS                        5432
    RDS_USER        Usuario de RDS                       root
    RDS_PASS        Contrasena de RDS                    ...
    RDS_DB          Nombre de la base de datos           minera_rag

FUNCTIONGRAPH (Environment Variables):

    Variable        Descripcion
    --------        -----------
    ECS_INGEST_URL  URL del endpoint /ingest del ECS
    ECS_DOCS_URL    URL del endpoint /documents del ECS
    OBS_BUCKET      Nombre del bucket OBS
    OBS_ENDPOINT    Endpoint regional de OBS
    OBS_AK          Access Key de Huawei Cloud
    OBS_SK          Secret Key de Huawei Cloud


=============================================================
9. USO DEL SISTEMA
=============================================================

ENDPOINTS DISPONIBLES:

    Metodo   Endpoint                 Descripcion
    ------   --------                 -----------
    GET      /health                  Estado del servicio
    POST     /chat/stream             Chat con streaming (Streamlit)
    GET      /documents               Lista documentos indexados
    DELETE   /documents/{doc_id}      Elimina un documento
    POST     /ingest                  Indexa un PDF
    POST     /sql                     Ejecuta SQL directo (Dify)
    POST     /css                     Busqueda semantica directa (Dify)

PROBAR EL CHAT DESDE TERMINAL:

    curl -X POST http://localhost:8000/chat/stream \
      -H "Content-Type: application/json" \
      -d '{"question": "Que equipos estan parados?"}' \
      --no-buffer

PROBAR CONSULTA SQL DIRECTA:

    curl -X POST http://localhost:8000/sql \
      -H "Content-Type: application/json" \
      -d '{"sql": "SELECT codigo, nombre, estado FROM equipos LIMIT 5"}'

PROBAR BUSQUEDA SEMANTICA DIRECTA:

    curl -X POST http://localhost:8000/css \
      -H "Content-Type: application/json" \
      -d '{"query": "protocolo emergencia accidente tajo", "top_k": 3}'


=============================================================
10. PREGUNTAS DE DEMOSTRACION
=============================================================

DATOS OPERATIVOS - RDS (responde con datos en tiempo real):

    "Que equipos estan parados o en mantenimiento?"
    -> Lista equipos con estado parado/mantenimiento

    "Cuales son los incidentes criticos pendientes?"
    -> Incidentes con severidad alto/critico sin cerrar

    "Cual fue la produccion del turno dia de hoy?"
    -> Toneladas, ley mineral y rendimiento por area

    "Que mantenimientos estan urgentes?"
    -> Ordenes de trabajo con prioridad urgente/alta

    "Que equipos tienen mas horas de operacion?"
    -> Equipos ordenados por horas descendente

NORMATIVA - CSS (responde con informacion de los documentos PDF):

    "Cual es el protocolo de emergencia ante un accidente en el tajo?"
    -> Pasos del protocolo del Reglamento de Seguridad

    "Que dice el reglamento sobre trabajos en altura?"
    -> Requisitos EPP, permisos y certificaciones

    "Que es el procedimiento LOTO?"
    -> Lockout-Tagout para mantenimiento de equipos

    "Cuales son los EPP obligatorios en area operativa?"
    -> Lista de equipos de proteccion por zona

    "Cuales son las reglas de trafico en el tajo?"
    -> Velocidades maximas y normas de circulacion

DATOS + NORMATIVA - AMBOS (las mas impactantes para la demo):

    *** "Hay un incidente en el tajo norte, cual es el protocolo?"
    -> Muestra incidentes activos + pasos del protocolo del reglamento
    -> El sistema cruza automaticamente datos reales con la normativa

    *** "Que equipos estan parados en el tajo sur y cual es el
         procedimiento de mantenimiento?"
    -> Equipos parados + procedimiento LOTO del manual

    *** "Cuales son los incidentes criticos y que dice el reglamento
         sobre como reportarlos?"
    -> Incidentes activos + normativa de reporte a autoridades

    *** "Un volquete tiene fuga de aceite, que debo hacer segun
         los procedimientos?"
    -> Procedimiento de detencion por falla + mantenimiento correctivo

    (Las preguntas marcadas con *** son las mas impactantes
     para demostrar el valor del sistema RAG)


=============================================================
11. SOLUCION DE PROBLEMAS COMUNES
=============================================================

PROBLEMA: Backend no responde
    Verificar que uvicorn esta corriendo:
        ps aux | grep uvicorn

    Ver logs en tiempo real (sin el & al final):
        uvicorn main:app --host 0.0.0.0 --port 8000

    Verificar que el puerto 8000 esta abierto en el Security Group.

PROBLEMA: CSS no encuentra documentos
    Verificar chunks indexados:
        curl -X GET "https://<CSS_HOST>:9200/minera_docs/_count" \
          -k -u admin:<PASS>

    Listar documentos indexados:
        curl http://localhost:8000/documents

    Si el indice no existe, subir un PDF al bucket OBS y
    esperar 2 minutos para que el FunctionGraph lo indexe.

PROBLEMA: RDS no conecta
    Probar conexion desde el ECS:
        psql -h <RDS_HOST> -U root -d minera_rag \
          -c "SELECT COUNT(*) FROM equipos;"

    Verificar que el Security Group del RDS permite
    trafico en el puerto 5432 desde la IP del ECS.

PROBLEMA: FunctionGraph con error 403 en OBS
    - Verificar que OBS_AK y OBS_SK son correctos (sin espacios)
    - Verificar que el AK/SK tiene permisos sobre el bucket en IAM
    - Verificar que el nombre del bucket coincide exactamente
    - Verificar que OBS_ENDPOINT corresponde a la region correcta

PROBLEMA: Streamlit no carga
    Verificar que el proceso esta corriendo:
        ps aux | grep streamlit

    Si el puerto 8501 esta ocupado:
        pkill -f streamlit
        streamlit run app.py --server.port 8501 --server.address 0.0.0.0 &

    Verificar que el puerto 8501 esta abierto en el Security Group.

PROBLEMA: Respuesta incorrecta del chat
    El router puede generar SQL incorrecto en casos no contemplados
    en los ejemplos del ROUTER_PROMPT. Para mejorar:
    - Agregar el caso como ejemplo en ROUTER_PROMPT en main.py
    - Reiniciar uvicorn para que tome los cambios

=============================================================
  MineraDemo RAG - Desarrollado con Huawei Cloud
  MaaS + CSS + RDS + ECS + OBS + FunctionGraph
  Version 1.0 - 2026
=============================================================
