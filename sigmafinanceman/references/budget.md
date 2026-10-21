# Budget input

A JSON file the user keeps on the machine. Amounts are monthly; annual costs go in as one twelfth. Example: `assets/household-example.json`.

```json
{
  "currency": "EUR",
  "net_income_monthly": 3600,
  "emergency_fund": 5000,
  "lines": [
    {"name": "Rent", "amount": 1200, "bucket": "needs"},
    {"name": "Going out", "amount": 220, "bucket": "wants"},
    {"name": "Savings plan (ETF)", "amount": 600, "bucket": "savings"}
  ]
}
```

| Key | Meaning |
|---|---|
| `net_income_monthly` | pay after tax and social insurance, all earners together |
| `emergency_fund` | cash set aside today |
| `lines[].bucket` | `needs` (rent, food, insurance, minimum debt payments), `wants` (eating out, hobbies, subscriptions, travel), `savings` (saving, investing, extra debt payments) |

From a bank export: sum each category over 3 months, divide by 3, and give each category one bucket. Ask the user when a line could be either (a gym can be a need or a want); his answer wins.
