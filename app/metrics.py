import pandas as pd

from data_loader import get_clean_data


def create_billing_metrics(outlets, billing):

    # Latest month available in the dataset
    latest_month = billing["Month"].max()

    # Previous month
    previous_month = latest_month - pd.offsets.MonthBegin(1)

    # All months available in billing data
    months = pd.date_range(
        start=billing["Month"].min(),
        end=latest_month,
        freq="MS"
    )

    # --------------------------------------------------
    # Create every Outlet × Month combination
    # --------------------------------------------------
    # This makes missing billing months become zero.
    outlet_month_index = pd.MultiIndex.from_product(
        [
            outlets["Outlet Code"],
            months
        ],
        names=[
            "Outlet Code",
            "Month"
        ]
    )

    monthly_billing = (
        billing
        .groupby(
            ["Outlet Code", "Month"]
        )[["Units", "Value"]]
        .sum()
        .reindex(
            outlet_month_index,
            fill_value=0
        )
        .reset_index()
    )

    # --------------------------------------------------
    # Latest month
    # --------------------------------------------------

    latest_metrics = (
        monthly_billing[
            monthly_billing["Month"] == latest_month
        ][
            [
                "Outlet Code",
                "Units",
                "Value"
            ]
        ]
        .rename(
            columns={
                "Units": "Latest_Units",
                "Value": "Latest_Billing"
            }
        )
    )

    # --------------------------------------------------
    # Previous month
    # --------------------------------------------------

    previous_metrics = (
        monthly_billing[
            monthly_billing["Month"] == previous_month
        ][
            [
                "Outlet Code",
                "Units",
                "Value"
            ]
        ]
        .rename(
            columns={
                "Units": "Previous_Units",
                "Value": "Previous_Billing"
            }
        )
    )

    # --------------------------------------------------
    # 6-month aggregate metrics
    # --------------------------------------------------

    
    aggregate_metrics = (
    monthly_billing
    .groupby("Outlet Code")
    .agg(
        Total_6M_Billing=("Value", "sum"),
        Average_Monthly_Billing=("Value", "mean"),
        Months_With_Billing=(
            "Value",
            lambda values: (values > 0).sum()
        )
    )
    .reset_index()
)
# Whether the outlet has billed at least once
# during the available 6-month period
    aggregate_metrics["Has_Billing_History"] = (
        aggregate_metrics["Months_With_Billing"] > 0
    )
    # --------------------------------------------------
    # Last month where billing > 0
    # --------------------------------------------------

    last_billing = (
        monthly_billing[
            monthly_billing["Value"] > 0
        ]
        .groupby("Outlet Code")["Month"]
        .max()
        .reset_index()
        .rename(
            columns={
                "Month": "Last_Billing_Month"
            }
        )
    )

    # --------------------------------------------------
    # Combine billing metrics
    # --------------------------------------------------

    metrics = (
        outlets[["Outlet Code"]]
        .merge(
            latest_metrics,
            on="Outlet Code",
            how="left"
        )
        .merge(
            previous_metrics,
            on="Outlet Code",
            how="left"
        )
        .merge(
            aggregate_metrics,
            on="Outlet Code",
            how="left"
        )
        .merge(
            last_billing,
            on="Outlet Code",
            how="left"
        )
    )

    # --------------------------------------------------
    # Billing change %
    # --------------------------------------------------

    def calculate_change(row):

        previous = row["Previous_Billing"]
        latest = row["Latest_Billing"]

        if previous > 0:
            return (
                (latest - previous)
                / previous
            ) * 100

        # No billing in either month
        if previous == 0 and latest == 0:
            return 0

        # Previous = 0 and latest > 0
        # Percentage growth is undefined,
        # so leave it blank instead of pretending
        # it is 100%.
        return None

    metrics["Billing_Change_Pct"] = (
        metrics.apply(
            calculate_change,
            axis=1
        )
    )

    # --------------------------------------------------
    # Months since last billing
    # --------------------------------------------------

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


