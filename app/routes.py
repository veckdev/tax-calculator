from flask import Blueprint, render_template, request
from tax_calculator import (
    Job,
    YTDData,
    calculate_split,
    calculate_refund,
)

main = Blueprint("main", __name__)


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/jobs", methods=["POST"])
def jobs():
    try:
        num_jobs = int(request.form["num_jobs"])
        tax_credits = float(request.form["tax_credits"])
        mode = request.form["mode"]
    except (ValueError, KeyError):
        return render_template(
            "error.html", message="Invalid setup data. Please go back and try again."
        )

    return render_template(
        "jobs.html",
        num_jobs=num_jobs,
        tax_credits=tax_credits,
        mode=mode,
    )


@main.route("/results", methods=["POST"])
def results():
    try:
        tax_credits = float(request.form["tax_credits"])
        mode = request.form["mode"]
        num_jobs = sum(1 for k in request.form if k.startswith("company_"))

        jobs = []
        for i in range(1, num_jobs + 1):
            company = request.form.get(f"company_{i}", "").strip()
            if not company:
                return render_template(
                    "error.html", message=f"Company name for job #{i} cannot be empty."
                )

            ytd = YTDData(
                gross_pay=float(request.form.get(f"gross_{i}", 0) or 0),
                income_tax_paid=float(request.form.get(f"paye_{i}", 0) or 0),
                usc_paid=float(request.form.get(f"usc_{i}", 0) or 0),
                prsi_paid=float(request.form.get(f"prsi_{i}", 0) or 0),
            )

            income_type = request.form.get(f"income_type_{i}", "hourly")
            if income_type == "salary":
                salary = float(request.form.get(f"salary_{i}", 0) or 0)
                if mode in ["split", "both"] and salary <= 0:
                    return render_template(
                        "error.html",
                        message=f"Annual salary for job #{i} must be greater than zero.",
                    )
                job = Job(company_name=company, ytd=ytd, annual_salary=salary)
            else:
                hours = float(request.form.get(f"hours_{i}", 0) or 0)
                rate = float(request.form.get(f"rate_{i}", 0) or 0)
                if mode in ["split", "both"] and (hours <= 0 or rate <= 0):
                    return render_template(
                        "error.html",
                        message=f"Hours and rate for job #{i} must be greater than zero.",
                    )
                job = Job(
                    company_name=company,
                    ytd=ytd,
                    hours_per_week=hours,
                    salary_per_hour=rate,
                )

            jobs.append(job)

        split = (
            calculate_split(jobs, tax_credits) if mode in ["split", "both"] else None
        )
        refund = (
            calculate_refund(jobs, tax_credits) if mode in ["refund", "both"] else None
        )

    except (ValueError, TypeError) as e:
        return render_template("error.html", message=f"Something went wrong: {e}")

    return render_template(
        "results.html",
        mode=mode,
        tax_credits=tax_credits,
        split=split,
        refund=refund,
    )
