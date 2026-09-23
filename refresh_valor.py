#!/usr/bin/env python3
"""
Sallee Fuel Board — Valor Oil (1174-Lexington, KY) data refresh.

Valor bills Sallee weekly with a one-invoice-per-week PDF statement
("SALLEE_HORSE_VANS-CFSI-#####-<date>.pdf"). Unlike the main ULSD
fuel-card export, these invoices only show the price actually paid —
there's no retail/undiscounted price to compare against, so no $-saved
figure can be computed here yet. Run this whenever a batch of new Valor
invoice PDFs comes in; it merges Valor's price/volume into
challenge_data.json as its own section (separate from the ranked fuel
stops and the Savings Challenge, which both require real discount data).

Usage:
    python3 refresh_valor.py path/to/valor_pdfs/*.pdf

What it does:
    1. Parses each invoice's transaction table (Driver, Date, Qty, Price).
       Uses the driver name on each transaction line, not the card-holder
       name in the "Card:" header, since invoices show cards used by more
       than one driver on some days.
    2. Keeps diesel fuel lines only (product code starting "21"); drops
       DEF and non-fuel lines. "SHOP DSL" (shop dispensing, not a driver)
       is kept in the site total but left out of driver-level figures.
    3. Aggregates by month and All-Time, both site-wide and by driver.
    4. Writes/updates the "valor" key in challenge_data.json, leaving
       everything else in that file untouched.

Once a discount fraction is available for Valor (flat or a table), this
becomes: retail = price / (1 - fraction), saved = retail - price — at
that point Valor fill-ups can move into the ranked Fuel Stops list and
the Savings Challenge like any other stop.
"""
import sys
import re
import json
import glob
import datetime
import pandas as pd
import pdfplumber

TXN_RE = re.compile(
    r'^(?P<site>.+?)\s+'
    r'(?P<date>\d{2}/\d{2})\s+'
    r'(?P<time>\d{2}:\d{2})\*?\s+'
    r'(?P<driver>[A-Z][A-Z\.\'\-]*(?:\s+[A-Z][A-Z\.\'\-]*)+)\s+'
    r'(?P<odom>\d+)\s+'
    r'(?P<mpgproduct>-?[\d\.\-]+)\s+'
    r'(?P<qty>\d+\.\d+)\s+'
    r'(?P<price>\d+\.\d+)\s+'
    r'(?P<total>\d+\.\d+)\s*$'
)
MPG_PRODUCT_RE = re.compile(r'^(?P<mpg>-?\d+\.\d{2})(?P<product>[\d\-]+)$')
INVOICE_DATE_RE = re.compile(r'Invoice Date:\s*(\d{2})/(\d{2})/(\d{4})')

# Valor spelling -> canonical spelling, matched against the main ULSD
# export's Driver Name values and the team-pairing roster.
NAME_MAP = {
    'BRADNLEY STEWART': 'Bradley Stewart',
    "DAI'SHAWN HUNT": 'Daishawn Hunt',
    'SHAWN DRUM': 'Shawn Drumm',
    'ZACKARY STEWART': 'Zackarey Stewart',
    'NORBERTO RAMOS': 'Norberto Ramos',
}

def normalize(name):
    name = name.strip()
    if name in NAME_MAP:
        return NAME_MAP[name]
    if name == 'SHOP DSL':
        return 'SHOP DSL'
    return name.title()

def extract_one(path):
    rows = []
    with pdfplumber.open(path) as pdf:
        full_text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    m = INVOICE_DATE_RE.search(full_text)
    year = m.group(3) if m else None
    for line in full_text.splitlines():
        line = line.strip()
        mm = TXN_RE.match(line)
        if not mm:
            continue
        d = mm.groupdict()
        mp = MPG_PRODUCT_RE.match(d['mpgproduct'])
        if not mp or not mp.group('product').startswith('21'):
            continue
        month, day = d['date'].split('/')
        rows.append({
            'date': f"{year}-{month}-{day}" if year else d['date'],
            'driver': normalize(d['driver']),
            'qty': float(d['qty']),
            'total': float(d['total']),
        })
    return rows

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 refresh_valor.py path/to/valor_pdfs/*.pdf")
        sys.exit(1)

    paths = []
    for pattern in sys.argv[1:]:
        paths.extend(glob.glob(pattern))
    paths = sorted(set(paths))
    if not paths:
        print("No PDFs matched.")
        sys.exit(1)

    all_rows = []
    for p in paths:
        rows = extract_one(p)
        all_rows.extend(rows)
    df = pd.DataFrame(all_rows)
    df['month'] = df['date'].str[:7]
    months = sorted(df['month'].unique().tolist())

    def site_agg(frame):
        return {
            'tx': int(len(frame)),
            'g': round(float(frame['qty'].sum()), 1),
            'paid': round(float(frame['total'].sum()), 2),
            'price': round(float(frame['total'].sum() / frame['qty'].sum()), 3) if len(frame) else 0,
        }

    def driver_board(frame):
        d = frame[frame['driver'] != 'SHOP DSL']
        g = d.groupby('driver').agg(tx=('qty', 'size'), gallons=('qty', 'sum'), paid=('total', 'sum')).reset_index()
        g = g.sort_values('gallons', ascending=False)
        return [
            {'n': r['driver'], 'tx': int(r['tx']), 'g': round(float(r['gallons']), 1), 'paid': round(float(r['paid']), 2)}
            for _, r in g.iterrows()
        ]

    valor = {
        'site': '1174-Lexington, KY (Valor Oil)',
        'months': months,
        'monthly': {m: site_agg(df[df['month'] == m]) for m in months},
        'allTime': site_agg(df),
        'driversAllTime': driver_board(df),
        'asOf': months[-1] if months else '',
        'updated': datetime.date.today().isoformat(),
        'note': ("Price shown is what we actually paid at Valor — their invoices don't include a "
                 "retail/undiscounted comparison, so this can't be ranked against other stops' "
                 "discounted prices or counted toward the Savings Challenge yet."),
    }

    try:
        with open('challenge_data.json') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    data['valor'] = valor
    with open('challenge_data.json', 'w') as f:
        json.dump(data, f, separators=(',', ':'))

    print(f"Merged Valor data into challenge_data.json — {len(paths)} invoices, "
          f"{len(df)} fill-ups, {len(months)} months through {valor['asOf']}, "
          f"{len(valor['driversAllTime'])} drivers.")
    print(f"All-Time: {valor['allTime']['g']:,.0f} gal, ${valor['allTime']['paid']:,.2f} paid, "
          f"${valor['allTime']['price']:.3f}/gal weighted avg.")

if __name__ == '__main__':
    main()
