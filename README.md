[README.md](https://github.com/user-attachments/files/32574351/README.md)
# Sallee Fuel Board

Live board of ULSD fuel-card fuel stops ranked by state, plus the monthly
driver Savings Challenge leaderboard. Same pattern as `barn-boards` and
`SALLEE-LOAD-BOARD`: a static page on GitHub Pages, reading one JSON data
file. Refreshing the board means regenerating that one file and pushing.

**Live at:** `https://<org-or-user>.github.io/sallee-fuel-board/` (enable
Pages on this repo, serving from the `main` branch root, to get this URL).

## Structure

```
index.html          the board (fetches challenge_data.json)
challenge_data.json  all the numbers the board displays
refresh.py           regenerates challenge_data.json from a new ULSD fuel-card export
refresh_valor.py     merges Valor Oil (1174-Lexington, KY) invoice PDFs into challenge_data.json
```

There's no build step — `index.html` is plain HTML/CSS/JS and fetches the
JSON at load time. Editing the page's look means editing `index.html`
directly.

## Refreshing the data (twice a week)

1. Export the latest fuel-card transactions (same report used for the
   Sallee_Fuel_Discount_Corridor_Plan.xlsx workbook — ULSD fills, with
   `Tran Date`, `Driver Name`, `Location Name`, `City`, `State/ Prov`,
   `Item`, `Unit Price`, `Disc PPU`, `Qty`, `Amt` columns).
2. Run:
   ```
   python3 refresh.py path/to/new_export.xlsx
   ```
   This overwrites `challenge_data.json` in place.
3. Commit and push:
   ```
   git add challenge_data.json
   git commit -m "Refresh data through <month>"
   git push
   ```
4. GitHub Pages rebuilds automatically — the live board updates within a
   minute or two, no other changes needed.

### What "price" and "discount" mean

For each fuel stop, **price** is the weighted net price — what was
actually paid per gallon after the card discount, averaged across every
fill-up there (`SUM(paid) / SUM(gallons)`), not the sticker discount rate.
**Discount** is the average per-gallon savings off retail
(`SUM(savings) / SUM(gallons)`). A stop built from very few fill-ups can
show a misleadingly good price — the board shows the fill-up count on
every row so that's visible at a glance.

### Automating the refresh further

Right now this is a manual two-step (run `refresh.py`, `git push`). If a
scheduled/automated refresh is wanted later, the same
Power Automate → GitHub pattern used for `barn-boards` applies: a flow
reads the new export on a schedule, calls `refresh.py`'s logic (or an
equivalent HTTP-triggered rebuild), and pushes `challenge_data.json`
via the GitHub API.

## The Savings Challenge

The leaderboard ranks drivers by total dollars saved (paid vs. retail) on
ULSD fuel-card fills, reset each calendar month (an All-Time view is also
available). This board tracks and ranks savings — it does not set reward
amounts; that's a separate call for dispatch/ops.

**Individual and Team views.** Most drivers run as fixed team-driving
pairs, so the Challenge tab has a toggle: Individual (as above) or Team,
which combines each pair's fill-ups/gallons/savings so one driver fueling
up more often for the team doesn't split their shared total. The roster
lives in `refresh.py` as `TEAM_PAIRS` — edit that list and re-run
`refresh.py` any time pairings change. A driver not listed there (solo or
short-term pairings) only shows up on the Individual board.

## Valor Oil (1174-Lexington, KY)

Sallee's Lexington, KY site runs on a separate card system (Valor Oil),
billed weekly as a PDF invoice per card-swipe. Valor's invoices only show
the price actually paid — there's no retail/undiscounted price on them to
compare against, so **Valor fill-ups aren't ranked against the other fuel
stops' discounted prices, and aren't counted in the Savings Challenge.**
They show up as a separate flagged card at the top of the KY fuel-stops
view instead (price, volume, fill-up count only).

To refresh Valor data: drop the new weekly invoice PDFs in a folder and run
```
python3 refresh_valor.py path/to/valor_pdfs/*.pdf
```
This updates the `valor` section of `challenge_data.json` in place —
commit and push it the same way as after `refresh.py`.

**If/when a discount fraction becomes available** (flat rate, or a small
table if it varies), Valor fill-ups can be folded into the regular
methodology: `retail = price / (1 - fraction)`, `saved = retail - price`,
same as everywhere else. At that point Valor's KY stop moves from the
flagged card into the ranked list and its drivers' savings roll into the
Challenge like any other fill-up.
