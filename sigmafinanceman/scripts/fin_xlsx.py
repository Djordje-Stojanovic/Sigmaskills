"""Excel workbooks with live formulas (openpyxl), banker colours and the Ledger look.

Rules (the banker convention and anthropics/financial-services `xlsx-author`/`audit-xls`):
- Blue font = a typed input (with a cell comment that names its source). Black = a formula. Green = a pure link to another sheet.
- No typed number in a calculation cell: change an input and the whole model moves.
- Sensitivity grids are full formulas per cell, odd-sized, the base case in the centre (fill #BDD7EE, bold).
- A Checks sheet lists the tie-outs as TRUE/FALSE; `finman.py audit` recalculates the file in LibreOffice and reads them.
Money in $ millions unless a header says otherwise.
"""
from copy import copy

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter as L

import fin_models as F
import fin_svg as S

C = {k: "FF" + v[1:] for k, v in S.TOK.items()}
MONEY = '#,##0_);(#,##0);"-"_)'
FMT = {"money": MONEY, "pct": "0.0%", "x": '0.0"x"', "ps": '$#,##0.00_);($#,##0.00);"-"_)', "num1": "0.0", "num2": "0.00",
       "int": "0", "text": "@", "date": "@"}
THIN, DOUBLE = Side(style="thin", color=C["ink"]), Side(style="double", color=C["ink"])
FONT = "Calibri"


class Book:
    def __init__(self):
        self.wb = Workbook()
        self.wb.remove(self.wb.active)
        self.checks = []

    def sheet(self, name, widths=(34, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14, 14)):
        ws = self.wb.create_sheet(name)
        ws.sheet_view.showGridLines = False
        ws.page_setup.orientation = "landscape"          # prints one page wide
        ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        for i, w in enumerate(widths, start=1):
            ws.column_dimensions[L(i)].width = w
        return ws

    def save(self, path):
        if self.checks:
            ws = self.sheet("Checks", (52, 16, 60))
            title(ws, 1, "Checks: every line must say TRUE")
            header(ws, 3, ["Check", "Result", "What it ties"])
            for i, (name, formula, what) in enumerate(self.checks, start=4):
                put(ws, f"A{i}", name)
                put(ws, f"B{i}", formula, "calc")
                put(ws, f"C{i}", what)
            put(ws, f"A{len(self.checks) + 5}", "All checks", bold=True)
            put(ws, f"B{len(self.checks) + 5}", f"=AND(B4:B{len(self.checks) + 3})", "calc", bold=True)
        self.wb.save(path)
        return path


def put(ws, ref, v, kind="label", fmt=None, bold=False, comment=None, fill=None, align=None):
    c = ws[ref]
    c.value = v
    color = {"input": C["input"], "link": C["link"], "calc": "FF000000", "label": C["ink"], "muted": C["muted"]}[kind]
    c.font = Font(name=FONT, size=11, bold=bold, color=color)
    if fmt:
        c.number_format = FMT.get(fmt, fmt)
    if comment:
        c.comment = Comment(comment[:900], "sigmafinanceman")
    if fill:
        c.fill = PatternFill("solid", fgColor=C.get(fill, fill))
    if align:
        c.alignment = Alignment(horizontal=align)
    return c


def title(ws, row, text, sub=None):
    put(ws, f"A{row}", text, bold=True).font = Font(name=FONT, size=16, bold=True, color=C["navy"])
    if sub:
        put(ws, f"A{row + 1}", sub, "muted")


TEXT_HEADS = {"Source", "What it ties", "Why it matters", "Bucket"}   # text columns: the header aligns left like its cells


def header(ws, row, names, start=1):
    for i, n in enumerate(names):
        c = ws.cell(row=row, column=start + i, value=n)
        c.font = Font(name=FONT, size=11, bold=True, color="FFFFFFFF")
        c.fill = PatternFill("solid", fgColor=C["navy"])
        c.alignment = Alignment(horizontal="left" if i == 0 or n in TEXT_HEADS else "right")


def total(ws, row, c1, c2, double=False):
    for col in range(c1, c2 + 1):
        cell = ws.cell(row=row, column=col)
        ft = copy(cell.font)
        ft.b = True
        cell.font = ft
        cell.border = Border(top=THIN, bottom=DOUBLE if double else None)


def inputs_sheet(book, a, name="Inputs"):
    """Every assumption as a blue input with its source; returns {key: absolute ref}."""
    ws = book.sheet(name, (24, 16, 90))
    title(ws, 1, "Inputs", "Blue = typed input. Change a value here and every sheet moves.")
    header(ws, 3, ["Input", "Value", "Source"])
    refs = {}
    pcts = {"growth_y1", "ebit_margin", "tax_rate", "da_pct", "capex_pct_y0", "nwc_pct", "rf", "erp", "kd", "terminal_g", "premium", "rate",
            "fees", "sweep", "cogs_pct", "opex_pct", "interest_rate", "payout"}
    for i, (k, v) in enumerate(a.items(), start=4):
        fmt = "pct" if k in pcts else "x" if k in ("entry_multiple", "exit_multiple", "leverage") else "num2" if k == "beta" else \
            "ps" if k == "price" else "num1" if k in ("dso", "dio", "dpo") else "int" if k == "years" else "money"
        put(ws, f"A{i}", F.LABELS.get(k, k))
        put(ws, f"B{i}", v["value"], "input", fmt, comment="Source: " + v["source"])
        put(ws, f"C{i}", v["source"], "muted")
        refs[k] = f"{name}!$B${i}"
    ws.freeze_panes = "B4"
    return refs


def links(ws, refs, keys, row, label_col="A", val_col="B"):
    """A green link block (=Inputs!B5); returns {key: local absolute ref}."""
    out = {}
    for i, k in enumerate(keys):
        r = row + i
        put(ws, f"{label_col}{r}", F.LABELS.get(k, k))
        put(ws, f"{val_col}{r}", "=" + refs[k], "link", "pct" if "pct" in k or k in ("growth_y1", "ebit_margin", "tax_rate", "terminal_g", "rf", "erp", "kd",
                                                                                     "rate", "fees", "sweep", "premium", "payout", "cogs_pct", "opex_pct", "interest_rate")
            else "x" if k in ("entry_multiple", "exit_multiple", "leverage") else "num2" if k == "beta" else "ps" if k == "price"
            else "num1" if k in ("dso", "dio", "dpo") else "int" if k == "years" else "money")
        out[k] = f"${val_col}${r}"
    return out


