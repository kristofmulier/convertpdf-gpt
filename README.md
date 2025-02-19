# convertpdf-gpt

Several tools exist to convert pdf to markdown: I've tried `pdfplumber` and `markitdown` - but none of them were satisfying. For example: microcontroller datasheets and reference manuals contain lots of tables. These tools fail to convert them properly. Maybe it's due to the buildup of the pdf-file? Whatever it is - I want a more robust conversion strategy.

ChatGPT does a tremendous job converting pdf page screenshots to markdown. The beauty of a screenshot is that it rules out any problems related to internal pdf buildup: a screenshot is a screenshot - period. However, it isn't feasible to feed 500 screenshots manually to ChatGPT. So I created this `convertpdf-gpt` project to do that automatically (note: using the ChatGPT API costs some money, but it's less than one dollar per 100 pages).

&nbsp;
> **Updates**
> - `2024-01-22`: Release first version
> - `2024-01-24`: Strengthen the query and use default model `gpt-4o` (`gpt-4o-mini` as fallback)<br><sup>Model `gpt-4o-mini` sometimes moves pdf elements around, corrupting the order. I mitigate the problem (update 2024-01-24) through strengthening the query and switching to model `gpt-4o` as the default for converting to markdown. Model `gpt-4o` performs better, but sometimes fails to make the conversion. If it fails, my script will retry a few times and eventually switch to fallback model `gpt-4o-mini`.</sup>

&nbsp;
## 1. Quick Start Guide

The `convertpdf-gpt` project lets you convert a pdf file to markdown in three (or four) steps:

- **STEP 1:** Run `convert_pdf.py` on the pdf-file.
- **STEP 2:** Check for missing pages and add them manually.
- **STEP 3:** Run `post_process.py`.
- **STEP 4:** [Optional] Check for missing bitfields.

&nbsp;
### 1.1 STEP 1: `convert_pdf.py` script

The first script does a rough conversion:

