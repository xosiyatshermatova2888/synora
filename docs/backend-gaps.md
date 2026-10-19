# Backend gaps behind the redesigned UI

The dashboard shows only what the backend supports. These items appear as
"Tez orada / Coming soon" or are omitted; none are faked.

| Area | Missing backend piece |
|---|---|
| Delivery inbox | Endpoint merging QR / Telegram / website / Instagram orders into one inbox, plus courier + address model. (QR and Telegram orders already show in Orders via the *Source* filter.) |
| Instagram channel | No integration exists. |
| Inventory | Suppliers, goods receipt, write-off documents, recipes and automatic ingredient consumption (only stock items + IN/OUT movements exist). |
| AI assistant | A configured AI service (API key) and an endpoint that calls it. |
| Orders list | Server-side filters for `source` and order number (currently client-side on the loaded page; number search scans the latest 100). |
| Overview | A "recent payments" feed endpoint (recent orders are shown instead); order-status counts use the latest 100 orders. |
| Reports/export | CSV export is not implemented. |
