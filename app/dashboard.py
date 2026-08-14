import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from metrics import create_outlet_metrics
from data_loader import get_clean_data


# ==================================================
# PAGE CONFIG
# ==================================================

st.set_page_config(
    page_title="BDM Visit Assistant",
    page_icon="📱",
    layout="wide"
)


# ==================================================
# FILE PATHS
# ==================================================

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

COMPLETED_VISITS_FILE = (
    DATA_DIR / "completed-visits.csv"
)


# ==================================================
# OUTLET-TYPE CHECKLISTS
# ==================================================

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


# ==================================================
# LOAD APP DATA
# ==================================================

@st.cache_data
def load_app_data():

    outlet_metrics = (
        create_outlet_metrics()
    )

    clean_data = (
        get_clean_data()
    )

    return (
        outlet_metrics,
        clean_data["bdms"],
        clean_data["billing"],
        clean_data["visits"],
    )


outlets, bdms, billing, visits = (
    load_app_data()
)


# ==================================================
# LOAD COMPLETED VISITS
# ==================================================

def load_completed_visits():

    if not COMPLETED_VISITS_FILE.exists():

        return pd.DataFrame()

    completed = pd.read_csv(
        COMPLETED_VISITS_FILE
    )

    # ----------------------------------------------
    # Dates
    # ----------------------------------------------

    if "completed_at" in completed.columns:

        completed["completed_at"] = (
            pd.to_datetime(
                completed[
                    "completed_at"
                ],
                errors="coerce"
            )
        )

    if "started_at" in completed.columns:

        completed["started_at"] = (
            pd.to_datetime(
                completed[
                    "started_at"
                ],
                errors="coerce"
            )
        )

    if "follow_up_date" in completed.columns:

        completed["follow_up_date"] = (
            pd.to_datetime(
                completed[
                    "follow_up_date"
                ],
                errors="coerce"
            )
        )

    # ----------------------------------------------
    # Numeric fields
    # ----------------------------------------------

    if "payment_collected" in completed.columns:

        completed[
            "payment_collected"
        ] = pd.to_numeric(
            completed[
                "payment_collected"
            ],
            errors="coerce"
        ).fillna(0)

    if "order_value" in completed.columns:

        completed[
            "order_value"
        ] = pd.to_numeric(
            completed[
                "order_value"
            ],
            errors="coerce"
        ).fillna(0)

    return completed


# ==================================================
# SAVE COMPLETED VISIT
# ==================================================

