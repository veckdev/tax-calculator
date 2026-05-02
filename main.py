"""
main.py — CLI for the Revenue Tax Split Calculator.

Menu:
  1. Split tax credits   → splits rate band, credits and USC bands across jobs
  2. Year-end estimate   → estimates refund or amount owed based on YTD figures
  3. Both
  0. Quit

Run with: python3 main.py
"""

from tax_calculator import (
    Job,
    YTDData,
    SplitResult,
    RefundSummary,
    calculate_split,
    calculate_refund,
)

import sys
import io
from datetime import date
from contextlib import contextmanager

# terminal width — all rows and borders are built around this
W = 58


def eur(v: float) -> str:
    """Formats a float as euro, e.g. 1234.5 → €1,234.50"""
    return f"€{v:,.2f}"


def row(label: str, value: str, indent: int = 2) -> None:
    """Prints a dot-leader row: '  Label ......... Value'"""
    pad = " " * indent
    dots = "." * max(1, W - len(label) - len(value) - indent - 1)
    print(f"{pad}{label} {dots} {value}")


def blank() -> None:
    print()


def divider(char: str = "─") -> None:
    print(f"  {char * W}")


def header(title: str) -> None:
    """Prints a full-width box header."""
    print(f"\n╔{'═' * W}╗")
    print(f"║{title.upper().center(W)}║")
    print(f"╚{'═' * W}╝")


def section(title: str) -> None:
    """Prints a section title with a divider below."""
    blank()
    print(f"  ▸ {title}")
    divider()


def result_label(amount: float) -> str:
    """Returns a short label for a tax result — refund, owed, or balanced."""
    if amount > 0.005:
        return f"REFUND  {eur(amount)}"
    elif amount < -0.005:
        return f"OWED    {eur(abs(amount))}"
    else:
        return "BALANCED  €0.00"


# input helpers


def ask_float(prompt: str, allow_zero: bool = False) -> float:
    """Keeps asking until the user enters a valid float."""
    while True:
        try:
            v = float(input(f"  {prompt}"))
            if not allow_zero and v <= 0:
                print("  WARNING  Must be greater than zero.\n")
            elif v < 0:
                print("  WARNING  Cannot be negative.\n")
            else:
                return v
        except ValueError:
            print("  WARNING  Please enter a numeric value.\n")


def ask_int(prompt: str) -> int:
    """Keeps asking until the user enters a valid positive integer."""
    while True:
        try:
            v = int(input(f"  {prompt}"))
            if v <= 0:
                print("  WARNING  Must be a whole number greater than zero.\n")
            else:
                return v
        except ValueError:
            print("  WARNING  Please enter a whole number.\n")


def ask_str(prompt: str) -> str:
    """Keeps asking until the user enters a non-empty string."""
    while True:
        v = input(f"  {prompt}").strip()
        if not v:
            print("  WARNING  This field cannot be empty.\n")
        else:
            return v


def ask_income_method() -> str:
    """Asks whether to enter income as hourly rate or annual salary."""
    while True:
        v = input("  Income type (1=hourly / 2=annual salary): ").strip()
        if v in ("1", "2"):
            return v
        print("  WARNING  Please enter 1 or 2.\n")


def ask_menu() -> str:
    """Asks the user to pick an option from the main menu. 0 to quit."""
    while True:
        v = input("  Choose (1/2/3) or 0 to quit: ").strip()
        if v in ("1", "2", "3", "0"):
            return v
        print("  WARNING  Please enter 1, 2, 3 or 0.\n")


# input collection


def collect_base_info() -> tuple[int, float]:
    """Number of jobs and tax credits — always required."""
    section("General Information")
    blank()
    num_jobs = ask_int("Number of jobs              : ")
    tax_credits = ask_float("Annual tax credits (€)      : ")
    return num_jobs, tax_credits


def collect_income(name: str, ytd: YTDData) -> Job:
    """Asks income method and returns a Job with estimated_annual_income set."""
    method = ask_income_method()
    if method == "1":
        hours = ask_float("  Hours per week              : ")
        rate = ask_float("  Hourly rate (€)             : ")
        return Job(
            company_name=name, ytd=ytd, hours_per_week=hours, salary_per_hour=rate
        )
    else:
        salary = ask_float("  Annual gross salary (€)     : ")
        return Job(company_name=name, ytd=ytd, annual_salary=salary)


