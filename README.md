# Zaelix AI

**A single AI agent that manages two Gmail inboxes — work and personal — through one unified interface.**

Zaelix AI is built on [Agno](https://docs.agno.com/) and Google's Gmail API. Instead of running two separate agents or juggling two Gmail tabs, Zaelix gives one agent dual-inbox awareness: it can read, search, triage, draft, and reply across both your personal and work Gmail accounts, keeping each inbox's tools clearly namespaced so the agent (and you) always know which mailbox it's acting on.

Deployable on **Google Cloud Run** or run entirely **locally**. Optional **Telegram bot** interface for chatting with your inboxes from your phone.

---

## ✨ Features

- **Dual-inbox support** — one agent, two Gmail accounts (personal + work), each with its own OAuth token and isolated toolset
- **Namespaced tools** — every Gmail function is prefixed (`personal_get_latest_emails`, `work_send_email`, etc.) so the agent never confuses which inbox it's operating on
- **Clean, LLM-friendly email bodies** — HTML is stripped, whitespace is normalized, and bodies are truncated to keep context windows lean
- **Container-friendly credential loading** — credentials and tokens can be supplied as base64-encoded environment variables (great for Cloud Run / serverless) or as local file paths (great for local dev)
- **Deploy anywhere** — run locally with plain file-based tokens, or deploy to Google Cloud Run using env-var-encoded secrets
- **Optional Telegram interface** — talk to your agent, and by extension both inboxes, from a Telegram chat

---

## 🧠 How dual-inbox support works

Zaelix wraps Agno's `GmailTools` twice — once per inbox — and renames every tool function with an inbox-specific prefix so the underlying LLM agent can tell them apart and call the correct one.

```python
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

creds_path = write_temp_json("GMAIL_CREDS_B64", "creds/client_secret_XXXX.apps.googleusercontent.com.json")
personal_token_path = write_temp_json("PERSONAL_TOKEN_B64", "personal_token/personal.json")
work_token_path = write_temp_json("WORK_TOKEN_B64", "work_token/work.json")

class HtmlStrippedGmail(GmailTools):
    def _get_message_body(self, msg_data: dict) -> str:
        body = super()._get_message_body(msg_data)
        body = re.sub(r"<[^>]+>", "", body)
        body = "\n".join(line.strip() for line in body.splitlines() if line.strip())
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
    credentials_path=creds_path,
    token_path=personal_token_path,
    max_body_length=1000,
    include_html=False,
    login_hint=os.getenv("PERSONAL_EMAIL")
)

work_gmail = WorkGmail(
    credentials_path=creds_path,
    token_path=work_token_path,
    max_body_length=1000,
    include_html=False,
    login_hint=os.getenv("WORK_EMAIL")
)
```

**What's happening here:**

1. **`write_temp_json`** loads credentials either from a base64 env var (decoded into a temp file — ideal for Cloud Run secrets) or from a local JSON file path (ideal for local dev). One function handles both deployment modes.
2. **`HtmlStrippedGmail`** is a shared base class that overrides Agno's message body parsing to strip HTML tags, collapse blank lines, and cap body length — keeping emails clean and token-efficient before they ever reach the LLM.
3. **`PersonalGmail`** and **`WorkGmail`** each subclass that base, then rename every registered tool function with a `personal_` or `work_` prefix. This is the core of dual-inbox support: the agent sees two completely distinct sets of tools (`personal_search_emails` vs. `work_search_emails`, etc.) instead of one ambiguous Gmail toolkit, so it always acts on the inbox you intend.
4. **`login_hint`** pre-selects which Google account to authenticate during the OAuth consent flow, so the browser window opens with the right account already suggested instead of defaulting to whichever Google account you're currently logged into. This is pulled automatically from the `PERSONAL_EMAIL` and `WORK_EMAIL` environment variables — you don't need to touch the code at all.

> ⚠️ **Important — set your email addresses in `.env`, not in the code.** Before running Zaelix, set `PERSONAL_EMAIL` and `WORK_EMAIL` in your `.env` file to your **own** Gmail addresses (see [Setting up your `.env` file](#️-setting-up-your-env-file)). The code reads these automatically via `os.getenv(...)` — leaving them blank or mismatched will cause the wrong account to be authorized, or the OAuth flow to fail.

Both `personal_gmail` and `work_gmail` instances are then passed into the Agno agent's `tools` list together, giving one agent simultaneous, clearly-separated access to both inboxes.

---

## 📁 Project structure

```
zaelix-ai/
├── creds/
│   └── client_secret_XXXX.apps.googleusercontent.com.json   # OAuth client (shared by both inboxes)
├── personal_token/
│   └── personal.json           # OAuth token for the personal inbox (auto-created on first auth)
├── work_token/
│   └── work.json                # OAuth token for the work inbox (auto-created on first auth)
├── tmp/                          # Scratch/runtime files (safe to ignore, safe to delete)
├── .venv/                        # Local virtual environment (created by uv)
├── .env                          # Your actual secrets — never commit this
├── .env.example                  # Template for required environment variables
├── env.yaml                      # Your actual GCP deploy env vars — never commit this
├── env.yaml.example              # Template for Cloud Run deployment env vars
├── email_agent.py                 # Core agent + dual Gmail tool setup
├── first_run.py                   # One-time script to generate OAuth creds/tokens (opens browser)
├── instructions.py                # Agent instructions/prompt configuration
├── models-list.py                 # Model listing/reference helper
├── creds_b64.txt                  # Base64-encoded OAuth client secret (for env.yaml / Cloud Run)
├── personal_b64.txt               # Base64-encoded personal token (for env.yaml / Cloud Run)
├── work_b64.txt                   # Base64-encoded work token (for env.yaml / Cloud Run)
├── Dockerfile
├── pyproject.toml                 # Project dependencies (managed with uv)
├── uv.lock
├── .python-version
├── .gitignore
└── README.md
```

The `credentials_path` (OAuth client secret JSON) is **shared** across both inboxes — it identifies your Google Cloud OAuth app, not a specific mailbox. The `token_path` for each inbox is what's actually per-account, since each one stores that account's own access/refresh tokens after you authenticate.

> The `*_b64.txt` files and `env.yaml` are only needed when you're ready to deploy to Cloud Run — see the [Deploying to Google Cloud Run](#️-deploying-to-google-cloud-run) section. Keep them out of version control (see `.gitignore` below).

---

## 🔧 Prerequisites

- Python 3.10+ (see `.python-version` for the exact version used)
- [`uv`](https://docs.astral.sh/uv/) — this project's dependencies are managed via `pyproject.toml` / `uv.lock`
- A Google Cloud project with the **Gmail API** enabled
- Two Gmail accounts you want the agent to manage (personal + work)
- A **Mistral API key** ([console.mistral.ai](https://console.mistral.ai)) — Zaelix's agent is powered by Mistral
- (Optional) A Telegram bot token, if you want the Telegram interface
- (Optional) A Neon PostgreSQL database, if you don't want to use local SQLite
- (Optional) A Google Cloud account, if deploying to Cloud Run

Install dependencies:

```bash
uv sync
```

This reads `pyproject.toml` and `uv.lock`, creates/updates `.venv`, and installs everything the project needs — including Agno and the Gmail API client libraries.

---

## 🔑 Setting up Gmail OAuth (one client, two tokens)

Zaelix uses **one OAuth client** (your Google Cloud app credentials) to authenticate **two separate Gmail accounts**, producing two separate token files. Follow Agno's official Gmail setup guide for the underlying OAuth flow: **[docs.agno.com/tools/toolkits/social/gmail](https://docs.agno.com/tools/toolkits/social/gmail)**.

### Step 1 — Enable the Gmail API and create OAuth credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/apis/enableflow?apiid=gmail.googleapis.com) and enable the **Gmail API** for your project.
2. Go to **APIs & Services → OAuth consent screen**.
3. Choose **External** (unless you're on Google Workspace, in which case choose **Internal**).
4. Fill in the required app details (name, support email, etc.).
5. Under **Scopes**, add whichever scopes you need:
   - Read-only: `.../auth/gmail.readonly`
   - Full access (read, send, compose): `.../auth/gmail.modify` and `.../auth/gmail.compose`
6. Under **Test users**, add **both** of your Gmail addresses (personal and work) — while the app is in "Testing" mode, only listed test users can complete the OAuth flow. Any other account will get an access-denied error.
7. Go to **Credentials → Create Credentials → OAuth Client ID**.
8. Set **Application type** to **Desktop app**, then create and **download the JSON** file.
9. Save that file into the `creds/` folder — this is your `GMAIL_CREDS_B64` / `credentials_path` source, shared by both inboxes.

### Step 2 — Generate two separate token paths

Each inbox needs its **own** token file, generated by authenticating that specific Gmail account against the shared OAuth client:

```
personal_token/personal.json
work_token/work.json
```

These files are created **automatically** the first time each `GmailTools` subclass runs its OAuth flow — you don't create them by hand. What you need to do is:

1. Make sure `PERSONAL_EMAIL` in your `.env` file is set to your **personal** Gmail address, and `WORK_EMAIL` is set to your **work** Gmail address (see [Setting up your `.env` file](#️-setting-up-your-env-file) — **no code changes needed**, `login_hint` picks these up automatically via `os.getenv(...)`).
2. Run the agent locally for the first time. Each Gmail tool instance will open a browser window for its respective OAuth consent screen (pre-filled thanks to `login_hint`).
3. Log in with the matching account for each prompt — personal account for the `personal_gmail` prompt, work account for the `work_gmail` prompt.
4. On successful authorization, Agno writes the access/refresh tokens to `personal_token/personal.json` and `work_token/work.json` respectively. From then on, both inboxes refresh their tokens silently without further browser prompts (until a token is revoked or expires).

> If you're deploying somewhere without browser access (like a headless server or a first-time Cloud Run deploy), generate both token files **locally first**, then upload/encode them as described below.

### Where to place credentials and tokens

| File | Local path | Purpose |
| --- | --- | --- |
| OAuth client secret | `creds/client_secret_XXXX.apps.googleusercontent.com.json` | Shared Google Cloud OAuth app credentials |
| Personal inbox token | `personal_token/personal.json` | Personal Gmail account's access/refresh tokens |
| Work inbox token | `work_token/work.json` | Work Gmail account's access/refresh tokens |

Keep all three out of version control — add them to `.gitignore`:

```gitignore
creds/
personal_token/
work_token/
*.json
.env
env.yaml
*_b64.txt
```

---

## 🗝️ Setting up your `.env` file

Zaelix reads its configuration from a `.env` file locally. Copy the template and fill it in:

```bash
cp .env.example .env
```

```dotenv
# Google Gmail credentials (base64 encoded)
# Run: certutil -encode creds/your_creds.json creds_b64.txt (Windows)
# Run: base64 -i creds/your_creds.json (Mac/Linux)
GMAIL_CREDS_B64: "paste_base64_output_here"

# Personal Gmail OAuth token (base64 encoded)
# Generated after first local OAuth login
PERSONAL_TOKEN_B64: "paste_base64_output_here"

# Work Gmail OAuth token (base64 encoded)
WORK_TOKEN_B64: "paste_base64_output_here"

# Telegram bot token
# Get from @BotFather on Telegram → /newbot
TELEGRAM_TOKEN: "your_telegram_bot_token"

# Telegram webhook secret for request validation
# Any random string you choose, must match what you pass to setWebhook
TELEGRAM_WEBHOOK_SECRET_TOKEN: "your_random_secret"

# Mistral API key
# Get from https://console.mistral.ai
MISTRAL_API_KEY: "your_mistral_api_key"

# Set to false to use Neon PostgreSQL instead of local SQLite
USE_LOCAL_DB: "true"

# Neon PostgreSQL connection string (only needed if USE_LOCAL_DB=false)
# Get from https://neon.tech → your project → connection string
NEON_DB: "postgresql://user:password@host/dbname"

# Replace with your personal and work email addresses. (Work alias is optional and is handy if you have a separate address that forwards mails to work email)
PERSONAL_EMAIL: "your.personal@gmail.com"
WORK_EMAIL: "your.work@gmail.com"
WORK_ALIAS: ""
```

**Notes on specific variables:**

| Variable | Required? | Notes |
| --- | --- | --- |
| `GMAIL_CREDS_B64` | Only if deploying / not using local file fallback | Leave blank locally if you're relying on `creds/` + `fallback_path` instead |
| `PERSONAL_TOKEN_B64` / `WORK_TOKEN_B64` | Same as above | Generated **after** you run `first_run.py` (see below) — you won't have these yet on a fresh clone |
| `TELEGRAM_TOKEN` / `TELEGRAM_WEBHOOK_SECRET_TOKEN` | Only if using the Telegram interface | See [Telegram bot interface](#-optional-telegram-bot-interface) |
| `MISTRAL_API_KEY` | **Yes** | The agent's underlying LLM calls go through Mistral |
| `USE_LOCAL_DB` | No — defaults to `true` | Set to `"false"` to use Neon Postgres instead of local SQLite |
| `NEON_DB` | Only if `USE_LOCAL_DB` is `"false"` | Full Postgres connection string from your Neon project |
| `PERSONAL_EMAIL` | **Yes** | Your actual personal Gmail address — read automatically by `login_hint` in the code via `os.getenv(...)`, no code edits needed |
| `WORK_EMAIL` | **Yes** | Your actual work Gmail address — read automatically by `login_hint` in the code via `os.getenv(...)`, no code edits needed |
| `WORK_ALIAS` | No — optional | Handy if you have a separate email alias that forwards mail into your work inbox; leave blank if not applicable |

> Since `GMAIL_CREDS_B64` / `PERSONAL_TOKEN_B64` / `WORK_TOKEN_B64` don't exist yet on a fresh clone, the very first thing you should do after setting up `creds/` is run `first_run.py` (next section) to generate the actual token files — then base64-encode them into `.env` only once you're ready to deploy.

---

## 💻 Running locally

1. Clone the repo and install dependencies:
   ```bash
   git clone https://github.com/omarnahdi/zaelix-ai.git && cd zaelix-ai && uv sync
   ```
2. Place your OAuth client JSON in `creds/`.
3. Copy `.env.example` to `.env` and fill in at least `MISTRAL_API_KEY` (see above).
4. Update `PERSONAL_EMAIL` and `WORK_EMAIL` in your `.env` file to your own personal and work Gmail addresses — no code changes needed.
5. **Run `first_run.py` to generate your OAuth credentials and tokens:**

   ```bash
   uv run first_run.py
   ```

   This step is **required** and only needs to be done once. Here's what happens:

   - The script first prints a **Personal Inbox Setup** banner with a 10-second countdown, giving you time to read the warning before anything happens.
   - A **browser window will pop up** — you must sign in with your **personal** Gmail account and grant the requested permissions. Do **not** use your work account here.
   - Once authenticated, the script calls the agent to fetch an email from the personal inbox, confirming the connection works and writing `personal_token/personal.json`.
   - It then repeats the same process for the **Work Inbox Setup** — another 10-second countdown, another browser popup, this time you must sign in with your **work** Gmail account. This writes `work_token/work.json`.

   ⚠️ **Signing into the wrong account at either step will misconfigure that inbox** — pay attention to which banner is currently showing (Personal vs. Work) before completing the browser login.

6. Once both `personal_token/personal.json` and `work_token/work.json` exist, you're fully set up locally. Run the agent normally:
   ```bash
   uv run email_agent.py
   ```
7. On subsequent runs, both inboxes authenticate silently using the saved tokens — you won't see the browser popups again unless a token is revoked or deleted.

Locally, Zaelix reads credentials directly from the file paths (`creds/...`, `personal_token/personal.json`, `work_token/work.json`) via the `fallback_path` argument in `write_temp_json` — the `*_B64` environment variables in `.env` are not required for local use, only for deployment.

> 💡 **Tip:** Once Zaelix is up and running, take a look at `instructions.py` — this is where the agent's behavior and prompt instructions are defined. Feel free to modify it to match how you actually want the agent to triage, summarize, or respond to your emails (tone, priorities, what counts as urgent, how it should handle newsletters/spam, etc.) for a more tailored experience.

---

## ☁️ Deploying to Google Cloud Run

Cloud Run containers don't have a persistent local filesystem or a browser for interactive OAuth, so Zaelix is designed to accept credentials as **base64-encoded environment variables** instead of file paths. You must generate real token files locally first via `first_run.py` (see [Running locally](#-running-locally)) — Cloud Run cannot perform an interactive browser login.

### 1. Confirm you've already run `first_run.py`

Make sure `personal_token/personal.json` and `work_token/work.json` exist and are valid before continuing. If not, go back and complete the [Running locally](#-running-locally) steps first.

### 2. Base64-encode your three JSON files

```bash
base64 -i creds/client_secret_XXXX.apps.googleusercontent.com.json | tr -d '\n' > creds_b64.txt
base64 -i personal_token/personal.json | tr -d '\n' > personal_b64.txt
base64 -i work_token/work.json | tr -d '\n' > work_b64.txt
```

*(On Windows, use `certutil -encode`, matching the comments in `.env.example`: `certutil -encode creds/your_creds.json creds_b64.txt` — note `certutil` wraps output with header/footer lines and line breaks, so strip those before pasting into `env.yaml`.)*

This produces `creds_b64.txt`, `personal_b64.txt`, and `work_b64.txt` — matching the files already present in the project structure.

### 3. Fill in `env.yaml` for deployment

Copy the template:

```bash
cp env.yaml.example env.yaml
```

`env.yaml.example` mirrors `.env.example` — same keys, same YAML `key: value` format:

```yaml
# Google Gmail credentials (base64 encoded)
# Run: certutil -encode creds/your_creds.json creds_b64.txt (Windows)
# Run: base64 -i creds/your_creds.json (Mac/Linux)
GMAIL_CREDS_B64: "paste_base64_output_here"

# Personal Gmail OAuth token (base64 encoded)
# Generated after first local OAuth login
PERSONAL_TOKEN_B64: "paste_base64_output_here"

# Work Gmail OAuth token (base64 encoded)
WORK_TOKEN_B64: "paste_base64_output_here"

# Telegram bot token
# Get from @BotFather on Telegram → /newbot
TELEGRAM_TOKEN: "your_telegram_bot_token"

# Telegram webhook secret for request validation
# Any random string you choose, must match what you pass to setWebhook
TELEGRAM_WEBHOOK_SECRET_TOKEN: "your_random_secret"

# Mistral API key
# Get from https://console.mistral.ai
MISTRAL_API_KEY: "your_mistral_api_key"

# Set to false to use Neon PostgreSQL instead of local SQLite
USE_LOCAL_DB: "true"

# Neon PostgreSQL connection string (only needed if USE_LOCAL_DB=false)
# Get from https://neon.tech → your project → connection string
NEON_DB: "postgresql://user:password@host/dbname"

# Replace with your personal and work email addresses. (Work alias is optional and is handy if you have a separate address that forwards mails to work email)
PERSONAL_EMAIL: "your.personal@gmail.com"
WORK_EMAIL: "your.work@gmail.com"
WORK_ALIAS: ""
```

Paste the contents of `creds_b64.txt`, `personal_b64.txt`, and `work_b64.txt` into `GMAIL_CREDS_B64`, `PERSONAL_TOKEN_B64`, and `WORK_TOKEN_B64` respectively, then fill in the rest (`MISTRAL_API_KEY`, `PERSONAL_EMAIL`, and `WORK_EMAIL` are required; `TELEGRAM_*` only if you're using the Telegram interface; `NEON_DB` only if `USE_LOCAL_DB` is `"false"`; `WORK_ALIAS` only if applicable). See the [.env setup](#️-setting-up-your-env-file) section for what each variable means — they're identical here.

`env.yaml` is what `gcloud run deploy` uses to set environment variables on the deployed service — keep it out of version control just like `.env`.

### 4. Deploy

```bash
gcloud run deploy zaelix-ai \
  --source . \
  --region YOUR_REGION \
  --allow-unauthenticated \
  --env-vars-file env.yaml
```

At runtime, `write_temp_json` detects the `GMAIL_CREDS_B64`, `PERSONAL_TOKEN_B64`, and `WORK_TOKEN_B64` env vars pulled from `env.yaml`, base64-decodes them, and writes them to temporary files — so the rest of the code behaves identically whether it's running locally from disk or in a stateless Cloud Run container. No browser interaction is needed on Cloud Run, since valid refresh tokens are already baked into the deployed environment.

> For production secrets, consider using Google Cloud **Secret Manager** (`--set-secrets`) instead of a plain `env.yaml`, especially if this repo or its deploy artifacts are ever made public.

---

## 🤖 Optional: Telegram bot interface

If you'd like to chat with Zaelix (and both inboxes) from Telegram instead of only via API/CLI, follow Agno's Telegram interface guide: **[docs.agno.com/agent-os/interfaces/telegram/introduction](https://docs.agno.com/agent-os/interfaces/telegram/introduction)**.

### 1. Create a Telegram bot

1. Open Telegram and message **[@BotFather](https://t.me/BotFather)**.
2. Send `/newbot` and follow the prompts to name your bot.
3. BotFather will give you a **bot token** — save it.

### 2. Configure environment variables

| Variable | Purpose |
| --- | --- |
| `TELEGRAM_TOKEN` | Your bot token from BotFather |
| `TELEGRAM_WEBHOOK_SECRET_TOKEN` | Required in production; skipped when `APP_ENV=development` |

### 3. Wire it into the agent

```python
from agno.os.app import AgentOS
from agno.os.interfaces.telegram import Telegram

agent_os = AgentOS(
    agents=[zaelix_agent],
    interfaces=[Telegram(agent=zaelix_agent)],
)
app = agent_os.get_app()

if __name__ == "__main__":
    agent_os.serve(app="main:app", port=7777, reload=True)
```

### 4. Local testing (with ngrok)

```bash
# Terminal 1 — run the app
uv run email_agent.py

# Terminal 2 — expose it publicly
ngrok http 7777

# Register the webhook
curl "https://api.telegram.org/bot${TELEGRAM_TOKEN}/setWebhook?url=${NGROK_URL}/telegram/webhook"
```

Then open your bot in Telegram and send `/start` to begin chatting with Zaelix across both inboxes.

On Cloud Run, point the Telegram webhook at your deployed service URL instead of an ngrok tunnel, and make sure `TELEGRAM_WEBHOOK_SECRET_TOKEN` is set since `APP_ENV` will be `production`.

---

## 🛠️ Tech stack

- **[Agno](https://docs.agno.com/)** — agent framework and Gmail toolkit
- **Google Gmail API** — email read/search/send/label operations
- **Google Cloud Run** — serverless deployment target
- **Telegram Bot API** (optional) — chat interface

---

## ⚠️ Security notes

- Never commit `creds/`, `personal_token/`, `work_token/`, or any base64-encoded secrets to version control.
- Use Google Cloud **Secret Manager** rather than plain environment variables for production deployments.
- Keep your OAuth consent screen in **Testing** mode with only your own accounts listed as test users, unless you specifically intend for other users to authenticate against this app.
- Review the OAuth scopes you request — only enable `gmail.modify` / `gmail.compose` if the agent actually needs to send or organize mail; `gmail.readonly` is sufficient for a read-only assistant.

---

## 📄 License

This project is licensed under the **[PolyForm Noncommercial License 1.0.0](./LICENSE.md)** — a real, standardized, lawyer-drafted license.

**In short:**
- ✅ Free for any noncommercial purpose — personal use, learning, hobby projects, experimentation.
- ✅ Free for use by charitable organizations, educational institutions, public research organizations, public safety/health organizations, environmental protection organizations, and government institutions, for their own noncommercial purposes.
- ❌ Not licensed for any commercial use, by anyone — individuals, freelancers, startups, or companies. This includes client deliverables, paid SaaS, reselling, white-labeling, internal business use, or any commercial product integration.
- 📩 See [`COMMERCIAL-LICENSE.md`](./COMMERCIAL-LICENSE.md) for concrete examples of what counts as commercial, and how to get a separate commercial license.

This is **not** an OSI-approved "open source" license in the traditional sense (it restricts commercial use), but it is source-available under a standardized, publicly documented license — read `LICENSE.md` and `COMMERCIAL-LICENSE.md` in full before using or distributing the project.

---

## 🙌 Acknowledgements

Built on [Agno](https://github.com/agno-agi/agno). Thanks to everyone following along — this project is being source-availabe as part of a 1,000 followers milestone on Linkedin. If Zaelix is useful to you, a ⭐ on the repo is always appreciated.