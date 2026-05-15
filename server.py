import json
import hashlib
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
OPENAI_FILES_URL = "https://api.openai.com/v1/files"
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.2")
MAX_TEXT_CHARS = 45000
RETENTION_DAYS = 30
SIGNED_URL_TTL_SECONDS = 60 * 60
CHAT_RETENTION_DAYS = int(os.getenv("CHAT_RETENTION_DAYS", "30"))
DEFAULT_GROUP_NAME = "Los Pichudos"
DEFAULT_GROUP_SLUG = "los-pichudos"
MAX_PLAN_FILE_BYTES = 25 * 1024 * 1024
SUPPORTED_PLAN_SUFFIXES = {".pdf", ".docx", ".xlsx", ".csv", ".tsv", ".txt", ".md"}


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


def get_openai_api_key():
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip().strip('"').strip("'")
    if not api_key:
        raise RuntimeError("Falta configurar OPENAI_API_KEY en el ambiente del servidor.")
    if "\n" in api_key or "\r" in api_key or "$env:" in api_key:
        raise RuntimeError(
            "OPENAI_API_KEY está mal configurada. En Render debe ir solo la key real, sin comillas ni comandos."
        )
    return api_key


def get_supabase_config():
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    service_key = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip().strip('"').strip("'")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    if not url or not service_key:
        return None
    if "\n" in service_key or "\r" in service_key or "$env:" in service_key:
        raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY estÃ¡ mal configurada.")
    return {"url": url, "service_key": service_key}


def get_supabase_public_config():
    url = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
    anon_key = (os.getenv("SUPABASE_ANON_KEY") or "").strip().strip('"').strip("'")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    if not url or not anon_key:
        return None
    if "\n" in anon_key or "\r" in anon_key or "$env:" in anon_key:
        raise RuntimeError("SUPABASE_ANON_KEY estÃ¡ mal configurada.")
    return {"url": url, "anon_key": anon_key}


def admin_emails():
    raw = os.getenv("ADMIN_EMAILS", "cesar@ckmecr.com")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def infer_beta_display_name(email, full_name):
    if (email or "").lower() in admin_emails():
        return "César"
    source = f"{full_name or ''} {email or ''}".lower()
    if "cesar" in source or "cÃ©sar" in source:
        return "CÃ©sar"
    return (full_name or email or "Usuario").split()[0]


