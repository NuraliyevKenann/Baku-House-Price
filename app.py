import base64
import json
from pathlib import Path

import folium
import joblib
import pandas as pd
import streamlit as st
from streamlit_folium import st_folium


ROOT = Path(__file__).parent
MODEL_PATH = ROOT / "baku_price_model.joblib"
METADATA_PATH = ROOT / "model_metadata.json"
MAP_PATH = ROOT / "assets" / "baku-districts.geojson"
BAKU_MAP_BOUNDS = [[39.45, 49.10], [40.85, 50.45]]
MAP_MIN_ZOOM = 8
MAP_MAX_ZOOM = 14

TEXT = {
    "ru": {
        "page_title": "Оценка недвижимости в Баку",
        "title": "Baku Home Value",
        "subtitle": "Оценка стоимости недвижимости в Баку",
        "details": "Параметры объекта",
        "property": "Недвижимость",
        "apartment": "Квартира",
        "house": "Дом",
        "district": "Район",
        "location": "Расположение",
        "area": "Площадь, м²",
        "rooms": "Количество комнат",
        "building": "Тип здания",
        "new_building": "Новостройка",
        "old_building": "Старое здание",
        "house_building": "Частный дом",
        "floor": "Этаж",
        "total_floors": "Этажей в здании",
        "repair": "Состояние ремонта",
        "needs_repair": "Требуется ремонт",
        "average": "Средний ремонт",
        "good": "Хороший ремонт",
        "excellent": "Отличный ремонт",
        "metro": "Метро рядом",
        "parking": "Парковка",
        "yes": "Да",
        "no": "Нет",
        "unknown": "Не указано",
        "map": "Районы Баку",
        "selected": "Выбранный район",
        "estimate": "Рассчитать стоимость",
        "result": "Примерная рыночная стоимость",
        "range": "Ожидаемый диапазон",
        "model_quality": "Средняя процентная ошибка модели на тесте: {mape:.1f}%",
        "disclaimer": "Экспериментальная оценка по открытым объявлениям, не профессиональная экспертиза.",
        "data_note": "Модель обучена на {rows:,} объявлениях о продаже.",
    },
    "az": {
        "page_title": "Bakıda daşınmaz əmlak qiyməti",
        "title": "Baku Home Value",
        "subtitle": "Bakıda daşınmaz əmlakın qiymətləndirilməsi",
        "details": "Əmlakın parametrləri",
        "property": "Əmlak",
        "apartment": "Mənzil",
        "house": "Həyət evi",
        "district": "Rayon",
        "location": "Ərazi",
        "area": "Sahə, m²",
        "rooms": "Otaq sayı",
        "building": "Bina növü",
        "new_building": "Yeni tikili",
        "old_building": "Köhnə tikili",
        "house_building": "Həyət evi",
        "floor": "Mərtəbə",
        "total_floors": "Binanın mərtəbə sayı",
        "repair": "Təmir vəziyyəti",
        "needs_repair": "Təmirsiz",
        "average": "Orta təmir",
        "good": "Yaxşı təmir",
        "excellent": "Əla təmir",
        "metro": "Metro yaxınlığı",
        "parking": "Dayanacaq",
        "yes": "Bəli",
        "no": "Xeyr",
        "unknown": "Qeyd edilməyib",
        "map": "Bakı rayonları",
        "selected": "Seçilmiş rayon",
        "estimate": "Qiyməti hesabla",
        "result": "Təxmini bazar qiyməti",
        "range": "Gözlənilən interval",
        "model_quality": "Modelin test üzrə orta faiz xətası: {mape:.1f}%",
        "disclaimer": "Açıq elanlar əsasında eksperimental qiymətləndirmədir, peşəkar ekspertiza deyil.",
        "data_note": "Model {rows:,} satış elanı ilə öyrədilib.",
    },
}

DISTRICT_NAMES = {
    "Absheron": {"ru": "Абшерон", "az": "Abşeron"},
    "Garadagh": {"ru": "Гарадаг", "az": "Qaradağ"},
    "Khatai": {"ru": "Хатаи", "az": "Xətai"},
    "Khazar": {"ru": "Хазар", "az": "Xəzər"},
    "Narimanov": {"ru": "Нариманов", "az": "Nərimanov"},
    "Nasimi": {"ru": "Насими", "az": "Nəsimi"},
    "Nizami": {"ru": "Низами", "az": "Nizami"},
    "Sabail": {"ru": "Сабаил", "az": "Səbail"},
    "Sabunchu": {"ru": "Сабунчу", "az": "Sabunçu"},
    "Surakhani": {"ru": "Сураханы", "az": "Suraxanı"},
    "Yasamal": {"ru": "Ясамал", "az": "Yasamal"},
}


