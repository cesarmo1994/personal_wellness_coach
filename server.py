import base64
import json
import mimetypes
import os
import posixpath
import re
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zipfile
from email.parser import BytesParser
from email.policy import default
from html import unescape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(ROOT / "data"))).resolve()
UPLOAD_DIR = DATA_DIR / "uploads"
STATE_FILE = DATA_DIR / "app_state.json"
OPENAI_API_URL = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")
MAX_TEXT_CHARS = 45000
RETENTION_DAYS = 30


PLAN_LABELS = {
    "nutrition": "nutricion",
    "training": "entrenamiento",
    "wellness": "wellness",
}


DEVELOPER_PROMPT = """
Sos el coach IA de The Pichudo's App, una beta privada de wellness entre amigos.
Respondés siempre en español, con tono motivador suave, directo y accionable.
No reemplazás consejo médico profesional. Si detectás riesgo médico, dolor fuerte,
lesión, trastorno alimentario o síntoma preocupante, recomendá consultar a un profesional.

Cuando analizás planes:
- Identificá el tipo de plan: nutrición, entrenamiento o wellness.
- Extraé objetivos, frecuencia, tareas diarias/semanales, restricciones y métricas.
- Convertí el plan en acciones simples para check-ins diarios.
- Señalá dudas o datos faltantes.
- Devolvé texto claro y útil para guardar como plan activo.
""".strip()


def json_response(handler, status, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def set_data_dir(path):
    global DATA_DIR, UPLOAD_DIR, STATE_FILE
    DATA_DIR = Path(path).resolve()
    UPLOAD_DIR = DATA_DIR / "uploads"
    STATE_FILE = DATA_DIR / "app_state.json"


def ensure_data_dirs():
    fallback_dir = Path(tempfile.gettempdir()) / "pichudos-data"
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        probe = DATA_DIR / ".write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except (OSError, PermissionError):
        set_data_dir(fallback_dir)
        DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - RETENTION_DAYS * 24 * 60 * 60
    for item in UPLOAD_DIR.glob("*"):
        try:
            if item.is_file() and item.stat().st_mtime < cutoff:
                item.unlink()
        except OSError:
            pass


def cutoff_ms():
    return int((time.time() - RETENTION_DAYS * 24 * 60 * 60) * 1000)


def parse_date_ms(value):
    if not value:
        return int(time.time() * 1000)
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            if value.endswith("Z"):
                value = value[:-1] + "+00:00"
            from datetime import datetime

            return int(datetime.fromisoformat(value).timestamp() * 1000)
        except ValueError:
            return int(time.time() * 1000)
    return int(time.time() * 1000)


def prune_state(state):
    cutoff = cutoff_ms()
    state["groupMessages"] = [
        message for message in state.get("groupMessages", []) if parse_date_ms(message.get("at")) >= cutoff
    ]
    for user in state.get("users", {}).values():
        user["messages"] = [
            message for message in user.get("messages", []) if parse_date_ms(message.get("at")) >= cutoff
        ]
        user["checkins"] = [
            checkin for checkin in user.get("checkins", []) if parse_date_ms(checkin.get("at") or checkin.get("date")) >= cutoff
        ]
    return state


def read_app_state():
    ensure_data_dirs()
    if not STATE_FILE.exists():
        return None
    try:
      with STATE_FILE.open("r", encoding="utf-8") as file:
          return prune_state(json.load(file))
    except (json.JSONDecodeError, OSError):
        return None


def write_app_state(state):
    ensure_data_dirs()
    state = prune_state(state)
    state["serverSavedAt"] = int(time.time() * 1000)
    with STATE_FILE.open("w", encoding="utf-8") as file:
        json.dump(state, file, ensure_ascii=False, indent=2)
    return state


def safe_upload_name(filename):
    suffix = Path(filename).suffix.lower()
    stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(filename).stem).strip("-")[:50] or "archivo"
    return f"{int(time.time())}-{uuid.uuid4().hex[:10]}-{stem}{suffix}"


def read_request_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    return handler.rfile.read(length)


def parse_multipart(headers, body):
    content_type = headers.get("Content-Type", "")
    message = BytesParser(policy=default).parsebytes(
        f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8") + body
    )
    fields = {}
    files = {}
    for part in message.iter_parts():
        disposition = part.get("Content-Disposition", "")
        name_match = re.search(r'name="([^"]+)"', disposition)
        if not name_match:
            continue
        name = name_match.group(1)
        filename = part.get_filename()
        payload = part.get_payload(decode=True) or b""
        if filename:
            files[name] = {
                "filename": filename,
                "content_type": part.get_content_type(),
                "bytes": payload,
            }
        else:
            fields[name] = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    return fields, files


def extract_docx(data):
    with zipfile.ZipFile(BytesIO(data)) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
        if texts:
            paragraphs.append("".join(texts))
    return "\n".join(paragraphs)


