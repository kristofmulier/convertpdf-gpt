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

    We enhance this to detect lines that have 2 or more '|' (pipes)
    as table rows, even if they don't start with '|'. We fix them
    so they do start with '|', removing any leading '#' if present.
    """
    lines = md_text.splitlines()
    blocks: List[Dict[str, Union[str, List[str]]]] = []
    current_block_lines: List[str] = []
    current_type: Optional[str] = None

    def add_block(block_type: str, block_lines: List[str]) -> None:
        if block_lines:
            blocks.append({"type": block_type, "lines": block_lines})

    for line in lines:
        # Check if it looks like a table row or separator
        if line.startswith("|") or looks_like_table_row(line):
            # It's part of a table row or separator row
            fixed_line = fix_table_row(line)
            if current_type == "table":
                current_block_lines.append(fixed_line)
            else:
                # Close out whatever we had before
                add_block(current_type or "text", current_block_lines)
                current_block_lines = [fixed_line]
                current_type = "table"
        else:
            # normal line or heading
            line_strip = line.strip()
            if is_markdown_heading(line_strip):
                # If we were building another block, close it first
                add_block(current_type or "text", current_block_lines)
                current_block_lines = [line]
                current_type = "heading"
            else:
                if current_type == "table":
                    # close the table block
                    add_block("table", current_block_lines)
                    current_block_lines = [line]
                    current_type = "text"
                elif current_type == "heading":
                    # close heading block
                    add_block("heading", current_block_lines)
                    current_block_lines = [line]
                    current_type = "text"
                else:
                    current_block_lines.append(line)

    # End the last block
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
    1) Remove any leading '#' or spaces, so we don't get '# 1' etc.
    2) Ensure it starts with '|'.
    """
    line = re.sub(r'^[#\s]+', '', line)  # remove leading '#' + optional spaces
    if not line.strip().startswith("|"):
        line = "| " + line.lstrip()
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
            existing_hashes = match.group(1)
            numeric_part = match.group(2)
            rest = match.group(3).rstrip()

            # If the text after the numeric part starts with a colon, skip heading logic
            if rest.lstrip().startswith(':'):
                fixed_lines.append(line)
                continue

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
    lines_out: List[str] = []
    for idx, block in enumerate(blocks):
        if idx > 0:
            lines_out.append("")  # one blank line between blocks
        lines_out.extend(block["lines"])
    return "\n".join(lines_out).strip()

def skip_header_and_separator(table_lines: List[str]) -> List[str]:
    lines_after_header = table_lines[1:]
    if lines_after_header and is_dash_separator(lines_after_header[0]):
        lines_after_header = lines_after_header[1:]
    return lines_after_header

def is_dash_separator(line: str) -> bool:
    stripped = line.replace(' ', '')
    if not (stripped.startswith('|') and stripped.endswith('|')):
        return False
    inner = stripped[1:-1]
    return all(ch in '-:|' for ch in inner)

def same_table_structure(table_lines_a: List[str], table_lines_b: List[str]) -> bool:
    if not table_lines_a or not table_lines_b:
        return False
    return table_lines_a[0].count("|") == table_lines_b[0].count("|")

def is_markdown_heading(line: str) -> bool:
    return line.startswith("#")

def is_page_heading(block: Dict[str, Union[str, List[str]]]) -> bool:
    if block["type"] != "heading":
        return False
    text = " ".join(block["lines"]).strip()
    return bool(re.match(r"^#{1,6}\s+Page\s+\d+", text, re.IGNORECASE))

def is_empty_text_block(block: Dict[str, Union[str, List[str]]]) -> bool:
    if block["type"] != "text":
        return False
    return all(not ln.strip() for ln in block["lines"])

def main() -> None:
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

    # 8) Write output file
    with open(args.output, "w", encoding="utf-8") as out:
        out.write(final_md)

    print(f"Done! Processed '{args.input}' → '{args.output}'.")
    return

if __name__ == "__main__":
    main()