st.set_page_config(
    page_title="Baku Home Value",
    page_icon=str(ROOT / "assets" / "brand-mark.png"),
    layout="wide",
)

st.markdown(
    """
    <style>
        :root {
            --red: #c81d25;
            --red-dark: #9f141b;
            --ink: #202225;
            --muted: #666a70;
            --line: #e4e5e7;
            --surface: #ffffff;
            --canvas: #f5f5f4;
        }
        .stApp { background: var(--canvas); color: var(--ink); }
        .block-container {
            max-width: 1440px;
            padding-top: 1rem;
            padding-bottom: 2.5rem;
            animation: page-in .65s ease-out both;
        }
        @keyframes page-in {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        @keyframes result-in {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        h1, h2, h3, p { letter-spacing: 0 !important; }
        h1 { font-size: 2rem !important; margin: .15rem 0 0 !important; }
        h2 { font-size: 1.2rem !important; margin: .2rem 0 .7rem !important; }
        [data-testid="stImage"] img { object-fit: contain; }
        .brand-row { display: flex; align-items: center; gap: .8rem; min-height: 64px; }
        .brand-row img { width: 58px; height: 58px; object-fit: contain; }
        .brand-row h1 { margin: 0 !important; }
        .brand-row p { margin: .15rem 0 0; color: var(--muted); font-size: .9rem; }
        .hero [data-testid="stImage"] img { object-fit: cover; }
        .hero-copy {
            margin: -7.2rem 0 2rem;
            padding: 2.2rem 2rem 1.25rem;
            position: relative;
            color: white;
            background: linear-gradient(0deg, rgba(20, 8, 9, .84), transparent);
            pointer-events: none;
        }
        .hero-copy h1 { color: white; font-size: 2.25rem !important; }
        .hero-copy p { margin: .2rem 0 0; color: rgba(255,255,255,.88); }
        .control-panel { border-top: 3px solid var(--red); padding-top: .9rem; }
        [data-testid="stSelectbox"] label,
        [data-testid="stNumberInput"] label {
            color: var(--ink);
            font-weight: 650;
        }
        div[data-testid="stButton"] button {
            min-height: 48px;
            background: var(--red);
            color: white;
            border: 1px solid var(--red);
            border-radius: 6px;
            font-weight: 750;
        }
        div[data-testid="stButton"] button:hover {
            background: var(--red-dark);
            color: white;
            border-color: var(--red-dark);
        }
        .map-heading {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 1rem;
            border-top: 3px solid var(--red);
            padding-top: .9rem;
            margin-bottom: .55rem;
        }
        .map-heading strong { font-size: 1.2rem; }
        .map-heading span { color: var(--red-dark); font-weight: 700; }
        [data-testid="stIFrame"] {
            border-radius: 6px;
            overflow: hidden;
        }
        iframe {
            display: block;
            border-radius: 6px;
        }
        .price-result {
            margin-top: 1rem;
            padding: 1.15rem 1.3rem;
            background: var(--surface);
            border: 1px solid #dedfe1;
            border-left: 5px solid var(--red);
            border-radius: 6px;
            animation: result-in .4s ease-out both;
        }
        .price-label { color: var(--muted); font-size: .86rem; font-weight: 700; }
        .price-value { color: var(--ink); font-size: 2rem; font-weight: 800; margin: .2rem 0; }
        .price-range { color: var(--muted); font-size: .93rem; }
        .quality-note { color: var(--muted); font-size: .82rem; margin-top: .65rem; }
        footer { visibility: hidden; }
        @media (max-width: 760px) {
            .hero-copy { margin-top: -6.4rem; padding-left: 1rem; }
            .hero-copy h1 { font-size: 1.65rem !important; }
            .block-container { padding-left: .8rem; padding-right: .8rem; }
        }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_model():
    return joblib.load(MODEL_PATH)


@st.cache_data
def load_json(path):
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)


def geometry_points(coordinates):
    if coordinates and isinstance(coordinates[0], (int, float)):
        yield coordinates
        return
    for item in coordinates:
        yield from geometry_points(item)


def selected_bounds(features, district):
    feature = next(
        item for item in features if item["properties"]["district"] == district
    )
    points = list(geometry_points(feature["geometry"]["coordinates"]))
    longitudes = [point[0] for point in points]
    latitudes = [point[1] for point in points]
    return [[min(latitudes), min(longitudes)], [max(latitudes), max(longitudes)]]


def build_map(boundaries, selected_district, language, supported_districts):
    features = []
    for feature in boundaries["features"]:
        district = feature["properties"]["district"]
        if district not in supported_districts:
            continue
        feature = json.loads(json.dumps(feature))
        feature["properties"]["display_name"] = DISTRICT_NAMES[district][language]
        features.append(feature)

    map_data = {"type": "FeatureCollection", "features": features}
    district_map = folium.Map(
        location=[40.40, 49.90],
        tiles=None,
        zoom_start=9,
        min_zoom=MAP_MIN_ZOOM,
        max_zoom=MAP_MAX_ZOOM,
        min_lat=BAKU_MAP_BOUNDS[0][0],
        max_lat=BAKU_MAP_BOUNDS[1][0],
        min_lon=BAKU_MAP_BOUNDS[0][1],
        max_lon=BAKU_MAP_BOUNDS[1][1],
        max_bounds=True,
        zoom_control=True,
        control_scale=True,
        prefer_canvas=True,
    )
    district_map.options.update(
        minZoom=MAP_MIN_ZOOM,
        maxZoom=MAP_MAX_ZOOM,
        maxBoundsViscosity=1.0,
    )
    folium.TileLayer(
        "OpenStreetMap",
        min_zoom=MAP_MIN_ZOOM,
        max_zoom=MAP_MAX_ZOOM,
        no_wrap=True,
        control=False,
    ).add_to(district_map)
    district_map.fit_bounds(
        selected_bounds(features, selected_district), max_zoom=10
    )

    folium.GeoJson(
        map_data,
        name="districts",
        style_function=lambda feature: {
            "fillColor": (
                "#c81d25"
                if feature["properties"]["district"] == selected_district
                else "#aeb2b7"
            ),
            "color": "#ffffff",
            "weight": 1.5,
            "fillOpacity": (
                0.72
                if feature["properties"]["district"] == selected_district
                else 0.35
            ),
        },
        highlight_function=lambda _: {
            "fillColor": "#e21d2d",
            "color": "#9f141b",
            "weight": 2.5,
            "fillOpacity": 0.72,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["display_name"], aliases=[""], labels=False, sticky=True
        ),
    ).add_to(district_map)
    return district_map


def sync_district_from_select():
    st.session_state.selected_district = st.session_state.district_widget


model = load_model()
metadata = load_json(METADATA_PATH)
boundaries = load_json(MAP_PATH)

brand_column, language_column = st.columns(
    [0.84, 0.16], vertical_alignment="center"
)
with language_column:
    language_label = st.segmented_control(
        "Language",
        ["RU", "AZ"],
        default="RU",
        label_visibility="collapsed",
    )
language = (language_label or "RU").lower()
t = TEXT[language]

brand_mark = base64.b64encode(
    (ROOT / "assets" / "brand-mark.png").read_bytes()
).decode("ascii")
with brand_column:
    st.markdown(
        f'<div class="brand-row">'
        f'<img src="data:image/png;base64,{brand_mark}" alt="">'
        f'<div><h1>{t["title"]}</h1><p>{t["subtitle"]}</p></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown('<div class="hero">', unsafe_allow_html=True)
st.image(ROOT / "assets" / "baku-skyline-red.png", width="stretch")
st.markdown(
    f'<div class="hero-copy"><h1>{t["page_title"]}</h1>'
    f'<p>{t["data_note"].format(rows=metadata["dataset_rows"])}</p></div>',
    unsafe_allow_html=True,
)
st.markdown("</div>", unsafe_allow_html=True)

districts = metadata["districts"]
if "selected_district" not in st.session_state:
    st.session_state.selected_district = "Yasamal"
if "district_widget" not in st.session_state:
    st.session_state.district_widget = st.session_state.selected_district
if st.session_state.district_widget != st.session_state.selected_district:
    st.session_state.district_widget = st.session_state.selected_district

controls_column, map_column = st.columns([0.82, 1.18], gap="large")

with controls_column:
    st.markdown('<div class="control-panel">', unsafe_allow_html=True)
    st.subheader(t["details"])
    property_choice = st.selectbox(
        t["property"],
        ["apartment", "house"],
        format_func=lambda value: t[value],
    )
    st.selectbox(
        t["district"],
        districts,
        key="district_widget",
        format_func=lambda value: DISTRICT_NAMES[value][language],
        on_change=sync_district_from_select,
    )
    district_choice = st.session_state.selected_district
    locations = metadata["locations_by_district"][district_choice]
    location_choice = st.selectbox(t["location"], locations)

    area_limits = metadata["area_limits"][property_choice]
    area_default = 85 if property_choice == "apartment" else 160
    area_m2 = st.number_input(
        t["area"],
        min_value=int(area_limits["min"]),
        max_value=int(area_limits["max"]),
        value=area_default,
        step=1,
    )
    rooms_count = st.number_input(
        t["rooms"], min_value=1, max_value=16, value=3, step=1
    )
    building_options = (
        ["new_building", "old_building"]
        if property_choice == "apartment"
        else ["house"]
    )
    building_type = st.selectbox(
        t["building"],
        building_options,
        format_func=lambda value: (
            t["house_building"] if value == "house" else t[value]
        ),
        disabled=property_choice == "house",
    )
    total_floors = st.number_input(
        t["total_floors"],
        min_value=1,
        max_value=28 if property_choice == "apartment" else 4,
        value=15 if property_choice == "apartment" else 1,
        step=1,
    )
    if property_choice == "apartment":
        floor = st.number_input(
            t["floor"],
            min_value=1,
            max_value=int(total_floors),
            value=min(6, int(total_floors)),
            step=1,
        )
    else:
        floor = 1
    repair_choice = st.selectbox(
        t["repair"],
        ["needs_repair", "average", "good", "excellent"],
        index=2,
        format_func=lambda value: t[value],
    )
    metro_choice = st.selectbox(
        t["metro"], ["yes", "no"], format_func=lambda value: t[value]
    )
    parking_choice = st.selectbox(
        t["parking"],
        ["yes", "unknown"],
        format_func=lambda value: t[value],
    )
    estimate = st.button(
        t["estimate"],
        icon=":material/calculate:",
        width="stretch",
        type="primary",
    )
    st.markdown("</div>", unsafe_allow_html=True)

with map_column:
    district_display = DISTRICT_NAMES[district_choice][language]
    st.markdown(
        f'<div class="map-heading"><strong>{t["map"]}</strong>'
        f'<span>{t["selected"]}: {district_display}</span></div>',
        unsafe_allow_html=True,
    )
    map_result = st_folium(
        build_map(boundaries, district_choice, language, set(districts)),
        height=650,
        width=None,
        returned_objects=["last_object_clicked_tooltip"],
        key=f"district_map_{district_choice}_{language}",
    )
    clicked_name = map_result.get("last_object_clicked_tooltip")
    district_by_display_name = {
        DISTRICT_NAMES[district][language]: district for district in districts
    }
    clicked_district = district_by_display_name.get(clicked_name)
    if clicked_district and clicked_district != district_choice:
        st.session_state.selected_district = clicked_district
        st.rerun()

input_data = pd.DataFrame(
    [
        {
            "property_type": property_choice,
            "building_type": building_type,
            "district": district_choice,
            "location_name": location_choice,
            "metro_near": metro_choice,
            "area_m2": area_m2,
            "rooms": rooms_count,
            "floor": floor,
            "total_floors": total_floors,
            "repair_quality": repair_choice,
            "has_parking": parking_choice,
        }
    ]
)

if estimate:
    prediction = float(model.predict(input_data)[0])
    error_margin = float(metadata["mae_azn"])
    lower_price = max(0, prediction - error_margin)
    upper_price = prediction + error_margin
    st.markdown(
        f"""
        <div class="price-result">
            <div class="price-label">{t["result"]}</div>
            <div class="price-value">{prediction:,.0f} AZN</div>
            <div class="price-range">
                {t["range"]}: {lower_price:,.0f} - {upper_price:,.0f} AZN
            </div>
            <div class="quality-note">
                {t["model_quality"].format(mape=metadata["mape_percent"])}<br>
                {t["disclaimer"]}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
