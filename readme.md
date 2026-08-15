# BDM Visit Assistant

A simple field-sales tool for BDMs managing retail outlets across Tamil Nadu.

The goal is to help a BDM answer three questions:

1. Which outlet should I visit?
2. Why should I visit it?
3. What should I discuss when I get there?

The app also gives managers a simple view of completed visits and their outcomes.

---

## What the App Does

### BDM View

A BDM can:

- See outlets assigned to their territory
- See High, Medium, and Low priority outlets
- Understand why an outlet needs attention
- Review recent billing and visit history
- Use a short checklist based on outlet type
- Start and complete a visit
- Record the blocker, agreed action, payment, order, and follow-up

### Manager View

A manager can see:

- Completed visits
- BDM visit activity
- Payments collected
- Orders recorded
- Follow-ups required
- High-priority outlet coverage
- Recent visit outcomes

---

## How to Run

### Requirements

- Python 3.10+
- pip

Install the dependencies:

```bash
pip install -r requirements.txt
```

Start the app:

```bash
python -m streamlit run app/dashboard.py
```

Then open the local Streamlit URL shown in the terminal.

### Live Demo

> Streamlit link will be added here.

---

## Priority Logic

Each outlet receives a priority score out of **100**.

| Factor | Maximum Points |
|---|---:|
| Activity / billing risk | 40 |
| Business value | 30 |
| Time since last visit | 30 |
| **Total** | **100** |

Priority labels:

- **High:** 70–100
- **Medium:** 40–69
- **Low:** 0–39

### Activity

Billing behaviour is used to classify outlets as:

- **Active** — billing normally
- **Declining** — billing fell by at least 30% from the previous month
- **Dormant** — previously billed but has not billed for at least 2 months
- **No Recent Billing** — no billing in the available six-month data

### Business Value

Business value is based on average monthly billing.

Outlets are compared with other outlets in the same territory:

- Top 25% → High Value
- Middle 50% → Medium Value
- Bottom 25% → Low Value
- No billing → No Billing

This avoids using one fixed sales value across territories with different sales volumes.

---

## Key Assumptions

The task was intentionally open-ended, so I made a few MVP assumptions:

- `Outlet Code` is the main outlet identifier.
- `BDM Code` is the main BDM identifier.
- Outlet towns are normalized before matching them to BDM territories.
- Current BDM assignment comes from the BDM territory and normalized outlet town.
- Missing billing for a month is treated as zero billing.
- Billing behaviour is used to derive current outlet activity instead of relying only on the outlet master status.
- A 30% billing drop is treated as a significant decline.
- Two months without billing is treated as dormant.
- Historical visit logs are used for visit history.
- Priority rules are MVP assumptions and should be validated with the sales team.

---

## What I Left Out

To keep the solution within the scope of the assignment, I did not build:

- User authentication
- GPS or location verification
- Route optimization
- A production database
- Notifications
- Predictive ML or AI models
- Modern UI

Visit outcomes are stored in a local CSV for the MVP.

On Streamlit Community Cloud, this storage is temporary and may reset when the application restarts or redeploys.

---

## What I Would Do Next

With more time, I would:

1. Talk to BDMs and managers and validate the priority rules and visit workflow.
2. Move visit outcomes to a database such as PostgreSQL.
3. Add location verification for outlet visits.
4. Add weekly beat planning and route suggestions.
5. Add follow-up reminders and manager alerts.
6. Improvise the UI. 
7. Implement a mobile version of the app

---

## Tech Stack

- Python
- Pandas
- Streamlit
- CSV data storage

---

## AI Usage

AI tools were used during development.

See [`AI-USAGE.md`](AI-USAGE.md) for details.