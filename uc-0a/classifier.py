"""
UC-0A — Complaint Classifier

Deterministic enforcement of the RICE rules defined in agents.md / skills.md.

Design decisions (these encode the enforcement rules — see agents.md):
  * Category and priority are decided from the `description` field ONLY.
    Ward / location / reporter / date are ignored to prevent taxonomy drift.
  * Category names come from a fixed allow-list — no variations are ever emitted.
  * Priority is Urgent iff a severity keyword (stem match) is present.
  * Every reason quotes words copied verbatim from the description.
  * Genuine ambiguity (keyword tie, or no match) -> best label + NEEDS_REVIEW.
  * A missing description or a row that raises never aborts the batch.
"""
import argparse
import csv
import re

# --- Allowed taxonomy (exact strings — enforced, never varied) -----------------
ALLOWED_CATEGORIES = [
    "Pothole", "Flooding", "Streetlight", "Waste", "Noise",
    "Road Damage", "Heritage Damage", "Heat Hazard", "Drain Blockage", "Other",
]

# Category -> evidence keywords. Order of this list is the deterministic
# tie-break order (earlier categories win an exact tie). Keywords are matched
# case-insensitively as substrings of the lower-cased description.
CATEGORY_KEYWORDS = [
    ("Pothole",         ["pothole"]),
    ("Flooding",        ["flood", "waterlogg", "water-logg", "knee-deep", "knee deep",
                         "submerg", "stranded", "inundat", "rainwater"]),
    ("Streetlight",     ["streetlight", "street light", "lights out", "light out",
                         "lamp post", "lamppost", "lamp", "dark at night",
                         "very dark", "darkness", "unlit", "flickering"]),
    ("Waste",           ["garbage", "trash", "litter", "rubbish", "dead animal",
                         "waste", "dumped", "dumping", "overflowing bin", "bins",
                         "sanitation", "not cleared", "not removed"]),
    ("Noise",           ["noise", "loud", "music", "blaring", "loudspeaker",
                         "past midnight", "late night", "honking", "drilling",
                         "band playing"]),
    ("Road Damage",     ["road surface", "cracked", "sinking", "footpath", "pavement",
                         "paving", "tiles broken", "broken tiles", "subsid", "caved in",
                         "crater", "road collapsed", "road sinking"]),
    ("Heritage Damage", ["heritage", "monument", "historic", "old city", "museum"]),
    ("Heat Hazard",     ["heat", "heatwave", "heat wave", "scorching", "high temperature",
                         "temperature", "melting", "sweltering", "full sun", "sunstroke"]),
    ("Drain Blockage",  ["drain", "manhole", "sewer", "sewage", "clogged",
                         "blocked drain", "open drain", "gutter"]),
]

# Severity keywords -> Urgent. Stem-matched at a word boundary so that, e.g.,
# "child" matches "children" and "collaps" matches "collapsed".
SEVERITY_STEMS = [
    "injur", "child", "school", "hospital", "ambulance",
    "fire", "hazard", "fell", "collaps",
]
SEVERITY_RE = re.compile(r"\b(" + "|".join(SEVERITY_STEMS) + r")\w*", re.IGNORECASE)

OUTPUT_FIELDS = ["complaint_id", "category", "priority", "reason", "flag"]


def _matched_keywords(text_lower):
    """Return {category: [keywords found]} for every category with >=1 hit."""
    hits = {}
    for category, keywords in CATEGORY_KEYWORDS:
        found = [kw for kw in keywords if kw in text_lower]
        # Count only maximal matches: drop a keyword that is a substring of
        # another matched keyword (e.g. "lamp" inside "lamp post") so overlapping
        # phrases don't inflate a category's score past a genuine tie.
        found = [kw for kw in found
                 if not any(kw != other and kw in other for other in found)]
        if found:
            hits[category] = found
    return hits


