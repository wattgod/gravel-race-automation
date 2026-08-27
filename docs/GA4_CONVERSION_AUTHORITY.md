# GA4 conversion authority

GA4 is the behavioral funnel record. It is not the financial source of truth.
The provider ledger owns successful payment, refunds, fees, and cash settlement.

The manual **GA4 Conversion Authority Audit** workflow reads the Gravel God GA4
property through the existing service account and writes a receipt containing:

- the live key-event registry before and after the requested action;
- event counts, users, and key-event counts for the selected period;
- purchase rows by `transactionId` and their reported purchase revenue;
- controls for missing and duplicate transaction IDs; and
- the exact key-event action taken.

`audit` mode is entirely read-only. `demote_cta_click` can delete only the exact
`cta_click` key-event resource belonging to the configured property. It then
reads the registry again and fails if `cta_click` remains keyed. The underlying
`cta_click` event continues to be collected as a diagnostic funnel event.

This correction intentionally does not mark additional events as key events.
Each promoted event must first prove a durable business outcome and a stable
join to the canonical customer/order/payment model.
