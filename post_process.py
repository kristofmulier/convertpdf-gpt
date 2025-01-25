#!/usr/bin/env python
import argparse
import re
import os
import sys
from typing import List, Dict, Union, Optional, NoReturn

def _help(parser: argparse.ArgumentParser, error_message: Optional[str] = None) -> NoReturn:
    """
    Print an optional error message, then the parser's help text,
    and exit with status code 1.
    """
    if error_message:
        print(error_message, file=sys.stderr)
        print(file=sys.stderr)
    parser.print_help(sys.stderr)
    sys.exit(1)

def parse_markdown_into_blocks(md_text: str) -> List[Dict[str, Union[str, List[str]]]]:
    """
    Splits the Markdown into blocks of 'heading', 'table', or 'text'.
    Each block is a dict:
       { "type": "heading"|"table"|"text", "lines": [str, ...] }

    This version:
      - Only checks if a line has >= 2 '|' to treat it as a table row;
      - Calls fix_table_row() so the line definitely starts with '|';
      - Never breaks the table block prematurely if the line has '|' in it.
    """
    lines = md_text.splitlines()
    blocks: List[Dict[str, Union[str, List[str]]]] = []
    current_block_lines: List[str] = []
    current_type: Optional[str] = None

    def add_block(block_type: str, block_lines: List[str]) -> None:
        """TODO: ADD COMMENT"""
        if block_lines:
            blocks.append({"type": block_type, "lines": block_lines})

    for line in lines:
        line_strip = line.strip()

        # 1) If it has >=2 pipes, treat as a table row
        if looks_like_table_row(line):
            fixed_line = fix_table_row(line)  # ensures it starts with "|"
            if current_type == "table":
                current_block_lines.append(fixed_line)
            else:
                # We are starting a new table block
                add_block(current_type or "text", current_block_lines)
                current_block_lines = [fixed_line]
                current_type = "table"

        # 2) Else, see if it's a heading
        elif is_markdown_heading(line_strip):
            add_block(current_type or "text", current_block_lines)
            current_block_lines = [line]
            current_type = "heading"

        # 3) Otherwise, normal text
        else:
            if current_type == "table":
                # We are leaving the table block
                add_block("table", current_block_lines)
                current_block_lines = [line]
                current_type = "text"
            elif current_type == "heading":
                # We are leaving a heading block
                add_block("heading", current_block_lines)
                current_block_lines = [line]
                current_type = "text"
            else:
                current_block_lines.append(line)

    # Finish the last block
    add_block(current_type or "text", current_block_lines)
    return blocks

def looks_like_table_row(line: str) -> bool:
    """
    Returns True if 'line' has 2 or more '|' characters,
    implying it's likely part of a table row or separator.
    """
    return line.count("|") >= 2

def fix_table_row(line: str) -> str:
    """
    1) Remove any leading '#' or spaces.
    2) Ensure it starts with '|'.
    3) Ensure it ends with '|'.
    """
    # Remove leading '#' + spaces
    line = re.sub(r'^[#\s]+', '', line)

    # Ensure it starts with '|'
    if not line.strip().startswith("|"):
        line = "| " + line.lstrip()

    # Ensure it ends with '|'
    if not line.rstrip().endswith("|"):
        line = line.rstrip() + " |"

    return line

