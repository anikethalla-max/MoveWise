# Evaluation (dataset v1)

The committed [dataset](../data/demo/evaluation-v1.json) and [raw results](evaluation-results/mock-v1.json) are versioned. Run `python -m scripts.evaluate --output ../docs/evaluation-results/mock-v1.json` from `backend` to reproduce the deterministic mock run. It uses an isolated SQLite database, a scripted chat double, deterministic embeddings, and three synthetic documents and homes. It makes **no real AI provider calls**. The browser journey uses the same explicitly labeled simulation. No live PostgreSQL/pgvector or OIDC provider was available during this evaluation.

## Dataset and scoring

There are five agreement cases (deposit, notice, unsupported, conflict, prompt injection), three Coordinator routing cases, three single versus multi agent task cases, three homes, and three documents. The budget and workflow checks use the same fixture. Retrieval hit means all expected evidence terms appear in the returned excerpts; the unsupported case is excluded from that denominator. Answer correctness requires the expected outcome status and all case answer terms. Citation validity requires every cited chunk ID to occur among that run's retrieved hits. Citation support requires the expected evidence terms in cited excerpts; unsupported answers have no support denominator. Routing is exact specialist set equality. Task completion is exact coverage of the specialists required by the case; a fixed Housing only run is the single specialist baseline. A budget violation means an over-limit home was reported as affordable. Latency is wall-clock time inside the local process and excludes browser navigation. Provider token counts and cost are recorded only when actual usage and configured prices exist; a conservative token estimate is never presented as billed usage.

| Measured result, scripted mock | Value |
| --- | ---: |
| Retrieval hit rate | 4/4 = 100% |
| RAG answer correctness | 5/5 = 100% |
| No-retrieval answer correctness | 1/5 = 20% |
| Citation validity | 5/5 cases = 100% |
| Citation support | 4/4 cited cases = 100% |
| Coordinator routing | 3/3 = 100% |
| Housing only task completion | 1/3 = 33.3% |
| Coordinator multi-agent task completion | 3/3 = 100% |
| Budget constraint violations | 0 in fixture |
| Budget expected totals | Matched fixture |
| Cancellation preserved confirmed plan | Yes |
| Duplicate confirmation idempotent | Yes |
| Workspace isolation | Passed fixture check |
| Median RAG latency | 2.37 ms |
| Median no-retrieval latency | 0.24 ms |
| Provider tokens / estimated cost | Unavailable / unavailable |

The no-retrieval baseline is intentionally evidence blind and always abstains; it answers only the unsupported case correctly. This comparison checks that retrieval and citations are wired into the scripted flow, **not** that RAG improves a real model by 80 points. The single specialist baseline is fixed to Housing, so the multi-agent comparison tests task coverage, not quality of a general single agent. Three routing cases and five questions are too small for statistical or real-world claims. The prompt injection case tests one synthetic malicious instruction; it does not prove broad resistance.

## LangGraph migration rerun

The [separate raw result](evaluation-results/mock-v1-langgraph.json) reruns the same dataset through the LangGraph state graph and LangChain structured tools. Retrieval, answers, citations, routing, task completion, budget, cancellation, and workspace isolation retained the scores above. Median local RAG latency was **9.54 ms** and median no-retrieval latency was **5.32 ms**, compared with **2.37 ms** and **0.24 ms** in the original custom-loop run. These are one small local scripted runs, so they show framework overhead in this fixture rather than a general latency benchmark. No real model improvement is claimed. Run `python -m scripts.evaluate --output ../docs/evaluation-results/mock-v1-langgraph.json` from `backend` to reproduce the current path.

## Failures and tradeoffs

The first browser run exposed a too-small 12,000-token cumulative estimate cap: Housing and Document completed, while Planning failed in a combined request. The cap was raised to 40,000 estimated tokens and the full journey then passed. The estimator counts repeated context and can be much larger than actual provider billing. A larger cap permits more work and potentially more cost; the tool step and elapsed-time bounds remain. A real provider could choose different tools, produce wrong or incomplete content, or exceed limits. No `OPENAI_API_KEY`, live PostgreSQL server, or configured OIDC issuer was available, so real-provider accuracy, cost, pgvector performance, and live authentication were not measured. Do not quote these scripted scores as model quality.

For a real-provider evaluation, configure `OPENAI_API_KEY`, PostgreSQL with pgvector, and the models in `backend/.env` through local environment management. Run the journey against real providers, inspect each answer and citation manually, record provider usage and actual configured prices, then add those measurements as a separate results file. The mock evaluation mode is rejected in production and displays a simulation banner in the UI.