def auth_user_from_access_token(access_token):
    public_config = get_supabase_public_config()
    if not public_config:
        raise RuntimeError("Faltan SUPABASE_URL y SUPABASE_ANON_KEY para auth.")
    request = urllib.request.Request(
        f"{public_config['url']}/auth/v1/user",
        headers={
            "apikey": public_config["anon_key"],
            "Authorization": f"Bearer {access_token}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase Auth respondiÃ³ {exc.code}: {details}") from exc


def access_token_from_headers(headers):
    auth_header = (headers.get("Authorization") or "").strip()
    if not auth_header.lower().startswith("bearer "):
        return ""
    return auth_header[7:].strip()


def supabase_request(method, path, payload=None, extra_headers=None, timeout=60):
    config = get_supabase_config()
    if not config:
        raise RuntimeError("Faltan SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY.")

    body = None
    headers = {
        "apikey": config["service_key"],
        "Authorization": f"Bearer {config['service_key']}",
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)

    request = urllib.request.Request(
        f"{config['url']}{path}",
        data=body,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase respondiÃ³ {exc.code}: {details}") from exc


def supabase_insert(table, payload):
    result = supabase_request(
        "POST",
        f"/rest/v1/{table}",
        payload,
        {"Prefer": "return=representation"},
    )
    if isinstance(result, list) and result:
        return result[0]
    return result


def supabase_insert_ignore(table, payload):
    try:
        return supabase_insert(table, payload)
    except RuntimeError as exc:
        if "duplicate key value" in str(exc) or "23505" in str(exc):
            return None
        raise


def supabase_update(table, filters, payload):
    query = urllib.parse.urlencode(filters)
    result = supabase_request(
        "PATCH",
        f"/rest/v1/{table}?{query}",
        payload,
        {"Prefer": "return=representation"},
    )
    return result if isinstance(result, list) else []


def supabase_select_one(table, filters, select="id"):
    query = {"select": select, "limit": "1"}
    query.update(filters)
    path = f"/rest/v1/{table}?{urllib.parse.urlencode(query)}"
    result = supabase_request("GET", path)
    if isinstance(result, list) and result:
        return result[0]
    return None


def supabase_select_many(table, filters=None, select="*", order=None, limit=None):
    query = {"select": select}
    if filters:
        query.update(filters)
    if order:
        query["order"] = order
    if limit:
        query["limit"] = str(limit)
    path = f"/rest/v1/{table}?{urllib.parse.urlencode(query)}"
    result = supabase_request("GET", path)
    return result if isinstance(result, list) else []


def profile_handle(display_name):
    base = (display_name or "usuario").strip().lower()
    replacements = {"Ã¡": "a", "Ã©": "e", "Ã­": "i", "Ã³": "o", "Ãº": "u", "Ã±": "n", "Ã¼": "u"}
    for source, target in replacements.items():
        base = base.replace(source, target)
    handle = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return handle or f"user-{uuid.uuid4().hex[:8]}"


def get_or_create_profile(display_name, email=None, auth_user_id=None):
    name = (display_name or "Usuario").strip() or "Usuario"
    if auth_user_id:
        existing = supabase_select_one("profiles", {"auth_user_id": f"eq.{auth_user_id}"}, "id,display_name,email,auth_user_id,default_role")
        if existing:
            return existing
    if email:
        existing = supabase_select_one("profiles", {"email": f"eq.{email.lower()}"}, "id,display_name,email,auth_user_id,default_role")
        if existing:
            if auth_user_id and not existing.get("auth_user_id"):
                supabase_update("profiles", {"id": f"eq.{existing['id']}"}, {"auth_user_id": auth_user_id})
            return existing
    existing = supabase_select_one("profiles", {"display_name": f"eq.{name}"}, "id,display_name,email,auth_user_id,default_role")
    if existing:
        updates = {}
        if email and not existing.get("email"):
            updates["email"] = email.lower()
        if auth_user_id and not existing.get("auth_user_id"):
            updates["auth_user_id"] = auth_user_id
        if updates:
            supabase_update("profiles", {"id": f"eq.{existing['id']}"}, updates)
        return existing
    role = "owner" if email and email.lower() in admin_emails() else "athlete"
    return supabase_insert(
        "profiles",
        {
            "auth_user_id": auth_user_id,
            "display_name": name,
            "handle": profile_handle(name),
            "email": email.lower() if email else None,
            "default_role": role,
            "is_beta_user": True,
            "metadata": {"source": "auth" if auth_user_id else "beta-storage-upload"},
        },
    )


def ensure_authenticated_profile(access_token):
    auth_user = auth_user_from_access_token(access_token)
    email = (auth_user.get("email") or "").lower()
    metadata = auth_user.get("user_metadata") or {}
    full_name = metadata.get("full_name") or metadata.get("name") or email
    display_name = infer_beta_display_name(email, full_name)
    profile = get_or_create_profile(display_name, email=email, auth_user_id=auth_user.get("id"))
    team = get_or_create_team()
    role = "owner" if email in admin_emails() else profile.get("default_role", "athlete") or "athlete"
    ensure_team_member(team["id"], profile["id"], "team_admin" if role == "owner" else role)
    return {
        "profile": {
            "id": profile["id"],
            "displayName": profile["display_name"],
            "email": email,
            "role": role,
        },
        "team": team,
    }


def get_or_create_team(name=DEFAULT_GROUP_NAME, slug=DEFAULT_GROUP_SLUG):
    existing = supabase_select_one("teams", {"slug": f"eq.{slug}"}, "id,name,slug")
    if existing:
        return existing
    return supabase_insert(
        "teams",
        {
            "name": name,
            "slug": slug,
            "kind": "accountability_group",
            "weekly_goal": "Cumplir el objetivo de la semana con check-ins diarios.",
            "metadata": {"source": "beta-chat-sync"},
        },
    )


def ensure_team_member(team_id, profile_id, role="athlete"):
    existing = supabase_select_one(
        "team_members",
        {"team_id": f"eq.{team_id}", "profile_id": f"eq.{profile_id}"},
        "id",
    )
    if existing:
        return existing
    return supabase_insert_ignore(
        "team_members",
        {"team_id": team_id, "profile_id": profile_id, "role": role},
    )


def get_or_create_conversation(kind, profile_id=None, team_id=None, title=None):
    if kind == "personal":
        existing = supabase_select_one("conversations", {"kind": "eq.personal", "profile_id": f"eq.{profile_id}"}, "id")
        if existing:
            return existing
        return supabase_insert(
            "conversations",
            {"kind": "personal", "profile_id": profile_id, "title": title or "Coach personal"},
        )

    existing = supabase_select_one("conversations", {"kind": "eq.group", "team_id": f"eq.{team_id}"}, "id")
    if existing:
        return existing
    return supabase_insert(
        "conversations",
        {"kind": "group", "team_id": team_id, "title": title or DEFAULT_GROUP_NAME},
    )


def sender_type_from_role(role):
    if role == "coach":
        return "coach_ai"
    if role == "system":
        return "system"
    return "user"


def stable_message_id(scope, message):
    raw = "|".join(
        [
            scope,
            str(message.get("role", "")),
            str(message.get("sender", "")),
            str(message.get("at", "")),
            str(message.get("text", "")),
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def iso_timestamp(value):
    if not value:
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if isinstance(value, str):
        return value
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def message_to_client(row, personal_user=None):
    sender_type = row.get("sender_type")
    if sender_type == "coach_ai":
        role = "coach"
    elif sender_type == "system":
        role = "system"
    else:
        role = "user"
    message = {
        "role": role,
        "text": row.get("body", ""),
        "at": row.get("created_at"),
    }
    sender_name = row.get("profiles", {}).get("display_name") if isinstance(row.get("profiles"), dict) else None
    if personal_user and role == "user":
        sender_name = personal_user
    if sender_name:
        message["sender"] = sender_name
    return message


def dedupe_client_messages(messages):
    deduped = []
    seen_defaults = set()
    for message in messages:
        text = (message.get("text") or "").strip()
        role = message.get("role", "")
        sender = message.get("sender", "")
        if not text:
            continue

        default_key = (role, sender, text)
        if role in {"coach", "system"} and text.startswith(("Bienvenido.", "Chat grupal listo.")):
            if default_key in seen_defaults:
                continue
            seen_defaults.add(default_key)

        if deduped:
            previous = deduped[-1]
            same_content = (
                previous.get("role") == role
                and previous.get("sender", "") == sender
                and (previous.get("text") or "").strip() == text
            )
            if same_content:
                continue

        deduped.append(message)
    return deduped


def sync_chats_to_supabase(state):
    if not get_supabase_config() or not isinstance(state, dict):
        return

    users = state.get("users", {})
    profiles = {}
    for user_name in users.keys():
        profile = get_or_create_profile(user_name)
        profiles[user_name] = profile

    team = get_or_create_team()
    for profile in profiles.values():
        ensure_team_member(team["id"], profile["id"])

    for user_name, user_state in users.items():
        profile = profiles.get(user_name)
        if not profile:
            continue
        conversation = get_or_create_conversation("personal", profile_id=profile["id"], title=f"Coach personal - {user_name}")
        for message in user_state.get("messages", []):
            body = (message.get("text") or "").strip()
            if not body:
                continue
            client_id = stable_message_id(f"personal:{user_name}", message)
            if supabase_select_one("messages", {"client_message_id": f"eq.{client_id}"}, "id"):
                continue
            role = message.get("role", "user")
            supabase_insert_ignore(
                "messages",
                {
                    "conversation_id": conversation["id"],
                    "profile_id": profile["id"] if role == "user" else None,
                    "sender_type": sender_type_from_role(role),
                    "body": body,
                    "mentions_coach": "@coach" in body.lower(),
                    "client_message_id": client_id,
                    "created_at": iso_timestamp(message.get("at")),
                    "ai_context": {"scope": "personal", "user": user_name},
                },
            )

    group_conversation = get_or_create_conversation("group", team_id=team["id"], title=DEFAULT_GROUP_NAME)
    for message in state.get("groupMessages", []):
        body = (message.get("text") or "").strip()
        if not body:
            continue
        sender = message.get("sender", "")
        profile = profiles.get(sender)
        client_id = stable_message_id("group:los-pichudos", message)
        if supabase_select_one("messages", {"client_message_id": f"eq.{client_id}"}, "id"):
            continue
        role = message.get("role", "user")
        supabase_insert_ignore(
            "messages",
            {
                "conversation_id": group_conversation["id"],
                "profile_id": profile["id"] if profile and role == "user" else None,
                "team_id": team["id"],
                "sender_type": sender_type_from_role(role),
                "body": body,
                "mentions_coach": "@coach" in body.lower(),
                "client_message_id": client_id,
                "created_at": iso_timestamp(message.get("at")),
                "ai_context": {"scope": "group", "sender": sender},
            },
        )


def load_chats_from_supabase(state):
    if not get_supabase_config() or not isinstance(state, dict):
        return state

    users = state.get("users", {})
    for user_name in list(users.keys()):
        profile = supabase_select_one("profiles", {"display_name": f"eq.{user_name}"}, "id,display_name")
        if not profile:
            continue
        conversation = supabase_select_one("conversations", {"kind": "eq.personal", "profile_id": f"eq.{profile['id']}"}, "id")
        if not conversation:
            continue
        rows = supabase_select_many(
            "messages",
            {"conversation_id": f"eq.{conversation['id']}", "created_at": f"gte.{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - CHAT_RETENTION_DAYS * 24 * 60 * 60))}"},
            "id,sender_type,body,created_at,mentions_coach,profiles(display_name)",
            "created_at.asc",
            500,
        )
        if rows:
            users[user_name]["messages"] = dedupe_client_messages(
                [message_to_client(row, personal_user=user_name) for row in rows]
            )

    team = supabase_select_one("teams", {"slug": f"eq.{DEFAULT_GROUP_SLUG}"}, "id")
    if team:
        conversation = supabase_select_one("conversations", {"kind": "eq.group", "team_id": f"eq.{team['id']}"}, "id")
        if conversation:
            rows = supabase_select_many(
                "messages",
                {"conversation_id": f"eq.{conversation['id']}", "created_at": f"gte.{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - CHAT_RETENTION_DAYS * 24 * 60 * 60))}"},
                "id,sender_type,body,created_at,mentions_coach,profiles(display_name)",
                "created_at.asc",
                800,
            )
            if rows:
                state["groupMessages"] = dedupe_client_messages([
                    {
                        **message_to_client(row),
                        "sender": (
                            row.get("profiles", {}).get("display_name")
                            if isinstance(row.get("profiles"), dict) and row.get("profiles", {}).get("display_name")
                            else ("Coach" if row.get("sender_type") == "coach_ai" else "Sistema")
                        ),
                    }
                    for row in rows
                ])
    return prune_state(state)


def file_kind_for(filename, content_type=""):
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf" or content_type == "application/pdf":
        return "pdf"
    if suffix == ".docx":
        return "docx"
    if suffix == ".xlsx":
        return "xlsx"
    if suffix == ".csv":
        return "csv"
    if suffix in {".txt", ".md", ".tsv"}:
        return "txt"
    if content_type.startswith("image/"):
        return "image"
    if content_type.startswith("audio/"):
        return "audio"
    return "other"


def validate_plan_upload(filename, data):
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_PLAN_SUFFIXES:
        allowed = ", ".join(sorted(SUPPORTED_PLAN_SUFFIXES))
        raise RuntimeError(f"Formato no soportado para planes: {suffix or 'sin extension'}. UsÃ¡ uno de estos: {allowed}.")
    if len(data) > MAX_PLAN_FILE_BYTES:
        raise RuntimeError("El archivo es muy grande para esta beta. SubÃ­ un archivo de 25 MB o menos.")
    if suffix == ".pdf":
        return "file"
    return "text"


def archive_active_plans(profile_id, plan_type):
    if not get_supabase_config():
        return []
    return supabase_update(
        "plans",
        {"profile_id": f"eq.{profile_id}", "plan_type": f"eq.{plan_type}", "status": "eq.active"},
        {"status": "archived", "archived_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
    )


def storage_object_path(bucket, profile_id, filename, plan_id=None, checkin_id=None):
    safe_name = safe_upload_name(filename)
    if bucket == "plan-files":
        return f"profiles/{profile_id}/plans/{plan_id or 'unassigned'}/{safe_name}"
    if bucket == "checkin-evidence":
        return f"profiles/{profile_id}/checkins/{checkin_id or 'unassigned'}/{safe_name}"
    return f"profiles/{profile_id}/avatar/{safe_name}"


def upload_supabase_storage(bucket, object_path, data, content_type):
    config = get_supabase_config()
    if not config:
        return None
    encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in object_path.split("/"))
    request = urllib.request.Request(
        f"{config['url']}/storage/v1/object/{bucket}/{encoded_path}",
        data=data,
        headers={
            "apikey": config["service_key"],
            "Authorization": f"Bearer {config['service_key']}",
            "Content-Type": content_type or "application/octet-stream",
            "x-upsert": "false",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {"path": object_path}
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase Storage respondiÃ³ {exc.code}: {details}") from exc


def create_supabase_signed_url(bucket, object_path, expires_in=SIGNED_URL_TTL_SECONDS):
    encoded_path = "/".join(urllib.parse.quote(part, safe="") for part in object_path.split("/"))
    result = supabase_request(
        "POST",
        f"/storage/v1/object/sign/{bucket}/{encoded_path}",
        {"expiresIn": expires_in},
    )
    if isinstance(result, dict):
        signed = result.get("signedURL") or result.get("signedUrl")
        if signed and signed.startswith("http"):
            return signed
        if signed:
            config = get_supabase_config()
            return f"{config['url']}/storage/v1{signed}"
    return ""


def create_plan_storage_record(user_name, plan_type, filename, data, content_type, user_notes, summary, response_id="", extracted_text="", openai_file_id=""):
    if not get_supabase_config():
        return None
    profile = get_or_create_profile(user_name)
    archive_active_plans(profile["id"], plan_type)
    plan = supabase_insert(
        "plans",
        {
            "profile_id": profile["id"],
            "plan_type": plan_type,
            "status": "active",
            "source": "upload",
            "title": filename,
            "user_notes": user_notes,
            "summary": summary,
            "structured_plan": {
                "summary": summary,
                "response_id": response_id,
                "source": "openai_upload_analysis",
                "file_name": filename,
            },
            "activated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )
    object_path = storage_object_path("plan-files", profile["id"], filename, plan.get("id"))
    upload_supabase_storage("plan-files", object_path, data, content_type)
    signed_url = create_supabase_signed_url("plan-files", object_path)
    plan_file = supabase_insert(
        "plan_files",
        {
            "plan_id": plan["id"],
            "profile_id": profile["id"],
            "bucket": "plan-files",
            "storage_path": object_path,
            "original_filename": filename,
            "content_type": content_type,
            "file_kind": file_kind_for(filename, content_type),
            "size_bytes": len(data),
            "extracted_text": extracted_text or None,
            "openai_file_id": openai_file_id or None,
            "metadata": {"signed_url_ttl_seconds": SIGNED_URL_TTL_SECONDS},
        },
    )
    return {"profile": profile, "plan": plan, "file": plan_file, "signedUrl": signed_url, "storagePath": object_path}


def create_conversation_plan_record(user_name, plan_type, notes, summary, response_id=""):
    if not get_supabase_config():
        return None
    profile = get_or_create_profile(user_name)
    archive_active_plans(profile["id"], plan_type)
    return supabase_insert(
        "plans",
        {
            "profile_id": profile["id"],
            "plan_type": plan_type,
            "status": "active",
            "source": "conversation",
            "title": f"Plan de {PLAN_LABELS.get(plan_type, plan_type)} creado por IA",
            "user_notes": notes,
            "summary": summary,
            "structured_plan": {
                "summary": summary,
                "response_id": response_id,
                "source": "openai_conversation",
            },
            "activated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )


def create_checkin_evidence_storage_record(user_name, filename, data, content_type):
    if not get_supabase_config():
        return None
    profile = get_or_create_profile(user_name)
    today = time.strftime("%Y-%m-%d")
    checkin = supabase_select_one(
        "checkins",
        {"profile_id": f"eq.{profile['id']}", "checkin_date": f"eq.{today}"},
        "id,profile_id,checkin_date",
    )
    if not checkin:
        checkin = supabase_insert(
            "checkins",
            {
                "profile_id": profile["id"],
                "checkin_date": today,
                "notes": "Evidencia cargada desde beta.",
                "metrics": {"source": "upload-evidence-endpoint"},
            },
        )
    object_path = storage_object_path("checkin-evidence", profile["id"], filename, checkin.get("id"))
    upload_supabase_storage("checkin-evidence", object_path, data, content_type)
    signed_url = create_supabase_signed_url("checkin-evidence", object_path)
    checkin_file = supabase_insert(
        "checkin_files",
        {
            "checkin_id": checkin["id"],
            "profile_id": profile["id"],
            "bucket": "checkin-evidence",
            "storage_path": object_path,
            "original_filename": filename,
            "content_type": content_type,
            "file_kind": file_kind_for(filename, content_type),
            "size_bytes": len(data),
            "metadata": {"signed_url_ttl_seconds": SIGNED_URL_TTL_SECONDS},
        },
    )
    return {"profile": profile, "checkin": checkin, "file": checkin_file, "signedUrl": signed_url, "storagePath": object_path}


def normalize_checkin_date(value):
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value
    return time.strftime("%Y-%m-%d")


def checkin_metrics(done=None, evidence=None, source="checkin-endpoint"):
    done = done if isinstance(done, list) else []
    metrics = {
        "source": source,
        "completed_items": done,
        "completed_count": len(done),
    }
    if evidence:
        metrics["evidence"] = evidence
    return metrics


def upsert_checkin_record(profile, team, payload):
    checkin_date = normalize_checkin_date(payload.get("date"))
    done = payload.get("done") if isinstance(payload.get("done"), list) else []
    note = (payload.get("note") or "").strip()
    evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
    record = {
        "profile_id": profile["id"],
        "team_id": team["id"] if team else None,
        "checkin_date": checkin_date,
        "goal_completed": bool(done),
        "notes": note or None,
        "metrics": checkin_metrics(done, evidence),
    }
    existing = supabase_select_one(
        "checkins",
        {"profile_id": f"eq.{profile['id']}", "checkin_date": f"eq.{checkin_date}"},
        "id,profile_id,team_id,checkin_date,goal_completed,notes,metrics,created_at,updated_at",
    )
    if existing:
        updated = supabase_update("checkins", {"id": f"eq.{existing['id']}"}, record)
        return updated[0] if updated else existing
    return supabase_insert("checkins", record)


def recent_checkins_for_profile(profile_id, limit=7):
    if not get_supabase_config() or not profile_id:
        return []
    return supabase_select_many(
        "checkins",
        {"profile_id": f"eq.{profile_id}"},
        "id,checkin_date,goal_completed,notes,metrics,created_at,updated_at",
        order="checkin_date.desc",
        limit=limit,
    )


def multipart_body(fields, files):
    boundary = f"----pichudos-{uuid.uuid4().hex}"
    chunks = []

    for name, value in fields.items():
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"))
        chunks.append(str(value).encode("utf-8"))
        chunks.append(b"\r\n")

    for name, file_info in files.items():
        filename = file_info["filename"]
        content_type = file_info.get("content_type") or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        chunks.append(f"--{boundary}\r\n".encode("utf-8"))
        chunks.append(
            (
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
                f"Content-Type: {content_type}\r\n\r\n"
            ).encode("utf-8")
        )
        chunks.append(file_info["bytes"])
        chunks.append(b"\r\n")

    chunks.append(f"--{boundary}--\r\n".encode("utf-8"))
    return boundary, b"".join(chunks)


def upload_openai_file(filename, data, content_type):
    boundary, body = multipart_body(
        {"purpose": "user_data"},
        {"file": {"filename": filename, "bytes": data, "content_type": content_type}},
    )
    request = urllib.request.Request(
        OPENAI_FILES_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {get_openai_api_key()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload["id"]
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI Files respondió {exc.code}: {details}") from exc


def call_openai(input_items, max_output_tokens=1200):
    api_key = get_openai_api_key()

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
        if public_path == "/api/config":
            public_config = get_supabase_public_config()
            json_response(
                self,
                200,
                {
                    "supabaseUrl": public_config["url"] if public_config else "",
                    "supabaseAnonKey": public_config["anon_key"] if public_config else "",
                    "authProvider": "google" if public_config else "beta",
                },
            )
            return
        if public_path == "/api/app-state":
            state = read_app_state()
            try:
                state = load_chats_from_supabase(state)
            except Exception:
                pass
            json_response(self, 200, {"state": state})
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
            elif self.path == "/api/auth/session":
                self.handle_auth_session()
            elif self.path == "/api/checkin":
                self.handle_checkin()
            else:
                json_response(self, 404, {"error": "Ruta no encontrada."})
        except Exception as exc:
            json_response(self, 500, {"error": str(exc)})

    def authenticated_session(self):
        access_token = access_token_from_headers(self.headers)
        if not access_token:
            return None
        return ensure_authenticated_profile(access_token)

    def request_identity(self, fallback):
        session = self.authenticated_session()
        if session:
            return {
                "profile": session["profile"],
                "team": session["team"],
                "user_name": session["profile"]["displayName"],
                "authenticated": True,
            }
        user_name = fallback or "Usuario"
        profile = get_or_create_profile(user_name)
        team = get_or_create_team()
        ensure_team_member(team["id"], profile["id"])
        return {
            "profile": {
                "id": profile["id"],
                "displayName": profile["display_name"],
                "email": profile.get("email", ""),
                "role": profile.get("default_role", "athlete"),
            },
            "team": team,
            "user_name": profile["display_name"],
            "authenticated": False,
        }

    def request_user_name(self, fallback):
        return self.request_identity(fallback)["user_name"]

    def handle_analyze_plan(self):
        fields, files = parse_multipart(self.headers, read_request_body(self))
        plan_type = fields.get("planType", "wellness")
        user_notes = fields.get("notes", "")
        user_name = self.request_user_name(fields.get("user", "Usuario"))
        file_data = files.get("file")
        if not file_data:
            json_response(self, 400, {"error": "No se recibió archivo."})
            return

        filename = file_data["filename"]
        data = file_data["bytes"]
        extraction_strategy = validate_plan_upload(filename, data)
        ensure_data_dirs()
        stored_name = safe_upload_name(filename)
        (UPLOAD_DIR / stored_name).write_bytes(data)
        file_url = f"/uploads/{stored_name}"
        try:
            extracted = trim_text(extract_text(filename, data))
        except Exception as exc:
            raise RuntimeError(f"No pude extraer texto de {filename}. Si es Word/Excel, guardalo como DOCX, XLSX o CSV e intentalo de nuevo.") from exc
        if extraction_strategy == "text" and not extracted:
            raise RuntimeError("No pude leer texto del archivo. ProbÃ¡ convertirlo a PDF, DOCX, XLSX, CSV o TXT y subilo de nuevo.")
        content = [{"type": "input_text", "text": build_analysis_prompt(plan_type, filename, extracted, user_notes)}]
        openai_file_id = ""

        if extraction_strategy == "file":
            openai_file_id = upload_openai_file(filename, data, file_data["content_type"])
            content = [
                {
                    "type": "input_file",
                    "file_id": openai_file_id,
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
        storage_record = create_plan_storage_record(
            user_name,
            plan_type,
            filename,
            data,
            file_data["content_type"],
            user_notes,
            answer,
            response_id,
            extracted,
            openai_file_id,
        )
        if storage_record and storage_record.get("signedUrl"):
            file_url = storage_record["signedUrl"]
        json_response(
            self,
            200,
            {
                "planType": plan_type,
                "name": filename,
                "summary": answer,
                "responseId": response_id,
                "extraction": "text" if extraction_strategy == "text" else "file",
                "fileUrl": file_url,
                "storage": {
                    "provider": "supabase" if storage_record else "local",
                    "bucket": storage_record["file"]["bucket"] if storage_record else "",
                    "path": storage_record["storagePath"] if storage_record else "",
                    "planId": storage_record["plan"]["id"] if storage_record else "",
                    "fileId": storage_record["file"]["id"] if storage_record else "",
                },
                "notes": user_notes,
            },
        )

    def handle_create_plan(self):
        payload = json.loads(read_request_body(self).decode("utf-8"))
        plan_type = payload.get("planType", "wellness")
        notes = payload.get("notes", "")
        messages = payload.get("messages", [])
        user_name = self.request_user_name(payload.get("user", "Usuario"))
        prompt = build_creation_prompt(plan_type, notes, messages)
        answer, response_id = call_openai(
            [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}],
            max_output_tokens=1300,
        )
        plan_record = create_conversation_plan_record(user_name, plan_type, notes, answer, response_id)
        json_response(
            self,
            200,
            {
                "planType": plan_type,
                "name": f"Plan de {PLAN_LABELS.get(plan_type, plan_type)} creado por IA",
                "summary": answer,
                "responseId": response_id,
                "storage": {
                    "provider": "supabase" if plan_record else "local",
                    "planId": plan_record["id"] if plan_record else "",
                },
            },
        )

    def handle_chat(self):
        payload = json.loads(read_request_body(self).decode("utf-8"))
        message = payload.get("message", "")
        plans = payload.get("plans", {})
        checkins = payload.get("checkins", [])
        identity = self.request_identity(payload.get("user", "Usuario")) if access_token_from_headers(self.headers) else None
        if identity and identity.get("profile", {}).get("id"):
            db_checkins = recent_checkins_for_profile(identity["profile"]["id"])
            if db_checkins:
                checkins = db_checkins
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
        sync_warning = ""
        try:
            sync_chats_to_supabase(saved)
        except Exception as exc:
            sync_warning = str(exc)
        json_response(self, 200, {"ok": True, "serverSavedAt": saved.get("serverSavedAt"), "syncWarning": sync_warning})

    def handle_auth_session(self):
        payload = json.loads(read_request_body(self).decode("utf-8"))
        access_token = payload.get("accessToken", "")
        if not access_token:
            json_response(self, 401, {"error": "Falta accessToken."})
            return
        session = ensure_authenticated_profile(access_token)
        json_response(self, 200, session)

    def handle_checkin(self):
        payload = json.loads(read_request_body(self).decode("utf-8"))
        identity = self.request_identity(payload.get("user", "Usuario"))
        checkin = upsert_checkin_record(identity["profile"], identity["team"], payload)
        json_response(
            self,
            200,
            {
                "ok": True,
                "checkin": checkin,
                "profile": identity["profile"],
                "team": identity["team"],
            },
        )

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
        user_name = self.request_user_name(fields.get("user", "Usuario"))
        storage_record = create_checkin_evidence_storage_record(
            user_name,
            file_data["filename"],
            file_data["bytes"],
            file_data["content_type"],
        )
        file_url = storage_record["signedUrl"] if storage_record and storage_record.get("signedUrl") else f"/uploads/{filename}"
        json_response(
            self,
            200,
            {
                "url": file_url,
                "name": file_data["filename"],
                "storedName": filename,
                "contentType": file_data["content_type"],
                "size": len(file_data["bytes"]),
                "user": user_name,
                "storage": {
                    "provider": "supabase" if storage_record else "local",
                    "bucket": storage_record["file"]["bucket"] if storage_record else "",
                    "path": storage_record["storagePath"] if storage_record else "",
                    "checkinId": storage_record["checkin"]["id"] if storage_record else "",
                    "fileId": storage_record["file"]["id"] if storage_record else "",
                },
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