def unify_headings_spread_over_two_lines(
    blocks: List[Dict[str, Union[str, List[str]]]]
) -> List[Dict[str, Union[str, List[str]]]]:
    """
    Some headings are spread across two lines, for example:

    # 8
    Nested Vector Interrupt Controller (NVIC)

    => becomes =>

    # 8 Nested Vector Interrupt Controller (NVIC)

    or

    ## 8.1
    # Full Name and Abbreviation of Terms

    => becomes =>

    ## 8.1 Full Name and Abbreviation of Terms
    """
    numeric_heading_no_text = re.compile(r'^#{1,6}\s+\d+(?:\.\d+)*$')
    bullet_pattern = re.compile(r'^#{0,6}\s*\d+(?:[.)])\s')
    heading_pattern = re.compile(r'^(#{0,6})\s*(\d+(?:\.\d+)*)(.*)$')

    i = 0
    while i < len(blocks) - 1:
        current_block = blocks[i]
        next_block = blocks[i + 1]

        if current_block["type"] == "heading" and len(current_block["lines"]) == 1:
            heading_line = current_block["lines"][0].strip()

            if numeric_heading_no_text.match(heading_line):
                if len(next_block["lines"]) >= 1:
                    next_line = next_block["lines"][0].rstrip()
                    ends_with_punct = (next_line and next_line[-1] in ('.', '!', '?'))
                    if not ends_with_punct:
                        next_line_stripped = next_line.lstrip()
                        is_bullet = bool(bullet_pattern.match(next_line_stripped))
                        is_numeric_heading = bool(heading_pattern.match(next_line_stripped))

                        if not (is_bullet or is_numeric_heading):
                            # If next_line starts with '#', remove it
                            next_line = re.sub(r'^[#\s]+', '', next_line, count=1).strip()
                            new_line = heading_line + " " + next_line
                            current_block["lines"] = [new_line]
                            next_block["lines"].pop(0)

                            # if next_block empty, remove it
                            if not any(ln.strip() for ln in next_block["lines"]):
                                blocks.pop(i + 1)
                            else:
                                i += 1
                            continue

        i += 1
    return blocks

def merge_multpage_tables(
    blocks: List[Dict[str, Union[str, List[str]]]]
) -> List[Dict[str, Union[str, List[str]]]]:
    """
    TODO: ADD COMMENT
    """
    merged_blocks: List[Dict[str, Union[str, List[str]]]] = []
    i = 0

    while i < len(blocks):
        block = blocks[i]
        if block["type"] == "table":
            tableA = block
            j = i + 1
            while j < len(blocks):
                if is_empty_text_block(blocks[j]) or is_page_heading(blocks[j]):
                    j += 1
                    continue
                if blocks[j]["type"] == "table":
                    tableB = blocks[j]
                    if same_table_structure(tableA["lines"], tableB["lines"]):
                        merged_lines = tableA["lines"] + skip_header_and_separator(tableB["lines"])
                        tableA = {"type": "table", "lines": merged_lines}
                        j += 1
                        continue
                break
            merged_blocks.append(tableA)
            i = j
        else:
            merged_blocks.append(block)
            i += 1
    return merged_blocks

def remove_page_headings_and_reassemble(
    blocks: List[Dict[str, Union[str, List[str]]]]
) -> str:
    """
    TODO: ADD COMMENT
    """
    filtered_blocks: List[Dict[str, Union[str, List[str]]]] = []
    for b in blocks:
        if is_page_heading(b):
            continue
        filtered_blocks.append(b)
    return reassemble_blocks(filtered_blocks)

def fix_titles_and_headings(md_text: str) -> str:
    """
    1) If a line ends with '.', '!', or '?', treat it as normal text (not a heading or bullet).
    2) If a line matches the bullet/list pattern (e.g. '# 1. Text'), remove all '#' so it becomes normal text: '1. Text'.
    3) If a line is a numeric heading (e.g. '# 8.1 Title' or '## 1.2.3 Another'), fix the number of '#' = (dot_count + 1),
       EXCEPT if the text after the numeric part starts with ':', e.g. '31:22'.
    4) If a line starts with '#' but doesn't match bullets or numeric heading, remove the '#'.
    """
    lines = md_text.splitlines()
    fixed_lines: List[str] = []

    bullet_pattern = re.compile(r'^#{0,6}\s*\d+(?:[.)])\s')
    heading_pattern = re.compile(r'^(#{0,6})\s*(\d+(?:\.\d+)*)(.*)$')

    for line in lines:
        original = line
        stripped = line.strip()

        # 1) If the stripped line ends with one of . ! ?, treat as normal text
        if stripped and stripped[-1] in ('.', '!', '?'):
            fixed_lines.append(line)
            continue

        # 2) Check bullet pattern
        if bullet_pattern.match(stripped):
            new_line = re.sub(r'^[#\s]+', '', original)
            fixed_lines.append(new_line)
            continue

        # 3) Check numeric heading pattern
        match = heading_pattern.match(stripped)
        if match:
            # If there's a colon in the numeric part or right afterward,
            # do NOT treat it as a heading at all.
            # Instead, skip to step 4 below (removing '#' entirely).
            if ':' in stripped:
                new_line = re.sub(r'^[#\s]+', '', original)
                fixed_lines.append(new_line)
                continue
    
            existing_hashes = match.group(1)
            numeric_part = match.group(2)
            rest = match.group(3).rstrip()

            # # If the text after the numeric part starts with a colon, skip heading logic
            # if rest.lstrip().startswith(':'):
            #     fixed_lines.append(line)
            #     continue

            # Otherwise, it's a valid numeric heading => set heading level
            level = numeric_part.count('.') + 1
            new_hashes = "#" * level
            if rest:
                new_line = f"{new_hashes} {numeric_part}{rest}"
            else:
                new_line = f"{new_hashes} {numeric_part}"
            fixed_lines.append(new_line)
            continue

        # 4) If line starts with '#' but doesn't match bullet or numeric => remove '#'
        if stripped.startswith('#'):
            new_line = re.sub(r'^[#\s]+', '', original)
            fixed_lines.append(new_line)
        else:
            fixed_lines.append(line)
    return "\n".join(fixed_lines)

