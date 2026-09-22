# Sallee Fuel Board

Live board of ULSD fuel-card fuel stops ranked by state, plus the monthly
driver Savings Challenge leaderboard. Same pattern as `barn-boards` and
`SALLEE-LOAD-BOARD`: a static page on GitHub Pages, reading one JSON data
file. Refreshing the board means regenerating that one file and pushing.

**Live at:** `https://<org-or-user>.github.io/sallee-fuel-board/` (enable
Pages on this repo, serving from the `main` branch root, to get this URL).

## Structure

```
index.html               the board (fetches data/challenge_data.json)
data/challenge_data.json  all the numbers the board displays
refresh.py                regenerates data/challenge_data.json from a new export
```

There's no build step — `index.html` is plain HTML/CSS/JS and fetches the
JSON at load time. Editing the page's look means editing `index.html`
directly.

## Refreshing the data (every ~2 weeks)

1. Export the latest fuel-card transactions (same report used for the
   Sallee_Fuel_Discount_Corridor_Plan.xlsx workbook — ULSD fills, with
   `Tran Date`, `Driver Name`, `Location Name`, `City`, `State/ Prov`,
   `Item`, `Unit Price`, `Disc PPU`, `Qty`, `Amt` columns).
2. Run:
   ```
   python3 refresh.py path/to/new_export.xlsx
   ```
   This overwrites `data/challenge_data.json` in place.
3. Commit and push:
   ```
   git add data/challenge_data.json
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
equivalent HTTP-triggered rebuild), and pushes `data/challenge_data.json`
via the GitHub API.

## The Savings Challenge

The leaderboard ranks drivers by total dollars saved (paid vs. retail) on
ULSD fuel-card fills, reset each calendar month (an All-Time view is also
available). This board tracks and ranks savings — it does not set reward
amounts; that's a separate call for dispatch/ops.
