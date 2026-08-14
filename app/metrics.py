import pandas as pd

from data_loader import get_clean_data


# ==================================================
# BUSINESS RULES / MVP ASSUMPTIONS
# ==================================================

DECLINE_THRESHOLD_PCT = -30
DORMANT_MONTHS = 2

ACTIVITY_SCORES = {
    "Declining": 40,
    "Dormant": 35,
    "Active": 10,
    "No Recent Billing": 5,
}

VALUE_SCORES = {
    "High Value": 30,
    "Medium Value": 20,
    "Low Value": 10,
    "No Billing": 0,
}

VISIT_SCORE_30_PLUS_DAYS = 30
VISIT_SCORE_15_TO_29_DAYS = 20
VISIT_SCORE_7_TO_14_DAYS = 10
VISIT_SCORE_RECENT = 0

HIGH_PRIORITY_THRESHOLD = 70
MEDIUM_PRIORITY_THRESHOLD = 40


# ==================================================
# BILLING METRICS
# ==================================================

def create_billing_metrics(outlets, billing):
    """Create billing metrics for every outlet."""

    latest_month = billing["Month"].max()
    previous_month = latest_month - pd.offsets.MonthBegin(1)

    months = pd.date_range(
        start=billing["Month"].min(),
        end=latest_month,
        freq="MS",
    )

    # Create a complete Outlet × Month grid so missing
    # billing months are treated as zero activity.
    outlet_month_index = pd.MultiIndex.from_product(
        [
            outlets["Outlet Code"],
            months,
        ],
        names=[
            "Outlet Code",
            "Month",
        ],
    )

    monthly_billing = (
        billing
        .groupby(
            ["Outlet Code", "Month"]
        )[["Units", "Value"]]
        .sum()
        .reindex(
            outlet_month_index,
            fill_value=0,
        )
        .reset_index()
    )

    latest_metrics = (
        monthly_billing[
            monthly_billing["Month"] == latest_month
        ][
            [
                "Outlet Code",
                "Units",
                "Value",
            ]
        ]
        .rename(
            columns={
                "Units": "Latest_Units",
                "Value": "Latest_Billing",
            }
        )
    )

    previous_metrics = (
        monthly_billing[
            monthly_billing["Month"] == previous_month
        ][
            [
                "Outlet Code",
                "Units",
                "Value",
            ]
        ]
        .rename(
            columns={
                "Units": "Previous_Units",
                "Value": "Previous_Billing",
            }
        )
    )

    aggregate_metrics = (
        monthly_billing
        .groupby("Outlet Code")
        .agg(
            Total_6M_Billing=(
                "Value",
                "sum",
            ),
            Average_Monthly_Billing=(
                "Value",
                "mean",
            ),
            Months_With_Billing=(
                "Value",
                lambda values: (values > 0).sum(),
            ),
        )
        .reset_index()
    )

    aggregate_metrics["Has_Billing_History"] = (
        aggregate_metrics["Months_With_Billing"] > 0
    )

    last_billing = (
        monthly_billing[
            monthly_billing["Value"] > 0
        ]
        .groupby("Outlet Code")["Month"]
        .max()
        .reset_index()
        .rename(
            columns={
                "Month": "Last_Billing_Month",
            }
        )
    )

    metrics = (
        outlets[
            ["Outlet Code"]
        ]
        .merge(
            latest_metrics,
            on="Outlet Code",
            how="left",
        )
        .merge(
            previous_metrics,
            on="Outlet Code",
            how="left",
        )
        .merge(
            aggregate_metrics,
            on="Outlet Code",
            how="left",
        )
        .merge(
            last_billing,
            on="Outlet Code",
            how="left",
        )
    )

    def calculate_change(row):
        previous = row["Previous_Billing"]
        latest = row["Latest_Billing"]

        if previous > 0:
            return (
                (latest - previous)
                / previous
            ) * 100

        if previous == 0 and latest == 0:
            return 0

        # Growth from zero is undefined.
        return None

    metrics["Billing_Change_Pct"] = (
        metrics.apply(
            calculate_change,
            axis=1,
        )
    )

    def months_since_last_billing(date):
        if pd.isna(date):
            return None

        return (
            (latest_month.year - date.year) * 12
            + latest_month.month
            - date.month
        )

    metrics["Months_Since_Last_Billing"] = (
        metrics["Last_Billing_Month"]
        .apply(
            months_since_last_billing
        )
    )

    return metrics