```sh
>python convert_pdf.py --model "gpt-4o"
                       --poppler-path "C:/poppler-24.08.0/Library/bin"
                       --api-key "sk-proj-xmj...ktgA"
                       my_file.pdf
```
This script takes your `my_file.pdf` file and uses Poppler (see [2. Prerequisites](#2-prerequisites)) to convert every page to a `.png` image. Then it feeds these images one-by-one to the OpenAI API (ChatGPT), with the request to convert the screenshot to markdown. You need an API key to get that working (see [2. Prerequisites](#2-prerequisites)).
When you run the script, you should see output like:

```cmd
C:\Users\krist\Documents\convertpdf-gpt>python convert_pdf.py --poppler-path "C:/poppler-24.08.0/Library/bin" user_manual.pdf
[pdftocairo] Converting PDF to images... This may take a while.
[pdftocairo] ...still working, please wait...
[pdftocairo] ...still working, please wait...
[pdftocairo] ...still working, please wait...
[pdftocairo] ...still working, please wait...
[pdftocairo] ...still working, please wait...
[pdftocairo] Done! Images are in: C:\Users\krist\AppData\Local\Temp\tmp8_bl38xh
Processing Page 1/858
Processing Page 2/858
Processing Page 3/858
    retry with model gpt-4o...
    success!
Processing Page 4/858
    retry with model gpt-4o...
    success!
Processing Page 5/858
Processing Page 6/858
Processing Page 7/858
Processing Page 8/858
Processing Page 9/858
Processing Page 10/858
Processing Page 11/858
Processing Page 12/858
Processing Page 13/858
Processing Page 14/858
Processing Page 15/858
...
```

The markdown output gets written to `my_file.md`. Open it to have a look *after* the script has fully completed.

&nbsp;
### 1.2 STEP 2: Check for missing pages

My first script sometimes skipped a page. That's because, once in a while, the GPT wouldn't provide a reply with a proper markdown conversion of the page. Now this problem is less severe, because my script *retries* a few times. If it fails after a few retries, it retries again with a fallback GPT model. Only after many failures, it gives up on converting that page. If you scan through the output, you can see a failed attempt like this:

```cmd
Processing Page 17/858
Processing Page 18/858
    retry with model gpt-4o...
    retry with model gpt-4o...
    retry with model gpt-4o-mini...
    retry with model gpt-4o-mini...
    retry with model gpt-4o-mini...
    failed!
Processing Page 19/858
```
The `"failed!"` statement gets printed out in red, so you should be able to see it quickly. In the markdown file, you can find then the following:

```markdown
# Page 18

> (No backtick block found)

I'm unable to access the content of the PDF or any specific page within it. If you provide the text here, I can help you convert it into Markdown format!
```

It's easy to find these missing pages in `my_file.md` (the output from the conversion script). Just search for the token `"backtick"` and you'll find them. Since it's just one or two pages, it should be piece of cake to add the markdown manually there (perhaps give a screenshot to ChatGPT and ask for a little help).

&nbsp;
### 1.3 STEP 3: `post_process.py` script

Now let the post processing script take care of your markdown file:

```sh
>python post_process.py my_file.md
                        -o my_file_processed.md
```

The result `my_file_processed.md` should be a high-quality conversion of the original pdf file!

&nbsp;
### 1.4 STEP 4: [Optional] Check for missing bitfields

It can happen that the markdown conversion misses a bitfield here and there. With the `gpt-4o-mini` model this is likely to happen. The `gpt-4o` model does a decent job, though. I just converted a 520 user manual (reference manual) today, and only had one missing bitfield in the entire markdown file. The conversion missed a `Reserved` bitfield in the `SMC_STSINT2` register.

To check for missing bitfields, I query ChatGPT manually. In the pro-version of ChatGPT, the context window is pretty large. I paste around 3000 lines of the markdown file and ask the following:

```
[ChatGPT Query]
I've written a script that converts a pdf file of an MCU reference manual into markdown.
Unfortunately, it seems that not all register tables are complete. Some have missing
bitfields. Please check if all register tables in this markdown file are complete. Tell
me which register tables have missing bitfields. Most registers are 32 bits wide, some
are 16 bits wide. Maybe some are 8 bits, I'm not sure.

Here is the first markdown snippet to check for register bitfield completeness:
[...]
```

I repeated this query until all 17.000 lines of my markdown file were checked. Only one
bitfield omission was found.


---

&nbsp;
## 2. Prerequisites

To use the `convert_pdf.py` and `post_process.py` scripts, you need to:
- Install Poppler
- Get your OpenAI key

&nbsp;
### 2.1 Poppler
Install Poppler:
https://github.com/oschwartz10612/poppler-windows/releases

I unzipped it at: `C:/poppler-24.08.0`. No installation was required - just unzip and go. The Poppler executables are now at:
`C:/poppler-24.08.0/Library/bin`.

Now you have two choices:

- **CHOICE 1:** Pass the Poppler path to the conversion script with the `--poppler-path` argument. For example:
   ```
   --poppler-path "C:/poppler-24.08.0/Library/bin"
   ```

- **CHOICE 2:** Add the path to your `PATH` environment variable. The script should find it there.

&nbsp;
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

- **CHOICE 1:** Pass the key to the conversion script with the `--api-key` argument. For example:
   ```
   --api-key "sk-proj-xmj...ktgA"
   ```


- **CHOICE 2:** Create a new `OPENAI_API_KEY` environment variable and store your key in there.

---

&nbsp;
## 3. Costs

Here are a few conversions I made so far:

| pages    | model         | cost  |
|----------|---------------|-------|
| 100      | `gpt-4o-mini` | $1.00 |
| 520      | `gpt-4o-mini` | $3.08 |
| 520      | `gpt-4o`      | $4.00 |

Model `gpt-4o` performs better than `gpt-4o-mini` at a marginally higher cost. The `gpt-4o` model is less likely to rearrange (corrupt) the order of the elements on the pdf page.

---

&nbsp;
## 4. Remarks

I only tested this script on Windows 11 so far. It should work on Linux too. Contact me if there's an issue.
