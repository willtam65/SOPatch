# SOPatch demo script (about 60 seconds)

A shot by shot walkthrough for a short screen recording. The whole loop runs in
Demo Mode with no keys and no external calls, so it is safe to record and nothing
touches a real wiki.

## Before you record

1. Start the app in Demo Mode: `SOPATCH_DEMO=1 python3 app.py`
2. Open `http://localhost:5001` at a clean 1280x800 window. Pick light or dark up
   front with the toggle and leave it (light usually reads better on LinkedIn).
3. Start from an empty queue so the story is clean: stop the app, run
   `rm data/sopatch.db`, start it again. The first simulated release becomes
   review #1.
4. Hide your bookmarks bar and any noisy browser extensions.

## Storyboard

| Time | Screen | Action | What it shows |
| --- | --- | --- | --- |
| 0:00 | Dashboard | Rest on the "Automated monitoring" card ("Watching Jira"). | It watches, it does not wait to be told. |
| 0:05 | Dashboard | Click **Simulate a Jira release**. | One click stands in for a real release shipping. |
| 0:08 | Dashboard | Let the status move: detected, then analyzing. | It reacts on its own. |
| 0:15 | Results | The flagged SOPs and the Slack style card appear. | It found the stale SOPs and drafted grounded edits. |
| 0:22 | Results | Point at the impact row (SOPs affected, sections, 100% grounded). | Every edit is grounded in the source document. |
| 0:28 | Results | Click **Open review #1** in the card. | The notification is a real link, not a dead end. |
| 0:32 | Review page | Scroll the before and after for one or two SOPs. | Current wording on the left, suggested on the right. |
| 0:42 | Review page | Rest on the grounding line ("quoted current wording exists in the source"). | The guard is real, not a promise. |
| 0:48 | Review page | Click **Approve edits**. | A human signs off; the status flips to approved. |
| 0:52 | Review queue | Click **Review queue** in the header. | The run is now approved in the queue. |
| 0:56 | Review page | Reopen it and rest on the audit trail (created, notified, approved by you). | The whole change is traceable end to end. |
| 1:00 | End | Hold on the review page. | Runs itself, a person approves, everything is auditable. |

## Optional captions

Short on screen text, one line at a time, no voiceover needed:

- "A release ships in Jira."
- "SOPatch finds the SOPs it made stale."
- "Every edit is grounded in the source document."
- "A human approves in one click."
- "And the whole change is auditable."

## Tips

- Move slowly. Pauses read as confidence; fast clicking reads as nerves.
- Record at 2x window scale if your screen is high resolution, so text stays crisp
  when LinkedIn compresses it.
- Keep it under 75 seconds. Post it as an MP4, or export a GIF for the profile
  Featured section.