def collect_jobs_basic(num_jobs: int) -> list[Job]:
    """Collects job details without YTD — used for split only (option 1)."""
    jobs: list[Job] = []
    section("Employment Details")

    for i in range(1, num_jobs + 1):
        blank()
        print(f"  ── Job #{i} ──")
        name = ask_str("  Company name                : ")
        job = collect_income(name, YTDData(0, 0, 0, 0))
        print(f"  → Est. annual income: {eur(job.estimated_annual_income)}")
        jobs.append(job)

    return jobs


def collect_ytd(index: int, name: str) -> YTDData:
    """Asks for YTD figures for one job. User pulls these from ros.ie."""
    print(f"\n  YTD figures  —  Job #{index}: {name}")
    divider()
    print(f"  Where to find these:")
    print(f"    1. Go to ros.ie and log in to myAccount")
    print(f"    2. PAYE Services → Manage your tax → Overview")
    print(f"    3. Click on this employment in the left sidebar")
    print(f"    4. Look at 'Pay and tax details Year To Date (YTD)'")
    blank()
    gross = ask_float("    Gross pay YTD (€)           : ", allow_zero=True)
    paye_paid = ask_float("    Income Tax paid YTD (€)     : ", allow_zero=True)
    usc_paid = ask_float("    USC paid YTD (€)            : ", allow_zero=True)
    prsi_paid = ask_float("    Employee PRSI paid YTD (€)  : ", allow_zero=True)
    return YTDData(
        gross_pay=gross,
        income_tax_paid=paye_paid,
        usc_paid=usc_paid,
        prsi_paid=prsi_paid,
    )


def collect_jobs_with_ytd(num_jobs: int, need_proportion: bool = False) -> list[Job]:
    """Collects job details including YTD.
    need_proportion=True adds income method — used when split is also needed (option 3).
    """
    jobs: list[Job] = []
    section("Employment Details")

    for i in range(1, num_jobs + 1):
        blank()
        print(f"  ── Job #{i} ──")
        name = ask_str("  Company name                : ")

        ytd = collect_ytd(i, name)

        if need_proportion:
            job = collect_income(name, ytd)
            print(f"  → Est. annual income: {eur(job.estimated_annual_income)}")
        else:
            job = Job(company_name=name, ytd=ytd)

        jobs.append(job)

    return jobs


# report sections


def print_paye_tab(split: SplitResult) -> None:
    """Section A — rate band and tax credits to enter on ros.ie."""
    section("A  ·  PAYE  — Rate Band & Tax Credits")
    print(f"  {'Enter these on ros.ie → Divide tax credits → PAYE tab':>{W}}")

    for i, a in enumerate(split.allocations, 1):
        blank()
        print(f"  Job #{i}  —  {a.job.company_name}")
        divider("·")
        row("Rate band (20%)", eur(a.allocated_rate_band))
        row("Tax credits", eur(a.allocated_tax_credits))

    blank()
    print(f"  {'All income above rate band is taxable at 40%':>{W}}")
    print(f"  {'WARNING: rate band assumes single assessment (€44,000)':>{W}}")


def print_usc_tab(split: SplitResult) -> None:
    """Section B — USC band amounts per job to enter on ros.ie."""
    section("B  ·  USC  — Universal Social Charge Bands")
    print(f"  {'Enter these on ros.ie → Divide tax credits → USC tab':>{W}}")

    for i, a in enumerate(split.allocations, 1):
        blank()
        print(f"  Job #{i}  —  {a.job.company_name}")
        divider("·")
        for b in a.usc_bands:
            row(f"  USC {b.rate:.1%}", eur(b.annual_amount))

    blank()
    print(f"  {'All income over €70,044 is chargeable at 8%':>{W}}")


