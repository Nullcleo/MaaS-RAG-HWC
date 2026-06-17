import os, json, base64, logging, urllib.request, re, hmac, hashlib, datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ECS_INGEST_URL = os.environ.get("ECS_INGEST_URL", "http://[IP-ECS]:8000/ingest")
ECS_DOCS_URL   = os.environ.get("ECS_DOCS_URL",   "http://[IP-ECS]:8000/documents")
OBS_BUCKET     = os.environ.get("OBS_BUCKET",     "[OBS-NAME]")
OBS_ENDPOINT   = os.environ.get("OBS_ENDPOINT",   "obs.la-south-2.myhuaweicloud.com")
OBS_AK         = os.environ.get("OBS_AK",         "")
OBS_SK         = os.environ.get("OBS_SK",         "")
ACCEPTED       = {".pdf", ".txt", ".md"}

def make_presigned_url(method, bucket, key, ak, sk, endpoint, expires=300):
    import time, urllib.parse
    exp = int(time.time()) + expires
    path = f"/{key}" if key else "/"
    string = f"{method}\n\n\n{exp}\n/{bucket}{path}"
    sig = base64.b64encode(
        hmac.new(sk.encode(), string.encode(), hashlib.sha1).digest()
    ).decode()
    encoded_path = urllib.parse.quote(path, safe="/")
    sig_enc = urllib.parse.quote(sig, safe="")
    ak_enc  = urllib.parse.quote(ak, safe="")
    url = f"https://{bucket}.{endpoint}{encoded_path}?AccessKeyId={ak_enc}&Expires={exp}&Signature={sig_enc}"
    return url

def list_obs_objects(bucket, endpoint, ak, sk):
    url = make_presigned_url("GET", bucket, "", ak, sk, endpoint)
    print(f"Presigned URL: {url[:80]}", flush=True)
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body = r.read().decode("utf-8")
        import html
        keys = re.findall(r"<Key>([^<]+)</Key>", body)
        keys = [html.unescape(k) for k in keys]
        print(f"Keys found: {keys}", flush=True)
        return keys
    except urllib.error.HTTPError as e:
        print(f"Error: {e.read().decode()[:300]}", flush=True)
        raise

def get_indexed_docs():
    try:
        with urllib.request.urlopen(ECS_DOCS_URL, timeout=10) as r:
            return {d["doc_name"] for d in json.loads(r.read()).get("documents",[])}
    except Exception as e:
        logger.warning("docs error: %s", e)
        return set()

def download_and_ingest(bucket, key, endpoint, ak, sk):
    import urllib.parse
    url = make_presigned_url("GET", bucket, key, ak, sk, endpoint)
    with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as r:
        file_bytes = r.read()
    print(f"Downloaded {key}: {len(file_bytes)} bytes", flush=True)
    content_b64 = base64.b64encode(file_bytes).decode()
    payload = json.dumps({"doc_name": key, "bucket": bucket, "content_b64": content_b64}).encode()
    req2 = urllib.request.Request(ECS_INGEST_URL, data=payload,
                                   headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req2, timeout=280) as r2:
        return json.loads(r2.read())

def handler(event, context):
    logger.info("Timer polling OBS: %s AK=%s", OBS_BUCKET, OBS_AK[:8] if OBS_AK else "EMPTY")
    try:
        all_keys     = list_obs_objects(OBS_BUCKET, OBS_ENDPOINT, OBS_AK, OBS_SK)
        indexed_docs = get_indexed_docs()
        logger.info("OBS:%d Indexed:%d", len(all_keys), len(indexed_docs))
    except Exception as e:
        logger.error("list error: %s", e)
        return {"statusCode": 500, "body": str(e)}
    results = []
    for key in all_keys:
        if os.path.splitext(key.lower())[1] not in ACCEPTED: continue
        if key in indexed_docs:
            logger.info("skip: %s", key); continue
        logger.info("new: %s", key)
        try:
            results.append({"key":key,"status":"ok",**download_and_ingest(OBS_BUCKET,key,OBS_ENDPOINT,OBS_AK,OBS_SK)})
        except Exception as e:
            logger.error("ingest error %s: %s", key, e)
            results.append({"key":key,"status":"error","reason":str(e)})
    return {"statusCode":200,"body":json.dumps(results,ensure_ascii=False)}