def history_sheet(book, f, name="Historicals"):
    """The filed numbers, one blue input per fiscal year, each with the us-gaap tag and the SEC URL. Returns {concept: row}, cols."""
    ws = book.sheet(name, (30,) + (15,) * len(f["fiscal_year_ends"]))
    ends, hist, _ = F.view(f)
    title(ws, 1, f"{f['name']} ({f['ticker']}): filed numbers ($m)", f"SEC EDGAR company facts, {f['source']}")
    header(ws, 3, ["Line"] + [e for e in ends])
    rows = {}
    for i, c in enumerate(f["annual"], start=4):
        put(ws, f"A{i}", F.FILED.get(c, c))
        for j, v in enumerate(hist(c)):
            if v is not None:
                put(ws, f"{L(2 + j)}{i}", v, "input", "ps" if c == "eps" else "money",
                    comment=f"Source: SEC 10-K, us-gaap:{f['tags'].get(c)}, period end {ends[j]}")
        rows[c] = i
    ws.freeze_panes = "B4"
    return rows, [L(2 + j) for j in range(len(ends))]


# ---------- DCF ----------

def dcf_book(f, a, path):
    b = Book()
    refs = inputs_sheet(b, a)
    history_sheet(b, f)
    ws = b.sheet("DCF", (34, 15, 15, 15, 15, 15, 15, 4, 15))
    title(ws, 1, f"{f['name']} ({f['ticker']}) DCF", "Green = link to Inputs. Black = formula. $ millions.")
    keys = ["revenue_base", "growth_y1", "terminal_g", "ebit_margin", "tax_rate", "da_pct", "capex_pct_y0", "nwc_pct", "rf", "beta", "erp", "kd",
            "debt", "cash", "shares", "price", "years"]
    header(ws, 3, ["Assumption", "Value"])
    k = links(ws, refs, keys, 4)
    r = 4 + len(keys) + 1   # WACC block
    header(ws, r, ["Cost of capital", "Value"])
    put(ws, f"A{r + 1}", "Cost of equity (rf + beta x ERP)"); put(ws, f"B{r + 1}", f"={k['rf']}+{k['beta']}*{k['erp']}", "calc", "pct")
    put(ws, f"A{r + 2}", "Market value of equity"); put(ws, f"B{r + 2}", f"={k['price']}*{k['shares']}", "calc", "money")
    put(ws, f"A{r + 3}", "After-tax cost of debt"); put(ws, f"B{r + 3}", f"={k['kd']}*(1-{k['tax_rate']})", "calc", "pct")
    put(ws, f"A{r + 4}", "WACC", bold=True)
    put(ws, f"B{r + 4}", f"=(B{r + 2}*B{r + 1}+{k['debt']}*B{r + 3})/(B{r + 2}+{k['debt']})", "calc", "pct", bold=True)
    total(ws, r + 4, 1, 2)
    wacc = f"$B${r + 4}"
    p = r + 6   # projection
    yrs = ["C", "D", "E", "F", "G"]
    header(ws, p, ["Projection", "Year 0", "Y1", "Y2", "Y3", "Y4", "Y5"])
    lines = ["Year", "Revenue growth", "Revenue", "EBIT", "NOPAT", "D&A", "Capex % of revenue", "Capex", "Change in working capital",
             "Unlevered free cash flow", "Discount period", "Discount factor", "PV of free cash flow"]
    R = {name: p + 1 + i for i, name in enumerate(lines)}
    for name, row in R.items():
        put(ws, f"A{row}", name)
    put(ws, f"B{R['Revenue']}", f"={k['revenue_base']}", "calc", "money")
    for i, col in enumerate(yrs, start=1):
        prev = "B" if i == 1 else yrs[i - 2]
        y = f"{col}${R['Year']}"
        put(ws, f"{col}{R['Year']}", i, "input", "int")
        put(ws, f"{col}{R['Revenue growth']}", f"={k['growth_y1']}-({k['growth_y1']}-{k['terminal_g']})*({y}-1)/{k['years']}", "calc", "pct")
        put(ws, f"{col}{R['Revenue']}", f"={prev}{R['Revenue']}*(1+{col}{R['Revenue growth']})", "calc", "money")
        put(ws, f"{col}{R['EBIT']}", f"={col}{R['Revenue']}*{k['ebit_margin']}", "calc", "money")
        put(ws, f"{col}{R['NOPAT']}", f"={col}{R['EBIT']}*(1-{k['tax_rate']})", "calc", "money")
        put(ws, f"{col}{R['D&A']}", f"={col}{R['Revenue']}*{k['da_pct']}", "calc", "money")
        put(ws, f"{col}{R['Capex % of revenue']}", f"={k['capex_pct_y0']}+({k['da_pct']}-{k['capex_pct_y0']})*{y}/{k['years']}", "calc", "pct")
        put(ws, f"{col}{R['Capex']}", f"={col}{R['Revenue']}*{col}{R['Capex % of revenue']}", "calc", "money")
        put(ws, f"{col}{R['Change in working capital']}", f"={k['nwc_pct']}*({col}{R['Revenue']}-{prev}{R['Revenue']})", "calc", "money")
        put(ws, f"{col}{R['Unlevered free cash flow']}",
            f"={col}{R['NOPAT']}+{col}{R['D&A']}-{col}{R['Capex']}-{col}{R['Change in working capital']}", "calc", "money")
        put(ws, f"{col}{R['Discount period']}", f"={y}-0.5", "calc", "num1")
        put(ws, f"{col}{R['Discount factor']}", f"=1/(1+{wacc})^{col}{R['Discount period']}", "calc", "num2")
        put(ws, f"{col}{R['PV of free cash flow']}", f"={col}{R['Unlevered free cash flow']}*{col}{R['Discount factor']}", "calc", "money")
    total(ws, R["Unlevered free cash flow"], 1, 7)
    v = R["PV of free cash flow"] + 2
    header(ws, v, ["Valuation", "Value"])
    fcf, per = R["Unlevered free cash flow"], R["Discount period"]
    val = [("Sum of PV of free cash flows", f"=SUM(C{R['PV of free cash flow']}:G{R['PV of free cash flow']})", "money"),
           ("Terminal value (growth method)", f"=G{fcf}*(1+{k['terminal_g']})/({wacc}-{k['terminal_g']})", "money"),
           ("PV of terminal value", f"=B{v + 2}/(1+{wacc})^G{per}", "money"),
           ("Enterprise value", f"=B{v + 1}+B{v + 3}", "money"),
           ("Less debt", f"=-{k['debt']}", "money"),
           ("Plus cash and investments", f"={k['cash']}", "money"),
           ("Equity value", f"=B{v + 4}+B{v + 5}+B{v + 6}", "money"),
           ("Diluted shares (m)", f"={k['shares']}", "money"),
           ("Value per share", f"=B{v + 7}/B{v + 8}", "ps"),
           ("Upside vs price", f"=B{v + 9}/{k['price']}-1", "pct"),
           ("Terminal value share of EV", f"=B{v + 3}/B{v + 4}", "pct")]
    for i, (lab, fm, fmt) in enumerate(val, start=1):
        put(ws, f"A{v + i}", lab)
        put(ws, f"B{v + i}", fm, "calc", fmt)
    total(ws, v + 4, 1, 2)
    total(ws, v + 7, 1, 2)
    total(ws, v + 9, 1, 2, double=True)
    vps = f"$B${v + 9}"
    s = v + len(val) + 2   # sensitivity: WACC rows x terminal growth columns, every cell a full DCF
    put(ws, f"A{s}", "Value per share: WACC (rows) by terminal growth (columns)", bold=True)
    header(ws, s + 1, ["WACC \\ g", "", "", "", "", ""])
    steps = [-0.01, -0.005, 0, 0.005, 0.01]
    for j, d in enumerate(steps):
        put(ws, f"{L(2 + j)}{s + 1}", f"={k['terminal_g']}+({d})", "calc", "pct", bold=True, fill="navy").font = Font(name=FONT, bold=True, color="FFFFFFFF")
    for i, d in enumerate(steps):
        row = s + 2 + i
        put(ws, f"A{row}", f"={wacc}+({d})", "calc", "pct", bold=True)
        for j in range(5):
            col = L(2 + j)
            fm = (f"=(SUMPRODUCT($C${fcf}:$G${fcf}/(1+$A{row})^$C${per}:$G${per})+$G${fcf}*(1+{col}${s + 1})/($A{row}-{col}${s + 1})"
                  f"/(1+$A{row})^$G${per}-{k['debt']}+{k['cash']})/{k['shares']}")
            put(ws, f"{col}{row}", fm, "calc", "ps", bold=(i == 2 and j == 2), fill="center" if (i == 2 and j == 2) else None)
    ws.freeze_panes = "B4"
    b.checks += [("Sensitivity centre equals the value per share", f"=ABS(DCF!D{s + 4}-DCF!{vps})<0.01", "the grid is wired to the model"),
                 ("WACC above terminal growth", f"=DCF!{wacc}>DCF!{k['terminal_g']}", "the growth formula is finite"),
                 ("Free cash flow formula ties", f"=ABS(DCF!G{fcf}-(DCF!G{R['NOPAT']}+DCF!G{R['D&A']}-DCF!G{R['Capex']}-DCF!G{R['Change in working capital']}))<0.01",
                  "NOPAT + D&A - capex - change in working capital")]
    return b.save(path), {"value_per_share": f"DCF!B{v + 9}", "ev": f"DCF!B{v + 4}", "center": f"DCF!D{s + 4}"}


