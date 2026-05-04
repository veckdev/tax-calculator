# tax-calculator

Command-line tool and web app for Irish PAYE workers with multiple employments.

Splits tax credits, PAYE rate band and USC bands proportionally across jobs — mirrors what Revenue expects on ros.ie — and estimates your year-end refund or underpayment based on YTD figures.

## Web app

🌐 **[paye-calculator-k39g.onrender.com](https://paye-calculator-k39g.onrender.com)**

No installation needed — works in any browser on desktop or mobile.

> Note: hosted on Render's free tier. First load after inactivity may take ~30 seconds.

## CLI

### Requirements

Python 3.10+. No external dependencies.

### Usage

```bash
python3 main.py
```

Pick from the menu:

Split tax credits across jobs      (ros.ie allocation)
Estimate year-end refund / owed    (YTD figures needed)
Both
Quit


**Option 1** asks for jobs, tax credits, annual gross income, hours/week and hourly rate per job. Outputs rate band, tax credits and USC band split to enter on ros.ie.

**Option 2** asks for jobs, tax credits and YTD figures per job. Find these on ros.ie → PAYE Services → Manage your tax → Overview → select employment → "Pay and tax details Year To Date (YTD)". Outputs estimated refund or amount owed.

**Option 3** combines both.

## Running tests

```bash
python3 -m unittest discover -s tests -v
```

## Project structure
tax-calculator/
├── main.py               # CLI — inputs and output formatting
├── tax_calculator.py     # Core logic — tax calculations and validation
├── run.py                # Flask entry point
├── Procfile              # Render deployment config
├── pyproject.toml
├── requirements.txt
├── CHANGELOG.md
├── LICENSE
├── app/
│   ├── init.py
│   ├── routes.py
│   ├── static/css/
│   └── templates/
└── tests/
├── init.py
└── test_tax_calculator.py

## Tax rates (2026)

| Tax | Details |
|-----|---------|
| PAYE | 20% up to €44,000 / 40% above |
| USC | 0.5% → 2% → 3% → 8% (exempt below €13,000) |
| PRSI (Class A) | 4.20% Jan–Sep / 4.35% Oct–Dec (blended ~4.24%) |

## Contributing

Keep logic in `tax_calculator.py` and interface in `main.py` (CLI) or `app/` (web). Update tests for any calculation changes and run them before opening a pull request. See `CHANGELOG.md` for version history.

## License

[MIT](LICENSE)

> WARNING: This tool provides estimates only. Always verify your allocation on
> [ros.ie](https://www.ros.ie) and consult a tax advisor for official advice.