def create_visit_metrics(outlets, visits):

    # Use the end of the latest available visit month
    # instead of today's real date.
    latest_visit_date = visits["Visit Date"].max()

    reference_date = (
        latest_visit_date
        + pd.offsets.MonthEnd(0)
    )

    # --------------------------------------------------
    # Last visit
    # --------------------------------------------------

    last_visit = (
        visits
        .groupby("Outlet Code")["Visit Date"]
        .max()
        .reset_index()
        .rename(
            columns={
                "Visit Date": "Last_Visit_Date"
            }
        )
    )

    # --------------------------------------------------
    # Total visits in provided visit history
    # --------------------------------------------------

    visit_count = (
        visits
        .groupby("Outlet Code")
        .size()
        .reset_index(
            name="Visit_Count_3M"
        )
    )

    # --------------------------------------------------
    # Combine
    # --------------------------------------------------

    metrics = (
        outlets[["Outlet Code"]]
        .merge(
            last_visit,
            on="Outlet Code",
            how="left"
        )
        .merge(
            visit_count,
            on="Outlet Code",
            how="left"
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

def assign_activity_status(row):

    # No billing anywhere in available 6-month history
    if not row["Has_Billing_History"]:
        return "No Recent Billing"

    # Previously billed, but hasn't billed for 2+ months
    if row["Months_Since_Last_Billing"] >= 2:
        return "Dormant"

    # Currently billing but significantly below previous month
    if (
        row["Latest_Billing"] > 0
        and row["Previous_Billing"] > 0
        and row["Billing_Change_Pct"] <= -30
    ):
        return "Declining"

    return "Active"


def assign_value_tier(group):

    group = group.copy()

    billing_outlets = group[
        group["Average_Monthly_Billing"] > 0
    ]

    if billing_outlets.empty:
        group["Value_Score"] = 0
        group["Value_Tier"] = "No Billing"
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
                ["No Billing", 0]
            )

        if value >= q75:
            return pd.Series(
                ["High Value", 30]
            )

        if value <= q25:
            return pd.Series(
                ["Low Value", 10]
            )

        return pd.Series(
            ["Medium Value", 20]
        )

    group[
        ["Value_Tier", "Value_Score"]
    ] = group[
        "Average_Monthly_Billing"
    ].apply(classify)

    return group

def calculate_activity_score(status):

    scores = {
        "Declining": 40,
        "Dormant": 35,
        "Active": 10,
        "No Recent Billing": 5,
    }

    return scores.get(status, 0)


def calculate_visit_score(days_since_visit):

    # Never visited
    if pd.isna(days_since_visit):
        return 30

    if days_since_visit >= 30:
        return 30

    if days_since_visit >= 15:
        return 20

    if days_since_visit >= 7:
        return 10

    return 0


def assign_priority_label(score):

    if score >= 70:
        return "High"

    if score >= 40:
        return "Medium"

    return "Low"

def create_outlet_metrics():

    data = get_clean_data()

    outlets = data["outlets"]
    billing = data["billing"]
    visits = data["visits"]

    billing_metrics = create_billing_metrics(
        outlets,
        billing
    )

    visit_metrics = create_visit_metrics(
        outlets,
        visits
    )

    # Start with cleaned outlet master
    outlet_metrics = outlets.copy()

    # Add billing information
    outlet_metrics = outlet_metrics.merge(
        billing_metrics,
        on="Outlet Code",
        how="left"
    )

    # Add visit information
    outlet_metrics = outlet_metrics.merge(
        visit_metrics,
        on="Outlet Code",
        how="left"
    )
    
    outlet_metrics["Activity_Status"] = (
    outlet_metrics.apply(
        assign_activity_status,
        axis=1
    )
)
    
    # --------------------------------------------------
    # Business value within territory
    # --------------------------------------------------

    territory_groups = []

    for _, group in outlet_metrics.groupby("Town_Normalized"):
        territory_groups.append(
            assign_value_tier(group)
        )

    outlet_metrics = pd.concat(
        territory_groups,
        ignore_index=True
    )
        

    # --------------------------------------------------
    # Activity score
    # --------------------------------------------------

    outlet_metrics["Activity_Score"] = (
        outlet_metrics["Activity_Status"]
        .apply(calculate_activity_score)
    )

    # --------------------------------------------------
    # Visit recency score
    # --------------------------------------------------

    outlet_metrics["Visit_Score"] = (
        outlet_metrics["Days_Since_Last_Visit"]
        .apply(calculate_visit_score)
    )

    # --------------------------------------------------
    # Final priority score
    # --------------------------------------------------

    outlet_metrics["Priority_Score"] = (
        outlet_metrics["Activity_Score"]
        + outlet_metrics["Value_Score"]
        + outlet_metrics["Visit_Score"]
    )

    # --------------------------------------------------
    # Priority label
    # --------------------------------------------------

    outlet_metrics["Priority_Label"] = (
        outlet_metrics["Priority_Score"]
        .apply(assign_priority_label)
    )
    
    outlet_metrics["Recommendation_Reason"] = (
    outlet_metrics.apply(
        generate_recommendation_reason,
        axis=1
    )
)

    return outlet_metrics


def generate_recommendation_reason(row):

    reasons = []

    # --------------------------------------------------
    # Business value
    # --------------------------------------------------

    if row["Value_Tier"] == "High Value":
        reasons.append("High-value outlet")

    # --------------------------------------------------
    # Activity / billing
    # --------------------------------------------------

    if row["Activity_Status"] == "Declining":

        change = abs(row["Billing_Change_Pct"])

        reasons.append(
            f"billing down {change:.0f}% vs last month"
        )

    elif row["Activity_Status"] == "Dormant":

        months = int(
            row["Months_Since_Last_Billing"]
        )

        reasons.append(
            f"no billing for {months} months"
        )

    elif row["Activity_Status"] == "No Recent Billing":

        reasons.append(
            "no billing in the last 6 months"
        )

    # --------------------------------------------------
    # Visit recency
    # --------------------------------------------------

    days = row["Days_Since_Last_Visit"]

    if pd.isna(days):

        reasons.append(
            "no recorded visit"
        )

    elif days >= 15:

        reasons.append(
            f"last visited {int(days)} days ago"
        )

    # --------------------------------------------------
    # Fallback
    # --------------------------------------------------

    if not reasons:
        return "Regular account follow-up"

    return " • ".join(reasons)


if __name__ == "__main__":

    outlet_metrics = create_outlet_metrics()

    columns = [
        "Outlet Code",
        "Outlet Name",
        "Town_Normalized",
        "Assigned_BDM_Name",
        "Activity_Status",
        "Latest_Billing",
        "Previous_Billing",
        "Days_Since_Last_Visit",
        "Priority_Score",
        "Priority_Label",
        "Recommendation_Reason",
    ]

    top_outlets = (
        outlet_metrics
        .sort_values(
            "Priority_Score",
            ascending=False
        )[columns]
        .head(10)
    )

    for _, outlet in top_outlets.iterrows():

        outlet_name = outlet["Outlet Name"]

        if pd.isna(outlet_name):
            outlet_name = (
                f"Unnamed Outlet "
                f"({outlet['Outlet Code']})"
            )

        print("\n" + "=" * 60)

        print(
            f"{outlet_name} "
            f"— {outlet['Town_Normalized']}"
        )

        print(
            f"Priority: "
            f"{outlet['Priority_Label']} "
            f"({outlet['Priority_Score']})"
        )

        print(
            f"Status: "
            f"{outlet['Activity_Status']}"
        )

        print(
            f"Why visit: "
            f"{outlet['Recommendation_Reason']}"
        )