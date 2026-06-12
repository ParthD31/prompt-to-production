# skills.md — UC-0A Complaint Classifier

skills:
  - name: classify_complaint
    description: >
      Labels a single citizen-complaint row with category, priority, reason, and an
      ambiguity flag, using only the complaint description as evidence.
    input: >
      dict — one CSV row with keys complaint_id, date_raised, city, ward, location,
      description, reported_by, days_open. Only `complaint_id` and `description`
      are read; all other keys are ignored by design.
    output: >
      dict with keys complaint_id, category, priority, reason, flag.
      category ∈ {Pothole, Flooding, Streetlight, Waste, Noise, Road Damage,
      Heritage Damage, Heat Hazard, Drain Blockage, Other}; priority ∈ {Urgent,
      Standard, Low}; reason is one sentence quoting words from the description;
      flag is "NEEDS_REVIEW" or "".
    error_handling: >
      Missing/empty description → category Other, priority Standard,
      flag NEEDS_REVIEW. Tie between categories → best label + NEEDS_REVIEW.
      No keyword match → Other + NEEDS_REVIEW. Never raises on a single row.

  - name: batch_classify
    description: >
      Reads an input complaints CSV, runs classify_complaint on every row, and writes
      a results CSV with the five output columns — producing output even if some rows fail.
    input: >
      input_path (str) to test_[city].csv, output_path (str) for results_[city].csv.
    output: >
      Writes a CSV with header complaint_id, category, priority, reason, flag —
      one row per input row, in input order. Returns the count of rows written.
    error_handling: >
      A row that raises during classification is written with category Other,
      priority Standard, flag NEEDS_REVIEW and a reason noting the failure, so a bad
      row never aborts the batch. Empty/whitespace cells are treated as missing.
