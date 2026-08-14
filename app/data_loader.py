from pathlib import Path

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


TOWN_MAPPING = {
    "chennai": "Chennai",
    "madras": "Chennai",
    "madurai": "Madurai",
    "mdu": "Madurai",
    "karur": "Karur",
    "tirupur": "Tirupur",
    "tiruppur": "Tirupur",
    "vellore": "Vellore",
    "thanjavur": "Thanjavur",
    "tanjore": "Thanjavur",
    "dindigul": "Dindigul",
    "coimbatore": "Coimbatore",
    "cbe": "Coimbatore",
    "trichy": "Trichy",
    "tiruchirappalli": "Trichy",
    "tirunelveli": "Tirunelveli",
    "nellai": "Tirunelveli",
    "erode": "Erode",
    "salem": "Salem",
}


def load_data():
    """Load the four source CSV files."""

    outlets = pd.read_csv(DATA_DIR / "outlets.csv")
    billing = pd.read_csv(DATA_DIR / "billing-monthly.csv")
    visits = pd.read_csv(DATA_DIR / "visit-log.csv")
    bdms = pd.read_csv(DATA_DIR / "bdms.csv")

    return outlets, billing, visits, bdms


def normalize_town(town):
    """Normalize town aliases to a consistent territory name."""

    if pd.isna(town):
        return None

    town = str(town).strip().lower()

    return TOWN_MAPPING.get(town, town.title())


def normalize_status(status):
    """Normalize outlet status values."""

    if pd.isna(status):
        return "Unknown"

    status = str(status).strip().lower()

    mapping = {
        "active": "Active",
        "dormant": "Dormant",
        "inactive": "Inactive",
        "hold": "Hold",
    }

    return mapping.get(status, "Unknown")


def parse_date_column(series):
    """Parse mixed date formats safely."""

    return pd.to_datetime(
        series,
        format="mixed",
        dayfirst=True,
        errors="coerce",
    )


def clean_outlets(outlets):
    """Clean and normalize the outlet master."""

    df = outlets.copy()

    df["Town_Normalized"] = df["Town"].apply(normalize_town)
    df["Status_Normalized"] = df["Status"].apply(normalize_status)
    df["Onboarded"] = parse_date_column(df["Onboarded"])

    return df


def clean_billing(billing):
    """Clean billing dates and numeric fields."""

    df = billing.copy()

    df["Month"] = pd.to_datetime(
        df["Month"],
        format="%Y-%m",
        errors="coerce",
    )

    df["Units"] = pd.to_numeric(
        df["Units"],
        errors="coerce",
    ).fillna(0)

    df["Value"] = pd.to_numeric(
        df["Value"],
        errors="coerce",
    ).fillna(0)

    return df


def clean_visits(visits):
    """Clean visit dates and duration values."""

    df = visits.copy()

    df["Visit Date"] = parse_date_column(df["Visit Date"])

    df["Duration (mins)"] = pd.to_numeric(
        df["Duration (mins)"],
        errors="coerce",
    )

    return df


def clean_bdms(bdms):
    """Clean BDM territory and joining-date fields."""

    df = bdms.copy()

    df["Territory_Normalized"] = df["Territory"].apply(
        normalize_town
    )

    df["Joined"] = parse_date_column(df["Joined"])

    return df


def assign_bdms_to_outlets(outlets, bdms):
    """Assign each outlet to the BDM responsible for its territory."""

    bdm_assignment = bdms[
        [
            "BDM Code",
            "Name",
            "Territory_Normalized",
        ]
    ].copy()

    bdm_assignment = bdm_assignment.rename(
        columns={
            "Name": "Assigned_BDM_Name",
        }
    )

    outlets_with_bdm = outlets.merge(
        bdm_assignment,
        left_on="Town_Normalized",
        right_on="Territory_Normalized",
        how="left",
    )

    return outlets_with_bdm


def get_clean_data():
    """Load, clean, and combine all source datasets."""

    outlets, billing, visits, bdms = load_data()

    outlets = clean_outlets(outlets)
    billing = clean_billing(billing)
    visits = clean_visits(visits)
    bdms = clean_bdms(bdms)

    outlets = assign_bdms_to_outlets(
        outlets,
        bdms,
    )

    return {
        "outlets": outlets,
        "billing": billing,
        "visits": visits,
        "bdms": bdms,
    }