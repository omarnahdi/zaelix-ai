from agno.agent import Agent
from agno.tools.google.gmail import GmailTools
from agno.models.mistral import MistralChat
from dotenv import load_dotenv
from instructions import INSTRUCTIONS_TEMPLATE 
from agno.os.app import AgentOS
from agno.db.postgres import PostgresDb
from agno.os.interfaces.telegram import Telegram
import re
import os
import base64, tempfile

load_dotenv()

PERSONAL_EMAIL = os.getenv("PERSONAL_EMAIL")
WORK_EMAIL = os.getenv("WORK_EMAIL")
WORK_ALIAS = os.getenv("WORK_ALIAS") or "Not configured"

INSTRUCTIONS = INSTRUCTIONS_TEMPLATE.format(
    personal_email=PERSONAL_EMAIL,
    work_email=WORK_EMAIL,
    work_alias=WORK_ALIAS,
)

def write_temp_json(env_var: str, fallback_path: str = None) -> str:
    val = os.getenv(env_var)
    if val:
        data = base64.b64decode(val)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".json")
        tmp.write(data)
        tmp.close()
        return tmp.name
    elif fallback_path and os.path.exists(fallback_path):
        return fallback_path
    else:
        raise ValueError(f"Missing env var {env_var} and no valid fallback path: {fallback_path}")

creds_path = write_temp_json("GMAIL_CREDS_B64", "creds/client_secret_XXX.apps.googleusercontent.com.json")
personal_token_path = write_temp_json("PERSONAL_TOKEN_B64", "personal_token/personal.json")
work_token_path = write_temp_json("WORK_TOKEN_B64", "work_token/work.json")


# Strip whole <style>/<script> blocks (and their contents) before tag-stripping
CSS_BLOCK_RE = re.compile(r"<style[^>]*>.*?</style>", re.DOTALL | re.IGNORECASE)
SCRIPT_BLOCK_RE = re.compile(r"<script[^>]*>.*?</script>", re.DOTALL | re.IGNORECASE)

# Heuristics for CSS-looking lines that leak in as plain text
_CSS_LINE_PATTERNS = [
    re.compile(r"^[.#@][\w\-\.\#\[\]=\"' >:,\*]*\{?\s*$"),   # .class, #id, @media, @font-face
    re.compile(r"^:root\s*\{?\s*$"),                          # :root
    re.compile(r"^[\w\-]+\s*:\s*.+;\s*$"),                    # property: value;
    re.compile(r"^[{}]\s*$"),                                 # lone braces
    re.compile(r".*\{\s*$"),                                  # selector opening brace
    re.compile(r"^\s*/\*.*\*/\s*$"),                           # /* comments */
    re.compile(r"^(-webkit-|-ms-|-moz-)"),                     # vendor prefixes
    re.compile(r"^\[data-ogsc\]|^\[data-ogsb\]"),              # dark-mode client hacks
]

def _looks_like_css(line: str) -> bool:
    if not line:
        return False
    if any(p.match(line) for p in _CSS_LINE_PATTERNS):
        return True
    # fallback heuristic: dense css punctuation (e.g. "color: #000 !important;")
    css_chars = sum(line.count(c) for c in "{};:")
    return css_chars >= 2 and len(line) < 200


class HtmlStrippedGmail(GmailTools):
    def _get_message_body(self, msg_data: dict) -> str:
        body = super()._get_message_body(msg_data)

        # 1. Nuke entire <style>/<script> blocks, contents included
        body = CSS_BLOCK_RE.sub("", body)
        body = SCRIPT_BLOCK_RE.sub("", body)

        # 2. Strip remaining HTML tags
        body = re.sub(r"<[^>]+>", "", body)

        # 3. Drop leftover CSS-looking lines line-by-line
        cleaned_lines = []
        for line in body.splitlines():
            line = line.strip()
            if not line or _looks_like_css(line):
                continue
            cleaned_lines.append(line)

        body = "\n".join(cleaned_lines)
        return body[:5000]

class PersonalGmail(HtmlStrippedGmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "personal_gmail"
        for fname in list(self.functions.keys()):
            func = self.functions.pop(fname)
            func.name = f"personal_{fname}"
            self.functions[f"personal_{fname}"] = func

class WorkGmail(HtmlStrippedGmail):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = "work_gmail"
        for fname in list(self.functions.keys()):
            func = self.functions.pop(fname)
            func.name = f"work_{fname}"
            self.functions[f"work_{fname}"] = func

personal_gmail = PersonalGmail(
    credentials_path= creds_path, 
    token_path= personal_token_path, 
    max_body_length=1000,      # ← truncate bodies to 500 chars
    include_html=False,        # ← strip HTML, plain text only
    login_hint=PERSONAL_EMAIL
)

work_gmail = WorkGmail(
    credentials_path=creds_path, #"/app/creds/client_secret_XXXapps.googleusercontent.com.json",
    token_path= work_token_path, #"/app/work_token/work.json",
    max_body_length=1000,      # ← truncate bodies to 500 chars
    include_html=False,        # ← strip HTML, plain text only
    login_hint=WORK_EMAIL
)

port = int(os.getenv("PORT", 8080))

USE_LOCAL_DB = os.getenv("USE_LOCAL_DB", "true").lower() == "true"

if USE_LOCAL_DB:
    from agno.db.sqlite import SqliteDb
    agent_db = SqliteDb(db_file="tmp/persistent_memory.db")
    print("Using local SQLite database")
else:
    DATABASE_URL = os.getenv("NEON_DB")
    agent_db = PostgresDb(DATABASE_URL)
    if not DATABASE_URL:
        raise ValueError("NEON_DB is missing in .env")

    print("Using Neon PostgreSQL database")



mistral_agent = Agent(
    model=MistralChat(
        # id="mistral-small-2506",
        retries=3,
        delay_between_retries=2, 
        exponential_backoff=True,
        # timeout=300
    ),
    tools=[
        personal_gmail,
        work_gmail,

    ],
    db=agent_db,
    add_history_to_context=True,
    num_history_runs=3,
    add_datetime_to_context=True,
    markdown=True,
    name="Mistral Email Agent",
    instructions=INSTRUCTIONS,
    debug_mode=True
)


tele_token = os.getenv("TELEGRAM_TOKEN")


agent_os = AgentOS(
    agents=[mistral_agent],
    interfaces=[
        Telegram(agent=mistral_agent, token=tele_token),
        ],
    authorization=True,
)
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="email_agent:app",host="0.0.0.0", reload=True,port=port)


