# RemitAI — Stablecoin Remittance Co-pilot

AI-powered multilingual remittance agent helping migrant workers send money home using USDC stablecoins.

## The problem
200M+ migrant workers pay 6.5% average fees on remittances.
$40B extracted annually from the world's most vulnerable workers.

## The solution
Voice + chat AI agent. Multilingual. Stablecoin rails.
Fee: under 0.5%. Delivery: under 60 seconds.

## Tech stack
- Azure AI Foundry — agent orchestration
- Azure OpenAI GPT-4o — agent brain
- Azure AI Speech — voice input/output
- Azure Translator — multilingual support
- Azure Functions — payment logic (Python)
- Azure Communication Services — SMS notifications
- Azure Cosmos DB — transaction history
- Circle USDC API — stablecoin transfers (ETH-SEPOLIA)
- Flask — local web server

---

## Prerequisites

Make sure the following are installed before you begin:

| Tool | Version | Notes |
|------|---------|-------|
| Python | 3.10+ | `python --version` |
| Node.js | 18+ | Required for `circle-setup/` scripts |
| npm | 8+ | Comes with Node.js |
| Azure Functions Core Tools | v4 | [Install guide](https://learn.microsoft.com/en-us/azure/azure-functions/functions-run-local) |
| Azure CLI | Latest | Optional — needed for deploying to Azure |

---

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/remitai.git
cd remitai
```

### 2. Set up environment variables

Copy the example file and fill in your credentials:

```bash
cp .env.example .env
```

Then open `.env` and fill in the values:

```env
# Azure OpenAI
AZURE_OPENAI_ENDPOINT=https://<your-resource>.openai.azure.com/
AZURE_OPENAI_KEY=<your-key>
AZURE_OPENAI_DEPLOYMENT=gpt-4o

# Azure Communication Services
AZURE_COMMS_CONNECTION_STRING=<your-connection-string>

# Azure Cosmos DB
COSMOS_DB_CONNECTION_STRING=<your-connection-string>
COSMOS_DB_DATABASE=remitai
COSMOS_DB_CONTAINER=transactions

# Circle API (use 'sandbox' for local development)
CIRCLE_API_KEY=<your-circle-api-key>
CIRCLE_ENVIRONMENT=sandbox

# FX Rate API (https://www.exchangerate-api.com)
FX_API_KEY=<your-fx-api-key>
FX_API_URL=https://v6.exchangerate-api.com/v6

# Azure AI Foundry
FOUNDRY_PROJECT_ENDPOINT=https://<your-hub>.services.ai.azure.com/api/projects/<your-project>
FOUNDRY_AGENT_ID=<your-agent-id>

# Azure Speech & Translator
AZURE_SPEECH_KEY=<your-speech-key>
AZURE_SPEECH_REGION=eastus
AZURE_TRANSLATOR_KEY=<your-translator-key>
AZURE_TRANSLATOR_REGION=eastus
AZURE_TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com

# Azure Functions (when running backend separately)
FUNCTION_BASE_URL=http://localhost:7071/api
FUNCTION_KEY=<your-function-key>
```

> **Note:** Never commit `.env` or `functions/local.settings.json` to version control — they contain secrets.

---

### 3. Set up the Python virtual environment

From the project root:

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

---

### 4. Set up Azure Functions locally

The Azure Functions backend lives in `functions/`. It needs its own environment config.

```bash
cd functions
python -m venv venv
source venv/bin/activate        # macOS/Linux
# venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

Create `functions/local.settings.json` (this file is gitignored):

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "CIRCLE_API_KEY": "<your-circle-api-key>",
    "CIRCLE_API_URL": "https://api.circle.com/v1/w3s",
    "CIRCLE_WALLET_SET_ID": "<your-wallet-set-id>",
    "CIRCLE_WALLET_ID": "<your-wallet-id>",
    "CIRCLE_WALLET_ADDRESS": "<your-wallet-address>",
    "CIRCLE_BLOCKCHAIN": "ETH-SEPOLIA",
    "CIRCLE_ENTITY_SECRET": "<your-entity-secret>",
    "CIRCLE_ENTITY_SECRET_CIPHERTEXT": "<your-entity-secret-ciphertext>",
    "SIMULATE_TRANSFERS": "false",
    "FX_API_URL": "https://v6.exchangerate-api.com/v6",
    "FX_API_KEY": "<your-fx-api-key>",
    "COSMOS_DB_CONNECTION_STRING": "<your-cosmos-connection-string>",
    "COSMOS_DB_DATABASE": "remitai",
    "COSMOS_DB_CONTAINER": "transactions",
    "AZURE_COMMS_CONNECTION_STRING": "<your-comms-connection-string>",
    "AZURE_EMAIL_CONNECTION_STRING": "<your-email-connection-string>",
    "AZURE_EMAIL_SENDER": "<your-sender-address>",
    "FOUNDRY_AGENT_ID": "<your-agent-id>",
    "AZURE_SPEECH_KEY": "<your-speech-key>",
    "AZURE_SPEECH_REGION": "eastus",
    "AZURE_TRANSLATOR_KEY": "<your-translator-key>",
    "AZURE_TRANSLATOR_REGION": "eastus",
    "AZURE_TRANSLATOR_ENDPOINT": "https://api.cognitive.microsofttranslator.com"
  }
}
```

---

## Running the project

### Option A: Web UI (chat interface)

Start the Azure Functions backend in one terminal:

```bash
cd functions
source venv/bin/activate
func start
```

In a second terminal, start the Flask web server:

```bash
# from project root
source venv/bin/activate
python web_server.py
```

Open your browser at `http://localhost:5000`.