# ==================================================
# VISIT METRICS
# ==================================================

def create_visit_metrics(outlets, visits):
    """Create historical visit metrics for every outlet."""

    latest_visit_date = visits["Visit Date"].max()

    reference_date = (
        latest_visit_date
        + pd.offsets.MonthEnd(0)
    )

    last_visit = (
        visits
        .groupby(
            "Outlet Code"
        )["Visit Date"]
        .max()
        .reset_index()
        .rename(
            columns={
                "Visit Date": "Last_Visit_Date",
            }
        )
    )

    visit_count = (
        visits
        .groupby(
            "Outlet Code"
        )
        .size()
        .reset_index(
            name="Visit_Count_3M"
        )
    )

    metrics = (
        outlets[
            ["Outlet Code"]
        ]
        .merge(
            last_visit,
            on="Outlet Code",
            how="left",
        )
        .merge(
            visit_count,
            on="Outlet Code",
            how="left",
        )
    )

    metrics["Visit_Count_3M"] = (
        metrics["Visit_Count_3M"]
        .fillna(0)
        .astype(int)
    )

    metrics["Days_Since_Last_Visit"] = (
        reference_date
        - metrics["Last_Visit_Date"]
    ).dt.days

    return metrics


# ==================================================
# ACTIVITY STATUS
# ==================================================

def assign_activity_status(row):
    """Classify outlet activity from recent billing behavior."""

    if not row["Has_Billing_History"]:
        return "No Recent Billing"

    if (
        row["Months_Since_Last_Billing"]
        >= DORMANT_MONTHS
    ):
        return "Dormant"

    if (
        row["Latest_Billing"] > 0
        and row["Previous_Billing"] > 0
        and row["Billing_Change_Pct"]
        <= DECLINE_THRESHOLD_PCT
    ):
        return "Declining"

    return "Active"


# ==================================================
# BUSINESS VALUE
# ==================================================

def assign_value_tier(group):
    """Assign value tier relative to other billing outlets in a territory."""

    group = group.copy()

    billing_outlets = group[
        group["Average_Monthly_Billing"] > 0
    ]

    if billing_outlets.empty:
        group["Value_Tier"] = "No Billing"
        group["Value_Score"] = VALUE_SCORES[
            "No Billing"
        ]
        return group

    q25 = billing_outlets[
        "Average_Monthly_Billing"
    ].quantile(0.25)

    q75 = billing_outlets[
        "Average_Monthly_Billing"
    ].quantile(0.75)

    def classify(value):
        if value <= 0:
            return pd.Series(
                [
                    "No Billing",
                    VALUE_SCORES[
                        "No Billing"
                    ],
                ]
            )

        if value >= q75:
            return pd.Series(
                [
                    "High Value",
                    VALUE_SCORES[
                        "High Value"
                    ],
                ]
            )

        if value <= q25:
            return pd.Series(
                [
                    "Low Value",
                    VALUE_SCORES[
                        "Low Value"
                    ],
                ]
            )

        return pd.Series(
            [
                "Medium Value",
                VALUE_SCORES[
                    "Medium Value"
                ],
            ]
        )

    group[
        [
            "Value_Tier",
            "Value_Score",
        ]
    ] = (
        group[
            "Average_Monthly_Billing"
        ]
        .apply(classify)
    )

    return group


# ==================================================
# PRIORITY SCORING
# ==================================================

def calculate_activity_score(status):
    """Return activity-risk contribution to priority score."""

    return ACTIVITY_SCORES.get(
        status,
        0,
    )


