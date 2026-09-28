import joblib
import pandas as pd
import streamlit as st


st.set_page_config(page_title="Baku Property Price", layout="centered")

st.markdown(
    """
    <style>
        .stApp {
            background: #f7f8f6;
            color: #17211f;
        }

        .block-container {
            max-width: 980px;
            padding-top: 1.25rem;
            padding-bottom: 3rem;
        }

        [data-testid="stImage"] img {
            max-height: 280px;
            object-fit: cover;
            border-radius: 8px;
        }

        h1 {
            color: #173f3a;
            font-size: 2.25rem !important;
            letter-spacing: 0 !important;
            margin-bottom: 0.25rem !important;
        }

        h2, h3 {
            color: #243b37;
            letter-spacing: 0 !important;
        }

        div[data-testid="stButton"] button {
            min-height: 48px;
            background: #0f766e;
            color: #ffffff;
            border: 1px solid #0f766e;
            border-radius: 6px;
            font-weight: 700;
        }

        div[data-testid="stButton"] button:hover {
            background: #115e59;
            color: #ffffff;
            border-color: #115e59;
        }

        .price-result {
            margin-top: 1.25rem;
            padding: 1.25rem 1.5rem;
            background: #ffffff;
            border: 1px solid #cad8d4;
            border-left: 5px solid #c65d3b;
            border-radius: 8px;
        }

        .price-label {
            color: #53635f;
            font-size: 0.9rem;
            font-weight: 700;
            text-transform: uppercase;
        }

        .price-value {
            color: #173f3a;
            font-size: 2rem;
            font-weight: 800;
            line-height: 1.2;
            margin: 0.25rem 0;
        }

        .price-range {
            color: #53635f;
            font-size: 0.95rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_model():
    return joblib.load("baku_price_model.joblib")


model = load_model()

st.image("assets/baku-skyline.png", width="stretch")
st.title("Baku Property Price")
st.caption("Estimate a property's market price from its main characteristics.")

st.subheader("Property details")

type_column, district_column = st.columns(2)
with type_column:
    property_choice = st.selectbox(
        "Property type",
        ["apartment", "house"],
        format_func=lambda value: value.title(),
    )
with district_column:
    district_choice = st.selectbox(
        "District",
        [
            "Absheron",
            "Binagadi",
            "Garadagh",
            "Khatai",
            "Khazar",
            "Narimanov",
            "Nasimi",
            "Nizami",
            "Sabail",
            "Surakhani",
            "Yasamal",
        ],
    )

if property_choice == "apartment":
    minimum_area, maximum_area, default_area = 42, 120, 80
    minimum_floors, maximum_floors, default_floors = 5, 20, 9
    minimum_age, maximum_age = 2, 40
else:
    minimum_area, maximum_area, default_area = 155, 280, 180
    minimum_floors, maximum_floors, default_floors = 2, 3, 2
    minimum_age, maximum_age = 5, 18

area_column, rooms_column, metro_column = st.columns(3)
with area_column:
    area_m2 = st.number_input(
        "Area (m2)",
        min_value=minimum_area,
        max_value=maximum_area,
        value=default_area,
        step=1,
    )
with rooms_column:
    rooms_count = st.number_input(
        "Rooms",
        min_value=1,
        max_value=7,
        value=2,
        step=1,
    )
with metro_column:
    metro_choice = st.selectbox(
        "Metro nearby",
        ["yes", "no"],
        format_func=lambda value: value.title(),
    )

floors_column, floor_column, age_column = st.columns(3)
with floors_column:
    total_floors = st.number_input(
        "Total floors",
        min_value=minimum_floors,
        max_value=maximum_floors,
        value=default_floors,
        step=1,
    )
with floor_column:
    if property_choice == "apartment":
        floor = st.number_input(
            "Apartment floor",
            min_value=1,
            max_value=total_floors,
            value=1,
            step=1,
        )
    else:
        floor = 1
        st.number_input("Property floor", value=1, disabled=True)
with age_column:
    building_age = st.number_input(
        "Building age",
        min_value=minimum_age,
        max_value=maximum_age,
        value=10,
        step=1,
    )

repair_column, elevator_column, parking_column = st.columns(3)
with repair_column:
    repair_choice = st.selectbox(
        "Repair quality",
        ["needs_repair", "average", "good", "excellent"],
        format_func=lambda value: value.replace("_", " ").title(),
        index=2,
    )
with elevator_column:
    if property_choice == "apartment":
        elevator_choice = st.selectbox(
            "Elevator",
            ["yes", "no"],
            format_func=lambda value: value.title(),
        )
    else:
        elevator_choice = "no"
        st.selectbox("Elevator", ["No"], disabled=True)
with parking_column:
    parking_choice = st.selectbox(
        "Parking",
        ["yes", "no"],
        format_func=lambda value: value.title(),
    )

distance_center_km = st.number_input(
    "Distance to city center (km)",
    min_value=1.2,
    max_value=20.2,
    value=5.0,
    step=0.1,
)

input_data = pd.DataFrame(
    [
        {
            "property_type": property_choice,
            "district": district_choice,
            "metro_near": metro_choice,
            "area_m2": area_m2,
            "rooms": rooms_count,
            "floor": floor,
            "total_floors": total_floors,
            "building_age": building_age,
            "repair_quality": repair_choice,
            "has_elevator": elevator_choice,
            "has_parking": parking_choice,
            "distance_center_km": distance_center_km,
        }
    ]
)

if st.button("Estimate price", width="stretch"):
    prediction = float(model.predict(input_data)[0])
    error_margin = 22742
    lower_price = max(0, prediction - error_margin)
    upper_price = prediction + error_margin

    st.markdown(
        f"""
        <div class="price-result">
            <div class="price-label">Estimated market price</div>
            <div class="price-value">{prediction:,.0f} AZN</div>
            <div class="price-range">
                Expected range: {lower_price:,.0f} - {upper_price:,.0f} AZN
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Experimental estimate based on a small sample dataset. "
        "It should not be treated as a professional valuation."
    )
