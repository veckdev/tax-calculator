"""
tax_calculator.py — Core logic for the Revenue Tax Split Calculator.

Two public functions:
  calculate_split()   → proportionally divides PAYE rate band, tax credits
                        and USC bands across jobs (what to enter on ros.ie)
  calculate_refund()  → estimates year-end refund or amount owed, based on
                        YTD figures from ros.ie (same method as the P21)

Tax year: 2026
"""

from dataclasses import dataclass, field


# 2026 Irish tax constants (Budget 2026, effective 1 Jan 2026)

PAYE_STANDARD_RATE      = 0.20
PAYE_HIGHER_RATE        = 0.40
PAYE_STANDARD_RATE_BAND = 44_000.00

USC_BANDS: list[tuple[float, float]] = [
    (12_012.00, 0.005),
    (16_688.00, 0.020),  # ceiling raised to €28,700 (was €27,382 in 2025)
    (41_344.00, 0.030),
    (float("inf"), 0.080),
]
USC_EXEMPTION_THRESHOLD = 13_000.00

# PRSI Class A: 4.2% Jan–Sep 2026, rising to 4.35% from 1 Oct 2026.
# Year-end estimates use 4.2% (full-year blended rate is ~4.24%, difference is minimal).
PRSI_RATE              = 0.042
PRSI_WEEKLY_EXEMPT     = 352.00
PRSI_TAPER_UPPER       = 424.00
PRSI_MAX_WEEKLY_CREDIT = 12.00
WEEKS_PER_YEAR         = 52


# data classes

@dataclass
class YTDData:
    """YTD figures pulled from ros.ie → PAYE Services → Overview."""
    gross_pay:       float
    income_tax_paid: float
    usc_paid:        float
    prsi_paid:       float

    @property
    def total_tax_paid(self) -> float:
        return self.income_tax_paid + self.usc_paid + self.prsi_paid


@dataclass
class Job:
    """A single employment."""
    company_name:    str
    hours_per_week:  float
    salary_per_hour: float
    ytd:             YTDData
    estimated_annual_income: float = field(init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.hours_per_week, (int, float)):
            raise TypeError(f"'hours_per_week' must be a number, not text.")
        if not isinstance(self.salary_per_hour, (int, float)):
            raise TypeError(f"'salary_per_hour' must be a number, not text.")
        self.estimated_annual_income = (
            self.hours_per_week * self.salary_per_hour * WEEKS_PER_YEAR
        )


@dataclass
class UscBandAllocation:
    """One USC band allocated to a single job."""
    rate:          float
    annual_amount: float


@dataclass
class JobAllocation:
    """Proportional allowance split for one job — what to enter on ros.ie."""
    job:                   Job
    proportion:            float
    allocated_rate_band:   float
    allocated_tax_credits: float
    usc_bands:             list[UscBandAllocation]


@dataclass
class SplitResult:
    """Output of calculate_split() — one allocation per job."""
    jobs:                list[Job]
    total_annual_income: float
    total_tax_credits:   float
    allocations:         list[JobAllocation]


@dataclass
class RefundSummary:
    """
    Output of calculate_refund() — year-end estimate based on YTD totals.
    Mirrors the Revenue P21 Statement of Liability calculation.
    Positive result = refund. Negative = amount owed to Revenue.
    """
    total_gross:     float
    total_paye_paid: float
    total_usc_paid:  float
    total_prsi_paid: float
    paye_due:        float
    usc_due:         float
    prsi_due:        float

    @property
    def paye_result(self) -> float:
        return self.total_paye_paid - self.paye_due

    @property
    def usc_result(self) -> float:
        return self.total_usc_paid - self.usc_due

    @property
    def prsi_result(self) -> float:
        return self.total_prsi_paid - self.prsi_due

    @property
    def total_result(self) -> float:
        return self.paye_result + self.usc_result + self.prsi_result

    @property
    def is_refund(self) -> bool:
        return self.total_result > 0


# input validation

def _require_str(value: object, field_name: str) -> str:
    """Ensures value is a non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise TypeError(f"'{field_name}' must be a non-empty string.")
    if all(ch.isdigit() or ch in " .,-" for ch in value.strip()):
        raise ValueError(f"'{field_name}' looks like a number — expected a name.")
    return value.strip()


def _require_positive_float(value: object, field_name: str) -> float:
    """Ensures value is a number greater than zero."""
    if isinstance(value, str):
        raise TypeError(f"'{field_name}' must be a number, not text.")
    try:
        v = float(value)  # type: ignore
    except (TypeError, ValueError):
        raise TypeError(f"'{field_name}' must be a numeric value.")
    if v <= 0:
        raise ValueError(f"'{field_name}' must be greater than zero.")
    return v


def _require_non_negative_float(value: object, field_name: str) -> float:
    """Ensures value is a number >= 0 (used for YTD fields that can be 0)."""
    if isinstance(value, str):
        raise TypeError(f"'{field_name}' must be a number, not text.")
    try:
        v = float(value)  # type: ignore
    except (TypeError, ValueError):
        raise TypeError(f"'{field_name}' must be a numeric value.")
    if v < 0:
        raise ValueError(f"'{field_name}' cannot be negative.")
    return v


def _validate_jobs(jobs: list[Job]) -> None:
    """Checks the jobs list and each job's fields before any calculation."""
    if not isinstance(jobs, list) or len(jobs) == 0:
        raise ValueError("At least one job is required.")

    for i, job in enumerate(jobs, 1):
        label = f"Job #{i}"
        _require_str(job.company_name, f"{label} company_name")
        _require_positive_float(job.hours_per_week,  f"{label} hours_per_week")
        _require_positive_float(job.salary_per_hour, f"{label} salary_per_hour")
        _require_non_negative_float(job.ytd.gross_pay,       f"{label} YTD gross_pay")
        _require_non_negative_float(job.ytd.income_tax_paid, f"{label} YTD income_tax_paid")
        _require_non_negative_float(job.ytd.usc_paid,        f"{label} YTD usc_paid")
        _require_non_negative_float(job.ytd.prsi_paid,       f"{label} YTD prsi_paid")