# ---------- LBO ----------

def lbo_book(f, a, path):
    b = Book()
    refs = inputs_sheet(b, a)
    ws = b.sheet("LBO", (34, 15, 15, 15, 15, 15, 15, 4, 15))
    title(ws, 1, f"{f['name']} ({f['ticker']}) LBO", "Green = link to Inputs. Black = formula. $ millions.")
    keys = ["ebitda_ltm", "entry_multiple", "exit_multiple", "leverage", "rate", "fees", "sweep", "revenue_base", "growth_y1", "terminal_g",
            "ebit_margin", "tax_rate", "da_pct", "capex_pct_y0", "nwc_pct", "years"]
    header(ws, 3, ["Assumption", "Value"])
    k = links(ws, refs, keys, 4)
    su = 4 + len(keys) + 1
    header(ws, su, ["Sources and uses", "Value"])
    rows = [("Entry enterprise value", f"={k['entry_multiple']}*{k['ebitda_ltm']}"), ("Fees", f"=B{su + 1}*{k['fees']}"),
            ("Total uses", f"=B{su + 1}+B{su + 2}"), ("Senior debt", f"={k['leverage']}*{k['ebitda_ltm']}"),
            ("Sponsor equity", f"=B{su + 3}-B{su + 4}"), ("Total sources", f"=B{su + 4}+B{su + 5}")]
    for i, (lab, fm) in enumerate(rows, start=1):
        put(ws, f"A{su + i}", lab)
        put(ws, f"B{su + i}", fm, "calc", "money")
    total(ws, su + 3, 1, 2)
    total(ws, su + 6, 1, 2, double=True)
    eq0, debt0 = f"$B${su + 5}", f"$B${su + 4}"
    p = su + 8
    yrs = ["C", "D", "E", "F", "G"]
    header(ws, p, ["Projection", "Entry", "Y1", "Y2", "Y3", "Y4", "Y5"])
    lines = ["Year", "Revenue growth", "Revenue", "EBIT", "D&A", "EBITDA", "Capex", "Change in working capital", "Interest (on opening debt)",
             "Tax", "Free cash flow", "Debt repaid", "Debt at year end", "Cash at year end"]
    R = {n: p + 1 + i for i, n in enumerate(lines)}
    for n, row in R.items():
        put(ws, f"A{row}", n)
    put(ws, f"B{R['Revenue']}", f"={k['revenue_base']}", "calc", "money")
    put(ws, f"B{R['Debt at year end']}", f"={debt0}", "calc", "money")
    put(ws, f"B{R['Cash at year end']}", 0, "input", "money", comment="Source: the deal starts with no cash on the balance sheet")
    for i, col in enumerate(yrs, start=1):
        prev = "B" if i == 1 else yrs[i - 2]
        y = f"{col}${R['Year']}"
        put(ws, f"{col}{R['Year']}", i, "input", "int")
        put(ws, f"{col}{R['Revenue growth']}", f"={k['growth_y1']}-({k['growth_y1']}-{k['terminal_g']})*({y}-1)/{k['years']}", "calc", "pct")
        put(ws, f"{col}{R['Revenue']}", f"={prev}{R['Revenue']}*(1+{col}{R['Revenue growth']})", "calc", "money")
        put(ws, f"{col}{R['EBIT']}", f"={col}{R['Revenue']}*{k['ebit_margin']}", "calc", "money")
        put(ws, f"{col}{R['D&A']}", f"={col}{R['Revenue']}*{k['da_pct']}", "calc", "money")
        put(ws, f"{col}{R['EBITDA']}", f"={col}{R['EBIT']}+{col}{R['D&A']}", "calc", "money")
        put(ws, f"{col}{R['Capex']}", f"={col}{R['Revenue']}*({k['capex_pct_y0']}+({k['da_pct']}-{k['capex_pct_y0']})*{y}/{k['years']})", "calc", "money")
        put(ws, f"{col}{R['Change in working capital']}", f"={k['nwc_pct']}*({col}{R['Revenue']}-{prev}{R['Revenue']})", "calc", "money")
        put(ws, f"{col}{R['Interest (on opening debt)']}", f"={prev}{R['Debt at year end']}*{k['rate']}", "calc", "money")
        put(ws, f"{col}{R['Tax']}", f"=MAX(0,{col}{R['EBIT']}-{col}{R['Interest (on opening debt)']})*{k['tax_rate']}", "calc", "money")
        put(ws, f"{col}{R['Free cash flow']}", f"={col}{R['EBITDA']}-{col}{R['Capex']}-{col}{R['Change in working capital']}"
                                               f"-{col}{R['Interest (on opening debt)']}-{col}{R['Tax']}", "calc", "money")
        put(ws, f"{col}{R['Debt repaid']}", f"=MIN({prev}{R['Debt at year end']},MAX(0,{col}{R['Free cash flow']})*{k['sweep']})", "calc", "money")
        put(ws, f"{col}{R['Debt at year end']}", f"={prev}{R['Debt at year end']}-{col}{R['Debt repaid']}", "calc", "money")
        put(ws, f"{col}{R['Cash at year end']}", f"={prev}{R['Cash at year end']}+{col}{R['Free cash flow']}-{col}{R['Debt repaid']}", "calc", "money")
    total(ws, R["Free cash flow"], 1, 7)
    rr = R["Cash at year end"] + 2
    header(ws, rr, ["Returns", "Value"])
    ret = [("Exit EV (exit multiple x Y5 EBITDA)", f"={k['exit_multiple']}*G{R['EBITDA']}", "money"),
           ("Less debt at exit", f"=-G{R['Debt at year end']}", "money"), ("Plus cash at exit", f"=G{R['Cash at year end']}", "money"),
           ("Exit equity", f"=B{rr + 1}+B{rr + 2}+B{rr + 3}", "money"), ("Sponsor equity in", f"={eq0}", "money"),
           ("Money multiple (MOIC)", f"=B{rr + 4}/B{rr + 5}", "x"), ("IRR", f"=B{rr + 6}^(1/{k['years']})-1", "pct")]
    for i, (lab, fm, fmt) in enumerate(ret, start=1):
        put(ws, f"A{rr + i}", lab)
        put(ws, f"B{rr + i}", fm, "calc", fmt)
    total(ws, rr + 4, 1, 2)
    total(ws, rr + 7, 1, 2, double=True)
    s = rr + len(ret) + 2
    put(ws, f"A{s}", "IRR: entry multiple (rows) by exit multiple (columns)", bold=True)
    header(ws, s + 1, ["Entry \\ exit", "", "", "", "", ""])
    steps = [-2, -1, 0, 1, 2]
    for j, d in enumerate(steps):
        put(ws, f"{L(2 + j)}{s + 1}", f"={k['exit_multiple']}+({d})", "calc", "x", bold=True, fill="navy").font = Font(name=FONT, bold=True, color="FFFFFFFF")
    for i, d in enumerate(steps):
        row = s + 2 + i
        put(ws, f"A{row}", f"={k['entry_multiple']}+({d})", "calc", "x", bold=True)
        for j in range(5):
            col = L(2 + j)
            fm = (f"=(({col}${s + 1}*$G${R['EBITDA']}-$G${R['Debt at year end']}+$G${R['Cash at year end']})"
                  f"/($A{row}*{k['ebitda_ltm']}*(1+{k['fees']})-{debt0}))^(1/{k['years']})-1")
            put(ws, f"{col}{row}", fm, "calc", "pct", bold=(i == 2 and j == 2), fill="center" if (i == 2 and j == 2) else None)
    ws.freeze_panes = "B4"
    b.checks += [("Sensitivity centre equals the IRR", f"=ABS(LBO!D{s + 4}-LBO!B{rr + 7})<0.0001", "the grid is wired to the model"),
                 ("Sources equal uses", f"=ABS(LBO!B{su + 6}-LBO!B{su + 3})<0.01", "sources and uses balance"),
                 ("Debt never negative", f"=MIN(LBO!C{R['Debt at year end']}:G{R['Debt at year end']})>=0", "the sweep stops at zero")]
    return b.save(path), {"irr": f"LBO!B{rr + 7}", "moic": f"LBO!B{rr + 6}", "center": f"LBO!D{s + 4}"}


