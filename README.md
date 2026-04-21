# AI Newsletter Pipeline

A fully-automated daily AI newsletter built on free-tier services.

```
GitHub Actions (scheduler) → Python (scraper + orchestrator)
  → Claude API (summarise / score / categorise)
  → Neo4j AuraDB (lineage graph)
  → Resend (email delivery)
```

---

## Folder Structure

```
ai-newsletter/
├── .github/workflows/newsletter.yml   # cron trigger — daily 07:00 UTC
├── scraper/
│   ├── sources.yaml                   # RSS feeds + sites
│   ├── fetch.py                       # feedparser + httpx + BS4
│   └── dedupe.py                      # SHA-256 fingerprint dedup
├── pipeline/
│   ├── summarise.py                   # Claude API batch calls
│   ├── categorise.py                  # group/filter by category
│   └── score.py                       # rank by relevance_score
├── graph/
│   ├── neo4j_client.py                # AuraDB driver singleton
│   ├── lineage.py                     # write nodes + relationships
│   └── queries.py                     # trending topics, co-occurrence
├── email/
│   ├── template.html.j2               # Jinja2 HTML email
│   └── build.py                       # render + send via Resend
├── main.py                            # orchestrator
├── requirements.txt
├── seen.json                          # persisted dedup fingerprints
└── .env.example
```

---

## Free-Tier Service Setup

### 1 — Anthropic API (Claude)

1. Sign up at <https://console.anthropic.com>
2. Go to **Settings → API Keys** → **Create key**
3. Copy the key → set as `ANTHROPIC_API_KEY`
4. Free tier includes $5 credit; `claude-sonnet-4-20250514` costs ~$3/M input tokens

### 2 — Neo4j AuraDB Free

1. Sign up at <https://console.neo4j.io>
2. Click **New Instance → AuraDB Free** (200 MB, always free, 1 instance)
3. Download the credentials file when prompted — it contains URI, username, password
4. Set `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` from those credentials
5. URI format: `neo4j+s://xxxxxxxx.databases.neo4j.io`

### 3 — Resend (Email Delivery)

1. Sign up at <https://resend.com>
2. Go to **API Keys → Create API Key** → copy it as `RESEND_API_KEY`
3. **For testing**: use `SENDER_EMAIL=onboarding@resend.dev` (no domain verification needed)
4. **For production**: go to **Domains → Add Domain**, verify DNS, then use `newsletter@yourdomain.com`
5. Free tier: 3 000 emails/month, 100/day

### 4 — GitHub Actions (Scheduler)

1. Fork / push this repo to GitHub
2. Go to **Settings → Secrets and variables → Actions → New repository secret**
3. Add all secrets from `.env.example`:
   - `ANTHROPIC_API_KEY`
   - `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`
   - `RESEND_API_KEY`
   - `RECIPIENT_EMAIL`
   - `SENDER_EMAIL`
4. The workflow at `.github/workflows/newsletter.yml` runs daily at **07:00 UTC**
5. Trigger manually anytime via **Actions → AI Newsletter → Run workflow**

---

## Local Development

```bash
# 1. Clone and install
git clone <your-repo>
cd ai-newsletter
pip install -r requirements.txt

# 2. Set up environment
cp .env.example .env
# Edit .env with your real credentials

# 3. Run the pipeline
python main.py
```

> **Neo4j is optional locally** — if `NEO4J_URI` / `NEO4J_USER` / `NEO4J_PASSWORD` are
> not set, the graph step is skipped and the newsletter still sends.

---

## How It Works

| Stage | File | What happens |
|-------|------|--------------|
| Fetch | `scraper/fetch.py` | feedparser parses RSS; httpx+BS4 scrapes HTML fallback |
| Dedupe | `scraper/dedupe.py` | SHA-256 fingerprint per `domain:title-slug` checked against `seen.json` |
| Enrich | `pipeline/summarise.py` | Batches of 10 articles sent to Claude; returns JSON with `one_liner`, `summary`, `category`, `relevance_score`, `entities`, `why_it_matters` |
| Score | `pipeline/score.py` | Articles ranked by score; those below 4/10 dropped |
| Graph | `graph/lineage.py` | Article, Entity, Topic, Source nodes + MENTIONS / TAGGED / FROM / CO_OCCURS_WITH edges |
| Email | `email/build.py` | Jinja2 renders inline-CSS HTML; Resend delivers it |

---

## Neo4j Graph Schema

```
(Article)-[:FROM]->(Source)
(Article)-[:TAGGED]->(Topic)
(Article)-[:MENTIONS]->(Entity)
(Entity)-[:CO_OCCURS_WITH {count}]-(Entity)
```

**Useful queries** (run in Neo4j Aura Browser):

```cypher
// Topics this week
MATCH (a:Article)-[:TAGGED]->(t:Topic)
WHERE a.ingested_at >= datetime() - duration('P7D')
RETURN t.name, count(a) ORDER BY count(a) DESC LIMIT 10

// Who co-occurs with OpenAI?
MATCH (e1:Entity {name:'OpenAI'})-[r:CO_OCCURS_WITH]-(e2)
RETURN e2.name, r.count ORDER BY r.count DESC LIMIT 10
```

## Customisation

### Add / remove sources
Edit `scraper/sources.yaml` — add a `name`, `url`, and `category`.

### Change scoring threshold
In `main.py`, adjust `filter_by_min_score(articles, min_score=4)`.

### Change email recipients
Set `RECIPIENT_EMAIL` to a comma-separated list; update `build.py`'s `"to"` field.

### Planned enhancements
- **Digest mode** — accumulate Mon–Fri, send a longer weekend edition
- **Slack/Telegram mirror** — post top 3 headlines to a channel
- **Web search grounding** — Claude web search to verify breaking news
- **Relevance tuning** — store click behaviour in Neo4j, re-rank future issues
