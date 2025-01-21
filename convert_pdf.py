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
      3. Send to OpenAI for OCR + Markdown conversion.
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
            encoded_image: str = encode_image_to_base64(pil_page)

            message_content: List[Dict[str, Any]] = [
                {
                    "type": "text",
                    "text": (
                        f"You are looking at page {i} of my PDF. "
                        "Please convert **all** visible text into Markdown, preserving the **exact order** "
                        "in which text, headings, and tables appear from top to bottom on the page. Do **not** "
                        "skip or summarize any text, and please keep the exact wording/numbering.\n"
                        "\n"
                        "# Preserve Layout\n"
                        "If a heading appears in the middle, keep it in the middle—do not move it to the top! "
                        "Do not reorder or rearrange any tables or other elements; keep them in the same order "
                        "they appear visually.\n"
                        "If you see references like 'Offset address' or 'Reset value', include them exactly where "
                        "they appear.\n"
                        "\n"
                        "# Headings\n"
                        "Use standard Markdown conventions for headings (#, ##, ###, etc.). A heading like "
                        "'x.y.z' should retain its numbering and be preceded by '###' (one hashtag per number).\n"
                        "\n"
                        "# Tables\n"
                        "Use standard Markdown conventions for tables. Pay attention to the vertical and horizontal "
                        "table lines in the image, and reproduce them in the markdown table. Use '<br>' instead of "
                        "'\\n' when text in a table cell spans multiple lines.\n"
                        "\n"
                        "# Page Footnotes\n"
                        "The bottom of each page might show a footnote with a URL and a page number. You can ignore "
                        "this footnote in the markdown output. It is the only thing you can ignore."
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

            response = client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": message_content}],
            )

            response_text: str = response.choices[0].message.content
            markdown_content: str = extract_markdown_from_response(response_text)

            if not markdown_content.strip():
                markdown_content = f"> (No backtick block found)\n\n{response_text}"

            md_file.write(f"# Page {i}\n\n{markdown_content}\n\n")

            print(f"Finished page {i}/{num_pages}, wrote to {md_file_path}")

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
            "[Optional] OpenAI model name to use. Default is 'gpt-4o-mini'.\n"
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

    model_name: str = args.model if args.model else "gpt-4o-mini"
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