# ---------- comps ----------

def comps_book(c, path):
    b = Book()
    ws = b.sheet("Comps", (12, 12, 12, 12, 12, 14, 14, 14, 14, 11, 11, 11, 11, 11, 11))
    t = c["target"]
    title(ws, 1, f"{t['name']} ({t['ticker']}) trading comparables", "Blue = filed or market input. Black = formula. $ millions, LTM.")
    cols = ["Ticker", "Price", "Shares (m)", "Debt", "Cash", "LTM revenue", "LTM EBITDA", "LTM EBIT", "LTM net income", "Revenue growth",
            "Market cap", "EV", "EV/Revenue", "EV/EBITDA", "EV/EBIT", "P/E", "EBIT margin"]
    for i, w in enumerate((10, 11, 11, 11, 11, 13, 13, 13, 13, 10, 13, 13, 11, 11, 11, 11, 11), start=1):
        ws.column_dimensions[L(i)].width = w
    header(ws, 3, cols)
    first = 4
    allrows = c["peers"] + [t]

    def company_row(r, row, bold=False):
        put(ws, f"A{row}", r["ticker"], bold=bold)
        for col, key, fmt in (("B", "price", "ps"), ("C", "shares", "money"), ("D", "debt", "money"), ("E", "cash", "money"),
                              ("F", "revenue", "money"), ("G", "ebitda", "money"), ("H", "ebit", "money"), ("I", "net_income", "money"),
                              ("J", "growth", "pct")):
            put(ws, f"{col}{row}", r[key], "input", fmt, comment=f"Source: SEC company facts LTM to {r['ltm_asof']}; Yahoo price" if col in "BF" else None)
        put(ws, f"K{row}", f"=B{row}*C{row}", "calc", "money")
        put(ws, f"L{row}", f"=K{row}+D{row}-E{row}", "calc", "money")
        put(ws, f"M{row}", f"=IFERROR(L{row}/F{row},\"n/a\")", "calc", "x")
        put(ws, f"N{row}", f"=IFERROR(IF(G{row}>0,L{row}/G{row},\"n/a\"),\"n/a\")", "calc", "x")
        put(ws, f"O{row}", f"=IFERROR(IF(H{row}>0,L{row}/H{row},\"n/a\"),\"n/a\")", "calc", "x")
        put(ws, f"P{row}", f"=IFERROR(IF(I{row}>0,K{row}/I{row},\"n/a\"),\"n/a\")", "calc", "x")
        put(ws, f"Q{row}", f"=IFERROR(H{row}/F{row},\"n/a\")", "calc", "pct")
    for i, r in enumerate(c["peers"]):
        company_row(r, first + i)
    last = first + len(c["peers"]) - 1
    st = last + 1
    for i, (lab, fn) in enumerate((("Maximum", "MAX({r})"), ("75th percentile", "_xlfn.QUARTILE.INC({r},3)"), ("Median", "MEDIAN({r})"),
                                   ("25th percentile", "_xlfn.QUARTILE.INC({r},1)"), ("Minimum", "MIN({r})"))):
        row = st + i
        put(ws, f"A{row}", lab, bold=True)
        for col in "MNOP":
            put(ws, f"{col}{row}", "=" + fn.format(r=f"{col}{first}:{col}{last}"), "calc", "x", bold=True)
    total(ws, st, 1, 17)
    trow = st + 6
    company_row(t, trow, bold=True)
    total(ws, trow, 1, 17, double=True)
    im = trow + 2
    put(ws, f"A{im}", "Implied value per share of the target", bold=True)
    header(ws, im + 1, ["Method", "", "25th", "Median", "75th"])
    put(ws, f"A{im + 2}", "EV/EBITDA")
    put(ws, f"A{im + 3}", "P/E")
    put(ws, f"A{im + 4}", "EV/Revenue")
    for col, srow in (("C", st + 3), ("D", st + 2), ("E", st + 1)):
        put(ws, f"{col}{im + 2}", f"=(N{srow}*G{trow}-D{trow}+E{trow})/C{trow}", "calc", "ps")
        put(ws, f"{col}{im + 3}", f"=P{srow}*I{trow}/C{trow}", "calc", "ps")
        put(ws, f"{col}{im + 4}", f"=(M{srow}*F{trow}-D{trow}+E{trow})/C{trow}", "calc", "ps")
    ws.freeze_panes = "B4"
    b.checks += [("Median between the quartiles", f"=AND(Comps!N{st + 2}>=Comps!N{st + 3},Comps!N{st + 2}<=Comps!N{st + 1})", "the statistics are ordered"),
                 ("Target EV = market cap + debt - cash", f"=ABS(Comps!L{trow}-(Comps!K{trow}+Comps!D{trow}-Comps!E{trow}))<0.01", "the EV bridge")]
    return b.save(path), {"median_ev_ebitda": f"Comps!N{st + 2}", "implied_median": f"Comps!D{im + 2}"}


