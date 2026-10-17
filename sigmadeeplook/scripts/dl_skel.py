"""SigmaDeepLook: a signature skeleton of a source file, so a big file costs a fraction of its bodies.

Agentless (arXiv 2407.01489) found the skeleton (class and function headers, signatures, one doc line) as good as the whole file for
finding the right place to edit, at a fraction of the lines. The skeleton is the file's table of contents: `L<line>  signature  # first doc line`.
The body of one definition is then one call away: `look.py FILE --func NAME`.

Python is parsed with ast (never imported or run). Other languages use one regex per construct; nothing is guessed beyond the header line.
"""
import ast
import re

DOC_CLIP = 70
SIG_CLIP = 130
MAX_DEFS = 600

# a header line in a brace/keyword language: keep the line as written, up to the opening brace or colon
HEADER_RE = re.compile(
    r"^(?P<ind>[ \t]*)(?P<sig>(?:export\s+(?:default\s+)?|public\s+|private\s+|protected\s+|static\s+|final\s+|abstract\s+|async\s+|pub(?:\([^)]*\))?\s+|unsafe\s+|extern\s+)*"
    r"(?:class|interface|struct|enum|trait|impl|type|func|fn|function|def|module|namespace|object|record)\b[^\n{;=]*|"
    r"(?:(?:public|private|protected|static|final|virtual|override|inline|async|export)\s+)*(?:[\w<>\[\],.*&:]+\s+)*[A-Za-z_]\w*\s*\([^;{}]*\)\s*(?:const\s*)?\{|"
    r"(?:export\s+)?(?:const|let|var)\s+[A-Za-z_$][\w$]*\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>)",
    re.M)
NOT_DEF = re.compile(r"^\s*(?:if|for|while|switch|catch|return|else|elif|with|try|match|do|foreach|using|throw|new|delete|sizeof)\b")


def _doc(node):
    d = ast.get_docstring(node, clean=True)
    return " ".join(d.split())[:DOC_CLIP] if d else ""


def _py_sig(n):
    if isinstance(n, ast.ClassDef):
        bases = ", ".join(ast.unparse(b) for b in n.bases)
        return f"class {n.name}" + (f"({bases})" if bases else "")
    try:
        args = ast.unparse(n.args)
    except Exception:
        args = "..."
    ret = f" -> {ast.unparse(n.returns)}" if getattr(n, "returns", None) is not None else ""
    return ("async " if isinstance(n, ast.AsyncFunctionDef) else "") + f"def {n.name}({args}){ret}"


def python_skeleton(text):
    """-> list of (line, depth, signature, doc) in file order, or None when the file does not parse."""
    try:
        tree = ast.parse(text)
    except (SyntaxError, ValueError, RecursionError):
        return None
    out = []

    def walk(body, depth):
        for n in body:
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                out.append((n.lineno, depth, _py_sig(n), _doc(n)))
                if isinstance(n, ast.ClassDef):
                    walk(n.body, depth + 1)   # methods of a class; functions nested in functions are body, not skeleton
            elif isinstance(n, (ast.If, ast.Try)) and depth == 0:
                walk(getattr(n, "body", []), depth)
    walk(tree.body, 0)
    return out[:MAX_DEFS]


def regex_skeleton(text):
    """-> list of (line, depth, signature, doc) from header lines. A leading comment line becomes the doc."""
    out = []
    lines = text.splitlines()
    for i, ln in enumerate(lines, 1):
        if len(ln) > 400 or NOT_DEF.match(ln) or ln.lstrip().startswith("}"):
            continue
        m = HEADER_RE.match(ln)
        if not m:
            continue
        sig = " ".join(m.group("sig").split()).rstrip("{ ").rstrip(":")
        if not re.search(r"\b(class|interface|struct|enum|trait|impl|type|func|fn|function|def|module|namespace|object|record)\b|\(|=>", sig):
            continue
        doc = ""
        if i >= 2:
            prev = lines[i - 2].strip()
            if prev.startswith(("//", "#", "*", "/*", "///", "--")):
                doc = prev.lstrip("/#*- ").strip()[:DOC_CLIP]
        indent = len(m.group("ind").replace("\t", "    "))
        out.append((i, min(indent // 2, 6), sig[:SIG_CLIP], doc))
        if len(out) >= MAX_DEFS:
            break
    return out


def skeleton(text, ext):
    """-> (rows, how). rows = [(line, depth, signature, doc)]; how = 'ast' | 'regex' | ''."""
    if ext in (".py", ".pyw"):
        rows = python_skeleton(text)
        if rows is not None:
            return rows, "ast"
    rows = regex_skeleton(text)
    return rows, ("regex" if rows else "")


def render(rows, total_lines):
    """Text form: one line per definition, indented by nesting, with the line number and a doc remark."""
    out = [f"# skeleton: {len(rows)} definitions of a {total_lines}-line file; body of one: look.py FILE --func NAME"]
    for line, depth, sig, doc in rows:
        out.append(f"L{line} " + "  " * depth + sig + (f"  # {doc}" if doc else ""))
    return "\n".join(out)