def extract_xlsx(data):
    with zipfile.ZipFile(BytesIO(data)) as archive:
        shared_strings = []
        if "xl/sharedStrings.xml" in archive.namelist():
            root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
            namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            for item in root.findall(".//m:si", namespace):
                shared_strings.append("".join(node.text or "" for node in item.findall(".//m:t", namespace)))

        rows = []
        sheet_names = [name for name in archive.namelist() if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")]
        namespace = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for sheet_name in sorted(sheet_names)[:8]:
            root = ElementTree.fromstring(archive.read(sheet_name))
            rows.append(f"\n[{Path(sheet_name).stem}]")
            for row in root.findall(".//m:row", namespace)[:250]:
                values = []
                for cell in row.findall("m:c", namespace):
                    value = cell.find("m:v", namespace)
                    if value is None:
                        values.append("")
                        continue
                    raw = value.text or ""
                    if cell.attrib.get("t") == "s":
                        idx = int(raw) if raw.isdigit() else -1
                        values.append(shared_strings[idx] if 0 <= idx < len(shared_strings) else raw)
                    else:
                        values.append(raw)
                if any(values):
                    rows.append(" | ".join(values))
    return "\n".join(rows)


def extract_text(filename, data):
    suffix = Path(filename).suffix.lower()
    if suffix in {".txt", ".csv", ".tsv", ".md"}:
        return data.decode("utf-8", errors="replace")
    if suffix == ".docx":
        return extract_docx(data)
    if suffix == ".xlsx":
        return extract_xlsx(data)
    return ""


def trim_text(text):
    cleaned = unescape(text or "").strip()
    if len(cleaned) <= MAX_TEXT_CHARS:
        return cleaned
    return cleaned[:MAX_TEXT_CHARS] + "\n\n[Contenido recortado por tamaño para esta beta.]"


def response_text(payload):
    if "output_text" in payload:
        return payload["output_text"]
    parts = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            if content.get("type") == "output_text":
                parts.append(content.get("text", ""))
    return "\n".join(parts).strip()


def call_openai(input_items, max_output_tokens=1200):
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        raise RuntimeError("Falta configurar OPENAI_API_KEY en el ambiente del servidor.")
    if "\n" in api_key or "\r" in api_key or "$env:" in api_key:
        raise RuntimeError(
            "OPENAI_API_KEY está mal configurada. En Render debe ir solo la key real, sin comillas ni comandos."
        )

    payload = {
        "model": DEFAULT_MODEL,
        "input": input_items,
        "instructions": DEVELOPER_PROMPT,
        "reasoning": {"effort": "none"},
        "text": {"verbosity": "medium"},
        "max_output_tokens": max_output_tokens,
    }
    request = urllib.request.Request(
        OPENAI_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            data = json.loads(response.read().decode("utf-8"))
            return response_text(data), data.get("id")
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI respondió {exc.code}: {details}") from exc


def build_analysis_prompt(plan_type, filename, extracted_text, user_notes=""):
    label = PLAN_LABELS.get(plan_type, plan_type)
    notes_block = user_notes.strip() if user_notes and user_notes.strip() else "Sin descripción adicional."
    return f"""
Analizá este documento como plan de {label}.

Archivo: {filename}

Descripción/contexto dado por el usuario:
{notes_block}

Quiero que devuelvas:
1. Resumen del plan.
2. Objetivo semanal sugerido.
3. Acciones diarias para check-in.
4. Alertas, restricciones o datos faltantes.
5. Cómo combinar la información del documento con la descripción del usuario.
6. Cómo debería usarlo el coach IA en conversaciones futuras.

Contenido extraído:
{extracted_text}
""".strip()


def build_creation_prompt(plan_type, notes, existing_messages):
    label = PLAN_LABELS.get(plan_type, plan_type)
    history = "\n".join(f"{msg.get('role', 'user')}: {msg.get('text', '')}" for msg in existing_messages[-10:])
    return f"""
Creá o refiná un plan de {label} mediante conversación.

Información del usuario:
{notes}

Contexto reciente:
{history}

Devolvé un plan activo claro con:
- Objetivo semanal.
- Rutina o acciones diarias.
- Check-ins que debe pedir el coach.
- Recomendaciones suaves.
- Preguntas pendientes si faltan datos.
""".strip()


class AppHandler(SimpleHTTPRequestHandler):
    public_files = {
        "/",
        "/index.html",
        "/styles.css",
        "/app.js",
        "/manifest.webmanifest",
        "/icon.svg",
        "/sw.js",
    }

    def translate_path(self, path):
        path = path.split("?", 1)[0].split("#", 1)[0]
        path = posixpath.normpath(urllib.parse.unquote(path))
        if path.startswith("/uploads/"):
            name = Path(path).name
            return str(UPLOAD_DIR / name)
        parts = [part for part in path.split("/") if part and part not in {".", ".."}]
        target = ROOT
        for part in parts:
            target = target / part
        if target.is_dir():
            target = target / "index.html"
        return str(target)

    def do_GET(self):
        public_path = self.path.split("?", 1)[0].split("#", 1)[0]
        if public_path == "/healthz":
            json_response(self, 200, {"ok": True})
            return
        if public_path == "/api/app-state":
            json_response(self, 200, {"state": read_app_state()})
            return
        if public_path.startswith("/uploads/"):
            super().do_GET()
            return
        if public_path not in self.public_files:
            self.send_error(404, "File not found")
            return
        super().do_GET()

    def do_POST(self):
        try:
            if self.path == "/api/analyze-plan":
                self.handle_analyze_plan()
            elif self.path == "/api/create-plan":
                self.handle_create_plan()
            elif self.path == "/api/chat":
                self.handle_chat()
            elif self.path == "/api/app-state":
                self.handle_save_state()
            elif self.path == "/api/upload-evidence":
                self.handle_upload_evidence()
            else:
                json_response(self, 404, {"error": "Ruta no encontrada."})
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def handle_analyze_plan(self):
        fields, files = parse_multipart(self.headers, read_request_body(self))
        plan_type = fields.get("planType", "wellness")
        user_notes = fields.get("notes", "")
        file_data = files.get("file")
        if not file_data:
            json_response(self, 400, {"error": "No se recibió archivo."})
            return

        filename = file_data["filename"]
        data = file_data["bytes"]
        ensure_data_dirs()
        stored_name = safe_upload_name(filename)
        (UPLOAD_DIR / stored_name).write_bytes(data)
        file_url = f"/uploads/{stored_name}"
        extracted = trim_text(extract_text(filename, data))
        content = [{"type": "input_text", "text": build_analysis_prompt(plan_type, filename, extracted, user_notes)}]

        if not extracted:
            encoded = base64.b64encode(data).decode("ascii")
            content = [
                {
                    "type": "input_file",
                    "filename": filename,
                    "file_data": encoded,
                },
                {
                    "type": "input_text",
                    "text": build_analysis_prompt(
                        plan_type,
                        filename,
                        "El archivo se adjuntó para que el modelo lo lea directamente.",
                        user_notes,
                    ),
                },
            ]

        answer, response_id = call_openai([{"role": "user", "content": content}], max_output_tokens=1500)
        json_response(
            self,
            200,
            {
                "planType": plan_type,
                "name": filename,
                "summary": answer,
                "responseId": response_id,
                "extraction": "text" if extracted else "file",
                "fileUrl": file_url,
                "notes": user_notes,
            },
        )

    def handle_create_plan(self):
        payload = json.loads(read_request_body(self).decode("utf-8"))
        plan_type = payload.get("planType", "wellness")
        notes = payload.get("notes", "")
        messages = payload.get("messages", [])
        prompt = build_creation_prompt(plan_type, notes, messages)
        answer, response_id = call_openai(
            [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            max_output_tokens=1300,
        )
        json_response(self, 200, {"planType": plan_type, "name": f"Plan de {PLAN_LABELS.get(plan_type, plan_type)} creado por IA", "summary": answer, "responseId": response_id})

    def handle_chat(self):
        payload = json.loads(read_request_body(self).decode("utf-8"))
        message = payload.get("message", "")
        plans = payload.get("plans", {})
        checkins = payload.get("checkins", [])
        messages = payload.get("messages", [])
        plan_context = json.dumps(plans, ensure_ascii=False)[:12000]
        checkin_context = json.dumps(checkins[-7:], ensure_ascii=False)
        history = "\n".join(f"{msg.get('role', 'user')}: {msg.get('text', '')}" for msg in messages[-12:])
        prompt = f"""
Contexto de planes activos:
{plan_context}

Check-ins recientes:
{checkin_context}

Conversación reciente:
{history}

Mensaje nuevo del usuario:
{message}

Respondé como coach IA motivador suave. Si hace falta, recomendá un ajuste pequeño y concreto.
""".strip()
        answer, response_id = call_openai(
            [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            max_output_tokens=800,
        )
        json_response(self, 200, {"reply": answer, "responseId": response_id})

    def handle_save_state(self):
        payload = json.loads(read_request_body(self).decode("utf-8"))
        state = payload.get("state")
        if not isinstance(state, dict):
            json_response(self, 400, {"error": "Estado inválido."})
            return
        saved = write_app_state(state)
        json_response(self, 200, {"ok": True, "serverSavedAt": saved.get("serverSavedAt")})

    def handle_upload_evidence(self):
        fields, files = parse_multipart(self.headers, read_request_body(self))
        file_data = files.get("file")
        if not file_data:
            json_response(self, 400, {"error": "No se recibió archivo."})
            return
        ensure_data_dirs()
        filename = safe_upload_name(file_data["filename"])
        target = UPLOAD_DIR / filename
        target.write_bytes(file_data["bytes"])
        json_response(
            self,
            200,
            {
                "url": f"/uploads/{filename}",
                "name": file_data["filename"],
                "storedName": filename,
                "contentType": file_data["content_type"],
                "size": len(file_data["bytes"]),
                "user": fields.get("user", ""),
            },
        )


def main():
    port = int(os.getenv("PORT", "3000"))
    host = os.getenv("HOST", "0.0.0.0")
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"The Pichudo's App running locally at http://127.0.0.1:{port}/")
    print(f"Same Wi-Fi link: http://YOUR_COMPUTER_IP:{port}/")
    server.serve_forever()


if __name__ == "__main__":
    main()