def calculate_visit_score(days_since_visit):
    """Return visit-recency contribution to priority score."""

    if pd.isna(days_since_visit):
        return VISIT_SCORE_30_PLUS_DAYS

    if days_since_visit >= 30:
        return VISIT_SCORE_30_PLUS_DAYS

    if days_since_visit >= 15:
        return VISIT_SCORE_15_TO_29_DAYS

    if days_since_visit >= 7:
        return VISIT_SCORE_7_TO_14_DAYS

    return VISIT_SCORE_RECENT


def assign_priority_label(score):
    """Convert numeric priority score into a simple label."""

    if score >= HIGH_PRIORITY_THRESHOLD:
        return "High"

    if score >= MEDIUM_PRIORITY_THRESHOLD:
        return "Medium"

    return "Low"


# ==================================================
# RECOMMENDATION REASON
# ==================================================

def generate_recommendation_reason(row):
    """Create a short BDM-facing explanation for the outlet ranking."""

    reasons = []

    if row["Value_Tier"] == "High Value":
        reasons.append(
            "High-value outlet"
        )

    if row["Activity_Status"] == "Declining":
        change = abs(
            row["Billing_Change_Pct"]
        )

        reasons.append(
            f"billing down "
            f"{change:.0f}% "
            f"vs last month"
        )

    elif row["Activity_Status"] == "Dormant":
        months = int(
            row[
                "Months_Since_Last_Billing"
            ]
        )

        reasons.append(
            f"no billing for "
            f"{months} months"
        )

    elif (
        row["Activity_Status"]
        == "No Recent Billing"
    ):
        reasons.append(
            "no billing in the last 6 months"
        )

    days = row[
        "Days_Since_Last_Visit"
    ]

    if pd.isna(days):
        reasons.append(
            "no recorded visit"
        )

    elif days >= 15:
        reasons.append(
            f"last visited "
            f"{int(days)} days ago"
        )

    if not reasons:
        return (
            "Regular account follow-up"
        )

    return " • ".join(
        reasons
    )


# ==================================================
# FINAL OUTLET METRICS
# ==================================================

def create_outlet_metrics():
    """Create the final outlet-level dataset used by the application."""

    data = get_clean_data()

    outlets = data["outlets"]
    billing = data["billing"]
    visits = data["visits"]

    billing_metrics = (
        create_billing_metrics(
            outlets,
            billing,
        )
    )

    visit_metrics = (
        create_visit_metrics(
            outlets,
            visits,
        )
    )

    outlet_metrics = (
        outlets.copy()
    )

    outlet_metrics = (
        outlet_metrics.merge(
            billing_metrics,
            on="Outlet Code",
            how="left",
        )
    )

    outlet_metrics = (
        outlet_metrics.merge(
            visit_metrics,
            on="Outlet Code",
            how="left",
        )
    )

    outlet_metrics[
        "Activity_Status"
    ] = (
        outlet_metrics.apply(
            assign_activity_status,
            axis=1,
        )
    )

    # Business value is calculated within territory.
    territory_groups = []

    for _, group in (
        outlet_metrics.groupby(
            "Town_Normalized"
        )
    ):
        territory_groups.append(
            assign_value_tier(
                group
            )
        )

    outlet_metrics = pd.concat(
        territory_groups,
        ignore_index=True,
    )

    outlet_metrics[
        "Activity_Score"
    ] = (
        outlet_metrics[
            "Activity_Status"
        ]
        .apply(
            calculate_activity_score
        )
    )

    outlet_metrics[
        "Visit_Score"
    ] = (
        outlet_metrics[
            "Days_Since_Last_Visit"
        ]
        .apply(
            calculate_visit_score
        )
    )

    outlet_metrics[
        "Priority_Score"
    ] = (
        outlet_metrics[
            "Activity_Score"
        ]
        + outlet_metrics[
            "Value_Score"
        ]
        + outlet_metrics[
            "Visit_Score"
        ]
    )

    outlet_metrics[
        "Priority_Label"
    ] = (
        outlet_metrics[
            "Priority_Score"
        ]
        .apply(
            assign_priority_label
        )
    )

    outlet_metrics[
        "Recommendation_Reason"
    ] = (
        outlet_metrics.apply(
            generate_recommendation_reason,
            axis=1,
        )
    )

    return outlet_metrics