def print_refund_section(refund: RefundSummary) -> None:
    """Section C — year-end refund or underpayment based on YTD totals."""
    section("C  ·  Year-End Estimate  — Refund or Amount Owed")

    blank()
    print(f"  {'YTD totals across all employments':>{W}}")
    blank()
    row("Total gross YTD", eur(refund.total_gross))
    blank()

    row("PAYE paid YTD", eur(refund.total_paye_paid))
    row("PAYE due on YTD gross", eur(refund.paye_due))
    row("→ PAYE result", result_label(refund.paye_result))
    blank()

    row("USC paid YTD", eur(refund.total_usc_paid))
    row("USC due on YTD gross", eur(refund.usc_due))
    row("→ USC result", result_label(refund.usc_result))
    blank()

    row("PRSI paid YTD", eur(refund.total_prsi_paid))
    row("PRSI due on YTD gross", eur(refund.prsi_due))
    row("→ PRSI result", result_label(refund.prsi_result))
    blank()

    divider()
    row("★ OVERALL RESULT", result_label(refund.total_result))
    blank()
    print("  WARNING  Estimate only. Final result depends on full-year income")
    print("     and any credits/reliefs claimed on your tax return.")
    print("  WARNING  Rate band assumes single assessment (€44,000).")
    print("     Married couples assessed jointly may have a higher rate band.")
    blank()


# menu flows


@contextmanager
def tee_stdout():
    """Prints to screen AND captures output at the same time."""
    buf = io.StringIO()
    old = sys.stdout

    class Tee:
        def write(self, s):
            old.write(s)
            buf.write(s)

        def flush(self):
            old.flush()

    sys.stdout = Tee()
    try:
        yield buf
    finally:
        sys.stdout = old


def ask_save(content: str) -> None:
    """Asks the user if they want to save, and writes a .txt file."""
    blank()
    answer = input("  Save results to file? (y/n): ").strip().lower()
    if answer == "y":
        filename = f"tax_result_{date.today()}.txt"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"\n  ✓  Saved to: {filename}")
        blank()


def flow_split() -> None:
    num_jobs, tax_credits = collect_base_info()
    jobs = collect_jobs_basic(num_jobs)
    split = calculate_split(jobs, tax_credits)

    input("\n  Press Enter to see results...")
    with tee_stdout() as buf:
        header("Results")
        print_paye_tab(split)
        print_usc_tab(split)
    ask_save(buf.getvalue())


def flow_refund() -> None:
    num_jobs, tax_credits = collect_base_info()
    jobs = collect_jobs_with_ytd(num_jobs, need_proportion=False)
    refund = calculate_refund(jobs, tax_credits)

    input("\n  Press Enter to see results...")
    with tee_stdout() as buf:
        header("Results")
        print_refund_section(refund)
    ask_save(buf.getvalue())


def flow_both() -> None:
    num_jobs, tax_credits = collect_base_info()
    jobs = collect_jobs_with_ytd(num_jobs, need_proportion=True)
    split = calculate_split(jobs, tax_credits)
    refund = calculate_refund(jobs, tax_credits)

    input("\n  Press Enter to see results...")
    with tee_stdout() as buf:
        header("Results")
        print_paye_tab(split)
        print_usc_tab(split)
        print_refund_section(refund)
    ask_save(buf.getvalue())


def main() -> bool:
    """Returns False if the user chose to quit, True otherwise."""
    header("Irish Revenue Tax Split Calculator  ·  2026")

    blank()
    print("  What do you want to do?")
    blank()
    print("    1. Split tax credits across jobs      (ros.ie allocation)")
    print("    2. Estimate year-end refund / owed    (YTD figures needed)")
    print("    3. Both")
    print("    0. Quit")
    blank()

    choice = ask_menu()

    if choice == "0":
        blank()
        print("  Goodbye!")
        blank()
        return False

    try:
        if choice == "1":
            flow_split()
        elif choice == "2":
            flow_refund()
        else:
            flow_both()
    except (ValueError, TypeError) as e:
        blank()
        print(f"  ✗  Invalid input: {e}")
        print("     Please restart and check your entries.")
        blank()
    except KeyboardInterrupt:
        blank()
        print("  Cancelled.")
        blank()

    return True


def run() -> None:
    """Keeps the program running until the user decides to quit."""
    while True:
        quit_requested = main() is False
        if quit_requested:
            break
        blank()
        again = input("  Run again? (y/n): ").strip().lower()
        if again != "y":
            blank()
            print("  Goodbye!")
            blank()
            break


if __name__ == "__main__":
    run()
