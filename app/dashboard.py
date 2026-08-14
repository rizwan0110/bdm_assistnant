import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from data_loader import get_clean_data
from metrics import create_outlet_metrics


# ==================================================
# CONFIG
# ==================================================

st.set_page_config(
    page_title="BDM Visit Assistant",
    page_icon="📱",
    layout="wide",
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
COMPLETED_VISITS_FILE = DATA_DIR / "completed-visits.csv"

CHECKLISTS = {
    "General Trade": [
        "Review billing vs last month",
        "Ask what is affecting current sales",
        "Check fast-moving models / stock gaps",
        "Discuss pending payment or credit issues",
        "Agree next order or follow-up action",
    ],
    "Mobile Specialist": [
        "Review billing trend and model mix",
        "Ask about customer demand and lost sales",
        "Check stock gaps across key iPhone models",
        "Discuss competitor or pricing pressure",
        "Agree next order and support needed",
    ],
    "Premium Reseller": [
        "Review performance vs last month",
        "Discuss premium model demand and availability",
        "Check customer experience / conversion blockers",
        "Review marketing or promotional support needed",
        "Agree next order and action plan",
    ],
    "Multi-Yard": [
        "Review performance across locations",
        "Identify which location is underperforming",
        "Check stock allocation between locations",
        "Discuss payment / operational blockers",
        "Agree next order and territory-level action",
    ],
}

DEFAULT_CHECKLIST = [
    "Review billing performance",
    "Understand current blockers",
    "Discuss stock / demand issues",
    "Review payment status",
    "Agree next action",
]


# ==================================================
# DATA
# ==================================================

@st.cache_data
def load_app_data():
    outlet_metrics = create_outlet_metrics()
    clean_data = get_clean_data()

    return (
        outlet_metrics,
        clean_data["bdms"],
        clean_data["billing"],
        clean_data["visits"],
    )


def load_completed_visits():
    """Load visits captured through this application."""

    if not COMPLETED_VISITS_FILE.exists():
        return pd.DataFrame()

    completed = pd.read_csv(COMPLETED_VISITS_FILE)

    for column in [
        "started_at",
        "completed_at",
        "follow_up_date",
    ]:
        if column in completed.columns:
            completed[column] = pd.to_datetime(
                completed[column],
                errors="coerce",
            )

    for column in [
        "payment_collected",
        "order_value",
    ]:
        if column in completed.columns:
            completed[column] = pd.to_numeric(
                completed[column],
                errors="coerce",
            ).fillna(0)

    return completed


def save_completed_visit(visit_outcome):
    """Append one completed visit to the MVP visit store."""

    record = visit_outcome.copy()

    record["visit_id"] = (
        "NEW-" + uuid.uuid4().hex[:8].upper()
    )

    record["started_at"] = record[
        "started_at"
    ].strftime("%Y-%m-%d %H:%M:%S")

    record["completed_at"] = record[
        "completed_at"
    ].strftime("%Y-%m-%d %H:%M:%S")

    if record["follow_up_date"] is not None:
        record["follow_up_date"] = record[
            "follow_up_date"
        ].strftime("%Y-%m-%d")

    new_visit = pd.DataFrame([record])

    new_visit.to_csv(
        COMPLETED_VISITS_FILE,
        mode="a" if COMPLETED_VISITS_FILE.exists() else "w",
        header=not COMPLETED_VISITS_FILE.exists(),
        index=False,
    )

    return record["visit_id"]


outlets, bdms, billing, visits = load_app_data()


# ==================================================
# HELPERS
# ==================================================

def get_outlet_name(outlet):
    """Return a safe display name for an outlet."""

    name = outlet["Outlet Name"]

    if pd.isna(name) or not str(name).strip():
        return f"Unnamed Outlet ({outlet['Outlet Code']})"

    return str(name)


def start_visit(outlet, selected_bdm_row):
    """Create an in-progress visit in Streamlit session state."""

    st.session_state["active_visit"] = {
        "outlet_code": outlet["Outlet Code"],
        "bdm_code": selected_bdm_row["BDM Code"],
        "bdm_name": selected_bdm_row["Name"],
        "started_at": datetime.now(),
        "status": "In Progress",
    }


def follow_up_is_required(value):
    """Handle boolean values loaded from either session state or CSV."""

    return str(value).strip().lower() == "true"


# ==================================================
# MANAGER VIEW
# ==================================================

def show_manager_view(outlets_df):
    st.title("Manager View")

    st.caption(
        "See field activity, visit outcomes, "
        "and whether priority outlets are receiving attention."
    )

    completed = load_completed_visits()

    if completed.empty:
        st.info(
            "No new completed visits have been recorded yet."
        )
        return

    # Summary
    total_visits = len(completed)
    total_payment = completed["payment_collected"].sum()
    total_orders = completed["order_value"].sum()

    follow_up_count = (
        completed["follow_up_required"]
        .fillna(False)
        .apply(follow_up_is_required)
        .sum()
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Completed Visits",
        total_visits,
    )

    col2.metric(
        "Payment Collected",
        f"₹{total_payment:,.0f}",
    )

    col3.metric(
        "Order Value",
        f"₹{total_orders:,.0f}",
    )

    col4.metric(
        "Follow-ups",
        int(follow_up_count),
    )

    st.divider()

    # BDM activity
    st.subheader("BDM Activity")

    bdm_summary = (
        completed
        .groupby(
            ["bdm_code", "bdm_name"],
            as_index=False,
        )
        .agg(
            Visits=("visit_id", "count"),
            Payment_Collected=(
                "payment_collected",
                "sum",
            ),
            Order_Value=(
                "order_value",
                "sum",
            ),
        )
        .sort_values(
            "Visits",
            ascending=False,
        )
    )

    display_bdm_summary = pd.DataFrame(
        {
            "BDM": bdm_summary["bdm_name"],
            "Visits": bdm_summary["Visits"],
            "Payment Collected": (
                bdm_summary["Payment_Collected"]
                .map(lambda value: f"₹{value:,.0f}")
            ),
            "Order Value": (
                bdm_summary["Order_Value"]
                .map(lambda value: f"₹{value:,.0f}")
            ),
        }
    )

    st.dataframe(
        display_bdm_summary,
        use_container_width=True,
        hide_index=True,
    )

    st.divider()

    # Priority coverage
    st.subheader("Priority Outlet Coverage")

    high_priority = outlets_df[
        outlets_df["Priority_Label"] == "High"
    ].copy()

    visited_codes = set(
        completed["outlet_code"]
        .dropna()
        .astype(str)
    )

    high_priority["Visited_New"] = (
        high_priority["Outlet Code"]
        .astype(str)
        .isin(visited_codes)
    )

    total_high = len(high_priority)

    visited_high = int(
        high_priority["Visited_New"].sum()
    )

    coverage_pct = (
        visited_high / total_high * 100
        if total_high
        else 0
    )

    col1, col2 = st.columns(2)

    col1.metric(
        "High Priority Visited",
        f"{visited_high} / {total_high}",
    )

    col2.metric(
        "Coverage",
        f"{coverage_pct:.0f}%",
    )

    unvisited_high = (
        high_priority[
            ~high_priority["Visited_New"]
        ]
        .sort_values(
            "Priority_Score",
            ascending=False,
        )
    )

    if not unvisited_high.empty:
        st.markdown(
            "#### High Priority Still Unvisited"
        )

        display_unvisited = unvisited_high[
            [
                "Outlet Code",
                "Outlet Name",
                "Assigned_BDM_Name",
                "Town_Normalized",
                "Activity_Status",
                "Priority_Score",
                "Recommendation_Reason",
            ]
        ].head(15).copy()

        display_unvisited["Outlet Name"] = (
            display_unvisited.apply(
                get_outlet_name,
                axis=1,
            )
        )

        display_unvisited = display_unvisited.rename(
            columns={
                "Outlet Name": "Outlet",
                "Assigned_BDM_Name": "BDM",
                "Town_Normalized": "Territory",
                "Activity_Status": "Status",
                "Priority_Score": "Priority",
                "Recommendation_Reason": "Why Visit",
            }
        )

        st.dataframe(
            display_unvisited,
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.success(
            "All high-priority outlets have been visited."
        )

    st.divider()

    # Recent outcomes
    st.subheader("Recent Visit Outcomes")

    recent_visits = (
        completed
        .sort_values(
            "completed_at",
            ascending=False,
        )
        .head(10)
    )

    for _, visit in recent_visits.iterrows():

        name = visit.get("outlet_name")

        if pd.isna(name) or not str(name).strip():
            name = (
                f"Unnamed Outlet "
                f"({visit['outlet_code']})"
            )

        with st.container(border=True):

            st.markdown(
                f"### {name}"
            )

            st.caption(
                f"{visit['bdm_name']} • "
                f"{visit['outlet_code']} • "
                f"{visit['visit_id']}"
            )

            if pd.notna(
                visit["completed_at"]
            ):
                st.write(
                    "**Completed:** "
                    + visit[
                        "completed_at"
                    ].strftime(
                        "%d %b %Y, %I:%M %p"
                    )
                )

            st.write(
                f"**Blocker:** "
                f"{visit['blocker']}"
            )

            st.write(
                f"**Action agreed:** "
                f"{visit['action_agreed']}"
            )

            col1, col2 = st.columns(2)

            col1.metric(
                "Payment",
                f"₹{visit['payment_collected']:,.0f}",
            )

            col2.metric(
                "Order",
                f"₹{visit['order_value']:,.0f}",
            )

            if follow_up_is_required(
                visit["follow_up_required"]
            ):
                follow_up_date = visit[
                    "follow_up_date"
                ]

                if pd.notna(follow_up_date):
                    st.warning(
                        "Follow-up required: "
                        + follow_up_date.strftime(
                            "%d %b %Y"
                        )
                    )
                else:
                    st.warning(
                        "Follow-up required"
                    )

            notes = visit.get("notes")

            if (
                pd.notna(notes)
                and str(notes).strip()
            ):
                st.write(
                    f"**Notes:** {notes}"
                )


# ==================================================
# OUTLET DETAIL
# ==================================================

def show_outlet_detail(
    outlet,
    billing_df,
    visits_df,
    selected_bdm_row,
):

    outlet_code = outlet["Outlet Code"]
    outlet_name = get_outlet_name(outlet)

    if st.button("← Back to outlets"):
        st.session_state.pop(
            "selected_outlet",
            None,
        )
        st.rerun()

    # Completed visit from current session
    completed_visit = st.session_state.get(
        "completed_visit"
    )

    if (
        completed_visit
        and completed_visit.get("outlet_code")
        == outlet_code
    ):
        st.success(
            "Latest visit completed in this session"
        )

        if "visit_id" in completed_visit:
            st.write(
                f"**Visit ID:** "
                f"{completed_visit['visit_id']}"
            )

        st.write(
            f"**Blocker:** "
            f"{completed_visit['blocker']}"
        )

        st.write(
            f"**Action agreed:** "
            f"{completed_visit['action_agreed']}"
        )

        st.write(
            f"**Payment collected:** "
            f"₹{completed_visit['payment_collected']:,.0f}"
        )

        st.write(
            f"**Order value:** "
            f"₹{completed_visit['order_value']:,.0f}"
        )

        if completed_visit[
            "follow_up_required"
        ]:
            st.write(
                f"**Follow-up:** "
                f"{completed_visit['follow_up_date']}"
            )

        if completed_visit["notes"]:
            st.write(
                f"**Notes:** "
                f"{completed_visit['notes']}"
            )

        st.divider()

    # Header
    st.title(outlet_name)

    st.caption(
        f"{outlet['Type']} • "
        f"{outlet['Town_Normalized']} • "
        f"{outlet_code}"
    )

    st.subheader(
        f"{outlet['Priority_Label']} Priority "
        f"— {int(outlet['Priority_Score'])}"
    )

    st.write(
        f"**Status:** "
        f"{outlet['Activity_Status']}"
    )

    st.info(
        f"Why visit: "
        f"{outlet['Recommendation_Reason']}"
    )

    st.divider()

    # Performance
    st.subheader("Performance")

    col1, col2, col3 = st.columns(3)

    col1.metric(
        "Latest Month",
        f"₹{outlet['Latest_Billing']:,.0f}",
    )

    col2.metric(
        "Previous Month",
        f"₹{outlet['Previous_Billing']:,.0f}",
    )

    change = outlet["Billing_Change_Pct"]

    change_text = (
        f"{change:.0f}%"
        if pd.notna(change)
        else "Billing resumed"
    )

    col3.metric(
        "Change",
        change_text,
    )

    st.markdown(
        "#### 6-Month Billing"
    )

    all_months = pd.date_range(
        start=billing_df["Month"].min(),
        end=billing_df["Month"].max(),
        freq="MS",
    )

    outlet_billing = (
        billing_df[
            billing_df["Outlet Code"]
            == outlet_code
        ]
        .groupby("Month")["Value"]
        .sum()
        .reindex(
            all_months,
            fill_value=0,
        )
        .rename_axis("Month")
        .reset_index()
    )

    if outlet_billing["Value"].sum() == 0:
        st.write(
            "No billing recorded in the "
            "available 6-month period."
        )
    else:
        st.line_chart(
            outlet_billing,
            x="Month",
            y="Value",
        )

    st.divider()

    # Outlet information
    st.subheader("Outlet Information")

    col1, col2, col3 = st.columns(3)

    owner = (
        outlet["Owner Name"]
        if pd.notna(outlet["Owner Name"])
        else "Not available"
    )

    phone = (
        outlet["Phone"]
        if pd.notna(outlet["Phone"])
        else "Not available"
    )

    credit_days = outlet["Credit Days"]

    credit_text = (
        f"{credit_days} days"
        if pd.notna(credit_days)
        else "Not available"
    )

    col1.write(
        f"**Owner**  \n{owner}"
    )

    col2.write(
        f"**Phone**  \n{phone}"
    )

    col3.write(
        f"**Credit Terms**  \n{credit_text}"
    )

    st.divider()

    # Historical visit
    st.subheader("Recent Visit")

    outlet_visits = (
        visits_df[
            visits_df["Outlet Code"]
            == outlet_code
        ]
        .copy()
        .sort_values(
            "Visit Date",
            ascending=False,
        )
    )

    if outlet_visits.empty:
        st.write(
            "No previous visit recorded."
        )

    else:
        last_visit = outlet_visits.iloc[0]

        visit_date = last_visit[
            "Visit Date"
        ]

        visit_date_text = (
            visit_date.strftime(
                "%d %b %Y"
            )
            if pd.notna(visit_date)
            else "Not recorded"
        )

        purpose = last_visit["Purpose"]

        if pd.isna(purpose):
            purpose = "Not recorded"

        remarks = last_visit["Remarks"]

        if pd.isna(remarks):
            remarks = "No remarks recorded"

        st.write(
            f"**Date:** {visit_date_text}"
        )

        st.write(
            f"**Purpose:** {purpose}"
        )

        st.write(
            f"**Remarks:** {remarks}"
        )

    st.divider()

    # Conversation checklist
    st.subheader("Today's Conversation")

    outlet_type = outlet["Type"]

    checklist = CHECKLISTS.get(
        outlet_type,
        DEFAULT_CHECKLIST,
    )

    st.caption(
        f"Suggested checklist "
        f"for {outlet_type}"
    )

    for number, item in enumerate(
        checklist,
        start=1,
    ):
        st.write(
            f"**{number}.** {item}"
        )

    st.divider()

    # Save confirmation
    saved_message = (
        st.session_state.pop(
            "visit_saved_message",
            None,
        )
    )

    if saved_message:
        st.success(saved_message)

        st.toast(
            "Visit outcome saved successfully!",
            icon="✅",
        )

    # Visit state
    active_visit = (
        st.session_state.get(
            "active_visit"
        )
    )

    is_this_visit_active = (
        active_visit is not None
        and active_visit.get(
            "outlet_code"
        )
        == outlet_code
    )

    if not is_this_visit_active:

        if st.button(
            "Start Visit",
            type="primary",
        ):
            start_visit(
                outlet,
                selected_bdm_row,
            )

            st.session_state.pop(
                "completed_visit",
                None,
            )

            st.rerun()

        return

    # Visit in progress
    st.success(
        "Visit in progress"
    )

    st.write(
        f"**BDM:** "
        f"{active_visit['bdm_name']}"
    )

    st.write(
        f"**Started:** "
        f"{active_visit['started_at'].strftime('%I:%M %p')}"
    )

    st.write(
        f"**Status:** "
        f"{active_visit['status']}"
    )

    if not st.session_state.get(
        "show_visit_form",
        False,
    ):
        if st.button(
            "Complete Visit",
            type="primary",
        ):
            st.session_state[
                "show_visit_form"
            ] = True

            st.rerun()

        return

    # Complete visit form
    st.divider()
    st.subheader("Complete Visit")

    st.caption(
        "Capture the key outcome "
        "of the retailer conversation."
    )

    with st.form(
        "visit_outcome_form"
    ):

        blocker = st.selectbox(
            "Main blocker / issue",
            [
                "No major blocker",
                "Low customer demand",
                "Stock availability",
                "Pricing / competitor pressure",
                "Credit / payment issue",
                "Product mix issue",
                "Store / operational issue",
                "Other",
            ],
        )

        action_agreed = st.text_input(
            "Action agreed",
            placeholder=(
                "Example: Share promotion "
                "material and confirm "
                "iPhone stock availability"
            ),
        )

        col1, col2 = st.columns(2)

        with col1:
            payment_collected = (
                st.number_input(
                    "Payment collected (₹)",
                    min_value=0.0,
                    step=1000.0,
                )
            )

        with col2:
            order_value = (
                st.number_input(
                    "Order value (₹)",
                    min_value=0.0,
                    step=1000.0,
                )
            )

        follow_up_required = st.checkbox(
            "Follow-up required"
        )

        follow_up_date = None

        if follow_up_required:
            follow_up_date = (
                st.date_input(
                    "Follow-up date"
                )
            )

        notes = st.text_area(
            "Short notes",
            placeholder=(
                "Keep this short — capture "
                "only anything the next "
                "visit should know."
            ),
        )

        submitted = (
            st.form_submit_button(
                "Save Visit Outcome",
                type="primary",
            )
        )

        if submitted:

            if not action_agreed.strip():
                st.error(
                    "Please record the "
                    "agreed next action."
                )
                return

            visit_outcome = {
                "outlet_code":
                    outlet_code,
                "outlet_name":
                    outlet_name,
                "bdm_code":
                    active_visit["bdm_code"],
                "bdm_name":
                    active_visit["bdm_name"],
                "started_at":
                    active_visit["started_at"],
                "completed_at":
                    datetime.now(),
                "status":
                    "Completed",
                "blocker":
                    blocker,
                "action_agreed":
                    action_agreed.strip(),
                "payment_collected":
                    payment_collected,
                "order_value":
                    order_value,
                "follow_up_required":
                    follow_up_required,
                "follow_up_date":
                    follow_up_date,
                "notes":
                    notes.strip(),
            }

            visit_id = save_completed_visit(
                visit_outcome
            )

            visit_outcome[
                "visit_id"
            ] = visit_id

            st.session_state[
                "completed_visit"
            ] = visit_outcome

            st.session_state.pop(
                "active_visit",
                None,
            )

            st.session_state.pop(
                "show_visit_form",
                None,
            )

            st.session_state[
                "visit_saved_message"
            ] = (
                "✅ Visit saved successfully. "
                f"Visit ID: {visit_id}"
            )

            st.rerun()


# ==================================================
# MAIN APP
# ==================================================

view_mode = st.sidebar.radio(
    "View",
    [
        "BDM View",
        "Manager View",
    ],
)

if view_mode == "Manager View":
    show_manager_view(outlets)
    st.stop()


# BDM selector
bdm_names = (
    bdms["Name"]
    .dropna()
    .sort_values()
    .tolist()
)

default_bdm = (
    st.session_state.get(
        "selected_bdm"
    )
)

default_index = (
    bdm_names.index(default_bdm)
    if default_bdm in bdm_names
    else 0
)

selected_bdm = st.selectbox(
    "Select BDM",
    bdm_names,
    index=default_index,
)

st.session_state[
    "selected_bdm"
] = selected_bdm

selected_bdm_row = (
    bdms[
        bdms["Name"]
        == selected_bdm
    ]
    .iloc[0]
)

bdm_code = selected_bdm_row[
    "BDM Code"
]

territory = selected_bdm_row[
    "Territory_Normalized"
]


# Outlet detail routing
if "selected_outlet" in st.session_state:

    selected_code = (
        st.session_state[
            "selected_outlet"
        ]
    )

    selected_rows = outlets[
        outlets["Outlet Code"]
        == selected_code
    ]

    if not selected_rows.empty:

        show_outlet_detail(
            selected_rows.iloc[0],
            billing,
            visits,
            selected_bdm_row,
        )

        st.stop()

    st.session_state.pop(
        "selected_outlet",
        None,
    )


# Main BDM dashboard
st.title("BDM Visit Assistant")

st.caption(
    "Focus on the right outlets "
    "and prepare for better retailer visits."
)

bdm_outlets = (
    outlets[
        outlets["BDM Code"]
        == bdm_code
    ]
    .copy()
    .sort_values(
        "Priority_Score",
        ascending=False,
    )
)

st.subheader(
    f"{selected_bdm} — {territory}"
)

col1, col2, col3, col4 = (
    st.columns(4)
)

col1.metric(
    "Total Outlets",
    len(bdm_outlets),
)

col2.metric(
    "High Priority",
    (
        bdm_outlets[
            "Priority_Label"
        ]
        .eq("High")
        .sum()
    ),
)

col3.metric(
    "Declining",
    (
        bdm_outlets[
            "Activity_Status"
        ]
        .eq("Declining")
        .sum()
    ),
)

col4.metric(
    "Dormant",
    (
        bdm_outlets[
            "Activity_Status"
        ]
        .eq("Dormant")
        .sum()
    ),
)

st.divider()

st.subheader("Priority Outlets")

priority_filter = st.selectbox(
    "Show",
    [
        "All",
        "High",
        "Medium",
        "Low",
    ],
)

if priority_filter == "All":
    display_outlets = bdm_outlets
else:
    display_outlets = bdm_outlets[
        bdm_outlets[
            "Priority_Label"
        ]
        == priority_filter
    ]


for _, outlet in (
    display_outlets
    .head(20)
    .iterrows()
):

    outlet_name = get_outlet_name(
        outlet
    )

    with st.container(border=True):

        left, right = st.columns(
            [3, 1]
        )

        with left:
            st.markdown(
                f"### {outlet_name}"
            )

            st.caption(
                f"{outlet['Type']} • "
                f"{outlet['Town_Normalized']} • "
                f"{outlet['Outlet Code']}"
            )

        with right:
            st.metric(
                "Priority",
                int(
                    outlet[
                        "Priority_Score"
                    ]
                ),
            )

        st.markdown(
            f"**{outlet['Priority_Label']} "
            f"Priority** • "
            f"{outlet['Activity_Status']}"
        )

        st.write(
            f"**Why visit:** "
            f"{outlet['Recommendation_Reason']}"
        )

        col1, col2, col3 = (
            st.columns(3)
        )

        col1.metric(
            "Latest Billing",
            f"₹{outlet['Latest_Billing']:,.0f}",
        )

        days_since_visit = outlet[
            "Days_Since_Last_Visit"
        ]

        last_visit_text = (
            f"{int(days_since_visit)} days ago"
            if pd.notna(days_since_visit)
            else "No record"
        )

        col2.metric(
            "Last Visit",
            last_visit_text,
        )

        col3.metric(
            "6M Billing",
            f"₹{outlet['Total_6M_Billing']:,.0f}",
        )

        if st.button(
            "View Outlet",
            key=(
                f"view_"
                f"{outlet['Outlet Code']}"
            ),
        ):
            st.session_state[
                "selected_outlet"
            ] = outlet[
                "Outlet Code"
            ]

            st.rerun()