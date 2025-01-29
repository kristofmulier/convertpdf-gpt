#!/usr/bin/env python3

import sys

def parse_register_tables(text):
    """
    Parse all 'register' tables from the given text in a very forgiving way:
      - A table begins when we find a line starting with '|' in which
        the *first column* contains the word 'register' (case-insensitive).
      - We skip storing that header row, but from then on, any subsequent
        line that starts with '|' is treated as a row in the current table.
      - If we encounter a line that doesn't start with '|', we consider
        the current table ended (if we were parsing one).
      - Each row is stored as a list of columns (split on '|').
      - We do not require any specific number of columns.
    Returns a list of tables, where each table is a list of rows,
    and each row is a list of columns (strings).
    """

    lines = text.splitlines()
    in_table = False
    all_tables = []
    current_table_rows = []

    for line in lines:
        striped = line.strip()
        if not striped.startswith("|"):
            # This line does NOT start with "|"
            # => if we were inside a table, that table ends
            if in_table and current_table_rows:
                all_tables.append(current_table_rows)
            in_table = False
            current_table_rows = []
            continue

        # If we do start with '|', let's split on '|'.
        # We'll ignore trailing pipes, so let's do something simple:
        parts = line.strip('|').split('|')
        # Strip whitespace in each column:
        parts = [col.strip() for col in parts]

        if not in_table:
            # We might have found a header row if the first column
            # includes "register" (case-insensitive).
            if len(parts) > 0 and "register" in parts[0].lower():
                # This is the header row => start a new table
                # and skip storing this header row itself
                in_table = True
                current_table_rows = []
            # Otherwise, not recognized as a header => skip
        else:
            # We are in the middle of a table => treat this as data row
            current_table_rows.append(parts)

    # End of file => if we are still in a table, finalize it
    if in_table and current_table_rows:
        all_tables.append(current_table_rows)

    return all_tables

def main():
    # Read text from a file if provided, else from stdin
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        with open(filename, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    tables = parse_register_tables(text)

    # Print them out for demonstration
    for idx, tbl in enumerate(tables, start=1):
        print(f"Table #{idx} ({len(tbl)} rows):")
        for row_i, row_cols in enumerate(tbl, start=1):
            # row_cols is a list of strings
            print(f"  Row {row_i}, columns={len(row_cols)}: {row_cols}")
        print()

if __name__ == "__main__":
    main()