---

### Option B: Voice agent (CLI)

Make sure your `.env` is configured, then from the project root:

```bash
source venv/bin/activate
python voice_agent.py
```

The voice agent supports 10+ languages including English, Spanish, Hindi, Tagalog, Arabic, French, Portuguese, and Mandarin. Speak your remittance request and the agent will guide you through the transfer.

---

### Option C: Run the agent directly (no voice)

```bash
source venv/bin/activate
python run_agent.py
```

---

## Scripts reference

### `web_server.py` — Flask web server

Serves the chat UI and acts as the bridge between the browser and Azure AI Foundry.

**What it does:**
- Serves the static frontend from `web/index.html` at `http://localhost:5000`
- Exposes three API endpoints:
  - `GET  /api/health` — returns agent ID and status
  - `POST /api/thread` — creates a new conversation thread in Azure AI Foundry
  - `POST /api/chat`   — sends a user message to the agent and returns the response
- When the agent needs to call a tool (e.g. look up FX rates or execute a transfer), it proxies the call to the Azure Functions backend using `FUNCTION_BASE_URL` and `FUNCTION_KEY`

**Environment variables required:** `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_AGENT_ID`, `FUNCTION_BASE_URL`, `FUNCTION_KEY`

**Run:**
```bash
source venv/bin/activate
python web_server.py
# Open http://localhost:5000
```

---

### `voice_agent.py` — CLI voice/text agent

Interactive command-line interface to the RemitAI agent. Supports both a **voice mode** (microphone + speakers) and a **text mode** (keyboard input).

**What it does:**
- Prompts you to choose voice mode or text mode on startup
- **Voice mode:** uses Azure AI Speech to listen via the default microphone, auto-detects the spoken language, sends the transcript to the agent, and reads the response back via text-to-speech
- **Text mode:** takes typed input and prints agent responses to the terminal — useful when no microphone is available
- Maintains a conversation thread across turns so the agent remembers context
- Supports 10 languages with matching neural TTS voices:

| Language | Locale | Voice |
|----------|--------|-------|
| English (US) | en-US | Jenny Neural |
| English (UK) | en-GB | Sonia Neural |
| Spanish (Mexico) | es-MX | Dalia Neural |
| Spanish (Spain) | es-ES | Elvira Neural |
| Hindi | hi-IN | Swara Neural |
| Filipino/Tagalog | tl-PH | Blessica Neural |
| Arabic | ar-SA | Zariyah Neural |
| French | fr-FR | Denise Neural |
| Portuguese (BR) | pt-BR | Francisca Neural |
| Mandarin | zh-CN | Xiaoxiao Neural |

**Environment variables required:** `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_AGENT_ID`, `FUNCTION_BASE_URL`, `FUNCTION_KEY`, `AZURE_SPEECH_KEY`, `AZURE_SPEECH_REGION`

**Run:**
```bash
source venv/bin/activate
python voice_agent.py
# Select 1 for voice mode or 2 for text mode
# Say or type 'quit' to exit
```

> On macOS, grant microphone access to Terminal/iTerm under System Settings → Privacy & Security → Microphone before using voice mode.

---

### `run_agent.py` — Minimal text agent (CLI)

A lightweight text-only chat loop that connects directly to Azure AI Foundry. No voice, no Flask server — just a simple REPL for testing the agent.

