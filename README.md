# AI Newsletter Pipeline

A fully-automated newsletter built entirely on free-tier services — no credit card required.

```
GitHub Actions (scheduler) → Python (scraper + orchestrator)
  → Groq API / Llama 3.3 70B (summarise / score / categorise)
  → Neo4j AuraDB (lineage graph)
  → Resend (email delivery)
```

---

## Folder Structure

```
ai-newsletter/
├── .github/workflows/newsletter.yml   # cron — every 2 days at 08:00 IST
├── scraper/
│   ├── sources.yaml                   # RSS feeds + HTML sources
│   ├── fetch.py                       # feedparser + httpx + BS4
│   └── dedupe.py                      # SHA-256 fingerprint dedup via seen.json
├── pipeline/
│   ├── summarise.py                   # Groq API batch calls (5 articles/call)
│   ├── categorise.py                  # group/filter by category
│   └── score.py                       # rank by relevance_score
├── graph/
│   ├── neo4j_client.py                # AuraDB driver singleton
│   ├── lineage.py                     # write nodes + relationships
│   └── queries.py                     # trending topics, co-occurrence
├── mailer/
│   ├── template.html.j2               # Jinja2 HTML email (inline CSS, dark mode)
│   └── build.py                       # render + send via Resend
├── main.py                            # orchestrator
├── requirements.txt
├── seen.json                          # persisted dedup fingerprints (auto-updated)
└── .env.example
```

---

## Free-Tier Services (all $0, no credit card)

| Service | Purpose | Limit |
|---------|---------|-------|
| **Groq** | AI summarisation (Llama 3.3 70B) | 14,400 req/day |
| **Neo4j AuraDB** | Article lineage graph | 200 MB forever |
| **Resend** | Email delivery | 3,000 emails/month |
| **GitHub Actions** | Scheduler + CI runner | 2,000 min/month |

---

## Setup

### 1 — Groq API (AI summarisation)

1. Sign up at <https://console.groq.com>
2. Go to **API Keys → Create API key**
3. Copy the key (starts with `gsk_`) → set as `GROQ_API_KEY`

### 2 — Neo4j AuraDB (lineage graph — optional)

1. Sign up at <https://console.neo4j.io>
2. Click **New Instance → AuraDB Free** (200 MB, always free)
3. Copy the **password shown on the creation screen** immediately (shown only once)
4. Set `NEO4J_URI`, `NEO4J_USER=neo4j`, `NEO4J_PASSWORD`
5. Comment out all three lines in `.env` to skip the graph step entirely

### 3 — Resend (email delivery)

1. Sign up at <https://resend.com>
2. Go to **API Keys → Create API key** → set as `RESEND_API_KEY`
3. For testing: use `SENDER_EMAIL=onboarding@resend.dev` (can only send to your own signup email)
4. For production: verify a domain at **resend.com/domains** and use `newsletter@yourdomain.com`

### 4 — GitHub Actions (automated schedule)

1. Push this repo to GitHub
2. Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Value |
|--------|-------|
| `GROQ_API_KEY` | from console.groq.com |
| `RESEND_API_KEY` | from resend.com |
| `RECIPIENT_EMAIL` | your email address |
| `SENDER_EMAIL` | `onboarding@resend.dev` |
| `NEO4J_URI` | `neo4j+s://xxxxxxxx.databases.neo4j.io` |
| `NEO4J_USER` | `neo4j` |
| `NEO4J_PASSWORD` | from AuraDB creation screen |

3. Go to **Actions → AI Newsletter → Run workflow** to trigger manually

---

## Local Development

```bash
git clone https://github.com/YOUR-USERNAME/AI-Newsletter.git
cd AI-Newsletter
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
python main.py
```

---

## How It Works

| Stage | File | What happens |
|-------|------|--------------|
| Fetch | `scraper/fetch.py` | feedparser parses RSS; httpx+BS4 scrapes HTML fallback |
| Dedupe | `scraper/dedupe.py` | SHA-256 fingerprint per `domain:title-slug` vs `seen.json` |
| Enrich | `pipeline/summarise.py` | Batches of 5 to Groq API, returns JSON with `one_liner`, `summary`, `category`, `relevance_score`, `entities`, `why_it_matters` |
| Score | `pipeline/score.py` | Articles ranked by score; below 4/10 dropped |
| Graph | `graph/lineage.py` | Article, Entity, Topic, Source nodes + edges |
| Email | `mailer/build.py` | Jinja2 renders inline-CSS HTML; Resend delivers it |

---

## Neo4j Graph Schema

```
(Article)-[:FROM]->(Source)
(Article)-[:TAGGED]->(Topic)
(Article)-[:MENTIONS]->(Entity)
(Entity)-[:CO_OCCURS_WITH {count}]-(Entity)
```

**Useful queries** in the Neo4j Aura Browser:

```cypher
// Topics this week
MATCH (a:Article)-[:TAGGED]->(t:Topic)
WHERE a.ingested_at >= datetime() - duration('P7D')
RETURN t.name, count(a) ORDER BY count(a) DESC LIMIT 10

// Most mentioned companies
MATCH (a:Article)-[:MENTIONS]->(e:Entity)
RETURN e.name, count(a) AS mentions ORDER BY mentions DESC LIMIT 10
```

---

## Customisation

- **Add sources** — edit `scraper/sources.yaml`
- **Change schedule** — edit the cron in `.github/workflows/newsletter.yml`
- **Change score threshold** — edit `filter_by_min_score(articles, min_score=4)` in `main.py`
- **Add recipients** — update `RECIPIENT_EMAIL` and the `"to"` list in `mailer/build.py`