# ---------- ratios, analysis, scorecard ----------

RATIO_ROWS = [  # (label, formula with {c} = column and H(x) = Historicals row of x, format)
    ("Gross margin", "={g}{gross_profit}/{g}{revenue}", "pct"), ("EBIT margin", "={g}{ebit}/{g}{revenue}", "pct"),
    ("Net margin", "={g}{net_income}/{g}{revenue}", "pct"), ("Return on equity", "={g}{net_income}/{g}{equity}", "pct"),
    ("Return on assets", "={g}{net_income}/{g}{assets}", "pct"),
    ("Return on invested capital", "={g}{ebit}*(1-MIN(0.4,MAX(0,{g}{tax}/{g}{pretax})))/({g}{equity}+{debt}-{g}{cash})", "pct"),
    ("Current ratio", "={g}{current_assets}/{g}{current_liabilities}", "x"),
    ("Quick ratio", "=({g}{current_assets}-N({g}{inventory}))/{g}{current_liabilities}", "x"),
    ("Debt / equity", "=({debt})/{g}{equity}", "x"), ("Debt / EBITDA", "=({debt})/({g}{ebit}+{g}{da})", "x"),
    ("Interest cover", "=IFERROR({g}{ebit}/{g}{interest},\"n/a\")", "x"), ("Asset turnover", "={g}{revenue}/{g}{assets}", "x"),
    ("Receivable days", "=N({g}{receivables})*365/{g}{revenue}", "num1"), ("Payable days", "=N({g}{payables})*365/{g}{cogs}", "num1"),
    ("Free cash flow", "={g}{cfo}-{g}{capex}", "money"), ("FCF margin", "=({g}{cfo}-{g}{capex})/{g}{revenue}", "pct"),
    ("Cash conversion (FCF / NI)", "=({g}{cfo}-{g}{capex})/{g}{net_income}", "x"), ("Diluted EPS", "={g}{eps}", "ps"),
    ("Payout ratio", "=N({g}{dividends})/{g}{net_income}", "pct"), ("Stock pay / revenue", "=N({g}{sbc})/{g}{revenue}", "pct")]


def ratio_sheet(b, f, hrows, cols, name="Ratios"):
    ws = b.sheet(name, (32,) + (14,) * len(cols))
    title(ws, 1, f"{f['name']} ({f['ticker']}) ratios", "Every ratio is a formula on the Historicals sheet.")
    header(ws, 3, ["Ratio"] + f["fiscal_year_ends"])
    out = {}
    for i, (lab, fm, fmt) in enumerate(RATIO_ROWS, start=4):
        put(ws, f"A{i}", lab)
        for col_i, hc in enumerate(cols):
            g = f"Historicals!{hc}"
            debt = f"N({g}{hrows['debt_current']})+N({g}{hrows['debt_noncurrent']})+N({g}{hrows['short_borrowings']})"
            text = fm.replace("{debt}", debt).replace("{g}", g)
            text = text.format(**{k: v for k, v in hrows.items()})
            put(ws, f"{L(2 + col_i)}{i}", f"=IFERROR({text[1:]},\"n/a\")", "calc", fmt)
        out[lab] = i
    ws.freeze_panes = "B4"
    return out


def ratios_book(f, path):
    b = Book()
    hrows, cols = history_sheet(b, f)
    ratio_sheet(b, f, hrows, cols)
    return b.save(path), {}


