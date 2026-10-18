"""SigmaDeepLook: more table containers, read the same way as a parquet file or a sqlite table.

ORC, DuckDB databases, Stata (.dta), SAS (.sas7bdat, .xpt), NumPy arrays (.npy, .npz). Each reader names the schema, counts the rows and
sends every row through the shared exact profiler (dl_data.table_profile), so a question about a count, a range or a distinct value is
answered from the print. A missing library is a "Not looked at" row with its install line, never a crash.
"""
import json
import time

import dl_core as core
import dl_data as D


def _rows_of_columns(cols_iter):
    """cols_iter() -> iterator of column-lists per batch; returns a callable giving (index, values) for D.table_profile."""
    def rows():
        k = 0
        for cols in cols_iter():
            for r in zip(*cols):
                k += 1
                yield k, r
    return rows


def _frame_rows(df):
    def rows():
        for k, r in enumerate(df.itertuples(index=False, name=None), 1):
            yield k, r
    return rows


def _intro(look, kind, nrows, ncols, headline_extra=""):
    look.headline = f"{kind}, {D.rows_fmt(nrows or 0)} rows x {ncols} columns{headline_extra}"
    look.dims = f"{D.rows_fmt(nrows or 0)} rows"
    look.fact("rows", nrows)
    look.fact("columns_n", ncols)


# ------------------------------------------------------------------------------------------------ ORC
def look_orc(look):
    if not look.need_mod("pyarrow", "ORC schema and rows"):
        look.line("ORC columnar file; its schema and rows need pyarrow.")
        return
    import pyarrow.orc as orc
    import dl_prof as P
    f = orc.ORCFile(str(look.path))
    sch = f.schema
    n = f.nrows
    _intro(look, "ORC", n, len(sch), f", {f.nstripes} stripes")
    P.counts(look, [("rows", n), ("columns", len(sch)), ("stripes", f.nstripes)], 96)
    look.line(f"ORC file: {n:,} rows, {len(sch)} columns, {f.nstripes} stripes, compression {f.compression}, writer {f.writer}, format {f.file_version}. Columns: "
              + ", ".join(f"{x.name} {x.type}" for x in sch) + ".", 92)
    try:
        md = {k.decode() if isinstance(k, bytes) else k: (v.decode("utf-8", "replace") if isinstance(v, bytes) else v) for k, v in (f.metadata or {}).items()} if hasattr(f, "metadata") else {}
        if md:
            look.line("User metadata: " + "; ".join(f"{k}={str(v)[:60]}" for k, v in list(md.items())[:10]), 70)
    except Exception:
        pass
    if look.quick:
        return
    names = [x.name for x in sch]

    def batches():
        for i in range(f.nstripes):
            t = f.read_stripe(i)
            yield [c.to_pylist() for c in t.columns]
    try:
        D.table_profile(look, "Rows", names, _rows_of_columns(batches), "row", n, 84, 28)
    except Exception as e:
        look.fail("exact row profile", "pyarrow", e)
    look.step("ORC footer and rows", "pyarrow")


