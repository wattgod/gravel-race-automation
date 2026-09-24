# GA4 custom dimensions and key events — the manual step

CLAUDE.md's rule: **"Custom dimensions for A/B reporting must be registered in
GA4 admin"** and **"GA4 key events require manual admin UI toggle."** Sending an
event with a parameter (what the site's code does) is not the same as being
able to filter or split a GA4 report by that parameter — GA4 only makes a
parameter reportable once someone registers it as a **custom dimension** in the
property's admin screen. This is a one-time, per-parameter, human step. Code
cannot do it: the Admin API can create the registration, but writing to a live
GA4 property is an action this repo's automation deliberately does not take
without a person deciding to (see `docs/GA4_CONVERSION_AUTHORITY.md`).

Property: `G-EJJZ9T6M52` (`wordpress/brand_tokens.py`), Gravel God Cycling.

## Custom dimensions to register (2027 goals funnel)

These parameters already ride on events the site sends. None of them show up
as a report dimension in GA4 until registered here.

| Parameter | Scope | Sent on | Why |
|---|---|---|---|
| `src` | Event | `goal_hero_click` (homepage poster wall / race-page goal strip — `wordpress/generate_homepage.py`, `wordpress/generate_neo_brutalist.py build_goal_strip`), and every `goal_*` event on `/goals/` itself (`wordpress/generate_season_review.py`) | Which surface sent the visitor: `home` or `race`. Read from `/goals/?src=`. |
| `offer_variant` | Event | `goal_offer_view`, `goal_offer_click`, `tp_form_start`, `tp_form_section`, `tp_form_submit`, `begin_checkout` | Which of the 3 offer copy variants (A/B/C) a visitor saw/clicked, carried through to the plan form. Needed to compare variants. |
| `plan_type` | Event | `goal_offer_click` | Race Plan vs Season Plan (only "race" exists today; Season Plan is a later build step). |
| `race_slug` | Event | `goal_hero_click` (race strip only), every `goal_*` event on `/goals/` | Which specific race page, if any, sent the visitor (`?race=` param — only set when `src=race`). |
| `entry_surface` | Event | every `tp_*`/`begin_checkout` event from the plan form | Already registered? Verify — this predates the goals funnel (Sep 2026 funnel-attribution work) and may already be a dimension. If not, it silently under-reports the same way. |
| `number` | Event | `goal_section` | Which numbered question section (1–6) a visitor scrolled to. |
| `variant` | Event | every season-review/goals event | Which question-set variant rendered (`goal_2027` on the public page; also `matti`, `athlete`, etc. on the coached versions). Likely already registered from the original season-review build — verify. |

Not yet live anywhere to register against: the homepage/race-page CTAs that
fire `goal_hero_click` merged to `main` (PR #381, "2027 goals: homepage
poster wall + race-page goal strip") but had not been deployed to
gravelgodcycling.com as of this audit (`curl` of the live homepage shows no
poster wall, no `goal_hero_click`) — check with a deploy operator before
assuming any `src`/`goal_hero_click` GA4 rows exist yet.

## Click path (GA4 admin UI, per dimension)

1. Admin (bottom-left gear) → **Custom definitions** → **Custom dimensions** tab
   → **Create custom dimension**.
2. Dimension name: use the parameter name as-is (e.g. `offer_variant`) so
   reports and this table stay in sync.
3. Scope: **Event**.
4. Event parameter: the exact parameter name from the table above.
5. Save. Repeat for each row.
6. Reports lag registration — GA4 only starts counting a dimension from the
   moment it's created; it will not backfill past events.

## Key events (conversions) — recommendation: not yet

`docs/GA4_CONVERSION_AUTHORITY.md` already sets the policy here: **"Each
promoted event must first prove a durable business outcome and a stable join
to the canonical customer/order/payment model"** before it's marked a key
event, and the repo already demoted `cta_click` for failing that bar. The
goals-funnel events are brand new and unproven, so the same standard applies:

- **Do not** key-event `goal_submit`, `goal_offer_click`, or `goal_results_view`
  yet. They're diagnostic funnel steps, not yet shown to predict revenue.
- **`purchase`** is very likely already a key event (standard GA4 e-commerce
  event, used property-wide, not specific to this funnel) — verify with
  `scripts/ga4_conversion_audit.py --mode audit` rather than assume.
- Revisit `goal_submit` as a key event once there is a real lead volume to
  check it against purchases (the repo's own CLAUDE.md: race pages get
  traffic, homepage/goals-style pages don't — read the numbers as directional
  for a while first).

If Matti decides otherwise: Admin → **Custom definitions... no** — Admin →
**Events** → find the event name → toggle **Mark as key event**. (Key events
moved out of the old "Conversions" tab name in 2024; some GA4 UIs still label
it "Conversions.")

## Can this repo's tooling do it instead of the click path?

Partially. `scripts/ga4_conversion_audit.py` already authenticates with
`analytics.edit` scope and can delete a key-event registration
(`--mode demote_cta_click`), so the service account *can* hold edit access.
Nothing in this repo currently calls the **create** custom-dimension or
**create** key-event Admin API endpoints — see
`scripts/ga4_register_goals_dimensions.py` (new, dry-run only, added with this
audit) for what such a script would send. It is not run. Registering GA4
config by API instead of by hand needs the same authorization decision as any
other write to the property; the click path above is the default until Matti
says otherwise.
