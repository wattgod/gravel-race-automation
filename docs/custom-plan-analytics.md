# Custom-plan conversion tracking

The existing brand GA4 property receives the calculator funnel after analytics consent. No new property or tag-manager container is created. Search events contain whether a query exists and the visible result count, never the query text. Email, workout notes, HR and FTP are excluded from calculator event parameters.

| Event | Meaning |
|---|---|
| plan_preview_view | Calculator heading first becomes visible after consent |
| plan_preview_race_search | Debounced race search; boolean and result count only |
| plan_preview_race_select | Goal-race selection changes |
| plan_preview_second_race_toggle | Second A race enabled/disabled |
| plan_preview_grit_toggle | Gravel Grit Notes enabled/disabled |
| plan_preview_ready | Successful server preview; weeks and sample count |
| plan_preview_error | Sanitized unavailable/validation/timeout category |
| plan_preview_update | User changes preview controls |
| plan_preview_week_open | User opens a week |
| plan_preview_workout_open | User opens workout detail |
| plan_modules_open | User opens the plan module reference |
| plan_preview_cta_click | User continues to race plan, season plan or ski intake |
| begin_checkout | Existing validated checkout start |
| purchase | Verified paid Stripe webhook, routed to the brand property |

Season checkout attaches consent and, when available, GA4 client/session IDs. ID lookup has a 500 ms deadline; unavailable analytics cannot block checkout. Confirmation pages report page views and follow-up clicks, never an unverified purchase.

The native ski preview is still review-only. Production records its unavailable category and intake clicks, without pretending it generated ski workouts. GA4 reporting receipt and paid purchase attribution require verification in the property and a verified payment; browser events alone cannot prove either.