# ------------------------------------------------------------------------------------------------ DuckDB
def look_duckdb(look):
    if not look.need_mod("duckdb", "DuckDB tables and rows"):
        look.line("DuckDB database file; its tables need the duckdb package.")
        return
    import duckdb
    import dl_prof as P
    try:
        con = duckdb.connect(str(look.path), read_only=True)
    except Exception as e:
        look.flag("DUCKDB-ERROR", "file", str(e)[:140], "the file may be locked by another process or from a newer DuckDB version")
        return
    try:
        ver = con.execute("select version()").fetchone()[0]
    except Exception:
        ver = "?"
    tabs = con.execute("select schema_name, table_name, estimated_size, column_count, has_primary_key, temporary from duckdb_tables() order by schema_name, table_name").fetchall()
    views = con.execute("select schema_name, view_name, sql from duckdb_views() where not internal order by 1, 2").fetchall()
    cols = con.execute("select schema_name, table_name, column_name, data_type, is_nullable, column_default from duckdb_columns() where not internal order by schema_name, table_name, column_index").fetchall()
    cons = con.execute("select schema_name, table_name, constraint_type, constraint_column_names from duckdb_constraints()").fetchall()
    idx = con.execute("select table_name, index_name, is_unique from duckdb_indexes()").fetchall()
    seqs = con.execute("select sequence_name from duckdb_sequences()").fetchall()
    bycol = {}
    for sc, t, c, ty, nul, dflt in cols:
        bycol.setdefault((sc, t), []).append((c, ty, nul, dflt))
    counts = {}
    for sc, t, *_ in tabs:
        try:
            counts[(sc, t)] = con.execute(f'select count(*) from "{sc}"."{t}"').fetchone()[0]
        except Exception:
            counts[(sc, t)] = None
    look.fact("tables", [t for _, t, *_ in tabs])
    look.fact("row_counts", {t: counts[(s, t)] for s, t, *_ in tabs})
    look.headline = f"DuckDB {ver}, {len(tabs)} tables, {len(views)} views, {core.human(look.size)}"
    look.line(f"DuckDB database (engine {ver}): {len(tabs)} tables, {len(views)} views, {len(idx)} indexes, {len(seqs)} sequences, {len(cons)} constraints, read-only.", 95)
    rk = sorted(tabs, key=lambda x: -(counts[(x[0], x[1])] or 0))
    look.line("Rows per table, biggest first: " + "; ".join(f"{t} {counts[(s, t)]:,}" if counts[(s, t)] is not None else f"{t} ?" for s, t, *_ in rk) + ".", 94)
    for s, t, *_ in rk[:12]:
        look.line(f"Table {t} ({counts[(s, t)]:,} rows): " + ", ".join(f"{c} {ty}" + ("" if nul else " NOT NULL") for c, ty, nul, _d in bycol.get((s, t), [])) + ".", 90)
    if cons:
        look.line("Constraints: " + "; ".join(f"{t} {ct} ({', '.join(map(str, cc)) if cc else ''})" for _s, t, ct, cc in cons[:30]) + ".", 86)
    if idx:
        look.line("Indexes: " + "; ".join(f"{i} on {t}" + (" unique" if u else "") for t, i, u in idx[:20]) + ".", 70)
    for s, v, sql in views:
        look.line(f"View {v}: {' '.join(str(sql).split())[:240]}", 82)
    if not look.quick:
        for s, t, *_ in rk[:8]:
            names = [c for c, *_x in bycol.get((s, t), [])]
            if not names or not counts[(s, t)]:
                continue

            def batches(s=s, t=t):
                cur = con.cursor()
                cur.execute(f'select * from "{s}"."{t}"')
                while True:
                    rows = cur.fetchmany(50000)
                    if not rows:
                        break
                    yield [list(c) for c in zip(*rows)]
            try:
                D.table_profile(look, f"Table {t}", names, _rows_of_columns(batches), "row", counts[(s, t)], 84, 28, cap_s=20.0, listing=counts[(s, t)] <= 40)
            except Exception as e:
                look.fail(f"row profile of {t}", "duckdb", e)
    con.close()
    look.step("DuckDB catalog, counts and rows", "duckdb")


# ------------------------------------------------------------------------------------------------ Stata / SAS
def _frame_look(look, kind, df, extra_lines=()):
    import dl_prof as P
    n, m = len(df), len(df.columns)
    _intro(look, kind, n, m)
    P.counts(look, [("rows", n), ("columns", m)], 96)
    for k, t in enumerate(extra_lines):
        look.line(t, 93 - k)
    look.line("Columns: " + ", ".join(f"{c} {df[c].dtype}" for c in df.columns[:60]) + (f" +{m - 60} more" if m > 60 else "") + ".", 90)
    if not look.quick:
        try:
            D.table_profile(look, "Rows", [str(c) for c in df.columns], _frame_rows(df), "row", n, 84, 28)
        except Exception as e:
            look.fail("exact row profile", "pandas", e)


