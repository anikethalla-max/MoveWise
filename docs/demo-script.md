# Five-minute MoveWise demo

Use a local backend with real provider credentials if available. For a fully reproducible **scripted simulation**, run `cd frontend; npm run test:e2e`, or start the disposable backend with `cd backend; python scripts/e2e_server.py` and the frontend with `cd frontend; npm run dev` using `NEXT_PUBLIC_EVALUATION_MOCK_MODE=true`. The simulation banner must remain visible. The agreement and homes in `data/demo` are synthetic.

| Time | Show | Say |
| --- | --- | --- |
| 0:00–0:45 | Create a Bengaluru profile with 15 January 2027 move date, ₹50,000 monthly and ₹100,000 upfront limits. | The workspace keeps user-entered facts separate from unknowns. |
| 0:45–1:30 | Add three clearly named synthetic homes; enter rent, maintenance, deposits, and budget estimates. | Decimal services compute monthly and upfront costs. Refundable deposits are separate from monthly spend. |
| 1:30–2:15 | Upload `data/demo/synthetic-rental-agreement.txt`; wait for Ready; ask “What is the refundable deposit?” and expand the source. | The Document Agent searches private chunks and cites the exact text. Unsupported questions abstain. |
| 2:15–3:00 | Open Housing advisor and compare homes, then select one. | The Housing Agent chooses tools; feasibility and scoring are deterministic. Source data and missing values remain visible. |
| 3:00–3:40 | Generate a Moving plan preview, inspect dated tasks and changes, then confirm. | Generated structure is proposed first. A user action creates the plan version. |
| 3:40–4:35 | Ask Assistant: “Compare my homes, explain the agreement deposit, and update my moving plan.” Expand the citation, specialist results, and run timeline. | The Coordinator delegates Housing, Document, then Planning work and preserves provenance. SSE reports observed actions. |
| 4:35–5:00 | Review the proposed revision, confirm it, and refresh. | Confirmation applies only the reviewed proposal. Conversations, run events, and plan versions persist. |

If using the scripted simulation, state that its answers and actions are deterministic test output, not evidence of a live LLM run. Never describe synthetic homes as available listings or user-entered commute minutes as live estimates.