def analysis_book(f, flags, path):
    b = Book()
    hrows, cols = history_sheet(b, f)
    ratio_sheet(b, f, hrows, cols)
    ws = b.sheet("Common size", (30,) + (14,) * len(cols))
    title(ws, 1, "Common-size statements", "Income lines as a share of revenue; balance-sheet lines as a share of total assets.")
    header(ws, 3, ["Line"] + f["fiscal_year_ends"])
    r = 4
    for c in ("revenue", "cogs", "gross_profit", "rnd", "ebit", "tax", "net_income"):
        put(ws, f"A{r}", F.FILED.get(c, c))
        for j, hc in enumerate(cols):
            put(ws, f"{L(2 + j)}{r}", f"=IFERROR(Historicals!{hc}{hrows[c]}/Historicals!{hc}{hrows['revenue']},\"n/a\")", "calc", "pct")
        r += 1
    r += 1
    for c in ("cash", "receivables", "inventory", "ppe", "assets", "payables", "liabilities", "equity"):
        put(ws, f"A{r}", F.FILED.get(c, c))
        for j, hc in enumerate(cols):
            put(ws, f"{L(2 + j)}{r}", f"=IFERROR(Historicals!{hc}{hrows[c]}/Historicals!{hc}{hrows['assets']},\"n/a\")", "calc", "pct")
        r += 1
    fs = b.sheet("Red flags", (46, 12, 40, 40))
    title(fs, 1, "Red-flag checks", "Latest fiscal year against the year before. TRUE = flag raised.")
    header(fs, 3, ["Check", "Flag", "Measured", "Why it matters"])
    a, p = cols[-1], cols[-2]
    H = lambda c, col: f"Historicals!{col}{hrows[c]}"
    gr = lambda c: f"({H(c, a)}/{H(c, p)}-1)"
    debt = lambda col: f"(N({H('debt_current', col)})+N({H('debt_noncurrent', col)})+N({H('short_borrowings', col)}))"
    formulas = [f"=IFERROR({gr('receivables')}>{gr('revenue')}+0.1,FALSE)",
                f"=IFERROR(AND({H('inventory', a)}>0.02*{H('revenue', a)},{gr('inventory')}>{gr('revenue')}+0.1),FALSE)",
                f"=IFERROR(({H('net_income', a)}-{H('cfo', a)})/{H('assets', a)}>0.1,FALSE)",
                f"=IFERROR({H('gross_profit', p)}/{H('revenue', p)}-{H('gross_profit', a)}/{H('revenue', a)}>0.03,FALSE)",
                f"=IFERROR(N({H('sbc', a)})/{H('revenue', a)}>0.1,FALSE)",
                f"=IFERROR(AND({debt(a)}/{debt(p)}-1>0.25,{gr('revenue')}<0.05),FALSE)",
                f"=IFERROR(AND({H('net_income', a)}>0,{H('cfo', a)}/{H('net_income', a)}<0.8),FALSE)"]
    for i, (fl, fm) in enumerate(zip(flags, formulas), start=4):
        put(fs, f"A{i}", fl["check"])
        put(fs, f"B{i}", fm, "calc")
        put(fs, f"C{i}", fl["measure"], "muted")
        put(fs, f"D{i}", fl["why"], "muted")
    return b.save(path), {"flags": f"'Red flags'!B4:B{3 + len(flags)}"}


def score_book(f, sc, dcf_value, path):
    b = Book()
    hrows, cols = history_sheet(b, f)
    rr = ratio_sheet(b, f, hrows, cols)
    ws = b.sheet("Scorecard", (44, 16, 16, 12))
    title(ws, 1, "Value-investing scorecard", "Blue = market input. The tests read the Ratios and Historicals sheets.")
    put(ws, "A3", "Price"); put(ws, "B3", f["market"]["price"], "input", "ps", comment="Source: " + f["market"]["source"])
    put(ws, "A4", "DCF value per share (base case)"); put(ws, "B4", dcf_value, "input", "ps", comment="Source: the DCF workbook of this run")
    put(ws, "A5", "10-year Treasury"); put(ws, "B5", f.get("rf"), "input", "pct", comment="Source: " + f.get("rf_source", ""))
    put(ws, "A6", "Diluted shares (m)"); put(ws, "B6", f"=Historicals!{cols[-1]}{hrows['shares_diluted']}", "link", "money")
    header(ws, 8, ["Test", "Measured", "Threshold", "Pass"])
    a, first = cols[-1], cols[0]
    H = lambda c, col=None: f"Historicals!{col or a}{hrows[c]}"
    rng = lambda lab: f"Ratios!B{rr[lab]}:{L(1 + len(cols))}{rr[lab]}"
    n = len(cols) - 1
    eps = [f"Historicals!{c}{hrows['eps']}" for c in cols]
    eps_up = "+".join(f"N({b2}>{a2})" for a2, b2 in zip(eps, eps[1:]))
    fcfs = ",".join(f"{H('cfo', c)}-{H('capex', c)}" for c in cols)
    debt = f"(N({H('debt_current')})+N({H('debt_noncurrent')})+N({H('short_borrowings')}))"
    tests = [("Return on equity 15 %+ (average)", f"=AVERAGE({rng('Return on equity')})", 0.15, ">=", "pct"),
             ("Return on invested capital 12 %+", f"=Ratios!{L(1 + len(cols))}{rr['Return on invested capital']}", 0.12, ">=", "pct"),
             ("Gross margin 40 %+ (moat)", f"=Ratios!{L(1 + len(cols))}{rr['Gross margin']}", 0.40, ">=", "pct"),
             ("Net margin 10 %+", f"=Ratios!{L(1 + len(cols))}{rr['Net margin']}", 0.10, ">=", "pct"),
             ("Revenue CAGR 5 %+", f"=({H('revenue')}/{H('revenue', first)})^(1/{n})-1", 0.05, ">=", "pct"),
             ("EPS up in most years", f"=({eps_up})/{n}", 0.6, ">=", "pct"),
             ("Debt / EBITDA 2.0x or less", f"={debt}/({H('ebit')}+{H('da')})", 2.0, "<=", "x"),
             ("Free cash flow positive every year", f"=MIN({fcfs})", 0, ">", "money"),
             ("Owner-earnings yield above the 10-year", f"=({H('net_income')}+{H('da')}-{H('capex')})/($B$3*$B$6)", "=$B$5", ">=", "pct"),
             ("Price at least 25 % under DCF value", "=$B$3/$B$4", 0.75, "<=", "pct")]
    for i, (lab, fm, thr, op, fmt) in enumerate(tests, start=9):
        put(ws, f"A{i}", lab)
        put(ws, f"B{i}", f"=IFERROR({fm[1:]},\"n/a\")", "calc", fmt)
        put(ws, f"C{i}", thr, "input" if not str(thr).startswith("=") else "link", fmt)
        put(ws, f"D{i}", f"=IFERROR(B{i}{op}C{i},FALSE)", "calc")
    put(ws, "A19", "Tests passed", bold=True)
    put(ws, "B19", "=COUNTIF(D9:D18,TRUE)", "calc", "int", bold=True)
    total(ws, 19, 1, 4, double=True)
    b.checks.append(("Pass count matches the Python run", f"=Scorecard!B19={sum(1 for x in sc if x['pass'])}", "the formulas and the report agree"))
    return b.save(path), {"passed": "Scorecard!B19"}


