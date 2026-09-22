#!/usr/bin/env python3
"""
Sallee Fuel Board — data refresh script.

Run this every time you have a fresh fuel-card transaction export, then
commit + push data/challenge_data.json. The board reads that one file —
nothing else needs to change.

Usage:
    python3 refresh.py path/to/new_export.xlsx
    python3 refresh.py path/to/new_export.csv

Expects the same columns as the Sallee ULSD fuel-card export:
    Tran Date, Driver Name, Location Name, City, State/ Prov,
    Item, Unit Price, Disc PPU, Qty, Amt

What it does:
    1. Filters to ULSD rows only.
    2. Computes, per fill-up: paid = Amt (what we actually paid),
       savings = (Unit Price - Disc PPU) * Qty.
    3. Aggregates by fuel stop (Location/City/State) -> price & discount
       per gallon, weighted across every fill at that stop.
    4. Aggregates by driver x month, plus an All-Time total, for the
       Savings Challenge leaderboard.
    5. Writes data/challenge_data.json in place.

This mirrors the methodology used in the Sallee_Fuel_Discount_Corridor_Plan.xlsx
workbook: net price = SUM(paid) / SUM(gallons), i.e. what we actually pay per
gallon after discount, not the sticker discount rate.
"""
import sys
import json
import datetime
import pandas as pd

def load(path):
    if path.lower().endswith(('.xlsx', '.xls')):
        return pd.read_excel(path)
    return pd.read_csv(path)

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 refresh.py path/to/new_export.xlsx")
        sys.exit(1)

    raw = load(sys.argv[1])
    raw.columns = [c.strip() for c in raw.columns]

    df = raw[raw['Item'].astype(str).str.upper().str.strip() == 'ULSD'].copy()
    df = df[(df['Qty'] > 0) & (df['Disc PPU'] > 0)]

    df['paid'] = df['Amt']
    df['savings'] = (df['Unit Price'] - df['Disc PPU']) * df['Qty']
    df['month'] = df['Tran Date'].astype(str).str[:7]

    # ---- fuel stops by state ----
    loc = df.groupby(['Location Name', 'City', 'State/ Prov']).agg(
        tx=('Qty', 'size'), gallons=('Qty', 'sum'),
        paid=('paid', 'sum'), savings=('savings', 'sum'),
    ).reset_index()
    loc['price'] = loc['paid'] / loc['gallons']
    loc['disc'] = loc['savings'] / loc['gallons']

    states = sorted(loc['State/ Prov'].dropna().unique().tolist())
    stopsByState = {}
    for st in states:
        g = loc[loc['State/ Prov'] == st].sort_values('price')
        stopsByState[st] = [
            {
                'n': r['Location Name'].title(),
                'c': str(r['City']).title(),
                'tx': int(r['tx']),
                'g': round(float(r['gallons']), 1),
                'p': round(float(r['price']), 3),
                'd': round(float(r['disc']), 3),
            }
            for _, r in g.iterrows()
        ]

    # ---- driver leaderboards ----
    months = sorted(df['month'].dropna().unique().tolist())

    def board_for(frame):
        g = frame.groupby('Driver Name').agg(
            tx=('Qty', 'size'), gallons=('Qty', 'sum'), savings=('savings', 'sum'),
        ).reset_index().sort_values('savings', ascending=False)
        return [
            {
                'n': r['Driver Name'],
                'tx': int(r['tx']),
                'g': round(float(r['gallons']), 1),
                's': round(float(r['savings']), 2),
            }
            for _, r in g.iterrows()
        ]

    leaderboards = {m: board_for(df[df['month'] == m]) for m in months}
    leaderboards['All-Time'] = board_for(df)

    out = {
        'states': states,
        'stopsByState': stopsByState,
        'months': months,
        'leaderboards': leaderboards,
        'asOf': months[-1] if months else '',
        'updated': datetime.date.today().isoformat(),
    }

    with open('data/challenge_data.json', 'w') as f:
        json.dump(out, f, separators=(',', ':'))

    print(f"Wrote data/challenge_data.json — {len(states)} states, "
          f"{sum(len(v) for v in stopsByState.values())} stops, "
          f"{len(months)} months through {out['asOf']}.")
    print("Next: git add data/challenge_data.json && git commit -m 'Refresh data' && git push")

if __name__ == '__main__':
    main()
