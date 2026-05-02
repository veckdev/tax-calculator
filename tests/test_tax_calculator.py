"""
test_tax_calculator.py — Tests for tax_calculator.py

Run with: python -m unittest test_tax_calculator -v
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tax_calculator import (
    Job, YTDData, calculate_split, calculate_refund,
    _usc_on_income, _prsi_on_income, _paye_on_income,
    PAYE_STANDARD_RATE_BAND,
)


# helpers

def make_job(name="Acme Ltd", hours=20.0, rate=15.0, ytd=None) -> Job:
    if ytd is None:
        ytd = YTDData(gross_pay=0, income_tax_paid=0, usc_paid=0, prsi_paid=0)
    return Job(company_name=name, hours_per_week=hours, salary_per_hour=rate, ytd=ytd)


def make_ytd(gross=0.0, paye=0.0, usc=0.0, prsi=0.0) -> YTDData:
    return YTDData(gross_pay=gross, income_tax_paid=paye, usc_paid=usc, prsi_paid=prsi)


class TestJobEstimatedIncome(unittest.TestCase):

    def test_estimated_annual_income(self):
        job = make_job(hours=24, rate=14.80)
        self.assertAlmostEqual(job.estimated_annual_income, 24 * 14.80 * 52, places=2)

    def test_estimated_annual_income_part_time(self):
        job = make_job(hours=20, rate=14.80)
        self.assertAlmostEqual(job.estimated_annual_income, 20 * 14.80 * 52, places=2)


class TestJobTypeGuards(unittest.TestCase):

    def test_rejects_text_in_hours(self):
        with self.assertRaises(TypeError):
            make_job(hours="twenty")

    def test_rejects_text_in_rate(self):
        with self.assertRaises(TypeError):
            make_job(rate="fifteen")

    def test_allows_numbers_in_company_name(self):
        job = make_job(name="7-Eleven Ireland Ltd")
        self.assertEqual(job.company_name, "7-Eleven Ireland Ltd")

    def test_allows_normal_company_name(self):
        job = make_job(name="Allpro Security Services Ireland Ltd")
        self.assertEqual(job.company_name, "Allpro Security Services Ireland Ltd")


class TestCalculateSplitProportions(unittest.TestCase):

    def setUp(self):
        self.jobs = [make_job("Allpro", 24, 14.80), make_job("Cagney", 20, 14.80)]
        self.result = calculate_split(self.jobs, annual_income=44000, tax_credits=5000)

    def test_proportions_are_correct(self):
        self.assertAlmostEqual(self.result.allocations[0].proportion, 24 / 44, places=4)
        self.assertAlmostEqual(self.result.allocations[1].proportion, 20 / 44, places=4)

    def test_proportions_sum_to_one(self):
        total = sum(a.proportion for a in self.result.allocations)
        self.assertAlmostEqual(total, 1.0, places=10)

    def test_rate_band_sums_to_44000(self):
        total = sum(a.allocated_rate_band for a in self.result.allocations)
        self.assertAlmostEqual(total, PAYE_STANDARD_RATE_BAND, places=2)

    def test_rate_band_matches_ros_ie(self):
        """Real case: 24h + 20h at €14.80 → €24,000 / €20,000"""
        self.assertAlmostEqual(self.result.allocations[0].allocated_rate_band, 24000.00, places=2)
        self.assertAlmostEqual(self.result.allocations[1].allocated_rate_band, 20000.00, places=2)

    def test_tax_credits_sum_to_total(self):
        total = sum(a.allocated_tax_credits for a in self.result.allocations)
        self.assertAlmostEqual(total, 5000.00, places=2)

    def test_usc_bands_sum_to_proportional_income(self):
        for alloc in self.result.allocations:
            band_total = sum(b.annual_amount for b in alloc.usc_bands)
            expected = 44000 * alloc.proportion
            self.assertAlmostEqual(band_total, expected, places=2)


class TestPAYE(unittest.TestCase):

    def test_all_at_standard_rate(self):
        self.assertAlmostEqual(_paye_on_income(30000, 0), 30000 * 0.20, places=2)

    def test_with_credits(self):
        self.assertAlmostEqual(_paye_on_income(30000, 5000), 30000 * 0.20 - 5000, places=2)

    def test_credits_exceed_tax_returns_zero(self):
        self.assertEqual(_paye_on_income(10000, 99999), 0.0)

    def test_higher_rate_band(self):
        gross = 60000
        expected = 44000 * 0.20 + (60000 - 44000) * 0.40
        self.assertAlmostEqual(_paye_on_income(gross, 0), expected, places=2)


class TestUSC(unittest.TestCase):

    def test_exempt_below_threshold(self):
        self.assertEqual(_usc_on_income(13000), 0.0)

    def test_just_above_threshold(self):
        self.assertGreater(_usc_on_income(13001), 0)

    def test_known_value(self):
        # €34,228.20 — crosses into the 3% band (2026: 0.5% up to €12,012, 2% up to €28,700, 3% above)
        expected = round(12012 * 0.005 + 16688 * 0.02 + (34228.20 - 28700) * 0.03, 2)
        self.assertAlmostEqual(_usc_on_income(34228.20), expected, places=2)


class TestPRSI(unittest.TestCase):

    def test_exempt_below_weekly_threshold(self):
        self.assertEqual(_prsi_on_income(352 * 52), 0.0)

    def test_above_threshold(self):
        self.assertGreater(_prsi_on_income(20000), 0)

    def test_rate_above_taper(self):
        gross = 40000
        self.assertAlmostEqual(_prsi_on_income(gross), gross * 0.042, places=2)


class TestCalculateRefund(unittest.TestCase):

    def test_refund_when_overpaid(self):
        jobs = [make_job("A", 24, 14.80, make_ytd(gross=10000, paye=2000, usc=200, prsi=400))]
        result = calculate_refund(jobs, tax_credits=5000)
        self.assertGreater(result.paye_result, 0)
        self.assertTrue(result.is_refund)

    def test_underpayment_when_paid_too_little(self):
        jobs = [make_job("A", 40, 30.0, make_ytd(gross=50000, paye=100, usc=100, prsi=100))]
        result = calculate_refund(jobs, tax_credits=100)
        self.assertLess(result.total_result, 0)
        self.assertFalse(result.is_refund)

    def test_usc_result_three_jobs(self):
        """USC result for 3-job scenario with 2025 YTD figures recalculated against 2026 bands."""
        jobs = [
            make_job("Apleona", 15, 14.74, make_ytd(11499.00, 674.51, 201.08, 483.96)),
            make_job("Cagney",  20, 14.80, make_ytd(3052.20,  146.64,  62.71, 128.19)),
            make_job("Allpro",  24, 14.80, make_ytd(19677.00, 789.52, 330.77, 826.43)),
        ]
        # Total gross: €34,228.20. USC paid: €594.56. USC due (2026 bands): €559.67. Result: +€34.89
        result = calculate_refund(jobs, tax_credits=5800)
        self.assertAlmostEqual(result.usc_result, 34.89, places=2)

    def test_ytd_totals_sum_across_jobs(self):
        jobs = [
            make_job("A", 24, 14.80, make_ytd(10000, 500, 100, 200)),
            make_job("B", 20, 14.80, make_ytd(5000,  200,  50, 100)),
        ]
        result = calculate_refund(jobs, tax_credits=5000)
        self.assertEqual(result.total_gross,     15000)
        self.assertEqual(result.total_paye_paid, 700)
        self.assertEqual(result.total_usc_paid,  150)
        self.assertEqual(result.total_prsi_paid, 300)


class TestValidation(unittest.TestCase):

    def test_split_raises_on_empty_jobs(self):
        with self.assertRaisesRegex(ValueError, "At least one job"):
            calculate_split([], 44000, 5000)

    def test_refund_raises_on_empty_jobs(self):
        with self.assertRaisesRegex(ValueError, "At least one job"):
            calculate_refund([], 5000)

    def test_split_raises_on_zero_income(self):
        with self.assertRaises(ValueError):
            calculate_split([make_job()], annual_income=0, tax_credits=5000)

    def test_split_raises_on_negative_credits(self):
        with self.assertRaises(ValueError):
            calculate_split([make_job()], annual_income=44000, tax_credits=-100)

    def test_refund_raises_on_negative_ytd(self):
        jobs = [make_job(ytd=make_ytd(gross=-1))]
        with self.assertRaises(ValueError):
            calculate_refund(jobs, tax_credits=5000)

    def test_split_raises_on_text_in_income(self):
        with self.assertRaises((TypeError, ValueError)):
            calculate_split([make_job()], annual_income="lots", tax_credits=5000)

    def test_split_raises_on_empty_company_name(self):
        with self.assertRaises(TypeError):
            calculate_split([make_job(name="")], 44000, 5000)

    def test_split_raises_on_numeric_only_company_name(self):
        with self.assertRaises(ValueError):
            calculate_split([make_job(name="12345")], 44000, 5000)


if __name__ == "__main__":
    unittest.main()