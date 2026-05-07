# Claude Certified Architect — Foundations: TypeScript SDK Objective Map

> **Scope**: The TypeScript SDK (`claude-agent-sdk-typescript-main/`) ships **only the
> `examples/session-stores/` reference adapters** — S3, Redis, and Postgres
> implementations of the `SessionStore` interface plus a 13-check behavioral
> conformance suite. This map covers what those examples *do* demonstrate.
> For full-domain coverage, see [`EXAM_MAP.md`](./EXAM_MAP.md) (Python SDK) and
> [`EXAM_MAP_PYTHON_VS_TYPESCRIPT.md`](./EXAM_MAP_PYTHON_VS_TYPESCRIPT.md).

> **Setup**: `cd claude-agent-sdk-typescript-main/examples/session-stores/<backend>`
> then `bun install && bun run demo.ts` (see `README.md` per adapter).

---

## Directory Layout

```
claude-agent-sdk-typescript-main/
├── CHANGELOG.md                         # SessionStore shipped 0.2.113; retry/backoff added 0.2.119
├── README.md
└── examples/
    └── session-stores/
        ├── README.md                    # Full adapter guide + production checklist
        ├── shared/
        │   └── conformance.ts           # 13-contract behavioral suite (SessionStore protocol)
        ├── s3/
        │   ├── src/S3SessionStore.ts    # JSONL part files, client-clock ordering
        │   ├── demo.ts
        │   └── test/
        ├── redis/
        │   ├── src/RedisSessionStore.ts # RPUSH/LRANGE + subkey set + session zset
        │   ├── demo.ts
        │   └── test/
        └── postgres/
            ├── src/PostgresSessionStore.ts  # One row per entry, BIGSERIAL ordering
            ├── demo.ts
            └── test/
```

---

## Domain Coverage Map (TypeScript examples only)

| Objective | Primary? | Example | Key Concept |
|-----------|----------|---------|-------------|
| **D5.8 State persistence** | ✅ Primary | all 3 adapters | Session transcripts mirrored to S3 / Redis / Postgres; SDK never auto-deletes |
| **D1.7 Session management / resume** | ✅ Primary | each `demo.ts` | `query({ options: { sessionStore, resume: sid } })` round-trip |
| **D5.6 Error categories** | ✅ Covered | adapter READMEs + CHANGELOG 0.2.119 | `append()` failure → `mirror_error` (SDK-level), never blocks conversation |
| **D1.1 Agentic loop / stop_reason** | Indirect | `demo.ts` | `for await (m of query(...))` loop; observe `m.type === 'result'` |
| **D1.3 Context passing to subagents** | Indirect | conformance test `subpath keys stored independently` | Main transcript vs `subagents/*` subpaths isolated |
| **D3.4 Deterministic contract enforcement** | Indirect | `shared/conformance.ts` | 13 behavioral tests = deterministic protocol guarantees (hook-equivalent for storage) |
| **D4.3 Structured outputs** | Indirect | `SessionStoreEntry` type | Typed `{ type: string; [k: string]: unknown }` entries; JSONB-safe deep-equal |
| **D4.4 Validation / retry** | Indirect | CHANGELOG 0.2.119 | `append()` retried up to 3× with backoff before `mirror_error` |

**Domains NOT covered by TS examples**: D1.2 (multi-agent coordinator), D1.4–5 (hooks), D1.6 (task decomposition), D2 in full (tool descriptions, `tool_choice`, MCP server, built-in tool selection), D3 entirely (CLAUDE.md, skills, CI/CD, planning mode), D4 (few-shot, self-correction, prompt chaining, interview pattern), D5.2–5.7 (facts block, trim results, position-aware, escalation, provenance).

---

## Domain 5.8 — State persistence (the core contribution)

| Adapter | File | What to observe |
|---------|------|-----------------|
| S3 | `s3/src/S3SessionStore.ts` | `{prefix}{projectKey}/{sessionId}/part-{epochMs13}-{rand6}.jsonl` layout; `append()` = one new part file, `load()` = list+sort+concat. Ordering depends on **client wall clock** — skew >1s across writers reorders entries. |
| Redis | `redis/src/RedisSessionStore.ts` | Four-key scheme: main list, subpath list, `__subkeys` set, `__sessions` zset. Each `append()` is an `RPUSH` + index update in a single `MULTI`. Must set `maxmemory-policy noeviction` or eviction silently drops sessions. |
| Postgres | `postgres/src/PostgresSessionStore.ts` | One row per entry; `BIGSERIAL id` orders within `(project_key, session_id, subpath)`. `subpath IS NOT DISTINCT FROM $3` handles `NULL` = main transcript. `jsonb` reorders object keys — contract is deep-equal, never byte-equal. |

### Conformance suite (`shared/conformance.ts`) — 13 contracts

1. append then load returns same entries in same order
2. load unknown key returns null
3. multiple append calls preserve call order
4. `append([])` is a no-op
5. subpath keys stored independently of main
6. projectKey isolation
7. `listSessions` returns sessionIds for project
8. `listSessions` excludes subagent subpaths
9. delete main then load returns null
10. delete main cascades to subkeys
11. delete with subpath removes only that subkey
12. `listSubkeys` returns subpaths for the session
13. `listSubkeys` excludes main transcript

**Exam relevance**: These are *deterministic protocol guarantees* — the TS analogue of
"hooks enforce workflow, prompts don't" (D1.4). A store that passes conformance
**guarantees** durable resume; a store written by spec alone does not.

---

## Domain 1.7 — Session management (resume flow)

Every `demo.ts` follows this shape:

