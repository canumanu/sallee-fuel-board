[README.md](https://github.com/user-attachments/files/32666856/README.md)
# Sallee Fuel Board

Live board of ULSD fuel-card fuel stops ranked by state, plus the monthly
driver Savings Challenge leaderboard. Same pattern as `barn-boards` and
`SALLEE-LOAD-BOARD`: a static page on GitHub Pages, reading one JSON data
file. Refreshing the board means regenerating that one file and pushing.

**Driver board (share this link):** `https://<org-or-user>.github.io/sallee-fuel-board/`
**Ops board (dispatch/ops only — do not share):** `https://<org-or-user>.github.io/sallee-fuel-board/ops.html`
(enable Pages on this repo, serving from the `main` branch root, to get these URLs).

## Structure

```
index.html          driver-facing board (Fuel Savings Points, no $ in Challenge/My Savings)
ops.html             internal board — same data, full $ savings figures, not linked from index.html
challenge_data.json  all the numbers both boards display (shared — one source of truth)
refresh.py           regenerates challenge_data.json from a new ULSD fuel-card export
refresh_valor.py     merges Valor Oil (1174-Lexington, KY) invoice PDFs into challenge_data.json
```

**Two boards, one data file.** `index.html` and `ops.html` both read
`challenge_data.json` — there's only one refresh workflow (below). The only
difference between the two pages is what the Challenge and My Savings tabs
*display*: `index.html` shows Fuel Savings Points, `ops.html` shows the
underlying dollars. The Fuel Stops tab (prices/discounts by state) is
identical on both, since drivers need that to pick where to fuel.

`ops.html` is gated behind a Microsoft sign-in (Azure AD / Microsoft Entra
ID) — see "Ops board access" below. It's also marked `noindex` for search
engines and isn't linked from the driver board, but that's just tidiness
now; the real access control is the sign-in gate.

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

**Fuel Savings Points (driver board only).** `index.html` never displays
the dollar figure in the Challenge or My Savings tabs — it converts to
points instead, at **1 point per $10 saved, rounded** (`toPoints()` near
the top of `index.html`'s script). Ranking itself is still computed from
the real dollar amounts (so rounding never changes who's ahead), only the
*displayed* number is points. This factor isn't printed anywhere on the
driver board on purpose — change it in one place (`toPoints()`) if it
ever needs adjusting, and update this note to match. `ops.html` is
unaffected and always shows the real dollars.

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

## Ops board access (Azure AD sign-in)

`ops.html` requires signing in with a Sallee Microsoft 365 account before
it shows anything — same pattern as the dispatch/load boards. It uses
[MSAL.js](https://github.com/AzureAD/microsoft-authentication-library-for-js)
(`@azure/msal-browser`, loaded from jsDelivr, pinned to `v2.38.3`) against
an app registration in Sallee's Azure AD tenant.

- **App registration:** single-tenant ("Accounts in this organizational
  directory only"), platform type **SPA** (not "Web"), redirect URI
  `https://<org-or-user>.github.io/sallee-fuel-board/ops.html` — must match
  exactly, including trailing path.
- **Allowlist:** who's allowed in is a plain array at the top of `ops.html`'s
  script, `ALLOWED_USERS` — currently just `mdavy@salleehorsevans.com`. To
  add or remove someone, edit that array (case-insensitive match against
  their Microsoft sign-in email) — no Azure-side change needed for that.
- **What happens:** an unauthenticated visitor sees a sign-in screen and
  never sees the board or fetches `challenge_data.json` from a signed-in
  session until they sign in. A signed-in visitor not on the allowlist sees
  a plain "not authorized" screen with a sign-out option — never the board
  itself. Config values (client ID, tenant ID) are public in the page
  source, which is normal for MSAL SPA apps — they only identify *which*
  Azure app to sign into, they don't grant access by themselves; the
  allowlist check is what actually gates the board.
- **Changing the Azure app registration:** if the client ID or tenant ID
  ever changes (new app registration, moved to a different tenant), update
  the `msalConfig` object near the bottom of `ops.html`'s script
  (`clientId` / `authority`).
- **The driver board (`index.html`) has no login** — it was never meant
  to be restricted, and still isn't. Only `ops.html` is gated.
