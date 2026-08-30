#!/usr/bin/env python3
"""
Spotify Music Analyzer — Schema / Script Dependency Audit

Purpose
-------
Audit the relationship between the SQLite schema and Python source files
without modifying either one.

This version intentionally avoids the previous heuristic that dynamically
constructed regular expressions from source code. That approach caused
FutureWarning messages and regex compilation errors when Python source
contained character classes, quantifiers, ranges, etc.

This script:
  1. Reads the SQLite schema.
  2. Discovers Python files in the project.
  3. Extracts likely SQL fragments using fixed, safe regular expressions.
  4. Detects SQL table references.
  5. Detects qualified column references (alias.column).
  6. Reports unknown tables / columns when they can be determined safely.
  7. Reports occurrences of schema column names in SQL fragments.
  8. Reviews MusicBrainz identifier naming variants.
  9. Does NOT modify the database or source files.

Important
---------
This remains a heuristic audit. Python can construct SQL dynamically, so
absence of a detected reference does not prove absence of a dependency.
"""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict
from pathlib import Path


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "spotify_music.db"

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
}

SQL_KEYWORDS = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE",
    "FROM",
    "JOIN",
    "CREATE TABLE",
    "ALTER TABLE",
    "DROP TABLE",
    "WITH",
)

# Fixed regular expressions only.
# Nothing from source code is ever interpolated into these patterns.
TRIPLE_STRING_RE = re.compile(
    r"""(?P<prefix>[rubfRUBF]{0,4})"""
    r"""(?P<quote>'''|\"\"\")"""
    r"""(?P<body>.*?)"""
    r"""(?P=quote)""",
    re.DOTALL,
)

SINGLE_STRING_RE = re.compile(
    r"""(?P<prefix>[rubfRUBF]{0,4})"""
    r"""(?P<quote>'|\")"""
    r"""(?P<body>(?:\\.|(?! (?P=quote) ).)*?)"""
    r"""(?P=quote)""".replace("(?! (?P=quote) )", r"(?!(?P=quote))"),
    re.DOTALL,
)

