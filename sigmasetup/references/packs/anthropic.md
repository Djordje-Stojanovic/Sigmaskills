# Anthropic pack setup

Source: [anthropics/skills](https://github.com/anthropics/skills). Only these skills name tools; the rest need nothing. Install a tool only for the skills the owner uses.

| Skill | Needs |
|---|---|
| `docx` | Node `docx`, `pandoc`, `pdftoppm`, LibreOffice |
| `pdf` | Python `pypdf`, `pdfplumber`, `reportlab`, `pytesseract`, `pdf2image`, `pypdfium2`; `qpdf`, `pdftotext`, `pdftk` |
| `pptx` | Node `pptxgenjs`, `react-icons`, `react`, `react-dom`, `sharp`; `markitdown`, LibreOffice, Python |
| `xlsx` | Python `openpyxl`, `pandas`, `markitdown`; LibreOffice for `scripts/recalc.py` |
| `webapp-testing` | Python Playwright with headless Chromium |
| `mcp-builder` | Python `anthropic>=0.39.0`, `mcp>=1.1.0`; `ANTHROPIC_API_KEY` for evaluations |
| `claude-api` | `pip install anthropic`; `ANTHROPIC_API_KEY` or an `ant auth login` profile |
| `slack-gif-creator` | Python `pillow`, `imageio`, `imageio-ffmpeg`, `numpy` |
| `web-artifacts-builder` | Node 18+; `bash scripts/init-artifact.sh <name>` |

Keys go in the environment, never in the repo.
