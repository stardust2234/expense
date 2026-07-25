# Expense Categoriser Backend

FastAPI and SQLAlchemy backend for the expense categorisation application.

Run it from the repository root with:

```bash
make backend-run
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`. Safe-spending plan
endpoints are available under `/api/payment-cycles`, `/api/commitments`, and `/api/allowances`.
Each payment cycle exposes its safe-to-spend projection at `/api/payment-cycles/{id}/forecast`.
Payment-period comparisons and user-assessed recurring-cost opportunities are exposed under
`/api/reports/payment-periods` and `/api/reports/recurring-opportunities`.

