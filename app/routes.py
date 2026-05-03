from flask import Blueprint, render_template, request, session
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
    num_jobs = int(request.form["num_jobs"])
    tax_credits = float(request.form["tax_credits"])
    mode = request.form["mode"]

    return render_template(
        "jobs.html",
        num_jobs=num_jobs,
        tax_credits=tax_credits,
        mode=mode,
    )


@main.route("/results", methods=["POST"])
def results():
    tax_credits = float(request.form["tax_credits"])
    mode = request.form["mode"]
    num_jobs = sum(1 for k in request.form if k.startswith("company_"))

    jobs = []
    for i in range(1, num_jobs + 1):
        ytd = YTDData(
            gross_pay=float(request.form.get(f"gross_{i}", 0)),
            income_tax_paid=float(request.form.get(f"paye_{i}", 0)),
            usc_paid=float(request.form.get(f"usc_{i}", 0)),
            prsi_paid=float(request.form.get(f"prsi_{i}", 0)),
        )
        income_type = request.form.get(f"income_type_{i}", "hourly")
        if income_type == "salary":
            job = Job(
                company_name=request.form[f"company_{i}"],
                ytd=ytd,
                annual_salary=float(request.form.get(f"salary_{i}", 0)),
            )
        else:
            job = Job(
                company_name=request.form[f"company_{i}"],
                ytd=ytd,
                hours_per_week=float(request.form.get(f"hours_{i}", 0)),
                salary_per_hour=float(request.form.get(f"rate_{i}", 0)),
            )
        jobs.append(job)

    split = calculate_split(jobs, tax_credits) if mode in ["split", "both"] else None
    refund = calculate_refund(jobs, tax_credits) if mode in ["refund", "both"] else None

    return render_template(
        "results.html",
        mode=mode,
        tax_credits=tax_credits,
        split=split,
        refund=refund,
    )
