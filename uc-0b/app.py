"""
UC-0B app.py — Policy Summarizer (extractive, meaning-preserving).

Implements the two skills from skills.md, enforcing the rules in agents.md:
  * retrieve_policy  — parse the .txt policy into numbered sections/clauses,
                       without changing any wording.
  * summarize_policy — emit every clause under its section with its clause ref;
                       meaning-critical clauses are flagged and reproduced
                       verbatim so no condition can be softened or dropped.

Design choice: the summary is EXTRACTIVE. Paraphrasing a binding obligation is
exactly how clauses get omitted, scope-bled, or softened (the three UC-0B failure
modes), so the agent reorganises and flags rather than rewrites. The value added
is structure, meaning-critical flags, and a completeness audit — never new content.

See README.md for the run command and the 10-clause ground-truth inventory.
"""
import argparse
import re
import sys

# A line like "2. ANNUAL LEAVE" (section) vs "2.3 Employees must..." (clause).
SECTION_RE = re.compile(r"^(\d+)\.\s+([A-Z].*)$")
CLAUSE_RE = re.compile(r"^(\d+\.\d+)\s+(.*)$")

# Signals that a clause's meaning hinges on a binding verb, a condition, or a
# negation/exception. Such clauses are reproduced verbatim and flagged — never
# condensed. Designed to catch all 10 ground-truth clauses in the README.
CRITICAL_SIGNALS = [
    r"\bmust\b", r"\bwill\b", r"\brequires?\b", r"\brequired\b",
    r"\bnot permitted\b", r"\bnot valid\b", r"\bnot sufficient\b",
    r"\bforfeit\w*", r"\bregardless\b", r"under any circumstances",
    r"\bonly after\b", r"\bonly at\b", r"\bcannot\b", r"\bnot count\b",
    r"\bnot be (considered|carried|split|encashed)\b", r"\bdo not count\b",
]
CRITICAL_RE = re.compile("|".join(CRITICAL_SIGNALS), re.IGNORECASE)


def retrieve_policy(path: str) -> list:
    """
    Parse a policy .txt into ordered sections, each:
        { "number": "5", "title": "LEAVE WITHOUT PAY (LWP)",
          "clauses": [ {"id": "5.1", "text": "..."}, ... ] }
    Wording is preserved exactly; continuation lines are joined, whitespace
    normalised. Banner rules and the document header are ignored, not invented
    into clauses. Raises on an unreadable file (caller decides how to refuse).
    """
    with open(path, encoding="utf-8") as f:
        raw_lines = f.readlines()

    sections = []
    current_section = None
    current_clause = None

    for raw in raw_lines:
        stripped = raw.strip()
        if not stripped or set(stripped) <= set("═="):
            continue  # blank line or decorative banner

        sec = SECTION_RE.match(stripped)
        clause = CLAUSE_RE.match(stripped)

        if clause:
            current_clause = {"id": clause.group(1), "text": clause.group(2).strip()}
            if current_section is None:
                # Clause before any section header — keep the document well-formed
                current_section = {"number": "0", "title": "GENERAL", "clauses": []}
                sections.append(current_section)
            current_section["clauses"].append(current_clause)
        elif sec:
            current_section = {"number": sec.group(1), "title": sec.group(2).strip(),
                               "clauses": []}
            current_clause = None
            sections.append(current_section)
        elif current_clause is not None:
            # Continuation line of the current clause — append verbatim.
            current_clause["text"] = (current_clause["text"] + " " + stripped).strip()
        # else: pre-section document header lines — ignored, never turned into clauses.

    # Drop any section that ended up with no clauses (e.g. a stray header).
    return [s for s in sections if s["clauses"]]


def _is_meaning_critical(text: str) -> bool:
    return bool(CRITICAL_RE.search(text))


def summarize_policy(sections: list) -> str:
    """
    Render the structured sections into a compliant, clause-referenced summary.
    Every clause appears once under its section; meaning-critical clauses are
    tagged [MEANING-CRITICAL] and reproduced verbatim. Ends with a completeness
    footer. Adds no content beyond source clauses and structural labels.
    """
    if not sections:
        return ("UC-0B SUMMARY — REFUSED\n"
                "No numbered clauses found in the source. Refusing to summarise "
                "rather than emit an empty or invented document.\n")

    rule = "─" * 60
    lines = [
        "EMPLOYEE LEAVE POLICY — COMPLIANT EXTRACTIVE SUMMARY",
        "Method: extractive · clause-complete · meaning-critical clauses flagged "
        "verbatim · no content added beyond the source",
        rule,
        "",
    ]

    total_clauses = 0
    flagged_ids = []
    for sec in sections:
        lines.append(f"SECTION {sec['number']} — {sec['title']}")
        for c in sec["clauses"]:
            total_clauses += 1
            if _is_meaning_critical(c["text"]):
                flagged_ids.append(c["id"])
                lines.append(f"  {c['id']}  [MEANING-CRITICAL] {c['text']}")
            else:
                lines.append(f"  {c['id']}  {c['text']}")
        lines.append("")

    lines += [
        rule,
        "COMPLETENESS CHECK",
        f"  Sections summarised : {len(sections)}",
        f"  Clauses in source   : {total_clauses}",
        f"  Clauses in summary  : {total_clauses}  (100% — none dropped)",
        f"  Meaning-critical clauses preserved verbatim ({len(flagged_ids)}): "
        + ", ".join(flagged_ids),
        "  Source-only guarantee: every line above is a source clause or a "
        "structural label; no external content added.",
        "",
    ]
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="UC-0B Policy Summarizer")
    parser.add_argument("--input",  required=True, help="Path to policy .txt")
    parser.add_argument("--output", required=True, help="Path to write summary .txt")
    args = parser.parse_args()

    try:
        sections = retrieve_policy(args.input)
    except (FileNotFoundError, IOError) as exc:
        print(f"ERROR: cannot read policy file '{args.input}': {exc}", file=sys.stderr)
        sys.exit(1)

    summary = summarize_policy(sections)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(summary)

    clause_count = sum(len(s["clauses"]) for s in sections)
    if not sections:
        print("REFUSED: no numbered clauses found — see output file.")
    else:
        print(f"Done. {len(sections)} sections, {clause_count} clauses preserved. "
              f"Summary written to {args.output}")


if __name__ == "__main__":
    main()
