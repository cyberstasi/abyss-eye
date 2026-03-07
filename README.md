[README.md](https://github.com/user-attachments/files/25811733/README.md)
# AURA — Autonomous Universal Reconnaissance & Analysis

> An AI-powered EVE Online intelligence assistant built for wormhole corporations.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![Claude](https://img.shields.io/badge/Powered%20by-Claude%20Sonnet-orange)
![EVE Online](https://img.shields.io/badge/Game-EVE%20Online-silver)

---

## What is AURA?
[README (1).md](https://github.com/user-attachments/files/25811855/README.1.md)# AURA — Autonomous Universal Reconnaissance & Analysis

> An AI-powered EVE Online intelligence assistant built for wormhole corporations.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green)
![Claude](https://img.shields.io/badge/Powered%20by-Claude%20Sonnet-orange)
![EVE Online](https://img.shields.io/badge/Game-EVE%20Online-silver)

---

## What is AURA?

AURA is a locally-hosted AI assistant that gives your EVE Online corporation real-time intelligence, market analysis, and combat advisory capabilities through a natural language chat interface. Powered by Anthropic's Claude, AURA connects to live EVE data sources and delivers actionable intel — no spreadsheets, no manual zkillboard diving.

Built by a wormhole corporation, for wormhole corporations.

---

## Features

### 🔴 Hunter Mode
Pilot and corporation threat assessment powered by live ESI and zKillboard data.

- **Pilot threat cards** — Full intelligence report on any pilot including kill efficiency, top ships flown, timezone activity, solo vs fleet behavior, WH pilot detection, capital capability, and awox history
- **Corp intel** — Alliance affiliation, member count, ISK efficiency, dominant timezone, and capital capability detection
- **Top pilot breakdown** — Identify the most dangerous pilots in any corp by kill count and K/D ratio with ship specialization
- **Recruit screening** — Awox detection, activity recency, corp history, and behavioral red flags

### 🌀 Wormholer Mode
J-space intelligence for your chain and targets.

- **System intel** — WH class detection, activity rating, kill history, and occupancy assessment
- **Resident identification** — Identifies likely resident corps and alliances from multi-day kill patterns vs one-day visitor spikes
- **Capital activity detection** — Flags systems with capital-class kills
- **Dominant timezone** — Activity pattern analysis for optimal strike timing

### 💹 Trader Mode
Market intelligence and ISK optimization tools.

- **Loot appraisal** — Paste any loot list and get instant Jita buy/sell valuation via Janice
- **Market price lookup** — Live Jita buy/sell prices with spread analysis via Fuzzwork
- **Haul calculator** — Net profit after Pushx hauling fees and broker/sales taxes
- **Blue loot valuation** — Fixed NPC buy prices for all Sleeper and Talocan blue loot
- **Fit cost estimator** — Full EFT-format fit pricing with per-module breakdown and fit validation

### ⚔️ Combat Advisor
FC-grade tactical analysis for engagements.

- **Killmail analysis** — Pull any kill from zKillboard by ID and extract the full enemy fit, fight duration estimate, logi presence, and attacker breakdown
- **Fight duration estimation** — Classifies kills as blap/gank, fast kill, sustained brawl, or extended engagement based on damage, attacker count, and logi presence
- **Head-to-head comparison** — Paste your fit against an enemy killmail and get a full tactical breakdown
- **Win/loss conditions** — Specific engagement advice: tackle matchup, web analysis, neut threat, range profile, cloak escape
- **Fit validation** — Catches impossible fits (oversized prop mods, slot count violations) before you undock wrong
- **FC recommendation** — ENGAGE / DISENGAGE / KITE / SITUATIONAL with reasoning

---

## Tech Stack

| Component | Technology |
|---|---|
| AI Brain | Anthropic Claude Sonnet (claude-sonnet-4-20250514) |
| Backend | Python 3.10+ / FastAPI |
| Ship/Corp Data | EVE ESI API |
| Kill Data | zKillboard API |
| Market Data | Fuzzwork / Janice |
| Frontend | HTML / CSS / Vanilla JS |

---

## Data Sources

| Source | Used For |
|---|---|
| `esi.evetech.net` | Pilot profiles, corp info, ship attributes, killmails, dogma |
| `zkillboard.com/api` | Kill history, loss history, corp stats, kill hashes |
| `market.fuzzwork.co.uk` | Jita buy/sell prices |
| `janice.e-351.com` | Loot appraisal |

All data is fetched live. No local database required.

---

## Installation

### Prerequisites
- Python 3.10+
- An Anthropic API key ([get one here](https://console.anthropic.com))
- Git

### Setup

```bash
# Clone the repo
git clone https://github.com/cyberstasi/abyss-eye.git
cd abyss-eye

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create your .env file
echo ANTHROPIC_API_KEY=your_key_here > .env
```

### Run

```bash
python main.py
```

Then open your browser to `http://localhost:8000`

---

## Project Structure

```
abyss-eye/
├── agent.py              # Core AI brain, tool definitions, conversation loop
├── main.py               # FastAPI server
├── requirements.txt
├── .env                  # Your API key (never commit this)
├── static/
│   └── index.html        # Web UI
└── tools/
    ├── __init__.py
    ├── esi.py            # EVE ESI API — pilot, corp, ship lookups
    ├── zkill.py          # zKillboard — kill history, stats, analysis
    ├── dotlan.py         # K-space system intel
    ├── wormhole.py       # J-space intel, resident detection
    ├── trader.py         # Market tools — appraisal, prices, haul calc
    ├── combat.py         # Combat analysis — killmail parsing, fit comparison
    └── fitting.py        # Fit validation — slot counts, prop size, ESI dogma
```

---

## Usage Examples

### Hunter Mode
```
Look up pilot Progodlegend
Give me intel on Hard Knocks Citizens
Who are the most dangerous pilots in Pandemic Legion?
Run a background check on pilot Xenuria — I am considering recruiting them
```

### Wormholer Mode
```
Give me full intel on J102055
Who lives in J170141 and what timezone are they?
Is J105934 active and safe to run sites?
Research J115422 — is it worth evicting?
```

### Trader Mode
```
What is the current Jita price of a Tengu?
Appraise this loot: [paste loot list]
I have 850M ISK in loot at 1,200 m3 — what will I net after Pushx and taxes?
Value my blue loot: Sleeper Mainframe x 4, Sleeper Preserved Relic x 6
How much does this fit cost? [paste EFT fit]
```

### Combat Advisor
```
Analyze kill 133837880
Compare kill 133837880 against my fit: [paste EFT fit]
Validate this fit and tell me if anything is wrong: [paste EFT fit]
My corp found a Proteus camping our static. We have a Tengu, a Loki, and a Sabre. Should we engage?
```

---

## Architecture

AURA uses Claude's native tool use (function calling) to route natural language queries to the appropriate data fetchers. The conversation loop:

```
User message
    → Claude decides which tool(s) to call
    → Tools fetch live data from ESI / zKill / Fuzzwork / Janice
    → Data returned to Claude
    → Claude synthesizes into tactical intelligence response
    → Response delivered to user
```

Claude maintains conversation history within a session, so follow-up questions work naturally without re-providing context. No mode switching required — AURA reads intent from the message.

---

## Cost

AURA uses Claude Sonnet which is billed per token via the Anthropic API.

| Usage Level | Estimated Monthly Cost |
|---|---|
| Light (solo player) | ~$2–5/month |
| Active corp (5–10 users) | ~$15–30/month |
| Heavy use (20+ users) | ~$40–80/month |

Intel lookups with multiple ESI fetches are the most expensive calls. Simple market price checks are cheap.

---

## Roadmap

- [ ] Discord bot integration (same brain, slash commands)
- [ ] Arbitrage scanner (regional price comparison)
- [ ] PI chain optimizer
- [ ] Corp wallet and asset summary (ESI auth required)
- [ ] Wanderer chain integration for live wormhole mapping
- [ ] EVE-Scout Thera connection data
- [ ] **Pluggable LLM backend** — swap Claude for any OpenAI-compatible API, including locally hosted models via Ollama or LM Studio. Intended for corps that want to run their own LLM on local hardware and avoid API costs entirely.

---

## Security Notes

- Your Anthropic API key is stored in `.env` and never committed to git
- No ESI authentication is required — all data used is publicly available
- No player data is stored locally — all queries are live and stateless
- The `.gitignore` excludes `.env` by default

---

## Contributing

PRs are welcome. If you're adding a new tool:

1. Create the data fetcher in `tools/`
2. Add the tool definition to the `TOOLS` list in `agent.py`
3. Add the handler function in `agent.py`
4. Register it in `process_tool_call()`
5. Update `EVE_SYSTEM_PROMPT` with output format expectations for the new tool

---

## Credits

Built with:
- [Anthropic Claude](https://anthropic.com) — AI brain
- [EVE ESI](https://esi.evetech.net) — Official EVE Online API
- [zKillboard](https://zkillboard.com) — Kill data
- [Fuzzwork](https://market.fuzzwork.co.uk) — Market aggregates
- [Janice](https://janice.e-351.com) — Loot appraisal

---

*AURA is not affiliated with CCP Games or EVE Online. EVE Online is a registered trademark of CCP hf.*


AURA is a locally-hosted AI assistant that gives your EVE Online corporation real-time intelligence, market analysis, and combat advisory capabilities through a natural language chat interface. Powered by Anthropic's Claude, AURA connects to live EVE data sources and delivers actionable intel — no spreadsheets, no manual zkillboard diving.

Built by a wormhole corporation, for wormhole corporations.

---

## Features

### 🔴 Hunter Mode
Pilot and corporation threat assessment powered by live ESI and zKillboard data.

- **Pilot threat cards** — Full intelligence report on any pilot including kill efficiency, top ships flown, timezone activity, solo vs fleet behavior, WH pilot detection, capital capability, and awox history
- **Corp intel** — Alliance affiliation, member count, ISK efficiency, dominant timezone, and capital capability detection
- **Top pilot breakdown** — Identify the most dangerous pilots in any corp by kill count and K/D ratio with ship specialization
- **Doctrine analysis** — Reverse-engineer enemy fleet doctrines from killboard ship frequency data
- **Recruit screening** — Awox detection, activity recency, and behavioral analysis for new applicants

### 🌀 Wormholer Mode
J-space intelligence for your chain and targets.

- **System intel** — WH class detection, activity rating, kill history, and occupancy assessment
- **Resident identification** — Identifies likely resident corps and alliances from multi-day kill patterns vs one-day visitor spikes
- **Capital activity detection** — Flags systems with capital-class kills
- **Dominant timezone** — Activity pattern analysis for optimal strike timing

### 💹 Trader Mode
Market intelligence and ISK optimization tools.

- **Loot appraisal** — Paste any loot list and get instant Jita buy/sell valuation via Janice
- **Market price lookup** — Live Jita buy/sell prices with spread analysis via Fuzzwork
- **Haul calculator** — Net profit after Pushx hauling fees and broker/sales taxes
- **Blue loot valuation** — Fixed NPC buy prices for all Sleeper and Talocan blue loot
- **Fit cost estimator** — Full EFT-format fit pricing with per-module breakdown and fit validation

### ⚔️ Combat Advisor
FC-grade tactical analysis for engagements.

- **Killmail analysis** — Pull any kill from zKillboard by ID and extract the full enemy fit, fight duration estimate, logi presence, and attacker breakdown
- **Fight duration estimation** — Classifies kills as blap/gank, fast kill, sustained brawl, or extended engagement based on damage, attacker count, and logi presence
- **Head-to-head comparison** — Paste your fit against an enemy killmail and get a full tactical breakdown
- **Win/loss conditions** — Specific engagement advice: tackle matchup, web analysis, neut threat, range profile, cloak escape
- **Fit validation** — Catches impossible fits (oversized prop mods, slot count violations) before you undock wrong
- **FC recommendation** — ENGAGE / DISENGAGE / KITE / SITUATIONAL with reasoning

---

## Tech Stack

| Component | Technology |
|---|---|
| AI Brain | Anthropic Claude Sonnet (claude-sonnet-4-20250514) |
| Backend | Python 3.10+ / FastAPI |
| Ship/Corp Data | EVE ESI API |
| Kill Data | zKillboard API |
| Market Data | Fuzzwork / Janice |
| System Activity | ESI sovereignty/kills endpoints |
| Frontend | HTML / CSS / Vanilla JS |

---

## Data Sources

| Source | Used For |
|---|---|
| `esi.evetech.net` | Pilot profiles, corp info, ship attributes, killmails, market data |
| `zkillboard.com/api` | Kill history, loss history, corp stats, kill hashes |
| `market.fuzzwork.co.uk` | Jita buy/sell prices |
| `janice.e-351.com` | Loot appraisal |

All data is fetched live. No local database required.

---

## Installation

### Prerequisites
- Python 3.10+
- An Anthropic API key ([get one here](https://console.anthropic.com))
- Git

### Setup

```bash
# Clone the repo
git clone https://github.com/bryankars/eve-agent.git
cd eve-agent

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create your .env file
echo ANTHROPIC_API_KEY=your_key_here > .env
```

### Run

```bash
python main.py
```

Then open your browser to `http://localhost:8000`

---

## Project Structure

```
eve-agent/
├── agent.py              # Core AI brain, tool definitions, conversation loop
├── main.py               # FastAPI server
├── requirements.txt
├── .env                  # Your API key (never commit this)
├── static/
│   └── index.html        # Web UI
└── tools/
    ├── __init__.py
    ├── esi.py            # EVE ESI API — pilot, corp, ship lookups
    ├── zkill.py          # zKillboard — kill history, stats, analysis
    ├── dotlan.py         # K-space system intel
    ├── wormhole.py       # J-space intel, resident detection
    ├── trader.py         # Market tools — appraisal, prices, haul calc
    ├── combat.py         # Combat analysis — killmail parsing, fit comparison
    └── fitting.py        # Fit validation — slot counts, prop size, ESI dogma
```

---

## Usage Examples

### Hunter Mode
```
Look up pilot Progodlegend
Give me intel on corp Pandemic Legion
Who are the most dangerous pilots in Hard Knocks Citizens?
```

### Wormholer Mode
```
Give me full intel on J102055
What class is J170141 and who lives there?
Is J105934 active?
```

### Trader Mode
```
What's the current price of a Loki?
Appraise this loot: [paste loot list]
I have 500M ISK in loot to haul, is it worth it?
Value my blue loot: Sleeper Mainframe x 4, Sleeper Preserved Relic x 6
How much does this fit cost? [paste EFT fit]
```

### Combat Advisor
```
Analyze kill 133837880
Compare kill 133837880 against my fit: [paste EFT fit]
What was the fight duration on kill 121456789?
```

---

## Architecture

AURA uses Claude's native tool use (function calling) to route natural language queries to the appropriate data fetchers. The conversation loop works as follows:

```
User message
    → Claude decides which tool(s) to call
    → Tools fetch live data from ESI/zKill/Fuzzwork/Janice
    → Data returned to Claude
    → Claude synthesizes into tactical intelligence response
    → Response delivered to user
```

Claude maintains conversation history within a session, so you can ask follow-up questions naturally without re-providing context.

---

## Cost

AURA uses Claude Sonnet which is billed per token.

| Usage Level | Estimated Monthly Cost |
|---|---|
| Light (solo player) | ~$2-5/month |
| Active corp (5-10 users) | ~$15-30/month |
| Heavy use (20+ users) | ~$40-80/month |

Intel lookups are the most expensive calls due to multiple ESI fetches. Market price lookups are cheap.

---

## Planned Features

- [ ] Discord bot integration (same brain, slash commands)
- [ ] Arbitrage scanner (regional price comparison)
- [ ] PI chain optimizer
- [ ] Corp wallet summary (ESI auth required)
- [ ] Wanderer chain integration for live wormhole mapping
- [ ] EVE-Scout Thera connection data
- [ ] PYFA integration for fit simulation

---

## Security Notes

- Your Anthropic API key is stored in `.env` and never committed to git
- No ESI authentication is required — all data used is public
- No player data is stored locally — all queries are live
- The `.gitignore` excludes `.env` by default

---

## Contributing

This project is built for internal corp use but PRs are welcome. If you're adding a new tool:

1. Create the data fetcher in `tools/`
2. Add the tool definition to `TOOLS` list in `agent.py`
3. Add the handler function in `agent.py`
4. Register it in `process_tool_call()`
5. Update the system prompt in `EVE_SYSTEM_PROMPT` with output format expectations

---

## Credits

Built with:
- [Anthropic Claude](https://anthropic.com) — AI brain
- [EVE ESI](https://esi.evetech.net) — Official EVE Online API
- [zKillboard](https://zkillboard.com) — Kill data
- [Fuzzwork](https://market.fuzzwork.co.uk) — Market aggregates
- [Janice](https://janice.e-351.com) — Loot appraisal

---

*AURA is not affiliated with CCP Games or EVE Online. EVE Online is a registered trademark of CCP hf.*