def reassemble_blocks(blocks: List[Dict[str, Union[str, List[str]]]]) -> str:
    """
    TODO: ADD COMMENT
    """
    lines_out: List[str] = []
    for idx, block in enumerate(blocks):
        if idx > 0:
            lines_out.append("")  # one blank line between blocks
        lines_out.extend(block["lines"])
    return "\n".join(lines_out).strip()

def skip_header_and_separator(table_lines: List[str]) -> List[str]:
    """
    TODO: ADD COMMENT
    """
    lines_after_header = table_lines[1:]
    if lines_after_header and is_dash_separator(lines_after_header[0]):
        lines_after_header = lines_after_header[1:]
    return lines_after_header

def is_dash_separator(line: str) -> bool:
    """
    TODO: ADD COMMENT
    """
    stripped = line.replace(' ', '')
    if not (stripped.startswith('|') and stripped.endswith('|')):
        return False
    inner = stripped[1:-1]
    return all(ch in '-:|' for ch in inner)

def same_table_structure(table_lines_a: List[str], table_lines_b: List[str]) -> bool:
    """
    TODO: ADD COMMENT
    """
    if not table_lines_a or not table_lines_b:
        return False
    return table_lines_a[0].count("|") == table_lines_b[0].count("|")

def is_markdown_heading(line: str) -> bool:
    """
    TODO: ADD COMMENT
    """
    return line.startswith("#")

def is_page_heading(block: Dict[str, Union[str, List[str]]]) -> bool:
    """
    TODO: ADD COMMENT
    """
    if block["type"] != "heading":
        return False
    text = " ".join(block["lines"]).strip()
    return bool(re.match(r"^#{1,6}\s+Page\s+\d+", text, re.IGNORECASE))

def is_empty_text_block(block: Dict[str, Union[str, List[str]]]) -> bool:
    """
    TODO: ADD COMMENT
    """
    if block["type"] != "text":
        return False
    return all(not ln.strip() for ln in block["lines"])