# SQL table references. These patterns are deliberately conservative.
TABLE_FROM_RE = re.compile(
    r"\b(?:FROM|JOIN|UPDATE|INTO|TABLE)\s+([A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)

TABLE_DELETE_RE = re.compile(
    r"\bDELETE\s+FROM\s+([A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)

# Qualified identifiers such as:
#   t.spotify_id
#   ta.artist_id
#   s.artist_id
QUALIFIED_COLUMN_RE = re.compile(
    r"\b([A-Za-z_][A-Za-z0-9_]*)\.([A-Za-z_][A-Za-z0-9_]*)\b"
)

# SQL aliases:
#   FROM tracks t
#   JOIN track_artists AS ta
ALIAS_RE = re.compile(
    r"\b(?:FROM|JOIN)\s+([A-Za-z_][A-Za-z0-9_]*)"
    r"(?:\s+AS)?\s+([A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)

# SQLite quoted identifiers.
QUOTED_IDENTIFIER_RE = re.compile(
    r'(?:"([A-Za-z_][A-Za-z0-9_]*)"|`([A-Za-z_][A-Za-z0-9_]*)`|\[([A-Za-z_][A-Za-z0-9_]*)\])'
)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def print_header(title: str) -> None:
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def print_section(title: str) -> None:
    print()
    print("-" * 78)
    print(title)
    print("-" * 78)


def normalize_sql(text: str) -> str:
    """Normalize whitespace while preserving SQL semantics sufficiently for audit."""
    return re.sub(r"\s+", " ", text).strip()


def looks_like_sql(text: str) -> bool:
    """Return True when a string looks sufficiently like SQL to inspect."""
    stripped = text.strip()
    if not stripped:
        return False

    upper = stripped.upper()

    # Must contain at least one SQL keyword.
    return any(
        re.search(r"\b" + re.escape(keyword) + r"\b", upper)
        for keyword in SQL_KEYWORDS
    )


def line_number(source: str, position: int) -> int:
    return source.count("\n", 0, position) + 1


def discover_python_files() -> list[Path]:
    files = []

    for path in BASE_DIR.rglob("*.py"):
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        files.append(path)

    return sorted(files)


def get_schema(connection: sqlite3.Connection):
    tables: dict[str, list[str]] = {}
    columns: dict[str, set[str]] = {}

    rows = connection.execute(
        """
        SELECT name
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
    ).fetchall()

    for (table_name,) in rows:
        table_columns = [
            row[1]
            for row in connection.execute(
                f'PRAGMA table_info("{table_name.replace(chr(34), chr(34) * 2)}")'
            ).fetchall()
        ]

        tables[table_name] = table_columns
        columns[table_name] = set(table_columns)

    return tables, columns


def extract_sql_fragments(source: str):
    """
    Extract likely SQL strings.

    Priority is given to triple-quoted strings because they are the dominant
    form for multi-line SQL in this project. Single-line strings are also
    inspected, but only when they clearly contain SQL keywords.

    Returns:
        list[(line_number, normalized_sql)]
    """
    fragments = []
    occupied_ranges = []

    for match in TRIPLE_STRING_RE.finditer(source):
        body = match.group("body")

        if looks_like_sql(body):
            fragments.append(
                (
                    line_number(source, match.start()),
                    normalize_sql(body),
                )
            )

        occupied_ranges.append((match.start(), match.end()))

    # Inspect single-line strings outside triple-string ranges.
    # This catches connection.execute("SELECT ...") and similar code.
    for match in SINGLE_STRING_RE.finditer(source):
        start = match.start()
        if any(a <= start < b for a, b in occupied_ranges):
            continue

        body = match.group("body")

        if looks_like_sql(body):
            fragments.append(
                (
                    line_number(source, match.start()),
                    normalize_sql(body),
                )
            )

    # Deduplicate identical line/sql pairs.
    return sorted(set(fragments))


def extract_table_references(sql: str) -> set[str]:
    refs = set()

    for match in TABLE_FROM_RE.finditer(sql):
        refs.add(match.group(1))

    for match in TABLE_DELETE_RE.finditer(sql):
        refs.add(match.group(1))

    return refs


def extract_aliases(sql: str) -> dict[str, str]:
    """
    Return alias -> table mappings.

    Example:
        FROM track_artists ta
        JOIN tracks AS t

    becomes:
        {"ta": "track_artists", "t": "tracks"}
    """
    aliases = {}

    for match in ALIAS_RE.finditer(sql):
        table = match.group(1)
        alias = match.group(2)

        # Avoid interpreting SQL keywords as aliases.
        if alias.upper() in {
            "WHERE", "ON", "USING", "LEFT", "RIGHT", "INNER", "OUTER",
            "FULL", "CROSS", "JOIN", "GROUP", "ORDER", "LIMIT", "OFFSET",
            "SET", "VALUES", "SELECT", "FROM",
        }:
            continue

        aliases[alias] = table

    return aliases


def extract_qualified_columns(sql: str):
    return [
        (match.group(1), match.group(2))
        for match in QUALIFIED_COLUMN_RE.finditer(sql)
    ]


def extract_unqualified_schema_columns(sql: str, schema_columns: set[str]):
    """
    Find exact SQL identifier occurrences matching known column names.

    This is deliberately a simple token scan, not a SQL parser. It is useful
    for dependency review but does not attempt to prove semantic ownership.
    """
    if not schema_columns:
        return set()

    identifiers = set(
        match.group(0)
        for match in re.finditer(r"\b[A-Za-z_][A-Za-z0-9_]*\b", sql)
    )

    return identifiers & schema_columns


def audit_file(
    path: Path,
    schema_tables: dict[str, list[str]],
    schema_columns: dict[str, set[str]],
):
    source = path.read_text(encoding="utf-8", errors="replace")
    fragments = extract_sql_fragments(source)

    table_refs: set[str] = set()
    qualified_refs: set[tuple[str, str]] = set()
    aliases: dict[str, str] = {}
    fragment_records = []

    all_schema_columns = set()
    for cols in schema_columns.values():
        all_schema_columns.update(cols)

    unqualified_refs: set[str] = set()

    for line_no, sql in fragments:
        tables = extract_table_references(sql)
        fragment_aliases = extract_aliases(sql)
        qualified = extract_qualified_columns(sql)
        unqualified = extract_unqualified_schema_columns(
            sql,
            all_schema_columns,
        )

        table_refs.update(tables)
        qualified_refs.update(qualified)
        aliases.update(fragment_aliases)
        unqualified_refs.update(unqualified)

        fragment_records.append(
            {
                "line": line_no,
                "sql": sql,
                "tables": tables,
                "aliases": fragment_aliases,
                "qualified": qualified,
                "unqualified": unqualified,
            }
        )

    unknown_tables = {
        table for table in table_refs
        if table.lower() not in {name.lower() for name in schema_tables}
    }

    unknown_qualified = []

    table_lookup = {
        name.lower(): name
        for name in schema_tables
    }

    for alias, column in sorted(qualified_refs):
        table_name = aliases.get(alias)

        if table_name is None:
            # We cannot safely resolve this qualified reference.
            continue

        canonical_table = table_lookup.get(table_name.lower())
        if canonical_table is None:
            continue

        if column not in schema_columns[canonical_table]:
            unknown_qualified.append(
                (alias, canonical_table, column)
            )

    return {
        "tables": table_refs,
        "qualified": qualified_refs,
        "unqualified": unqualified_refs,
        "aliases": aliases,
        "unknown_tables": unknown_tables,
        "unknown_qualified": unknown_qualified,
        "fragments": fragment_records,
    }


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report_schema(
    schema_tables: dict[str, list[str]],
) -> None:
    print_section("DATABASE SCHEMA")

    for table_name, columns in schema_tables.items():
        print()
        print(f"{table_name}")
        print("-" * len(table_name))
        for column in columns:
            print(f"  {column}")


def report_table_usage(file_results, schema_tables):
    print_section("TABLE USAGE")

    usage = defaultdict(set)

    for rel_path, result in file_results.items():
        for table in result["tables"]:
            canonical = next(
                (
                    name for name in schema_tables
                    if name.lower() == table.lower()
                ),
                table,
            )
            usage[canonical].add(rel_path)

    for table in sorted(usage):
        print()
        print(table)
        for path in sorted(usage[table]):
            print(f"  {path}")

    if not usage:
        print("  None detected.")


def report_invalid_references(file_results):
    print_section("INVALID / UNKNOWN TABLE REFERENCES")

    found = False

    for rel_path, result in file_results.items():
        for table in sorted(result["unknown_tables"]):
            found = True
            print(f"  {rel_path}: {table}")

    if not found:
        print("  None detected.")


def report_invalid_qualified(file_results):
    print_section("INVALID / UNKNOWN QUALIFIED COLUMN REFERENCES")

    found = False

    for rel_path, result in file_results.items():
        for alias, table, column in result["unknown_qualified"]:
            found = True
            print(
                f"  {rel_path}: {alias}.{column} "
                f"(resolved table: {table})"
            )

    if not found:
        print("  None detected.")


def report_qualified_usage(file_results):
    print_section("QUALIFIED COLUMN USAGE")

    usage = defaultdict(set)

    for rel_path, result in file_results.items():
        for alias, column in result["qualified"]:
            usage[f"{alias}.{column}"].add(rel_path)

    if not usage:
        print("  None detected.")
        return

    for reference in sorted(usage):
        print()
        print(reference)
        for path in sorted(usage[reference]):
            print(f"  {path}")


def report_file_level_sql(file_results):
    print_section("FILE-LEVEL SQL REFERENCES")

    files_with_sql = 0

    for rel_path, result in file_results.items():
        if not result["fragments"]:
            continue

        files_with_sql += 1

        print()
        print(rel_path)

        if result["tables"]:
            print("  Tables:")
            for table in sorted(result["tables"]):
                print(f"    {table}")

        if result["qualified"]:
            print("  Qualified columns:")
            for alias, column in sorted(result["qualified"]):
                print(f"    {alias}.{column}")

        print("  SQL fragments detected:")
        for fragment in result["fragments"]:
            print(
                f"    line {fragment['line']}: "
                f"{fragment['sql'][:180]}"
                + ("..." if len(fragment["sql"]) > 180 else "")
            )

    if files_with_sql == 0:
        print("  None detected.")


def report_column_occurrences(
    file_results,
    schema_tables,
):
    print_section("SCHEMA COLUMN OCCURRENCES IN SQL")

    # Build column -> table map.
    column_tables = defaultdict(set)

    for table, columns in schema_tables.items():
        for column in columns:
            column_tables[column].add(table)

    occurrences = defaultdict(set)

    for rel_path, result in file_results.items():
        for column in result["unqualified"]:
            for table in column_tables[column]:
                occurrences[column].add(
                    f"{rel_path} [possible table: {table}]"
                )

    if not occurrences:
        print("  None detected.")
        return

    for column in sorted(occurrences):
        print()
        print(column)
        for occurrence in sorted(occurrences[column]):
            print(f"  {occurrence}")

    print()
    print(
        "NOTE: unqualified column occurrences are reported as candidates, "
        "not proven dependencies."
    )


def report_mb_naming_review(schema_tables, file_results):
    print_section("MUSICBRAINZ IDENTIFIER NAMING REVIEW")

    variants = {
        "artist identifier": {
            "artist_id",
            "mb_artist_id",
        },
        "recording identifier": {
            "recording_id",
            "mb_recording_id",
            "mb_id",
        },
        "genre identifier": {
            "genre_id",
        },
        "tag identifier": {
            "tag_id",
        },
    }

    schema_column_locations = defaultdict(list)

    for table, columns in schema_tables.items():
        for column in columns:
            schema_column_locations[column].append(table)

    for label, names in variants.items():
        present = sorted(
            name for name in names
            if name in schema_column_locations
        )

        print()
        print(f"{label}:")

        if not present:
            print("  No matching schema columns detected.")
            continue

        for name in present:
            tables = ", ".join(
                sorted(schema_column_locations[name])
            )
            print(f"  {name:<20} -> {tables}")

    print()
    print("Cross-file references to relevant identifiers:")

    relevant = {
        "artist_id",
        "mb_artist_id",
        "recording_id",
        "mb_recording_id",
        "mb_id",
        "genre_id",
        "tag_id",
    }

    found = defaultdict(set)

    for rel_path, result in file_results.items():
        for fragment in result["fragments"]:
            sql = fragment["sql"]

            for identifier in relevant:
                if re.search(
                    r"\b" + re.escape(identifier) + r"\b",
                    sql,
                ):
                    found[identifier].add(
                        f"{rel_path}: line {fragment['line']}"
                    )

    for identifier in sorted(relevant):
        print()
        print(identifier)

        locations = sorted(found.get(identifier, set()))

        if not locations:
            print("  No SQL occurrence detected.")
        else:
            for location in locations:
                print(f"  {location}")

    print()
    print(
        "This section intentionally does NOT prescribe a rename. "
        "It identifies where each variant appears so a future schema "
        "change can be performed deliberately and completely."
    )


def report_dynamic_sql_candidates(file_results):
    print_section("POSSIBLE DYNAMIC SQL / MANUAL REVIEW CANDIDATES")

    # These are simple source-level indicators. They are not errors.
    indicators = (
        "execute(",
        "executemany(",
        "executescript(",
        "format(",
        "f\"",
        "f'",
        "f'''",
        'f"""',
    )

    found = []

    for rel_path, result in file_results.items():
        source_path = BASE_DIR / rel_path
        source = source_path.read_text(
            encoding="utf-8",
            errors="replace",
        )

        lines = source.splitlines()

        for index, line in enumerate(lines, start=1):
            if any(indicator in line for indicator in indicators):
                found.append((rel_path, index, line.strip()))

    if not found:
        print("  None detected.")
        return

    # Avoid flooding the report with every normal execute() call.
    # Group by file and show counts plus representative lines.
    by_file = defaultdict(list)

    for rel_path, line_no, text in found:
        by_file[rel_path].append((line_no, text))

    for rel_path in sorted(by_file):
        entries = by_file[rel_path]

        print()
        print(f"{rel_path}")
        print(f"  Candidate lines: {len(entries)}")

        for line_no, text in entries[:10]:
            print(f"    {line_no}: {text[:180]}")

        if len(entries) > 10:
            print(
                f"    ... {len(entries) - 10} additional candidate lines"
            )


def main():
    print_header(
        "SPOTIFY MUSIC ANALYZER — SCHEMA / SCRIPT DEPENDENCY AUDIT"
    )

    print()
    print(f"Project:  {BASE_DIR}")
    print(f"Database: {DB_PATH}")

    if not DB_PATH.exists():
        print()
        print("ERROR: SQLite database was not found.")
        print(f"Expected: {DB_PATH}")
        return 1

    python_files = discover_python_files()

    print()
    print(f"Python files discovered: {len(python_files)}")

    with sqlite3.connect(DB_PATH) as connection:
        schema_tables, schema_columns = get_schema(connection)

    print(f"Database tables discovered: {len(schema_tables)}")

    report_schema(schema_tables)

    file_results = {}
    analysis_errors = []

    for path in python_files:
        rel_path = path.relative_to(BASE_DIR)

        try:
            file_results[str(rel_path)] = audit_file(
                path,
                schema_tables,
                schema_columns,
            )
        except Exception as exc:
            analysis_errors.append(
                (str(rel_path), type(exc).__name__, str(exc))
            )

    if analysis_errors:
        print_section("FILES THAT COULD NOT BE ANALYZED")

        for rel_path, error_type, message in analysis_errors:
            print(f"  {rel_path}")
            print(f"    {error_type}: {message}")
    else:
        print_section("FILES THAT COULD NOT BE ANALYZED")
        print("  None.")

    report_table_usage(file_results, schema_tables)
    report_invalid_references(file_results)
    report_invalid_qualified(file_results)
    report_qualified_usage(file_results)
    report_file_level_sql(file_results)
    report_column_occurrences(file_results, schema_tables)
    report_mb_naming_review(schema_tables, file_results)
    report_dynamic_sql_candidates(file_results)

    # Statistics
    tables_detected = sum(
        len(result["tables"])
        for result in file_results.values()
    )

    qualified_detected = sum(
        len(result["qualified"])
        for result in file_results.values()
    )

    sql_fragments = sum(
        len(result["fragments"])
        for result in file_results.values()
    )

    print_header("AUDIT STATISTICS")

    print(f"Python files discovered:             {len(python_files)}")
    print(f"Python files analyzed:               {len(file_results)}")
    print(f"Database tables:                     {len(schema_tables)}")
    print(f"SQL fragments detected:              {sql_fragments}")
    print(f"SQL table references detected:       {tables_detected}")
    print(f"Qualified column references:         {qualified_detected}")
    print(f"Files with analysis errors:          {len(analysis_errors)}")

    print()
    print("IMPORTANT:")
    print("This audit is heuristic.")
    print(
        "Dynamic SQL, identifiers assembled at runtime, ORM-generated SQL, "
        "and SQL stored in unusual string constructions may require manual review."
    )
    print(
        "The script does not modify SQLite and does not modify Python source files."
    )

    print()
    print("=" * 78)
    print("AUDIT COMPLETED")
    print("=" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())