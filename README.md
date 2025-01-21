# convertpdf-gpt

## 1. Quick Use Guide

Convert a pdf file automatically to markdown. This `convertpdf-gpt` project provides two python scripts to get it done. The first one does a rough conversion:

```sh
>python convert_pdf.py --model "gpt-4o-mini"
                       --poppler-path "C:/poppler-24.08.0/Library/bin"
                       --api-key "sk-proj-xmj...ktgA"
                       my_file.pdf
```
This script takes your `my_file.pdf` file and uses Poppler (see https://github.com/oschwartz10612/poppler-windows/releases/tag/v24.08.0-0) to convert every page to a `.png` image. Then it feeds these images one-by-one to the OpenAI API (ChatGPT), with the request to convert the screenshot to markdown. The markdown for all pages is then written to `my_file.md`.

The second script does some post processing on `my_file.md`:

```sh
>python post_process.py my_file.md
                        -o my_file_processed.md
```

The result `my_file_processed.md` should be a high-quality conversion of your original pdf file.

---

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

## 3. Remarks

I only tested this script on Windows 11 so far. It should work on Linux too. Contact me if there's an issue.