def fix_broken_bitfield_tables(md_text: str) -> str:
    """
    Look for lines like:
        (some blank lines)
        10:9
        (some blank lines)
        Reserved
        (some blank lines)
    that appear *immediately* after a table, and fold them back
    into that preceding table as a new row:

        | 10:9 | Reserved |  |  |

    Then, only insert a blank line after the table if the next
    non-blank line is *not* another table row.
    """
    lines = md_text.splitlines()
    output: list[str] = []
    last_table: list[str] = []
    in_table = False

    # A line is table-like if it starts with "|"
    def is_table_line(line: str) -> bool:
        return line.strip().startswith("|")

    # Regex for lines like "10:9", "31:29", etc.
    bitfield_pattern = re.compile(r'^\s*\d+:\d+\s*$')

    i = 0
    while i < len(lines):
        line = lines[i]

        # CASE A: Is this line a table line?
        if is_table_line(line):
            if not in_table:
                in_table = True
            last_table.append(line)
            i += 1

        else:
            # We have a non-table line
            if in_table:
                # We just ended a table block => finalize it
                in_table = False

                # Fold in bitfield lines + "Reserved" lines
                while True:
                    # 1) Skip blank lines
                    while i < len(lines) and not lines[i].strip():
                        i += 1
                    # 2) Need at least two lines left for "bitrange + Reserved"
                    if i + 1 >= len(lines):
                        break

                    # 3) Check for bitfield + Reserved
                    if bitfield_pattern.match(lines[i]):
                        bit_range = lines[i].strip()
                        i += 1

                        # skip blank lines before "Reserved"
                        while i < len(lines) and not lines[i].strip():
                            i += 1

                        # next line must be "Reserved"
                        if i < len(lines) and lines[i].strip().lower() == "reserved":
                            i += 1
                            # skip blank lines after "Reserved"
                            while i < len(lines) and not lines[i].strip():
                                i += 1

                            # Insert the new row
                            new_row = f"| {bit_range} | Reserved |  |  |"
                            last_table.append(new_row)
                        else:
                            # Not the pattern => revert
                            i -= 1
                            break
                    else:
                        break

                # Now output the entire table
                output.extend(last_table)
                last_table.clear()

                # ----------------------------------------------------
                # *Peek* ahead in the input to see if the next NON-blank
                # line is a table row. If not, then insert a blank line.
                # ----------------------------------------------------
                peek = i
                while peek < len(lines) and not lines[peek].strip():
                    peek += 1
                # If we've hit EOF or the next line isn't table-like => blank line
                if peek >= len(lines) or not is_table_line(lines[peek]):
                    # Insert one blank line if last line of output not blank
                    if output and output[-1].strip():
                        output.append('')

                # We *don't* increment i here if it's still referencing
                # the current 'line'. We'll handle that in next loop iteration.

            else:
                # We are outside a table => just output
                output.append(line)
                i += 1

    # If ended in a table, finalize it.
    if in_table and last_table:
        output.extend(last_table)
        last_table.clear()

        # Similarly, check if we need a trailing blank line
        if output and output[-1].strip():
            output.append('')

    return "\n".join(output)

