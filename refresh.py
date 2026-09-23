#!/usr/bin/env python3
"""
Sallee Fuel Board — data refresh script.

Run this every time you have a fresh fuel-card transaction export, then
commit + push challenge_data.json. The board reads that one file —
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
    5. Writes challenge_data.json in place.

This mirrors the methodology used in the Sallee_Fuel_Discount_Corridor_Plan.xlsx
workbook: net price = SUM(paid) / SUM(gallons), i.e. what we actually pay per
gallon after discount, not the sticker discount rate.

Also builds the Team Challenge leaderboard from TEAM_PAIRS below — fixed
driver pairs (mostly team-driving partners), aggregated together so one
driver fueling up more often for the pair doesn't split their combined
savings. Drivers not listed are solo / short-term pairings and only show
up on the Individual leaderboard.

TO UPDATE THE ROSTER: edit TEAM_PAIRS below (driver names must match the
"Driver Name" column in the fuel-card export exactly — check spelling
against a fresh export if a driver's team total looks off) and re-run.
"""
import sys
import json
import datetime
import pandas as pd

# Fixed team-driving pairs for the Team Challenge. Names as they appear in
# the fuel-card "Driver Name" column. A driver not listed here drives solo
# or pairs up only briefly, and appears on the Individual board only.
TEAM_PAIRS = [
    ('Michael Becker', 'Valeria Becker'),
    ('Walter Cabarris', 'Lance Baxter'),
    ('William Sink', 'Shawn Drumm'),
    ('Jerald Little', 'Levy Jackson'),
    ('Allen Weston', 'Matthew Cowan'),
    ('Dave Stewart', 'Max Grishpenyuk'),
    ('Daishawn Hunt', 'Bradley Hunt'),
    ('Christopher Daniels', 'William Puerschner'),
    ('David Hedge', 'Clifford Geiser'),
    ('Charles Jones', 'Norberto Ramos'),
    ('Zackarey Stewart', 'Chase Mclemore'),
]
# driver name -> (team display name, [member names])
DRIVER_TEAM = {}
for a, b in TEAM_PAIRS:
    team_name = f"{a} & {b}"
    DRIVER_TEAM[a] = (team_name, [a, b])
    DRIVER_TEAM[b] = (team_name, [a, b])

# Known spelling fixes in the source export itself (confirmed against the
# Valor Oil invoices, which spell this driver's name correctly).
DRIVER_NAME_FIXES = {
    'Norberto Ramso': 'Norberto Ramos',
}

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
    df['Driver Name'] = df['Driver Name'].replace(DRIVER_NAME_FIXES)

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

    # ---- team leaderboards (fixed pairs) ----
    df['team'] = df['Driver Name'].map(lambda n: DRIVER_TEAM.get(n, (None, None))[0])
    team_df = df[df['team'].notna()].copy()

    def team_board_for(frame):
        by_driver = frame.groupby(['team', 'Driver Name']).agg(
            tx=('Qty', 'size'), gallons=('Qty', 'sum'), savings=('savings', 'sum'),
        ).reset_index()
        rows = []
        for team_name, grp in by_driver.groupby('team'):
            members = [
                {
                    'n': r['Driver Name'],
                    'tx': int(r['tx']),
                    'g': round(float(r['gallons']), 1),
                    's': round(float(r['savings']), 2),
                }
                for _, r in grp.sort_values('savings', ascending=False).iterrows()
            ]
            rows.append({
                'n': team_name,
                'tx': int(grp['tx'].sum()),
                'g': round(float(grp['gallons'].sum()), 1),
                's': round(float(grp['savings'].sum()), 2),
                'members': members,
            })
        rows.sort(key=lambda r: r['s'], reverse=True)
        return rows

    teamLeaderboards = {m: team_board_for(team_df[team_df['month'] == m]) for m in months}
    teamLeaderboards['All-Time'] = team_board_for(team_df)

    # flag any roster names that don't actually appear in this export
    known_drivers = set(df['Driver Name'].unique())
    missing = sorted({n for pair in TEAM_PAIRS for n in pair} - known_drivers)
    if missing:
        print(f"NOTE: these TEAM_PAIRS names aren't in this export "
              f"(check spelling, or they have no fill-ups yet): {', '.join(missing)}")

    out = {
        'states': states,
        'stopsByState': stopsByState,
        'months': months,
        'leaderboards': leaderboards,
        'teamLeaderboards': teamLeaderboards,
        'asOf': months[-1] if months else '',
        'updated': datetime.date.today().isoformat(),
    }

    with open('challenge_data.json', 'w') as f:
        json.dump(out, f, separators=(',', ':'))

    print(f"Wrote challenge_data.json — {len(states)} states, "
          f"{sum(len(v) for v in stopsByState.values())} stops, "
          f"{len(months)} months through {out['asOf']}, "
          f"{len(TEAM_PAIRS)} teams.")
    print("Next: git add challenge_data.json && git commit -m 'Refresh data' && git push")

if __name__ == '__main__':
    main()