```typescript
async function run(prompt: string, resume?: string) {
  let sessionId: string | undefined
  for await (const m of query({
    prompt,
    options: { sessionStore: store, resume, maxTurns: 1 },
  })) {
    if (m.type === 'system' && m.subtype === 'init') sessionId = m.session_id
    if (m.type === 'result') console.log(`[${m.subtype}]`, 'result' in m ? m.result : '')
  }
  return sessionId
}

const sid = await run('Reply with exactly the word: pineapple')
await run('What single word did you just reply with?', sid)   // resumes from store
```

Key exam points:
- `system:init` event exposes the `session_id` — capture it for later resume.
- `resume` takes a session ID, **not** a transcript blob — the store materializes state.
- The SDK, not the store, decides what to write; the store is a dumb mirror.

---

## Domain 5.6 — Error categories (what can go wrong)

| Failure | Surfaced as | Blocks turn? |
|---------|-------------|--------------|
| `append()` rejection (S3 5xx, Redis OOM, Postgres pool exhausted) | `SDKMirrorErrorMessage` (`subtype: 'mirror_error'`) — after 3 retries w/ backoff (CHANGELOG 0.2.119) | **No** — conversation continues; mirror has a gap |
| `load()` returns `null` for unknown key | Treated as empty session; resume starts fresh | No |
| Malformed JSONL line | Skipped silently (S3 `try/catch`, Redis `try/catch`) | No |
| `delete()` partial failure (S3 `DeleteObjectsCommand`) | Throws `Error` with list of failed keys | Caller's job |
| Conformance violation (e.g., append-order broken) | Fails CI — never reaches prod | N/A |

**Exam trap**: Don't design failure modes that *block* the conversation on storage
errors. The SDK guarantees: turn-critical state lives in the CLI subprocess;
`sessionStore` is a durability mirror, not a write-through cache.

---

## Key Exam Decisions — TypeScript session persistence

```
Which adapter?
  → Durable, cheap, high-volume archival: S3 (part-file JSONL; lifecycle policies)
  → Sub-ms resume latency, existing Redis: Redis (RPUSH/LRANGE; watch eviction policy)
  → Strong consistency, transactional joins: Postgres (ACID; retention DELETE job)

Write a new adapter?
  → Copy the closest existing adapter + run conformance
  → Factory MUST return a fresh isolated store per call
  → Accept deep-equal (not byte-equal) — JSONB/JSON canonicalization is legal

Production readiness?
  → S3: NTP-sync writers; lifecycle policies; >1000 parts → compact
  → Redis: maxmemory-policy noeviction; hash-tag `{...}` for Cluster
  → Postgres: dedicated pool; retention job; don't byte-compare rows

Retry strategy?
  → 0.2.119+: SDK retries append() 3× with backoff before mirror_error
  → Adapter's own retries should be idempotent (PUT/RPUSH/INSERT are; DELETE partially is)
```

---

## CHANGELOG highlights relevant to exam

- **0.2.113** — `sessionStore` option, `SessionStore` / `SessionKey` / `SessionStoreEntry` types, `InMemorySessionStore`, `importSessionToStore()`, `deleteSession()`, `SDKMirrorErrorMessage`.
- **0.2.119** — `SessionStore.append()` failures retried up to 3× with short backoff before `mirror_error` is emitted.
- **0.2.76** — `forkSession(sessionId, opts?)` for branching from a point (pairs with `sessionStore`).
- **0.2.59** — `getSessionMessages()` to read transcript history.
- **0.2.53** — `listSessions()` for discovery.

---

## Running the examples

```bash
# Redis (mock-backed unit tests, no Redis needed)
cd claude-agent-sdk-typescript-main/examples/session-stores/redis
bun install
bun test test/RedisSessionStore.test.ts

# Redis live conformance
docker run -d -p 6379:6379 redis:7-alpine
SESSION_STORE_REDIS_URL=redis://localhost:6379/0 bun test test/conformance.live.test.ts

# Redis end-to-end demo (requires ANTHROPIC_API_KEY or Bedrock creds)
SESSION_STORE_REDIS_URL=redis://localhost:6379/0 bun run demo.ts

# S3 via MinIO
docker run -d -p 9000:9000 minio/minio server /data
docker run --rm --network host minio/mc \
  sh -c 'mc alias set local http://localhost:9000 minioadmin minioadmin && mc mb local/claude-sessions'
cd ../s3
SESSION_STORE_S3_ENDPOINT=http://localhost:9000 \
SESSION_STORE_S3_BUCKET=claude-sessions \
AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin \
  bun run demo.ts

# Postgres
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=postgres postgres:16-alpine
cd ../postgres
SESSION_STORE_POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/postgres \
  bun run demo.ts
```

---

## What to study outside this directory

The TypeScript SDK examples alone are **not** sufficient for the exam — they
cover D5.8 deeply, D1.7 / D5.6 indirectly, and everything else not at all. To
prepare:

1. **For D1, D2, D3, D4, most of D5** → use the Python examples in
   [`EXAM_MAP.md`](./EXAM_MAP.md). The exam concepts (hooks, MCP, CLAUDE.md,
   planning mode, few-shot, escalation, etc.) are SDK-language-agnostic — the
   Python code demonstrates the patterns; translate to TS syntax as needed.
2. **For "when to use TypeScript vs Python"** →
   [`EXAM_MAP_PYTHON_VS_TYPESCRIPT.md`](./EXAM_MAP_PYTHON_VS_TYPESCRIPT.md).
3. **For the TypeScript API surface** → `claude-agent-sdk-typescript-main/CHANGELOG.md`
   is the fastest way to see what every feature is called in the TS SDK.
