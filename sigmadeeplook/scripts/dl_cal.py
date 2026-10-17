"""SigmaDeepLook: calendar recurrences with the standard library (daily, weekly, monthly, yearly; INTERVAL, COUNT, UNTIL, BYDAY, BYMONTHDAY).

The full RFC 5545 rule set (BYSETPOS, RDATE, time-zone database transitions) needs the icalendar and recurring-ical-events packages;
when they are missing the look says so with the install line and shows the occurrences this simple expander can prove.
"""
import datetime as dt
import re

DAYS = {"MO": 0, "TU": 1, "WE": 2, "TH": 3, "FR": 4, "SA": 5, "SU": 6}


def parse_dt(v):
    """'20261015T090000Z' | '20261015T090000' | '20261015' -> (datetime or date, kind) with kind utc|floating|date."""
    v = v.strip()
    if re.fullmatch(r"\d{8}", v):
        return dt.datetime.strptime(v, "%Y%m%d"), "date"
    if v.endswith("Z"):
        return dt.datetime.strptime(v, "%Y%m%dT%H%M%SZ"), "utc"
    return dt.datetime.strptime(v[:15], "%Y%m%dT%H%M%S"), "floating"


def parse_rrule(s):
    rule = {}
    for part in s.split(";"):
        if "=" in part:
            k, v = part.split("=", 1)
            rule[k.upper()] = v
    return rule


def add_months(d, n):
    y, m = divmod(d.year * 12 + d.month - 1 + n, 12)
    m += 1
    for day in (d.day, 30, 29, 28):
        try:
            return d.replace(year=y, month=m, day=day)
        except ValueError:
            continue
    return d


def expand(start, rule, limit=50, horizon_years=3, exdates=()):
    """First `limit` occurrences (datetimes) of a rule that this expander supports; (list, supported: bool)."""
    freq = rule.get("FREQ")
    if freq not in ("DAILY", "WEEKLY", "MONTHLY", "YEARLY") or any(k in rule for k in ("BYSETPOS", "BYWEEKNO", "BYYEARDAY", "BYHOUR", "BYMINUTE")):
        return [], False
    interval = int(rule.get("INTERVAL", 1))
    count = int(rule["COUNT"]) if "COUNT" in rule else None
    until = None
    if "UNTIL" in rule:
        try:
            until = parse_dt(rule["UNTIL"])[0]
        except ValueError:
            return [], False
    byday = [DAYS[x[-2:]] for x in rule.get("BYDAY", "").split(",") if x and x[-2:] in DAYS]
    if rule.get("BYDAY") and any(len(x) > 2 for x in rule["BYDAY"].split(",")) and freq != "WEEKLY":
        return [], False   # "2nd Tuesday" style needs the full rule engine
    bymd = [int(x) for x in rule.get("BYMONTHDAY", "").split(",") if x]
    out, cur, n = [], start, 0
    end = start + dt.timedelta(days=366 * horizon_years)
    ex = {e for e in exdates}
    guard = 0
    while len(out) < limit and guard < 20000:
        guard += 1
        cands = [cur]
        if freq == "WEEKLY" and byday:
            monday = cur - dt.timedelta(days=cur.weekday())
            cands = [monday + dt.timedelta(days=d) for d in sorted(byday)]
        elif freq == "MONTHLY" and bymd:
            cands = []
            for d in bymd:
                try:
                    cands.append(cur.replace(day=d))
                except ValueError:
                    pass
        for c in cands:
            if c < start:
                continue
            if until and c > until:
                return out, True
            if count is not None and n >= count:
                return out, True
            n += 1
            if c not in ex:
                out.append(c)
            if len(out) >= limit:
                return out, True
        if freq == "DAILY":
            cur += dt.timedelta(days=interval)
        elif freq == "WEEKLY":
            cur += dt.timedelta(weeks=interval)
        elif freq == "MONTHLY":
            cur = add_months(cur, interval)
        else:
            cur = add_months(cur, 12 * interval)
        if count is None and until is None and cur > end:
            break
    return out, True


def describe(rule):
    freq = {"DAILY": "day", "WEEKLY": "week", "MONTHLY": "month", "YEARLY": "year"}.get(rule.get("FREQ"), rule.get("FREQ", "?").lower())
    iv = int(rule.get("INTERVAL", 1))
    s = f"every {iv} {freq}s" if iv > 1 else f"every {freq}"
    if rule.get("BYDAY"):
        s += " on " + rule["BYDAY"]
    if rule.get("COUNT"):
        s += f", {rule['COUNT']} times"
    elif rule.get("UNTIL"):
        s += f", until {rule['UNTIL']}"
    else:
        s += ", forever"
    return s
