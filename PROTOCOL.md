# PROTOCOL: how Claude supervises you (read this before every milestone)

Files in this folder form the bridge between you and Claude. Keep them exactly in this format.

1. **INBOX.md** is Claude → you. **Read it at the start and after every milestone.** Execute any new entries (newest at the bottom),
   then append `ACK <entry-id>` lines to REPORT.md. Never edit INBOX.md yourself.
2. **REPORT.md** is you → Claude, append-only. After every milestone append:
   ```
   ## <ISO time> · M<n> done|partial · <one-line summary>
   - Built: …  (files/commands)
   - Verified: <test command> → <result>   (real output, never assumed)
   - Next: …
   - Blockers/questions for Claude: … (or "none")
   ```
   Keep each entry under 15 lines. Be exact: if something doesn't work, say so.
3. **STATUS.json** is machine-readable, overwrite it after every milestone and whenever you get blocked:
   ```json
   {"project":"...", "milestone":"M3", "state":"working|blocked|done", "percent":40,
    "last_update":"<ISO time>", "tests":"12 passed", "needs_claude":false, "needs_human":false,
    "question":"", "next":"M4 fix-list generator"}
   ```
   Set `needs_claude:true` for a decision you can't make; set `needs_human:true` only for things only Ashok can do (API key, account).
   **Then keep working** on the next unblocked task. Never idle waiting for an answer.
4. Commit to git after every milestone: `git commit -m "M<n>: …"`. Never push.
5. Work continuously through all milestones. Don't ask the human questions in chat. When all milestones are done, set
   `state:"done"`, write a final REPORT entry, and keep polishing (tests, README, UX) until INBOX.md gives new work.
