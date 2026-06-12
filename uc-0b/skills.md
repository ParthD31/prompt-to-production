# skills.md — UC-0B Policy Summarizer

skills:
  - name: retrieve_policy
    description: >
      Loads a .txt policy file and parses it into structured, numbered sections
      and clauses without altering any wording.
    input: >
      path (str) to a policy .txt file (e.g. policy_hr_leave.txt).
    output: >
      list of sections, each a dict { number, title, clauses }, where clauses is
      an ordered list of dicts { id (e.g. "5.2"), text } with continuation lines
      joined and whitespace normalised but no words changed, added, or removed.
    error_handling: >
      Missing/unreadable file -> raises FileNotFoundError / IOError to the caller.
      A file with zero numbered clauses returns an empty structure so the caller
      can refuse rather than emit an empty summary. Lines that are not section
      headers or clauses (banners, document header) are ignored, not invented into clauses.

  - name: summarize_policy
    description: >
      Turns the structured sections into a compliant, clause-referenced summary
      that preserves every clause and flags meaning-critical obligations verbatim.
    input: >
      the structured sections list produced by retrieve_policy.
    output: >
      str — the summary text. Each section heading is followed by its clauses,
      each line prefixed with its clause id; meaning-critical clauses are tagged
      [MEANING-CRITICAL] and reproduced verbatim. Ends with a completeness footer
      listing clause count and the flagged clause ids.
    error_handling: >
      Empty input -> returns an explicit "no clauses found; refusing to summarise"
      notice instead of an empty file. Never paraphrases a meaning-critical clause;
      when in doubt it flags and quotes rather than condensing. Adds no content
      beyond the source clauses and structural labels.
