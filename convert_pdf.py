import base64
import time
import io
import os
import re
import subprocess
import tempfile
import shutil
import argparse
import sys
from PIL import Image
import shutil
from openai import OpenAI
from typing import List, Optional, Any, Dict

# For colored output:
import colorama
from colorama import Fore, Style

# Initialize colorama so ANSI codes work (especially on Windows).
colorama.init(autoreset=True)

DEFAULT_MODEL: str = "gpt-4o"       # Use this model, unless the user passes another one as argument
FALLBACK_MODEL: str = "gpt-4o-mini" # Use this model if the primary one fails

VALID_MODELS: List[str] = [
    "o1",
    "o1-2024-12-17",
    "o1-preview",
    "o1-preview-2024-09-12",
    "o1-mini",
    "o1-mini-2024-09-12",
    "gpt-4o",
    "gpt-4o-2024-11-20",
    "gpt-4o-2024-08-06",
    "gpt-4o-2024-05-13",
    "gpt-4o-audio-preview",
    "gpt-4o-audio-preview-2024-10-01",
    "gpt-4o-audio-preview-2024-12-17",
    "gpt-4o-mini-audio-preview",
    "gpt-4o-mini-audio-preview-2024-12-17",
    "chatgpt-4o-latest",
    "gpt-4o-mini",
    "gpt-4o-mini-2024-07-18",
    "gpt-4-turbo",
    "gpt-4-turbo-2024-04-09",
    "gpt-4-0125-preview",
    "gpt-4-turbo-preview",
    "gpt-4-1106-preview",
    "gpt-4-vision-preview",
    "gpt-4",
    "gpt-4-0314",
    "gpt-4-0613",
    "gpt-4-32k",
    "gpt-4-32k-0314",
    "gpt-4-32k-0613",
    "gpt-3.5-turbo",
    "gpt-3.5-turbo-16k",
    "gpt-3.5-turbo-0301",
    "gpt-3.5-turbo-0613",
    "gpt-3.5-turbo-1106",
    "gpt-3.5-turbo-0125",
    "gpt-3.5-turbo-16k-0613",
]

def _help(parser: argparse.ArgumentParser, error_message: Optional[str] = None) -> None:
    """
    Print an optional error message, then the parser's help text,
    and exit with status code 1.
    """
    if error_message:
        print(error_message, file=sys.stderr)
        print(file=sys.stderr)
    parser.print_help(sys.stderr)
    sys.exit(1)

def call_pdftocairo(
    pdf_path: str,
    out_dir: str,
    poppler_path: str,
    dpi: int = 300,
    extra_args: Optional[List[str]] = None
) -> None:
    if extra_args is None:
        extra_args = []

    pdftocairo_exe: str = os.path.join(poppler_path, "pdftocairo")
    if os.name == 'nt' and not os.path.exists(pdftocairo_exe):
        pdftocairo_exe += ".exe"

    cmd: List[str] = [
        pdftocairo_exe,
        "-png",
        "-r", str(dpi),
    ] + extra_args + [
        pdf_path,
        os.path.join(out_dir, "page")
    ]

    print("[pdftocairo] Converting PDF to images... This may take a while.")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        # Poll the process every 3 seconds and print a message if still running
        while True:
            time.sleep(3)
            ret = proc.poll()
            if ret is not None:
                # Process finished
                break
            print("[pdftocairo] ...still working, please wait...")

        # Now check the return code
        if proc.returncode != 0:
            stdout, stderr = proc.communicate()
            print(stdout.decode('utf-8'))
            print(stderr.decode('utf-8'))
            raise subprocess.CalledProcessError(proc.returncode, cmd)
    finally:
        proc.stdout.close()
        proc.stderr.close()

    print("[pdftocairo] Done! Images are in:", out_dir)
    return

