# convertpdf-gpt

Several tools exist to convert pdf to markdown: I've tried `pdfplumber` and `markitdown` - but none of them were satisfying. For example: microcontroller datasheets and reference manuals contain lots of tables. These tools fail to convert them properly. Maybe it's due to the buildup of the pdf-file? Whatever it is - I want a more robust conversion strategy.

ChatGPT does a tremendous job converting pdf page screenshots to markdown. The beauty of a screenshot is that it rules out any problems related to internal pdf buildup: a screenshot is a screenshot - period. However, it isn't feasible to feed 500 screenshots manually to ChatGPT. So I created this `convertpdf-gpt` project to do that automatically (note: using the ChatGPT API costs some money, but it's less than one dollar per 100 pages).

&nbsp;
## 1. Quick Start Guide

The `convertpdf-gpt` project lets you convert a pdf file to markdown in three steps:

- **STEP 1:** Run `convert_pdf.py` on the pdf-file.
- **STEP 2:** Check for missing pages and add them manually.
- **STEP 3:** Run `post_process.py`.

### 1.1 STEP 1: `convert_pdf.py` script

The first script does a rough conversion:

```sh
>python convert_pdf.py --model "gpt-4o-mini"
                       --poppler-path "C:/poppler-24.08.0/Library/bin"
                       --api-key "sk-proj-xmj...ktgA"
                       my_file.pdf
```
This script takes your `my_file.pdf` file and uses Poppler (see [2. Prerequisites](#2-prerequisites)) to convert every page to a `.png` image. Then it feeds these images one-by-one to the OpenAI API (ChatGPT), with the request to convert the screenshot to markdown. You need an API key to get that working (see [2. Prerequisites](#2-prerequisites)).
When you run the script, you should see output like:

```
C:\Users\krist\Documents\convertpdf-gpt>python convert_pdf.py --poppler-path "C:/poppler-24.08.0/Library/bin" user_manual.pdf
[pdftocairo] Converting PDF to images... This may take a while.
[pdftocairo] ...still working, please wait...
[pdftocairo] ...still working, please wait...
[pdftocairo] ...still working, please wait...
[pdftocairo] ...still working, please wait...
[pdftocairo] ...still working, please wait...
[pdftocairo] Done! Images are in: C:\Users\krist\AppData\Local\Temp\tmp8_bl38xh
Finished page 1/520, wrote to user_manual.md
Finished page 2/520, wrote to user_manual.md
Finished page 3/520, wrote to user_manual.md
...
```

The markdown output gets written to `my_file.md`. Open it to have a look *after* the script has fully completed.

### 1.2 STEP 2: Check for missing pages

Upon converting a 520 page pdf-file, I miss two pages. Here is one of them:

```markdown
# Page 113

> (No backtick block found)

I'm unable to access the content of the PDF or any specific page within it. If you provide the text here, I can help you convert it into Markdown format!
```

It's easy to find these missing pages in `my_file.md` (the output from the conversion script). Just search for the token `"backtick"` and you'll find them. Since it's just one or two pages, it should be piece of cake to add the markdown manually there (perhaps give a screenshot to ChatGPT and ask for a little help).


### 1.3 STEP 3: `post_process.py` script

Now let the post processing script take care of your markdown file:

```sh
>python post_process.py my_file.md
                        -o my_file_processed.md
```

The result `my_file_processed.md` should be a high-quality conversion of the original pdf file!

---

&nbsp;
## 2. Prerequisites

To use the `convert_pdf.py` and `post_process.py` scripts, you need to install a few things:
- Install Poppler
- Get your OpenAI key

### 2.1 Poppler
Install Poppler:
https://github.com/oschwartz10612/poppler-windows/releases

I unzipped it at: `C:/poppler-24.08.0`. No installation was required - just unzip and go. The Poppler executables are now at:
`C:/poppler-24.08.0/Library/bin`.

Now you have two choices:

1. Pass the Poppler path to the conversion script with the `--poppler-path` argument. For example:
   ```
   --poppler-path "C:/poppler-24.08.0/Library/bin"
   ```

2. Add the path to your `PATH` environment variable. The script should find it there.

### 2.2 OpenAI Key
You obviously need an OpenAI (ChatGPT) account. Then go to:
https://platform.openai.com/settings/organization/api-keys
Make your OpenAI key there:
![image](https://github.com/user-attachments/assets/bdd28897-5793-4992-afb1-7ba49421a80c)

When you make the new key, you'll be given the entire key in a popup. Store it somehwere safe!

Now you need to add money to your key/account:
![image](https://github.com/user-attachments/assets/ec716931-a8d8-4314-b06a-f79ca148005b)

Wait about ten minutes after adding credit to your key. It doesn't work in the first ten minutes!

Now you can use the key with the `convert_pdf.py` script. You have two options:

1. Pass the key to the conversion script with the `--api-key` argument. For example:
   ```
   --api-key "sk-proj-xmj...ktgA"
   ```

2. Create a new `OPENAI_API_KEY` environment variable and store your key in there.

---

&nbsp;
## 3. Costs

Running the `convert_pdf.py` on a 100-page pdf costs me around $1.00. That's with the `--model "gpt-4o-mini"`. I didn't try other models yet.

On another occasion, I converted a 520-page pdf document, which cost me precisely $3.08.

---

&nbsp;
## 4. Remarks

I only tested this script on Windows 11 so far. It should work on Linux too. Contact me if there's an issue.