# ---------- earnings ----------

def earnings_book(f, e, path):
    b = Book()
    ws = b.sheet("Quarters", (26, 14, 14, 14, 14, 14, 14, 14, 14, 14))
    title(ws, 1, f"{f['name']} ({f['ticker']}) quarters ($m)", "Blue = filed quarter (fiscal Q4 = the year minus three quarters).")
    q = e["rows"]
    header(ws, 3, ["Line"] + [r["end"] for r in q])
    keys = ["revenue", "gross_profit", "ebit", "net_income", "eps", "cfo"]
    for i, k in enumerate(keys, start=4):
        put(ws, f"A{i}", F.LABELS.get(k, k))
        for j, r in enumerate(q):
            if r.get(k) is not None:
                put(ws, f"{L(2 + j)}{i}", r[k], "input", "ps" if k == "eps" else "money", comment=f"Source: SEC filings, quarter ended {r['end']}")
    put(ws, "A11", "Gross margin")
    put(ws, "A12", "Operating margin")
    for j in range(len(q)):
        col = L(2 + j)
        put(ws, f"{col}11", f"=IFERROR({col}5/{col}4,\"n/a\")", "calc", "pct")
        put(ws, f"{col}12", f"=IFERROR({col}6/{col}4,\"n/a\")", "calc", "pct")
    rv = b.sheet("Review", (26, 15, 15, 12, 15, 12))
    title(rv, 1, f"Quarter ended {e['quarter_end']}", "Year ago = the quarter 4 columns back; prior = the column before.")
    header(rv, 3, ["Line", "This quarter", "Year ago", "YoY", "Prior quarter", "QoQ"])
    n = len(q)
    now, ago, prv = L(1 + n), L(1 + n - 4) if n > 4 else None, L(n)
    for i, k in enumerate(keys, start=4):
        put(rv, f"A{i}", F.LABELS.get(k, k))
        fm = "ps" if k == "eps" else "money"
        put(rv, f"B{i}", f"=Quarters!{now}{i}", "link", fm)
        if ago:
            put(rv, f"C{i}", f"=Quarters!{ago}{i}", "link", fm)
            put(rv, f"D{i}", f"=IFERROR(B{i}/C{i}-1,\"n/a\")", "calc", "pct")
        put(rv, f"E{i}", f"=Quarters!{prv}{i}", "link", fm)
        put(rv, f"F{i}", f"=IFERROR(B{i}/E{i}-1,\"n/a\")", "calc", "pct")
    ws.freeze_panes = "B4"
    return b.save(path), {"revenue_yoy": "Review!D4"}


# ---------- budget ----------

def budget_book(bd, path):
    b = Book()
    ws = b.sheet("Budget", (30, 12, 14, 14, 14, 14))
    cur = bd["currency"]
    title(ws, 1, f"Monthly budget ({cur})", "Blue = your numbers. Change a line and the split, the left-over and the 12-month path move.")
    put(ws, "A3", "Net pay per month"); put(ws, "C3", bd["net"], "input", "money", comment="Source: the household's own numbers")
    put(ws, "A4", "Emergency fund today"); put(ws, "C4", bd["path"][0], "input", "money", comment="Source: the household's own numbers")
    header(ws, 6, ["Line", "Bucket", "Amount", "Share of pay"])
    first = 7
    for i, l in enumerate(bd["lines"]):
        r = first + i
        put(ws, f"A{r}", l["name"])
        put(ws, f"B{r}", l["bucket"], "input")
        put(ws, f"C{r}", l["amount"], "input", "money")
        put(ws, f"D{r}", f"=C{r}/$C$3", "calc", "pct")
    last = first + len(bd["lines"]) - 1
    s = last + 2
    header(ws, s, ["50/30/20", "", "Now", "Share", "Target", "Gap"])
    for i, (k, tgt) in enumerate((("needs", 0.5), ("wants", 0.3), ("savings", 0.2)), start=1):
        put(ws, f"A{s + i}", k)
        put(ws, f"C{s + i}", f"=SUMIF($B${first}:$B${last},\"{k}\",$C${first}:$C${last})", "calc", "money")
        put(ws, f"D{s + i}", f"=C{s + i}/$C$3", "calc", "pct")
        put(ws, f"E{s + i}", tgt, "input", "pct")
        put(ws, f"F{s + i}", f"=C{s + i}-E{s + i}*$C$3", "calc", "money")
    put(ws, f"A{s + 4}", "Left over", bold=True)
    put(ws, f"C{s + 4}", f"=$C$3-SUM(C{s + 1}:C{s + 3})", "calc", "money", bold=True)
    put(ws, f"D{s + 4}", f"=C{s + 4}/$C$3", "calc", "pct", bold=True)
    total(ws, s + 4, 1, 6, double=True)
    put(ws, f"A{s + 5}", "Months of needs the fund covers")
    put(ws, f"C{s + 5}", f"=$C$4/C{s + 1}", "calc", "num1")
    pth = s + 7
    header(ws, pth, ["Month", "", "Fund"])
    for m in range(13):
        r = pth + 1 + m
        put(ws, f"A{r}", m, "input", "int")
        put(ws, f"C{r}", "=$C$4" if m == 0 else f"=C{r - 1}+$C${s + 3}+MAX(0,$C${s + 4})", "calc", "money")
    b.checks.append(("Lines add up to pay", f"=ABS(SUM(Budget!C{first}:C{last})+Budget!C{s + 4}-Budget!C3)<0.01", "needs + wants + savings + left over = net pay"))
    return b.save(path), {"left": f"Budget!C{s + 4}", "fund12": f"Budget!C{pth + 13}"}


# ---------- three-statement ----------

