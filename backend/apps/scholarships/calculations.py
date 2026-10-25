"""Totals for the AU Need Based Financial Grant form. Always computed on the server;
values sent by the browser are never trusted. All amounts are whole rupees.

Agreed rules:
- Q25.1 total monthly income = net (take-home) pay of earning members + applicant net pay
  + monthly asset income (Q24.1). Q25.2 = Q25.1 x 12.
- Q29 education expenditure = Q11.1 (fees of family members studying).
- Q27 utilities = average of the months entered (up to the last three).
- Q30 monthly disposable = Q25.1 - Q29 monthly total. Q31 annual = Q30 x 12.
"""


def _sum(values):
    return sum(v or 0 for v in values)


def _grid_totals(rows, columns):
    column_totals = {c: _sum(getattr(r, c) for r in rows) for c in columns}
    return {
        'rows': {r.source if hasattr(r, 'source') else r.title: r.total for r in rows},
        'columns': column_totals,
        'total': sum(column_totals.values()),
    }


def summarize(app):
    earning = list(app.earning_members.all())
    studying = list(app.studying_members.all())
    utilities = list(app.utility_months.all())

    earning_gross = _sum(m.gross_pay for m in earning) + (app.applicant_gross_income or 0)  # Q10.1
    studying_fees = _sum(m.fee_per_month for m in studying)  # Q11.1

    asset_income = _grid_totals(list(app.asset_income.all()), ['father', 'mother', 'spouse', 'self_amount', 'other'])
    asset_worth = _grid_totals(list(app.asset_worth.all()), ['father', 'mother', 'spouse', 'self_amount', 'guardian'])

    net_pay = _sum(m.net_pay for m in earning) + (app.applicant_net_income or 0)
    monthly_income = net_pay + asset_income['total']  # Q25.1

    utilities_monthly = round(_sum(u.total for u in utilities) / len(utilities)) if utilities else 0
    accommodation_monthly = app.monthly_rent or 0
    expenditure = {
        'education': studying_fees,
        'accommodation': accommodation_monthly,
        'utilities': utilities_monthly,
        'medical': app.medical_monthly or 0,
        'misc': app.misc_monthly or 0,
    }
    monthly_expenditure = sum(expenditure.values())  # Q29 total
    monthly_disposable = monthly_income - monthly_expenditure  # Q30

    return {
        'total_family_earning_gross': earning_gross,
        'total_studying_fees': studying_fees,
        'asset_income': asset_income,
        'monthly_net_pay': net_pay,
        'monthly_asset_income': asset_income['total'],
        'total_monthly_income': monthly_income,
        'total_annual_income': monthly_income * 12,
        'accommodation_monthly_rent': accommodation_monthly,
        'accommodation_annual_rent': accommodation_monthly * 12,
        'utilities_monthly_average': utilities_monthly,
        'expenditure': expenditure,
        'total_monthly_expenditure': monthly_expenditure,
        'total_annual_expenditure': monthly_expenditure * 12,
        'net_monthly_disposable': monthly_disposable,
        'net_annual_disposable': monthly_disposable * 12,
        'asset_worth': asset_worth,
    }