# internal tax helpers

def _usc_on_income(income: float) -> float:
    """Calculates total USC liability using 2025 progressive bands."""
    if income <= USC_EXEMPTION_THRESHOLD:
        return 0.0
    total, remaining = 0.0, income
    for band_size, rate in USC_BANDS:
        if remaining <= 0:
            break
        taxable = min(remaining, band_size)
        total += taxable * rate
        remaining -= taxable
    return total


def _split_usc_bands(total_income: float, proportion: float) -> list[UscBandAllocation]:
    """Splits USC band amounts proportionally for one job."""
    bands: list[UscBandAllocation] = []
    remaining = total_income
    for band_size, rate in USC_BANDS:
        if remaining <= 0:
            break
        taxable = min(remaining, band_size)
        allocated = taxable * proportion
        if allocated > 0:
            bands.append(UscBandAllocation(rate=rate, annual_amount=allocated))
        remaining -= taxable
    return bands


def _prsi_on_income(gross: float) -> float:
    """PRSI Class A — 4.2% with tapered weekly credit."""
    weekly = gross / WEEKS_PER_YEAR
    if weekly <= PRSI_WEEKLY_EXEMPT:
        return 0.0
    annual = gross * PRSI_RATE
    if weekly <= PRSI_TAPER_UPPER:
        taper = (weekly - PRSI_WEEKLY_EXEMPT) / (PRSI_TAPER_UPPER - PRSI_WEEKLY_EXEMPT)
        annual = max(annual - PRSI_MAX_WEEKLY_CREDIT * (1 - taper) * WEEKS_PER_YEAR, 0.0)
    return annual


def _paye_on_income(gross: float, credits: float) -> float:
    """PAYE on total gross minus credits — same method Revenue uses in the P21."""
    if gross <= PAYE_STANDARD_RATE_BAND:
        gross_tax = gross * PAYE_STANDARD_RATE
    else:
        gross_tax = (
            PAYE_STANDARD_RATE_BAND * PAYE_STANDARD_RATE
            + (gross - PAYE_STANDARD_RATE_BAND) * PAYE_HIGHER_RATE
        )
    return max(gross_tax - credits, 0.0)


# public functions

def calculate_split(
    jobs:          list[Job],
    annual_income: float,
    tax_credits:   float,
) -> SplitResult:
    """
    Splits PAYE rate band, tax credits and USC bands across jobs.
    Proportion is based on estimated annual income (hours × rate × 52).
    Returns what the user should enter on ros.ie → Divide tax credits.
    """
    _validate_jobs(jobs)
    _require_positive_float(annual_income, "annual_income")
    _require_positive_float(tax_credits,   "tax_credits")

    total_estimated = sum(j.estimated_annual_income for j in jobs)
    allocations: list[JobAllocation] = []

    for job in jobs:
        proportion = job.estimated_annual_income / total_estimated
        allocations.append(JobAllocation(
            job                   = job,
            proportion            = proportion,
            allocated_rate_band   = PAYE_STANDARD_RATE_BAND * proportion,
            allocated_tax_credits = tax_credits * proportion,
            usc_bands             = _split_usc_bands(annual_income, proportion),
        ))

    return SplitResult(
        jobs                = jobs,
        total_annual_income = annual_income,
        total_tax_credits   = tax_credits,
        allocations         = allocations,
    )


def calculate_refund(
    jobs:        list[Job],
    tax_credits: float,
) -> RefundSummary:
    """
    Estimates the year-end refund or underpayment using YTD totals.
    Sums gross and tax paid across all jobs, then compares against
    what should have been paid — same logic as the Revenue P21.
    """
    _validate_jobs(jobs)
    _require_positive_float(tax_credits, "tax_credits")

    total_gross     = sum(j.ytd.gross_pay        for j in jobs)
    total_paye_paid = sum(j.ytd.income_tax_paid  for j in jobs)
    total_usc_paid  = sum(j.ytd.usc_paid         for j in jobs)
    total_prsi_paid = sum(j.ytd.prsi_paid        for j in jobs)

    return RefundSummary(
        total_gross     = total_gross,
        total_paye_paid = total_paye_paid,
        total_usc_paid  = total_usc_paid,
        total_prsi_paid = total_prsi_paid,
        paye_due        = _paye_on_income(total_gross, tax_credits),
        usc_due         = _usc_on_income(total_gross),
        prsi_due        = _prsi_on_income(total_gross),
    )