def three_book(f, a, m, path):
    b = Book()
    refs = inputs_sheet(b, a)
    h, p = m["history"], m["projection"]
    ws = b.sheet("Model", (30,) + (14,) * (len(h) + len(p)))
    title(ws, 1, f"{f['name']} ({f['ticker']}) three-statement model", "Filed years in blue, projected years as formulas. Cash is the plug. $ millions.")
    keys = ["growth_y1", "terminal_g", "cogs_pct", "opex_pct", "interest_rate", "tax_rate", "da_pct", "capex_pct_y0", "dso", "dio", "dpo", "payout", "years"]
    k = links(ws, refs, keys, 3, "A", "B")
    top = 3 + len(keys) + 1
    hc = [L(2 + i) for i in range(len(h))]
    pc = [L(2 + len(h) + i) for i in range(len(p))]
    header(ws, top, ["Line"] + [r["year"] for r in h] + [r["year"] for r in p])
    lines = ["Year index", "Revenue", "Cost of revenue", "Operating costs", "Operating income", "Interest", "Tax", "Net income", "",
             "Cash and investments", "Receivables", "Inventory", "PP&E", "Other assets", "Total assets", "Payables", "Debt", "Other liabilities",
             "Equity", "Liabilities and equity", "Balance check", "", "D&A", "Capex", "Dividends and buybacks", "Operating cash flow", "Change in cash"]
    R = {n: top + 1 + i for i, n in enumerate(lines) if n}
    for n, r in R.items():
        put(ws, f"A{r}", n, bold=n in ("Operating income", "Net income", "Total assets", "Liabilities and equity", "Balance check"))
    hk = {"Revenue": "revenue", "Cost of revenue": "cogs", "Operating costs": "opex", "Operating income": "ebit", "Interest": "interest", "Tax": "tax",
          "Net income": "net_income", "Cash and investments": "cash", "Receivables": "receivables", "Inventory": "inventory", "PP&E": "ppe",
          "Other assets": "other_assets", "Payables": "payables", "Debt": "debt", "Other liabilities": "other_liabilities", "D&A": "da",
          "Capex": "capex", "Dividends and buybacks": "dividends"}
    for j, row in enumerate(h):
        col = hc[j]
        for lab, key in hk.items():
            put(ws, f"{col}{R[lab]}", row[key], "input", "money", comment=f"Source: SEC 10-K, fiscal {row['year']}" if lab == "Revenue" else None)
        put(ws, f"{col}{R['Total assets']}", f"=SUM({col}{R['Cash and investments']}:{col}{R['Other assets']})", "calc", "money")
        put(ws, f"{col}{R['Equity']}", f"={col}{R['Total assets']}-{col}{R['Payables']}-{col}{R['Debt']}-{col}{R['Other liabilities']}", "calc", "money")
        put(ws, f"{col}{R['Liabilities and equity']}", f"=SUM({col}{R['Payables']}:{col}{R['Equity']})", "calc", "money")
        put(ws, f"{col}{R['Balance check']}", f"={col}{R['Total assets']}-{col}{R['Liabilities and equity']}", "calc", "money")
    for i, col in enumerate(pc, start=1):
        prev = hc[-1] if i == 1 else pc[i - 2]
        g = lambda lab, c=col: f"{c}{R[lab]}"
        pv = lambda lab: f"{prev}{R[lab]}"
        put(ws, g("Year index"), i, "input", "int")
        put(ws, g("Revenue"), f"={pv('Revenue')}*(1+{k['growth_y1']}-({k['growth_y1']}-{k['terminal_g']})*({g('Year index')}-1)/{k['years']})", "calc", "money")
        put(ws, g("Cost of revenue"), f"={g('Revenue')}*{k['cogs_pct']}", "calc", "money")
        put(ws, g("Operating costs"), f"={g('Revenue')}*{k['opex_pct']}", "calc", "money")
        put(ws, g("Operating income"), f"={g('Revenue')}-{g('Cost of revenue')}-{g('Operating costs')}", "calc", "money")
        put(ws, g("Interest"), f"={pv('Debt')}*{k['interest_rate']}", "calc", "money")
        put(ws, g("Tax"), f"=MAX(0,{g('Operating income')}-{g('Interest')})*{k['tax_rate']}", "calc", "money")
        put(ws, g("Net income"), f"={g('Operating income')}-{g('Interest')}-{g('Tax')}", "calc", "money")
        put(ws, g("D&A"), f"={g('Revenue')}*{k['da_pct']}", "calc", "money")
        put(ws, g("Capex"), f"={g('Revenue')}*({k['capex_pct_y0']}+({k['da_pct']}-{k['capex_pct_y0']})*{g('Year index')}/{k['years']})", "calc", "money")
        put(ws, g("Dividends and buybacks"), f"={g('Net income')}*{k['payout']}", "calc", "money")
        put(ws, g("Receivables"), f"={g('Revenue')}*{k['dso']}/365", "calc", "money")
        put(ws, g("Inventory"), f"={g('Cost of revenue')}*{k['dio']}/365", "calc", "money")
        put(ws, g("Payables"), f"={g('Cost of revenue')}*{k['dpo']}/365", "calc", "money")
        put(ws, g("Operating cash flow"), f"={g('Net income')}+{g('D&A')}-({g('Receivables')}-{pv('Receivables')})-({g('Inventory')}-{pv('Inventory')})"
                                          f"+({g('Payables')}-{pv('Payables')})", "calc", "money")
        put(ws, g("Change in cash"), f"={g('Operating cash flow')}-{g('Capex')}-{g('Dividends and buybacks')}", "calc", "money")
        put(ws, g("Cash and investments"), f"={pv('Cash and investments')}+{g('Change in cash')}", "calc", "money")
        put(ws, g("PP&E"), f"={pv('PP&E')}+{g('Capex')}-{g('D&A')}", "calc", "money")
        put(ws, g("Other assets"), f"={pv('Other assets')}", "calc", "money")
        put(ws, g("Total assets"), f"=SUM({col}{R['Cash and investments']}:{col}{R['Other assets']})", "calc", "money")
        put(ws, g("Debt"), f"={pv('Debt')}", "calc", "money")
        put(ws, g("Other liabilities"), f"={pv('Other liabilities')}", "calc", "money")
        put(ws, g("Equity"), f"={pv('Equity')}+{g('Net income')}-{g('Dividends and buybacks')}", "calc", "money")
        put(ws, g("Liabilities and equity"), f"=SUM({col}{R['Payables']}:{col}{R['Equity']})", "calc", "money")
        put(ws, g("Balance check"), f"={g('Total assets')}-{g('Liabilities and equity')}", "calc", "money")
    for lab in ("Operating income", "Net income", "Total assets"):
        total(ws, R[lab], 1, 1 + len(h) + len(p))
    total(ws, R["Liabilities and equity"], 1, 1 + len(h) + len(p), double=True)
    ws.freeze_panes = f"B{top + 1}"
    b.checks.append(("Balance sheet balances every year", f"=SUMPRODUCT(ABS(Model!B{R['Balance check']}:{pc[-1]}{R['Balance check']}))<0.01",
                     "total assets = liabilities + equity"))
    return b.save(path), {"ni_last": f"Model!{pc[-1]}{R['Net income']}", "check": f"Model!{pc[-1]}{R['Balance check']}"}
