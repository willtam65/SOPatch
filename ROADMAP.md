# Roadmap

SOPatch today is a working, evaluated prototype: paste a release note, get the
affected SOP sections flagged with grounded rewrites, review them, and push the
approved changes back to Confluence with version tracking. It does that one
thing, deliberately.

This roadmap is as much about what SOPatch will not build as what it will. The
guiding rule is simple: build from signal, not in a vacuum. The hard parts below
ship only once design partners have shown the problem is worth paying to solve.

## Shipped

- A token-aware tagger that flags which SOPs a release note affects, measured
  with a precision/recall eval harness rather than vibes.
- A grounding guard that drops any suggested edit whose quoted wording is not in
  the source document, so the tool never invents a change to your wiki.
- Typed, structured model output instead of brittle free-text parsing, plus
  retries, input validation, and structured logging.
- An optional content gate that trades a little precision for full recall, left
  off by default after measuring the tradeoff.
- Cost-tiered models (cheap classification on a small model, analysis on a
  stronger one), a credential-free demo mode, and CI.
- A Jira webhook trigger (`POST /webhook/jira`) that runs the pipeline on a
  released version or a labelled policy/process issue, parses the change note
  (including Jira Cloud's ADF format), and notifies a reviewer. This is the first
  step of removing the manual trigger: SOPatch can now start itself.
- A review queue and audit trail. Each run is persisted (SQLite), the reviewer
  notification links to a `/review/<id>` page with the flagged SOPs and a
  before/after of every drafted edit, and Approve or Reject is one click,
  attributed to the reviewer with a timestamp. Every step is written to an
  append-only audit trail, traceable from the Jira source to the approval.
- Approval ships the edit. Approving a run pushes each flagged SOP to Confluence
  with version tracking and audits every page individually, so a partial failure
  records exactly which SOPs landed and which did not instead of failing the
  whole approval. Demo Mode records the intent and sends nothing.

## Next: finish making it run itself

The webhook is in and a human no longer has to remember to paste the note; the
run is recorded and approved through the review queue. What remains is wiring the
trigger to live services and making it multi-tenant.

- **Deliver and connect for real.** Send the notification to real Slack or email
  (it logs today when unconfigured), and connect a live Jira via OAuth rather than
  an unauthenticated webhook.
- **The foundation that trigger needs.** Real login (SSO), a workspace model so
  one customer's SOPs and credentials are isolated, and per-tenant encrypted
  secrets in place of the single shared credential.

The distribution channel for this phase is an Atlassian Marketplace (Forge) app,
where the buyers with intent already are.

## Considered and deliberately deferred

- **File upload (PDF, Word, slides).** A convenience, not a capability. Pasting
  the text already covers it, and PDF or slide extraction is unreliable enough
  to undercut the trust the rest of the product earns. Revisit only on demand,
  and only for clean text formats.
- **Embeddings / vector retrieval.** Overkill at a few dozen SOPs. The
  token-aware matcher plus the content gate already hit the target on the eval
  set. This earns its cost at thousands of documents, not now.
- **Self-serve billing.** A fast follow once design partners are paying by
  manual invoice, not a precondition to the first dollar.
- **Regulated QMS (validated environments).** Highest willingness to pay, but
  out of reach until the product can meet the validation and security bar.

## Principle

Every addition has to answer one question: does it make the product run itself,
or just look busier? Convenience features and infrastructure no customer has
asked for wait until the signal is real.