def convert_pdf_to_images(pdf_path: str, poppler_path: str, debug: bool = False) -> List[Image.Image]:
    """
    Convert all pages in a PDF to Pillow Image objects by calling pdftocairo manually.
    If debug=True, also copy each page PNG into the current working directory
    as page_1.png, page_2.png, etc. so you can inspect them later.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        call_pdftocairo(
            pdf_path,
            tmpdir,
            poppler_path,
            dpi=120,
            extra_args=["-antialias", "subpixel"]
        )

        images: List[Image.Image] = []

        for fname in sorted(os.listdir(tmpdir)):
            if fname.startswith("page-") and fname.endswith(".png"):
                src_path: str = os.path.join(tmpdir, fname)

                if debug:
                    local_debug_name: str = fname.replace("page-", "page_")
                    shutil.copy2(src_path, local_debug_name)

                with Image.open(src_path) as im:
                    images.append(im.copy())

        return images

def encode_image_to_base64(pil_image: Image.Image) -> str:
    """
    Encode a Pillow Image into base64 (PNG format) without saving to disk.
    """
    buffer: io.BytesIO = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    buffer.seek(0)
    encoded_str: str = base64.b64encode(buffer.read()).decode("utf-8")
    return encoded_str

def extract_markdown_from_response(response_text: str) -> str:
    """
    Extract the text between triple backticks. If multiple blocks, just return
    the first match. If nothing is found, return an empty string.
    """
    pattern: str = r"```(?:markdown)?\s*([\s\S]*?)\s*```"
    match: Optional[re.Match] = re.search(pattern, response_text)
    if match:
        return match.group(1).strip()
    else:
        return ""

def attempt_markdown_extraction(
    client: OpenAI,
    message_content: List[Dict[str, Any]],
    primary_model: str,
    fallback_model: str,
    max_retries: int = 3
) -> Optional[str]:
    """
    Attempt to get a markdown block from the response. 
    1) Up to max_retries with primary_model. 
    2) If that fails, up to max_retries with fallback_model.
    3) Return None if all attempts fail.

    Prints minimal lines:
      - Prints a "retry with model X..." line for each attempt after the first.
      - Prints "    success!" if found.
      - Prints "    failed!" (in red) if all fail.
    """

    # Track if we are on the first attempt for primary vs fallback
    # so we can print "retry..." lines only when it's actually a retry.
    
    def try_model(model_name: str, is_retry: bool) -> Optional[str]:
        """
        Sends the prompt to the specified model, returns extracted Markdown or None.
        If it's a retry attempt, we print '    retry with model model_name...'
        Otherwise, we keep it silent for the first attempt of each model.
        """
        if is_retry:
            print(f"    retry with model {model_name}...")
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": message_content}],
        )
        response_text = response.choices[0].message.content
        md_content = extract_markdown_from_response(response_text)
        return md_content if md_content.strip() else None

    # 1) Try primary model up to max_retries
    for attempt in range(max_retries):
        is_retry = (attempt > 0)  # attempt 0 is first, attempt 1+ is retry
        md = try_model(primary_model, is_retry=is_retry)
        if md is not None:
            if is_retry:
                print("    success!")
            return md
    
    # If primary model fails all attempts, we switch to fallback
    print(f"    retry with model {fallback_model}...")  # indicates switching to fallback
    # 2) Try fallback model up to max_retries
    for attempt in range(max_retries):
        # For fallback, every attempt is effectively a 'retry' from the user's perspective
        md = try_model(fallback_model, is_retry=True)
        if md is not None:
            print("    success!")
            return md

    # 3) If all attempts (primary + fallback) fail:
    print(f"{Fore.RED}    failed!{Style.RESET_ALL}")
    return None

def pdf_pages_to_vision_api(
    pdf_path: str,
    poppler_path: str,
    model_name: str,
    api_key: str,
    debug: bool = False
) -> None:
    """
    Main pipeline:
      1. Convert PDF to images (optionally saving them if debug=True).
      2. Encode each page in base64.
      3. Send to OpenAI for OCR + Markdown conversion, with retries/fallback.
      4. Write extracted Markdown to file (pdf_name.md).
    """
    client: OpenAI = OpenAI(api_key=api_key)

    base_name: str = os.path.splitext(pdf_path)[0]
    md_file_path: str = base_name + ".md"

    if os.path.exists(md_file_path):
        os.remove(md_file_path)

    pages: List[Image.Image] = convert_pdf_to_images(pdf_path, poppler_path, debug=debug)
    num_pages: int = len(pages)

    with open(md_file_path, "a", encoding="utf-8") as md_file:
        for i, pil_page in enumerate(pages, start=1):
            # Print a single line for each page unless we need multiple attempts
            print(f"Processing Page {i}/{num_pages}")
            
            encoded_image: str = encode_image_to_base64(pil_page)

            message_content: List[Dict[str, Any]] = [
                {
                    "type": "text",
                    "text": (
                        f"You are looking at page {i} of my PDF. "
                        "Your task is to extract **all** visible text exactly as it appears, in strict top-left to bottom-right reading order. "
                        "Do **not** reorder or relocate headings, paragraphs, or tables—wherever something appears on the page, it must remain in that exact position in your output. "
                        "Do **not** fix, skip, or summarize any text; preserve the exact wording, numbering, and spacing.\n\n"
                        "# Markdown Formatting Rules\n"
                        "1. **Headings**: Use standard Markdown syntax (#, ##, ###, etc.) for headings. If the heading appears in the middle of the page, keep it there—do not move it to the top.\n"
                        "2. **Tables**: Use standard Markdown table syntax (rows/columns with pipes and dashes). If the text in a cell spans multiple lines in the image, replace line breaks with '<br>' within the same cell.\n"
                        "3. **References**: If you see references like 'Offset address' or 'Reset value,' or any other labels/annotations, include them exactly where they appear.\n"
                        "4. **Footnotes**: The only text you may ignore is a small footnote at the bottom margin that typically contains a URL and a page number. Everything else on the page must be transcribed.\n\n"
                        "# Output Requirements\n"
                        "- Return the transcribed text as a single Markdown block enclosed in triple backticks (```markdown ... ```). "
                        "- Do **not** add extra commentary, interpretation, or summary—only the transcribed text in the correct order.\n\n"
                        "Again, keep the **exact** sequence from top-left to bottom-right, including all headings, paragraphs, tables, and references in their original positions."
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{encoded_image}",
                        "detail": "high"
                    },
                },
            ]

            # Attempt extraction with retry/fallback
            markdown_content: Optional[str] = attempt_markdown_extraction(
                client=client,
                message_content=message_content,
                primary_model=model_name,
                fallback_model=FALLBACK_MODEL,  # fallback model if the main model fails
                max_retries=3
            )

            # If still no markdown, write a failure message
            if markdown_content is None or not markdown_content.strip():
                markdown_content = (
                    f"> (FAILED after all attempts, including fallback model '{FALLBACK_MODEL}')\n\n"
                    "No valid Markdown block found."
                )

            md_file.write(f"# Page {i}\n\n{markdown_content}\n\n")

def parse_arguments() -> argparse.ArgumentParser:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(description="Convert a pdf file to markdown.")
    parser.add_argument(
        "input",
        nargs="?",
        help=str(
            "[Required] Path to the input pdf file.\n"
        ),
    )
    parser.add_argument(
        "--model",
        default=None,
        help=str(
            f"[Optional] OpenAI model name to use. Default is '{DEFAULT_MODEL}'.\n"
        ),
    )
    parser.add_argument(
        "--poppler-path",
        default=None,
        help=str(
            "[Optional] Path to the Poppler /bin directory\n"
            "           (e.g., 'C:/poppler-xx/Library/bin').\n"
            "           If not provided, the script looks into the PATH env\n"
            "           var.\n"
        ),
    )
    parser.add_argument(
        "-k",
        "--api-key",
        default=None,
        help=str(
            "[Optional] OpenAI API key. If not provided, the script looks at\n"
            "           OPENAI_API_KEY env var.\n"
        ),
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help=str(
            "[Optional] If set, saves PNG pages locally to inspect.\n"
        ),
    )
    return parser

def main() -> None:
    parser: argparse.ArgumentParser = parse_arguments()
    args: argparse.Namespace = parser.parse_args()

    if not args.input:
        _help(parser, "Error: No input file provided.")
    if not os.path.isfile(args.input):
        _help(parser, f"Error: The file '{args.input}' does not exist or is not a valid path.")

    model_name: str = args.model if args.model else DEFAULT_MODEL
    if model_name not in VALID_MODELS:
        _help(
            parser,
            f"Error: '{model_name}' is not a valid model.\n"
            f"Please use one of: {', '.join(VALID_MODELS)}"
        )

    if args.poppler_path:
        poppler_path: str = os.path.normpath(args.poppler_path)
        if not os.path.isdir(poppler_path):
            _help(parser, f"Error: The provided Poppler path '{poppler_path}' is not a valid directory.")
        if not (poppler_path.endswith("bin") or poppler_path.endswith("bin" + os.sep)):
            _help(
                parser,
                "Error: The provided Poppler path doesn't end with 'bin'. "
                "Please ensure it is the /bin folder from your Poppler installation.\n"
                "Download from https://github.com/oschwartz10612/poppler-windows/releases"
            )
    else:
        pdftocairo_exe: Optional[str] = shutil.which("pdftocairo")
        if pdftocairo_exe:
            poppler_path = os.path.dirname(pdftocairo_exe)
        else:
            _help(
                parser,
                "Error: Could not find 'pdftocairo' in your PATH.\n"
                "Please install Poppler or point this script to the correct /bin folder using '--poppler-path'.\n"
                "For Windows, see https://github.com/oschwartz10612/poppler-windows/releases"
            )

    api_key: Optional[str] = args.api_key if args.api_key else os.getenv("OPENAI_API_KEY")
    if not api_key:
        _help(
            parser,
            "Error: No OpenAI API key provided.\n"
            "Please pass it via --api-key or set the OPENAI_API_KEY environment variable."
        )

    pdf_pages_to_vision_api(
        pdf_path=args.input,
        poppler_path=poppler_path,
        model_name=model_name,
        api_key=api_key,
        debug=args.debug
    )

if __name__ == "__main__":
    main()