def classify_complaint(row: dict) -> dict:
    """
    Classify a single complaint row using its `description` only.
    Returns: dict with keys complaint_id, category, priority, reason, flag.
    """
    complaint_id = (row.get("complaint_id") or "").strip()
    description = (row.get("description") or "").strip()

    # Missing description -> cannot classify; flag for human review.
    if not description:
        return {
            "complaint_id": complaint_id,
            "category": "Other",
            "priority": "Standard",
            "reason": "No description provided, so the complaint cannot be categorised.",
            "flag": "NEEDS_REVIEW",
        }

    text_lower = description.lower()
    hits = _matched_keywords(text_lower)

    # --- Category decision with explicit ambiguity handling --------------------
    flag = ""
    if not hits:
        category = "Other"
        cited_words = []
        flag = "NEEDS_REVIEW"
    else:
        # Score = number of distinct keywords matched per category.
        scored = sorted(
            hits.items(),
            key=lambda kv: (-len(kv[1]), ALLOWED_CATEGORIES.index(kv[0])),
        )
        category, cited_words = scored[0][0], scored[0][1]
        top_score = len(scored[0][1])
        # A genuine tie (two categories matched equally strongly) is ambiguous.
        if len(scored) > 1 and len(scored[1][1]) == top_score:
            flag = "NEEDS_REVIEW"
            # Cite evidence from both tied categories so the reason is honest.
            cited_words = cited_words + scored[1][1]

    # --- Priority decision -----------------------------------------------------
    severity_hits = list(dict.fromkeys(m.group(0) for m in SEVERITY_RE.finditer(description)))
    priority = "Urgent" if severity_hits else "Standard"

    # --- Reason: one sentence quoting words from the description ----------------
    reason = _build_reason(category, cited_words, priority, severity_hits, flag)

    return {
        "complaint_id": complaint_id,
        "category": category,
        "priority": priority,
        "reason": reason,
        "flag": flag,
    }


def _build_reason(category, cited_words, priority, severity_hits, flag):
    """One sentence, always quoting words that appear in the description."""
    if cited_words:
        evidence = ", ".join(f"'{w}'" for w in dict.fromkeys(cited_words))
        base = f"Categorised as {category} from {evidence} in the description"
    else:
        base = f"No category keyword matched, so labelled {category}"

    if priority == "Urgent":
        sev = ", ".join(f"'{w}'" for w in severity_hits)
        base += f"; marked Urgent because the severity term(s) {sev} appear"

    if flag == "NEEDS_REVIEW" and cited_words:
        base += "; flagged NEEDS_REVIEW because multiple categories match"
    elif flag == "NEEDS_REVIEW":
        base += "; flagged NEEDS_REVIEW because the category is unclear"

    return base + "."


def batch_classify(input_path: str, output_path: str) -> int:
    """
    Read input CSV, classify each row, write results CSV.
    Produces output even if individual rows fail. Returns rows written.
    """
    written = 0
    with open(input_path, newline="", encoding="utf-8") as fin, \
            open(output_path, "w", newline="", encoding="utf-8") as fout:
        reader = csv.DictReader(fin)
        writer = csv.DictWriter(fout, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()

        for row in reader:
            try:
                result = classify_complaint(row)
            except Exception as exc:  # a bad row must never abort the batch
                result = {
                    "complaint_id": (row.get("complaint_id") or "").strip(),
                    "category": "Other",
                    "priority": "Standard",
                    "reason": f"Row could not be classified ({type(exc).__name__}).",
                    "flag": "NEEDS_REVIEW",
                }
            writer.writerow(result)
            written += 1

    return written


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="UC-0A Complaint Classifier")
    parser.add_argument("--input",  required=True, help="Path to test_[city].csv")
    parser.add_argument("--output", required=True, help="Path to write results CSV")
    args = parser.parse_args()
    count = batch_classify(args.input, args.output)
    print(f"Done. {count} rows classified. Results written to {args.output}")