**What it does:**
- Creates a new conversation thread on first message
- Sends each typed message to the agent and prints the response
- Handles tool calls (FX rate lookups, transfers) by forwarding them to the Azure Functions backend
- Keeps the same thread alive for the session so the agent remembers prior context
- Type `quit` to exit

**Note:** The endpoint and function URL are currently hardcoded at the top of `run_agent.py`. Update them if you are running against your own Azure resources, or set them via environment variables.

**Environment variables / constants used:** `PROJECT_ENDPOINT`, `AGENT_ID`, `FUNCTION_BASE_URL`, `FUNCTION_KEY` (hardcoded in file — update as needed)

**Run:**
```bash
source venv/bin/activate
python run_agent.py
# You: I want to send $200 to Mexico
# RemitAI: ...
```

---

### `setup_agent.py` — Agent provisioning script

One-time script that creates or updates the RemitAI agent definition in Azure AI Foundry. Run this when setting up a new environment or when you need to update the agent's instructions or tool definitions.

**What it does:**
- Connects to Azure AI Foundry using `DefaultAzureCredential`
- Checks if an agent named `RemitAI` already exists
  - If it exists: updates its model, instructions, and tools
  - If not: creates a new agent
- Registers three tools the agent can call: `get_fx_rate`, `execute_transfer`, `send_email_confirmation`
- Prints the agent ID at the end — copy this value into `FOUNDRY_AGENT_ID` in your `.env` and `functions/local.settings.json`

**Run this once when:**
- Setting up the project for the first time in a new Azure environment
- Changing the agent's system prompt or tool definitions

```bash
source venv/bin/activate
python setup_agent.py
# Output will include:
# FOUNDRY_AGENT_ID=asst_xxxxxxxxxxxx
# Copy this value into your .env file
```

---

## Circle wallet setup (first-time only)

If you need to configure a new Circle developer wallet, use the scripts in `circle-setup/`:

```bash
cd circle-setup
npm install
```

1. Set your Circle API key and entity secret in a local config or environment variable.
2. Run `node setup.js` to create a wallet set and wallet.
3. Copy the wallet set ID, wallet ID, and wallet address into `functions/local.settings.json`.
4. Run `node get_ciphertext.js` to generate `CIRCLE_ENTITY_SECRET_CIPHERTEXT` and add it to `functions/local.settings.json`.

See Circle's [developer docs](https://developers.circle.com/w3s/developer-controlled-wallets) for details on sandbox setup.

---

## Project structure

```
remitai/
├── web/                    # Frontend — HTML/CSS/JS single-page app
│   ├── index.html
│   ├── app.js
│   └── styles.css
├── functions/              # Azure Functions backend (Python)
│   ├── function_app.py     # FX rates, USDC transfers, SMS
│   ├── host.json
│   ├── local.settings.json # Local secrets (gitignored)
│   └── requirements.txt
├── circle-setup/           # Circle wallet setup scripts (Node.js)
├── docs/                   # Azure provisioning documentation
├── tests/                  # Test stubs
├── web_server.py           # Flask server (serves web UI + proxies to agent)
├── voice_agent.py          # CLI voice interface
├── run_agent.py            # CLI text agent runner
├── setup_agent.py          # Agent configuration utility
├── requirements.txt        # Root Python dependencies
└── .env                    # Local secrets (gitignored)
```

---

## Azure resources

Full provisioning details are in `docs/azure-resources.md`.

| Service | Purpose |
|---------|---------|
| Azure AI Foundry | Agent orchestration (GPT-4o) |
| Azure OpenAI | GPT-4o model deployment |
| Azure AI Speech | STT/TTS for voice agent |
| Azure Translator | Multilingual support |
| Azure Functions | Payment logic backend |
| Azure Communication Services | SMS and email notifications |
| Azure Cosmos DB | Transaction history |
| Azure Static Web Apps | Frontend hosting |

---

## Troubleshooting

**`func start` fails with import errors**
Make sure you activated the venv inside `functions/` and ran `pip install -r functions/requirements.txt`.

**Voice agent has no audio output**
Ensure `AZURE_SPEECH_KEY` and `AZURE_SPEECH_REGION` are set in `.env`. On macOS you may need to grant microphone permissions to Terminal.

**Circle transfer returns an error**
Confirm `SIMULATE_TRANSFERS` is set to `"false"` in `local.settings.json` and that your Circle sandbox wallet has test USDC funded. Use Circle's faucet in the developer console.

**Flask server can't reach Azure Functions**
Make sure `func start` is running and `FUNCTION_BASE_URL` in `.env` points to `http://localhost:7071/api`.