def save_completed_visit(
    visit_outcome
):

    record = (
        visit_outcome.copy()
    )

    # ----------------------------------------------
    # Unique visit ID
    # ----------------------------------------------

    record["visit_id"] = (
        "NEW-"
        + uuid.uuid4()
        .hex[:8]
        .upper()
    )

    # ----------------------------------------------
    # Convert datetimes for CSV
    # ----------------------------------------------

    record["started_at"] = (
        record[
            "started_at"
        ].strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    record["completed_at"] = (
        record[
            "completed_at"
        ].strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    )

    # ----------------------------------------------
    # Optional follow-up date
    # ----------------------------------------------

    if (
        record[
            "follow_up_date"
        ]
        is not None
    ):

        record[
            "follow_up_date"
        ] = (
            record[
                "follow_up_date"
            ].strftime(
                "%Y-%m-%d"
            )
        )

    new_visit = (
        pd.DataFrame(
            [record]
        )
    )

    # ----------------------------------------------
    # Save
    # ----------------------------------------------

    if COMPLETED_VISITS_FILE.exists():

        new_visit.to_csv(
            COMPLETED_VISITS_FILE,
            mode="a",
            header=False,
            index=False
        )

    else:

        new_visit.to_csv(
            COMPLETED_VISITS_FILE,
            mode="w",
            header=True,
            index=False
        )

    return record["visit_id"]


# ==================================================
# START VISIT
# ==================================================

def start_visit(
    outlet,
    selected_bdm_row
):

    st.session_state[
        "active_visit"
    ] = {

        "outlet_code":
            outlet[
                "Outlet Code"
            ],

        "bdm_code":
            selected_bdm_row[
                "BDM Code"
            ],

        "bdm_name":
            selected_bdm_row[
                "Name"
            ],

        "started_at":
            datetime.now(),

        "status":
            "In Progress",
    }


# ==================================================
# MANAGER VIEW
# ==================================================

def show_manager_view(
    outlets
):

    st.title(
        "Manager View"
    )

    st.caption(
        "See field activity, visit outcomes, "
        "and whether priority outlets are "
        "receiving attention."
    )

    completed = (
        load_completed_visits()
    )

    # --------------------------------------------------
    # NO COMPLETED VISITS
    # --------------------------------------------------

    if completed.empty:

        st.info(
            "No new completed visits "
            "have been recorded yet."
        )

        return

    # --------------------------------------------------
    # SUMMARY METRICS
    # --------------------------------------------------

    total_visits = len(
        completed
    )

    total_payment = (
        completed[
            "payment_collected"
        ]
        .fillna(0)
        .sum()
    )

    total_orders = (
        completed[
            "order_value"
        ]
        .fillna(0)
        .sum()
    )

    follow_up_count = (
        completed[
            "follow_up_required"
        ]
        .fillna(False)
        .astype(str)
        .str.lower()
        .eq("true")
        .sum()
    )

    summary1, summary2, summary3, summary4 = (
        st.columns(4)
    )

    summary1.metric(
        "Completed Visits",
        total_visits
    )

    summary2.metric(
        "Payment Collected",
        f"₹{total_payment:,.0f}"
    )

    summary3.metric(
        "Order Value",
        f"₹{total_orders:,.0f}"
    )

    summary4.metric(
        "Follow-ups",
        follow_up_count
    )

    st.divider()

    # --------------------------------------------------
    # BDM ACTIVITY
    # --------------------------------------------------

    st.subheader(
        "BDM Activity"
    )

    bdm_summary = (
        completed
        .groupby(
            [
                "bdm_code",
                "bdm_name"
            ],
            as_index=False
        )
        .agg(
            Visits=(
                "visit_id",
                "count"
            ),

            Payment_Collected=(
                "payment_collected",
                "sum"
            ),

            Order_Value=(
                "order_value",
                "sum"
            )
        )
    )

    bdm_summary = (
        bdm_summary.sort_values(
            "Visits",
            ascending=False
        )
    )

    display_bdm_summary = (
        bdm_summary.copy()
    )

    display_bdm_summary[
        "Payment Collected"
    ] = (
        display_bdm_summary[
            "Payment_Collected"
        ].map(
            lambda value:
            f"₹{value:,.0f}"
        )
    )

    display_bdm_summary[
        "Order Value"
    ] = (
        display_bdm_summary[
            "Order_Value"
        ].map(
            lambda value:
            f"₹{value:,.0f}"
        )
    )

    display_bdm_summary = (
        display_bdm_summary[
            [
                "bdm_name",
                "Visits",
                "Payment Collected",
                "Order Value"
            ]
        ]
        .rename(
            columns={
                "bdm_name":
                    "BDM"
            }
        )
    )

    st.dataframe(
        display_bdm_summary,
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # --------------------------------------------------
    # PRIORITY OUTLET COVERAGE
    # --------------------------------------------------

    st.subheader(
        "Priority Outlet Coverage"
    )

    high_priority = (
        outlets[
            outlets[
                "Priority_Label"
            ]
            == "High"
        ]
        .copy()
    )

    visited_codes = set(
        completed[
            "outlet_code"
        ]
        .dropna()
        .astype(str)
    )

    high_priority[
        "Visited_New"
    ] = (
        high_priority[
            "Outlet Code"
        ]
        .astype(str)
        .isin(
            visited_codes
        )
    )

    total_high = len(
        high_priority
    )

    visited_high = int(
        high_priority[
            "Visited_New"
        ].sum()
    )

    if total_high > 0:

        coverage_pct = (
            visited_high
            / total_high
            * 100
        )

    else:

        coverage_pct = 0

    coverage1, coverage2 = (
        st.columns(2)
    )

    coverage1.metric(
        "High Priority Visited",
        f"{visited_high} / {total_high}"
    )

    coverage2.metric(
        "Coverage",
        f"{coverage_pct:.0f}%"
    )

    # --------------------------------------------------
    # HIGH PRIORITY STILL UNVISITED
    # --------------------------------------------------

    unvisited_high = (
        high_priority[
            ~high_priority[
                "Visited_New"
            ]
        ]
        .sort_values(
            "Priority_Score",
            ascending=False
        )
    )

    if not unvisited_high.empty:

        st.markdown(
            "#### High Priority Still Unvisited"
        )

        display_unvisited = (
            unvisited_high[
                [
                    "Outlet Code",
                    "Outlet Name",
                    "Assigned_BDM_Name",
                    "Town_Normalized",
                    "Activity_Status",
                    "Priority_Score",
                    "Recommendation_Reason",
                ]
            ]
            .head(15)
            .copy()
        )

        display_unvisited[
            "Outlet Name"
        ] = (
            display_unvisited.apply(
                lambda row: (
                    row[
                        "Outlet Name"
                    ]
                    if pd.notna(
                        row[
                            "Outlet Name"
                        ]
                    )
                    else (
                        f"Unnamed Outlet "
                        f"({row['Outlet Code']})"
                    )
                ),
                axis=1
            )
        )

        display_unvisited = (
            display_unvisited.rename(
                columns={
                    "Outlet Name":
                        "Outlet",

                    "Assigned_BDM_Name":
                        "BDM",

                    "Town_Normalized":
                        "Territory",

                    "Activity_Status":
                        "Status",

                    "Priority_Score":
                        "Priority",

                    "Recommendation_Reason":
                        "Why Visit",
                }
            )
        )

        st.dataframe(
            display_unvisited,
            use_container_width=True,
            hide_index=True
        )

    else:

        st.success(
            "All high-priority outlets "
            "have been visited."
        )

    st.divider()

    # --------------------------------------------------
    # RECENT VISIT OUTCOMES
    # --------------------------------------------------

    st.subheader(
        "Recent Visit Outcomes"
    )

    recent_visits = (
        completed
        .sort_values(
            "completed_at",
            ascending=False
        )
        .head(10)
    )

    for _, visit in (
        recent_visits.iterrows()
    ):

        outlet_name = (
            visit.get(
                "outlet_name"
            )
        )

        if (
            pd.isna(outlet_name)
            or not str(
                outlet_name
            ).strip()
        ):

            outlet_name = (
                f"Unnamed Outlet "
                f"({visit['outlet_code']})"
            )

        with st.container(
            border=True
        ):

            st.markdown(
                f"### {outlet_name}"
            )

            st.caption(
                f"{visit['bdm_name']} • "
                f"{visit['outlet_code']} • "
                f"{visit['visit_id']}"
            )

            if pd.notna(
                visit[
                    "completed_at"
                ]
            ):

                st.write(
                    "**Completed:** "
                    + visit[
                        "completed_at"
                    ].strftime(
                        "%d %b %Y, "
                        "%I:%M %p"
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

            result1, result2 = (
                st.columns(2)
            )

            result1.metric(
                "Payment",
                f"₹{visit['payment_collected']:,.0f}"
            )

            result2.metric(
                "Order",
                f"₹{visit['order_value']:,.0f}"
            )

            follow_up_value = (
                str(
                    visit[
                        "follow_up_required"
                    ]
                )
                .lower()
            )

            if (
                follow_up_value
                == "true"
            ):

                follow_up_date = (
                    visit[
                        "follow_up_date"
                    ]
                )

                if pd.notna(
                    follow_up_date
                ):

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

            notes = (
                visit.get(
                    "notes"
                )
            )

            if (
                pd.notna(notes)
                and str(
                    notes
                ).strip()
            ):

                st.write(
                    f"**Notes:** "
                    f"{notes}"
                )


# ==================================================
# OUTLET DETAIL PAGE
# ==================================================

def show_outlet_detail(
    outlet,
    billing,
    visits,
    selected_bdm_row
):

    outlet_code = (
        outlet[
            "Outlet Code"
        ]
    )

    outlet_name = (
        outlet[
            "Outlet Name"
        ]
    )

    if pd.isna(
        outlet_name
    ):

        outlet_name = (
            f"Unnamed Outlet "
            f"({outlet_code})"
        )

    # --------------------------------------------------
    # BACK BUTTON
    # --------------------------------------------------

    if st.button(
        "← Back to outlets"
    ):

        st.session_state.pop(
            "selected_outlet",
            None
        )

        st.rerun()

    # --------------------------------------------------
    # COMPLETED VISIT
    # --------------------------------------------------

    completed_visit = (
        st.session_state.get(
            "completed_visit"
        )
    )

    if (
        completed_visit
        and completed_visit.get(
            "outlet_code"
        )
        == outlet_code
    ):

        st.success(
            "Latest visit completed "
            "in this session"
        )

        if (
            "visit_id"
            in completed_visit
        ):

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

        if (
            completed_visit[
                "follow_up_required"
            ]
        ):

            st.write(
                f"**Follow-up:** "
                f"{completed_visit['follow_up_date']}"
            )

        if completed_visit[
            "notes"
        ]:

            st.write(
                f"**Notes:** "
                f"{completed_visit['notes']}"
            )

        st.divider()

    # --------------------------------------------------
    # HEADER
    # --------------------------------------------------

    st.title(
        outlet_name
    )

    st.caption(
        f"{outlet['Type']} • "
        f"{outlet['Town_Normalized']} • "
        f"{outlet_code}"
    )

    # --------------------------------------------------
    # PRIORITY
    # --------------------------------------------------

    st.subheader(
        f"{outlet['Priority_Label']} "
        f"Priority — "
        f"{int(outlet['Priority_Score'])}"
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

    # --------------------------------------------------
    # PERFORMANCE
    # --------------------------------------------------

    st.subheader(
        "Performance"
    )

    col1, col2, col3 = (
        st.columns(3)
    )

    col1.metric(
        "Latest Month",
        f"₹{outlet['Latest_Billing']:,.0f}"
    )

    col2.metric(
        "Previous Month",
        f"₹{outlet['Previous_Billing']:,.0f}"
    )

    change = (
        outlet[
            "Billing_Change_Pct"
        ]
    )

    if pd.notna(
        change
    ):

        change_text = (
            f"{change:.0f}%"
        )

    else:

        change_text = (
            "Billing resumed"
        )

    col3.metric(
        "Change",
        change_text
    )

    # --------------------------------------------------
    # BILLING CHART
    # --------------------------------------------------

    st.markdown(
        "#### 6-Month Billing"
    )

    all_months = (
        pd.date_range(
            start=billing[
                "Month"
            ].min(),
            end=billing[
                "Month"
            ].max(),
            freq="MS"
        )
    )

    outlet_billing = (
        billing[
            billing[
                "Outlet Code"
            ]
            == outlet_code
        ]
        .groupby(
            "Month"
        )["Value"]
        .sum()
        .reindex(
            all_months,
            fill_value=0
        )
        .rename_axis(
            "Month"
        )
        .reset_index()
    )

    if (
        outlet_billing[
            "Value"
        ].sum()
        == 0
    ):

        st.write(
            "No billing recorded "
            "in the available "
            "6-month period."
        )

    else:

        st.line_chart(
            outlet_billing,
            x="Month",
            y="Value"
        )

    st.divider()

    # --------------------------------------------------
    # OUTLET INFORMATION
    # --------------------------------------------------

    st.subheader(
        "Outlet Information"
    )

    info1, info2, info3 = (
        st.columns(3)
    )

    owner = (
        outlet[
            "Owner Name"
        ]
    )

    if pd.isna(owner):

        owner = (
            "Not available"
        )

    phone = (
        outlet["Phone"]
    )

    if pd.isna(phone):

        phone = (
            "Not available"
        )

    credit_days = (
        outlet[
            "Credit Days"
        ]
    )

    if pd.isna(
        credit_days
    ):

        credit_text = (
            "Not available"
        )

    else:

        credit_text = (
            f"{credit_days} days"
        )

    info1.write(
        f"**Owner**  \n"
        f"{owner}"
    )

    info2.write(
        f"**Phone**  \n"
        f"{phone}"
    )

    info3.write(
        f"**Credit Terms**  \n"
        f"{credit_text}"
    )

    st.divider()

    # --------------------------------------------------
    # RECENT VISIT
    # --------------------------------------------------

    st.subheader(
        "Recent Visit"
    )

    outlet_visits = (
        visits[
            visits[
                "Outlet Code"
            ]
            == outlet_code
        ]
        .copy()
        .sort_values(
            "Visit Date",
            ascending=False
        )
    )

    if outlet_visits.empty:

        st.write(
            "No previous visit "
            "recorded."
        )

    else:

        last_visit = (
            outlet_visits.iloc[0]
        )

        visit_date = (
            last_visit[
                "Visit Date"
            ]
        )

        if pd.notna(
            visit_date
        ):

            visit_date_text = (
                visit_date.strftime(
                    "%d %b %Y"
                )
            )

        else:

            visit_date_text = (
                "Not recorded"
            )

        st.write(
            f"**Date:** "
            f"{visit_date_text}"
        )

        purpose = (
            last_visit[
                "Purpose"
            ]
        )

        if pd.isna(
            purpose
        ):

            purpose = (
                "Not recorded"
            )

        st.write(
            f"**Purpose:** "
            f"{purpose}"
        )

        remarks = (
            last_visit[
                "Remarks"
            ]
        )

        if pd.isna(
            remarks
        ):

            remarks = (
                "No remarks recorded"
            )

        st.write(
            f"**Remarks:** "
            f"{remarks}"
        )

    st.divider()

    # --------------------------------------------------
    # CONVERSATION CHECKLIST
    # --------------------------------------------------

    st.subheader(
        "Today's Conversation"
    )

    outlet_type = (
        outlet["Type"]
    )

    checklist = (
        CHECKLISTS.get(
            outlet_type,
            [
                "Review billing performance",
                "Understand current blockers",
                "Discuss stock / demand issues",
                "Review payment status",
                "Agree next action",
            ]
        )
    )

    st.caption(
        f"Suggested checklist "
        f"for {outlet_type}"
    )

    for (
        number,
        item
    ) in enumerate(
        checklist,
        start=1
    ):

        st.write(
            f"**{number}.** "
            f"{item}"
        )

    st.divider()

    # --------------------------------------------------
    # VISIT SAVE CONFIRMATION
    # --------------------------------------------------

    saved_message = (
        st.session_state.pop(
            "visit_saved_message",
            None
        )
    )

    if saved_message:

        st.success(
            saved_message
        )

        st.toast(
            "Visit outcome "
            "saved successfully!",
            icon="✅"
        )

    # --------------------------------------------------
    # ACTIVE VISIT
    # --------------------------------------------------

    active_visit = (
        st.session_state.get(
            "active_visit"
        )
    )

    is_this_visit_active = (
        active_visit
        is not None
        and active_visit.get(
            "outlet_code"
        )
        == outlet_code
    )

    # --------------------------------------------------
    # START VISIT
    # --------------------------------------------------

    if not is_this_visit_active:

        if st.button(
            "Start Visit",
            type="primary"
        ):

            start_visit(
                outlet,
                selected_bdm_row
            )

            st.session_state.pop(
                "completed_visit",
                None
            )

            st.rerun()

    # --------------------------------------------------
    # VISIT IN PROGRESS
    # --------------------------------------------------

    else:

        started_at = (
            active_visit[
                "started_at"
            ]
        )

        st.success(
            "Visit in progress"
        )

        st.write(
            f"**BDM:** "
            f"{active_visit['bdm_name']}"
        )

        st.write(
            f"**Started:** "
            f"{started_at.strftime('%I:%M %p')}"
        )

        st.write(
            f"**Status:** "
            f"{active_visit['status']}"
        )

        # ----------------------------------------------
        # COMPLETE VISIT BUTTON
        # ----------------------------------------------

        if not (
            st.session_state.get(
                "show_visit_form",
                False
            )
        ):

            if st.button(
                "Complete Visit",
                type="primary"
            ):

                st.session_state[
                    "show_visit_form"
                ] = True

                st.rerun()

        # ----------------------------------------------
        # COMPLETE VISIT FORM
        # ----------------------------------------------

        if (
            st.session_state.get(
                "show_visit_form",
                False
            )
        ):

            st.divider()

            st.subheader(
                "Complete Visit"
            )

            st.caption(
                "Capture the key outcome "
                "of the retailer conversation."
            )

            with st.form(
                "visit_outcome_form"
            ):

                blocker = (
                    st.selectbox(
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
                        ]
                    )
                )

                action_agreed = (
                    st.text_input(
                        "Action agreed",
                        placeholder=(
                            "Example: Share promotion "
                            "material and confirm "
                            "iPhone stock availability"
                        )
                    )
                )

                form_col1, form_col2 = (
                    st.columns(2)
                )

                with form_col1:

                    payment_collected = (
                        st.number_input(
                            "Payment collected (₹)",
                            min_value=0.0,
                            step=1000.0
                        )
                    )

                with form_col2:

                    order_value = (
                        st.number_input(
                            "Order value (₹)",
                            min_value=0.0,
                            step=1000.0
                        )
                    )

                follow_up_required = (
                    st.checkbox(
                        "Follow-up required"
                    )
                )

                follow_up_date = (
                    None
                )

                if (
                    follow_up_required
                ):

                    follow_up_date = (
                        st.date_input(
                            "Follow-up date"
                        )
                    )

                notes = (
                    st.text_area(
                        "Short notes",
                        placeholder=(
                            "Keep this short — "
                            "capture only anything "
                            "the next visit "
                            "should know."
                        )
                    )
                )

                submitted = (
                    st.form_submit_button(
                        "Save Visit Outcome",
                        type="primary"
                    )
                )

                # --------------------------------------
                # SAVE VISIT
                # --------------------------------------

                if submitted:

                    if not (
                        action_agreed.strip()
                    ):

                        st.error(
                            "Please record the "
                            "agreed next action."
                        )

                    else:

                        completed_at = (
                            datetime.now()
                        )

                        visit_outcome = {

                            "outlet_code":
                                outlet_code,

                            "outlet_name":
                                outlet_name,

                            "bdm_code":
                                active_visit[
                                    "bdm_code"
                                ],

                            "bdm_name":
                                active_visit[
                                    "bdm_name"
                                ],

                            "started_at":
                                active_visit[
                                    "started_at"
                                ],

                            "completed_at":
                                completed_at,

                            "status":
                                "Completed",

                            "blocker":
                                blocker,

                            "action_agreed":
                                action_agreed
                                .strip(),

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

                        # ----------------------------------
                        # SAVE TO CSV
                        # ----------------------------------

                        visit_id = (
                            save_completed_visit(
                                visit_outcome
                            )
                        )

                        visit_outcome[
                            "visit_id"
                        ] = visit_id

                        # ----------------------------------
                        # SESSION COPY
                        # ----------------------------------

                        st.session_state[
                            "completed_visit"
                        ] = (
                            visit_outcome
                        )

                        # ----------------------------------
                        # CLEAR ACTIVE VISIT
                        # ----------------------------------

                        st.session_state.pop(
                            "active_visit",
                            None
                        )

                        st.session_state.pop(
                            "show_visit_form",
                            None
                        )

                        # ----------------------------------
                        # CONFIRMATION
                        # ----------------------------------

                        st.session_state[
                            "visit_saved_message"
                        ] = (
                            "✅ Visit saved successfully. "
                            f"Visit ID: {visit_id}"
                        )

                        st.rerun()


# ==================================================
# APP NAVIGATION
# ==================================================

view_mode = (
    st.sidebar.radio(
        "View",
        [
            "BDM View",
            "Manager View"
        ]
    )
)


# ==================================================
# MANAGER VIEW ROUTING
# ==================================================

if (
    view_mode
    == "Manager View"
):

    show_manager_view(
        outlets
    )

    st.stop()


# ==================================================
# BDM SELECTION
# ==================================================

bdm_names = (
    bdms[
        "Name"
    ]
    .dropna()
    .sort_values()
    .tolist()
)


default_bdm = (
    st.session_state.get(
        "selected_bdm"
    )
)


if (
    default_bdm
    and default_bdm
    in bdm_names
):

    default_index = (
        bdm_names.index(
            default_bdm
        )
    )

else:

    default_index = 0


selected_bdm = (
    st.selectbox(
        "Select BDM",
        bdm_names,
        index=default_index
    )
)


st.session_state[
    "selected_bdm"
] = selected_bdm


selected_bdm_row = (
    bdms[
        bdms[
            "Name"
        ]
        == selected_bdm
    ]
    .iloc[0]
)


bdm_code = (
    selected_bdm_row[
        "BDM Code"
    ]
)


territory = (
    selected_bdm_row[
        "Territory_Normalized"
    ]
)


# ==================================================
# OUTLET DETAIL ROUTING
# ==================================================

if (
    "selected_outlet"
    in st.session_state
):

    selected_code = (
        st.session_state[
            "selected_outlet"
        ]
    )

    selected_rows = (
        outlets[
            outlets[
                "Outlet Code"
            ]
            == selected_code
        ]
    )

    if not (
        selected_rows.empty
    ):

        selected_outlet = (
            selected_rows.iloc[0]
        )

        show_outlet_detail(
            selected_outlet,
            billing,
            visits,
            selected_bdm_row
        )

        st.stop()

    else:

        st.session_state.pop(
            "selected_outlet",
            None
        )


# ==================================================
# MAIN BDM DASHBOARD
# ==================================================

st.title(
    "BDM Visit Assistant"
)

st.caption(
    "Focus on the right outlets "
    "and prepare for better "
    "retailer visits."
)


# ==================================================
# FILTER BDM OUTLETS
# ==================================================

bdm_outlets = (
    outlets[
        outlets[
            "BDM Code"
        ]
        == bdm_code
    ]
    .copy()
    .sort_values(
        "Priority_Score",
        ascending=False
    )
)


# ==================================================
# BDM SUMMARY
# ==================================================

st.subheader(
    f"{selected_bdm} — "
    f"{territory}"
)


summary1, summary2, summary3, summary4 = (
    st.columns(4)
)


summary1.metric(
    "Total Outlets",
    len(
        bdm_outlets
    )
)


summary2.metric(
    "High Priority",
    len(
        bdm_outlets[
            bdm_outlets[
                "Priority_Label"
            ]
            == "High"
        ]
    )
)


summary3.metric(
    "Declining",
    len(
        bdm_outlets[
            bdm_outlets[
                "Activity_Status"
            ]
            == "Declining"
        ]
    )
)


summary4.metric(
    "Dormant",
    len(
        bdm_outlets[
            bdm_outlets[
                "Activity_Status"
            ]
            == "Dormant"
        ]
    )
)


st.divider()


# ==================================================
# PRIORITY FILTER
# ==================================================

st.subheader(
    "Priority Outlets"
)


priority_filter = (
    st.selectbox(
        "Show",
        [
            "All",
            "High",
            "Medium",
            "Low",
        ]
    )
)


if (
    priority_filter
    == "All"
):

    display_outlets = (
        bdm_outlets
    )

else:

    display_outlets = (
        bdm_outlets[
            bdm_outlets[
                "Priority_Label"
            ]
            == priority_filter
        ]
    )


# ==================================================
# OUTLET CARDS
# ==================================================

for _, outlet in (
    display_outlets
    .head(20)
    .iterrows()
):

    outlet_name = (
        outlet[
            "Outlet Name"
        ]
    )

    if pd.isna(
        outlet_name
    ):

        outlet_name = (
            f"Unnamed Outlet "
            f"({outlet['Outlet Code']})"
        )

    with st.container(
        border=True
    ):

        card_left, card_right = (
            st.columns(
                [3, 1]
            )
        )

        # ------------------------------------------
        # HEADER
        # ------------------------------------------

        with card_left:

            st.markdown(
                f"### {outlet_name}"
            )

            st.caption(
                f"{outlet['Type']} • "
                f"{outlet['Town_Normalized']} • "
                f"{outlet['Outlet Code']}"
            )

        # ------------------------------------------
        # PRIORITY SCORE
        # ------------------------------------------

        with card_right:

            st.metric(
                "Priority",
                int(
                    outlet[
                        "Priority_Score"
                    ]
                )
            )

        # ------------------------------------------
        # STATUS
        # ------------------------------------------

        st.markdown(
            f"**{outlet['Priority_Label']} "
            f"Priority** • "
            f"{outlet['Activity_Status']}"
        )

        # ------------------------------------------
        # WHY VISIT
        # ------------------------------------------

        st.write(
            f"**Why visit:** "
            f"{outlet['Recommendation_Reason']}"
        )

        # ------------------------------------------
        # METRICS
        # ------------------------------------------

        metric1, metric2, metric3 = (
            st.columns(3)
        )

        metric1.metric(
            "Latest Billing",
            f"₹{outlet['Latest_Billing']:,.0f}"
        )

        days_since_visit = (
            outlet[
                "Days_Since_Last_Visit"
            ]
        )

        if pd.notna(
            days_since_visit
        ):

            last_visit_text = (
                f"{int(days_since_visit)} "
                f"days ago"
            )

        else:

            last_visit_text = (
                "No record"
            )

        metric2.metric(
            "Last Visit",
            last_visit_text
        )

        metric3.metric(
            "6M Billing",
            f"₹{outlet['Total_6M_Billing']:,.0f}"
        )

        # ------------------------------------------
        # VIEW OUTLET
        # ------------------------------------------

        if st.button(
            "View Outlet",
            key=(
                f"view_"
                f"{outlet['Outlet Code']}"
            )
        ):

            st.session_state[
                "selected_outlet"
            ] = (
                outlet[
                    "Outlet Code"
                ]
            )

            st.rerun()