def look_stata(look):
    if not look.need_mod("pandas", "Stata file"):
        look.line("Stata data file; reading it needs pandas.")
        return
    import pandas as pd
    with pd.io.stata.StataReader(str(look.path)) as r:
        vl = r.variable_labels()
        val = r.value_labels() if hasattr(r, "value_labels") else {}
        dl = getattr(r, "_data_label", "") or ""
        ts = getattr(r, "_time_stamp", "") or ""
        ver = getattr(r, "_format_version", "?")
        df = r.read(convert_categoricals=False)
    ex = [f"Stata dta format {ver}" + (f", dataset label '{dl}'" if dl else "") + (f", saved {ts}" if ts else "") + "."]
    labelled = {k: v for k, v in vl.items() if v}
    if labelled:
        ex.append("Variable labels: " + "; ".join(f"{k} = {v}" for k, v in list(labelled.items())[:40]) + ".")
    if val:
        ex.append("Value labels: " + "; ".join(f"{k}: " + ", ".join(f"{a}={b}" for a, b in list(m.items())[:8]) for k, m in list(val.items())[:12]) + ".")
    _frame_look(look, "Stata", df, ex)
    look.step("Stata header, labels and rows", "pandas")


def look_sas7bdat(look):
    if not look.need_mod("pandas", "SAS file"):
        look.line("SAS data file; reading it needs pandas.")
        return
    import pandas as pd
    df = pd.read_sas(str(look.path))
    _frame_look(look, "SAS", df)
    look.step("SAS rows", "pandas")


look_sasxpt = look_sas7bdat


# ------------------------------------------------------------------------------------------------ NumPy
def _array_line(name, a):
    import numpy as np
    dt, sh = a.dtype, a.shape
    base = f"{name}: dtype {dt}, shape {'x'.join(map(str, sh)) or 'scalar'} ({a.size:,} elements, {a.nbytes:,} bytes)"
    if a.size == 0:
        return base + ", empty"
    try:
        if dt.kind == "b":
            t = int(a.sum())
            return base + f", {t:,} True ({100 * t / a.size:.1f} %), {a.size - t:,} False"
        if dt.kind in "iuf":
            x = a.astype("float64", copy=False).ravel()
            nan = int(np.isnan(x).sum()) if dt.kind == "f" else 0
            fin = x[~np.isnan(x)] if nan else x
            mono = ""
            if a.ndim == 1 and a.size > 1 and dt.kind in "iu":
                d = np.diff(a.astype("int64"))
                mono = ", strictly increasing" if (d > 0).all() else ", non-decreasing" if (d >= 0).all() else ""
            uniq = len(np.unique(fin[: 2_000_000])) if fin.size else 0
            return (base + f", min {fin.min():.6g}, max {fin.max():.6g}, mean {fin.mean():.6g}, median {np.median(fin):.6g}, std {fin.std():.6g}, sum {fin.sum():.6g}, "
                    f"{uniq:,} distinct{', ' + str(nan) + ' NaN' if nan else ''}{mono}; first values " + ", ".join(f"{v:.6g}" for v in fin[:6]))
        if dt.kind in "SUO":
            vals = a.ravel()[:5].tolist()
            return base + f", first values {vals}"
    except Exception as e:
        return base + f" (stats failed: {e})"
    return base


def look_npy(look):
    if not look.need_mod("numpy", "NumPy arrays"):
        look.line("NumPy array file; reading it needs numpy.")
        return
    import numpy as np
    a = np.load(str(look.path), allow_pickle=False, mmap_mode="r") if look.size > (200 << 20) else np.load(str(look.path), allow_pickle=False)
    look.headline = f"NumPy array {a.dtype} {'x'.join(map(str, a.shape))}"
    look.dims = "x".join(map(str, a.shape))
    look.line("NumPy array. " + _array_line("array", np.asarray(a)), 95)
    look.step("NumPy array", "numpy")


def look_npz(look):
    if not look.need_mod("numpy", "NumPy archive"):
        look.line("NumPy archive; reading it needs numpy.")
        return
    import numpy as np
    z = np.load(str(look.path), allow_pickle=False)
    names = list(z.files)
    look.headline = f"NumPy archive: {len(names)} arrays"
    look.fact("arrays", names)
    look.line(f"NumPy .npz archive with {len(names)} arrays: {', '.join(names)}.", 96)
    for k, nme in enumerate(names[:60]):
        try:
            look.line(_array_line(nme, z[nme]), 92 - min(k, 40) // 4)
        except Exception as e:
            look.line(f"{nme}: unreadable ({str(e)[:80]})", 60)
    look.step("NumPy archive arrays", "numpy")
