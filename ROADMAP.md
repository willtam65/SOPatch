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

## Next: finish making it run itself

The webhook is in; a human no longer has to remember to paste the note. What
remains is turning that trigger into a productionised loop.

- **Complete the automated trigger.** Deliver the notification to real Slack or
  email (it logs today when unconfigured), connect a live Jira via OAuth rather
  than an unauthenticated webhook, and add a review link so approval is one click.
- **The foundation that trigger needs.** Real login (SSO), a workspace model so
  one customer's SOPs and credentials are isolated, per-tenant encrypted secrets
  in place of the single shared credential, and a database for run history.
- **Audit trail.** Every change traceable from the Jira ticket to the SOP edit
  to the Confluence push, attributed to the person who approved it.

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
