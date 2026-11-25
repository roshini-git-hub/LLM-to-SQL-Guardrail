"""Generic guardrail settings.

Nothing here names a table or column. What a user may see (tables, columns, sensitive data,
row-level security, table sizes) is read from the database itself by schema_loader.py.
"""

# Only these functions may appear in queries (SQLGlot sometimes reports a different name
# than the SQL text, e.g. date_trunc -> timestamp_trunc, so both spellings are listed).
ALLOWED_FUNCTIONS = {
    # aggregates
    "count", "sum", "avg", "min", "max", "string_agg", "group_concat",
    # numbers
    "round", "abs", "floor", "ceil", "greatest", "least",
    # text
    "lower", "upper", "length", "trim", "ltrim", "rtrim", "concat", "substring", "replace",
    # null handling
    "coalesce", "nullif",
    # dates
    "date_trunc", "timestamp_trunc", "extract", "now",
    "current_timestamp", "current_date", "current_time",
    # window functions
    "row_number", "rank", "dense_rank", "lag", "lead",
}

MAX_LIMIT = 1000                # rows returned at most (LIMIT is injected or clamped)

# --- Cost thresholds, relative to the database's own size ---------------------------------
# One "scan cost unit" = planner cost of a full sequential scan of the biggest table the role
# can read. Thresholds are multiples of it, so a tiny database and a large one are judged fairly.
MIN_SCAN_COST_UNIT = 1000       # floor, so a near-empty database does not flag everything
COST_LOW_FACTOR = 2             # >= 2 full scans of the biggest table  -> moderate cost
COST_MEDIUM_FACTOR = 10         # >= 10 full scans                      -> high cost
COST_HIGH_FACTOR = 50           # >= 50 full scans                      -> very high cost

# A sequential scan is flagged when it reads at least SEQ_SCAN_ROWS rows AND at least
# SEQ_SCAN_FRACTION of its table (i.e. no filter narrows it), on a table of real size.
SEQ_SCAN_ROWS = 100_000
SEQ_SCAN_MIN_TABLE_ROWS = 10_000
SEQ_SCAN_FRACTION = 0.5
HUGE_ROWS_FACTOR = 5            # warn if a plan step produces > 5x the biggest table's rows
HUGE_ROWS_FLOOR = 100_000
CARTESIAN_MIN_ROWS = 1_000      # ignore tiny cross joins

# --- Risk decision ---------------------------------------------------------------------------
REVIEW_AT = 35                  # risk score at or above this -> REVIEW
BLOCK_AT = 70                   # risk score at or above this -> BLOCK
SOFT_FINDING_POINTS = 10        # points per warning from the validator...
RULE_POINTS = {"sensitive_access": 35}  # ...except these (reading PII goes to a human)

# --- Schema snapshot cache -------------------------------------------------------------------
SNAPSHOT_MAX_AGE_SECONDS = 300  # safety net; normally refreshed instantly by LISTEN/NOTIFY