def fix_multiline_table_cells(md_text: str) -> str:
    """
    Option A:
      - Keep "strict header" for the first (and optional second) row,
      - For subsequent data rows, treat them as "continuation" ONLY if
        *all* columns except the last are blank.
      - Otherwise, treat them as a brand-new row.

    This prevents losing data (e.g. "MBKEN") if the line
    isn't truly just a continuation of the previous row's last cell.
    """
    lines = md_text.splitlines()
    output: list[str] = []

    current_table: list[list[str]] = []
    table_cols_count: int | None = None
    in_table = False
    row_index_in_table = 0  # 0 => first row (header), 1 => possible dash-separator, >=2 => data

    def flush_table():
        """Convert all rows in current_table to Markdown lines, push them to output."""
        if not current_table:
            return
        for row in current_table:
            row_str = " | ".join(col.strip() for col in row)
            output.append(f"| {row_str} |")
        current_table.clear()

    def is_table_row(line: str) -> bool:
        """We assume lines that start/end with "|" are table rows"""
        text = line.strip()
        return text.startswith("|") and text.endswith("|")

    def is_dash_separator(columns: list[str]) -> bool:
        """e.g. ['---','----','---:'] etc."""
        dash_or_colon = re.compile(r'^[\-\:\s]+$')
        return all(dash_or_colon.match(c.strip()) for c in columns)

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # If it's not a table row => flush if in table, then output as normal text
        if not is_table_row(line):
            if in_table:
                flush_table()
                in_table = False
                row_index_in_table = 0
                table_cols_count = None
                # Optionally add a blank line after closing a table
                if output and output[-1].strip():
                    output.append("")
            output.append(line)
            i += 1
            continue

        # Otherwise => it's a table row
        columns = [c for c in line.split("|")[1:-1]]

        if not in_table:
            # Starting a brand-new table
            in_table = True
            row_index_in_table = 0
            current_table.append(columns)
            table_cols_count = len(columns)
            i += 1
            continue

        # We are inside a table already
        if row_index_in_table == 0:
            # The second line in the table might be a dash-separator or data row
            # We'll handle both as "strict" checks: if mismatch => close old, start new
            if len(columns) == table_cols_count:
                current_table.append(columns)
                row_index_in_table += 1
            else:
                flush_table()
                output.append("")
                current_table.clear()
                current_table.append(columns)
                table_cols_count = len(columns)
                row_index_in_table = 0
            i += 1

        elif row_index_in_table == 1:
            # Possibly a dash row or second header => still strict
            if len(columns) == table_cols_count:
                current_table.append(columns)
                row_index_in_table += 1
            else:
                flush_table()
                output.append("")
                current_table.clear()
                current_table.append(columns)
                table_cols_count = len(columns)
                row_index_in_table = 0
            i += 1

        else:
            # row_index_in_table >= 2 => "data" => lenient
            col_count = len(columns)

            if col_count == table_cols_count:
                #
                # 1) Check if it's a "continuation" line => all columns except last are blank?
                #    e.g. "|     |     |     | some text |"
                #    That means columns[0..-2] must be empty, or else it's a new row.
                #
                if all(not c.strip() for c in columns[:-1]):
                    # => merge into last row's last column
                    current_table[-1][-1] += "<br>" + columns[-1].strip()
                else:
                    # => new row
                    current_table.append(columns)

            elif col_count < table_cols_count:
                # Possibly a continuation or possibly just a row missing columns
                # We'll still do the same check:
                if all(not c.strip() for c in columns[:-1]):
                    # merge into last column
                    # pad the last column with anything that *is* in columns[-1]
                    # or if col_count=0 => do nothing
                    if columns:
                        current_table[-1][-1] += "<br>" + columns[-1].strip()
                else:
                    # pad it out => new row
                    needed = table_cols_count - col_count
                    columns += [""] * needed
                    current_table.append(columns)

            else:
                # col_count > table_cols_count => merge extras into last column
                merged = columns[:table_cols_count - 1]
                remainder = columns[table_cols_count - 1:]
                merged_last = " / ".join(s.strip() for s in remainder)
                merged.append(merged_last)
                # Check if the first columns are all blank => continuation
                if all(not c.strip() for c in merged[:-1]):
                    current_table[-1][-1] += "<br>" + merged[-1]
                else:
                    current_table.append(merged)

            row_index_in_table += 1
            i += 1

    # Finish file => if we ended in a table => flush
    if in_table:
        flush_table()
        if output and output[-1].strip():
            output.append("")

    return "\n".join(output)

def main() -> None:
    """
    TODO: ADD COMMENT
    """
    parser = argparse.ArgumentParser(description="Post-process a Markdown file.")
    parser.add_argument("input", nargs="?", help="Path to the input Markdown file")
    parser.add_argument("-o", "--output", help="Path to the output (processed) Markdown file")
    args = parser.parse_args()

    # 1) Basic sanity checks
    if not args.input:
        _help(parser, "Error: No input file provided.")

    if not os.path.isfile(args.input):
        _help(parser, f"Error: The file '{args.input}' does not exist or is not a valid path.")

    if not args.output:
        _help(parser, "Error: No output file specified (use -o OUTPUT.md).")

    # 2) Read input file
    with open(args.input, "r", encoding="utf-8") as f:
        original_md = f.read()

    # 3) Parse into blocks
    blocks = parse_markdown_into_blocks(original_md)

    # 4) Unify headings spread across two lines
    blocks = unify_headings_spread_over_two_lines(blocks)

    # 5) Merge multi-page tables
    blocks = merge_multpage_tables(blocks)

    # 6) Remove '# Page X' headings and reassemble
    merged_md = remove_page_headings_and_reassemble(blocks)

    # 7) Fix numeric headings, remove spurious '#', etc.
    final_md = fix_titles_and_headings(merged_md)

    # 8) Post-post-processing to fix broken bitfield tables
    final_md = fix_broken_bitfield_tables(final_md)

    # 9) Fix multiline table cells
    final_md = fix_multiline_table_cells(final_md)

    # 10) Write output file
    with open(args.output, "w", encoding="utf-8") as out:
        out.write(final_md)

    print(f"Done! Processed '{args.input}' → '{args.output}'.")
    return

if __name__ == "__main__":
    main()
