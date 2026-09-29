import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import (
    ExtraTreesRegressor,
    GradientBoostingRegressor,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    r2_score,
)
from sklearn.model_selection import KFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


DATA_PATH = Path("data/baku_housing_1000.csv")
MODEL_PATH = Path("baku_price_model.joblib")
METADATA_PATH = Path("model_metadata.json")

TARGET = "price_azn"
NUMERIC_FEATURES = ["area_m2", "rooms", "floor", "total_floors"]
CATEGORICAL_FEATURES = [
    "property_type",
    "building_type",
    "district",
    "location_name",
    "metro_near",
    "repair_quality",
    "has_parking",
]
MODEL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def load_dataset():
    data = pd.read_csv(DATA_PATH)
    data = data.drop_duplicates(subset="listing_id").copy()
    data = data[
        data[TARGET].between(20000, 5000000)
        & data["area_m2"].between(20, 1500)
        & data["rooms"].between(1, 30)
    ]
    return data


def build_preprocessor():
    numeric_pipeline = Pipeline(
        steps=[("imputer", SimpleImputer(strategy="median"))]
    )
    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            (
                "encoder",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
            ),
        ]
    )
    return ColumnTransformer(
        transformers=[
            ("numeric", numeric_pipeline, NUMERIC_FEATURES),
            ("categorical", categorical_pipeline, CATEGORICAL_FEATURES),
        ]
    )


def build_estimator(regressor):
    pipeline = Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            ("model", regressor),
        ]
    )
    return TransformedTargetRegressor(
        regressor=pipeline,
        func=np.log1p,
        inverse_func=np.expm1,
    )


def candidate_models():
    return {
        "random_forest": build_estimator(
            RandomForestRegressor(
                n_estimators=500,
                min_samples_leaf=2,
                max_features=0.85,
                n_jobs=-1,
                random_state=42,
            )
        ),
        "extra_trees": build_estimator(
            ExtraTreesRegressor(
                n_estimators=500,
                min_samples_leaf=2,
                max_features=0.9,
                n_jobs=-1,
                random_state=42,
            )
        ),
        "gradient_boosting": build_estimator(
            GradientBoostingRegressor(
                n_estimators=350,
                learning_rate=0.035,
                max_depth=3,
                loss="huber",
                random_state=42,
            )
        ),
    }


def evaluate_candidates(models, x_train, y_train):
    cross_validation = KFold(n_splits=5, shuffle=True, random_state=42)
    scores = {}
    for name, estimator in models.items():
        fold_scores = -cross_val_score(
            estimator,
            x_train,
            y_train,
            cv=cross_validation,
            scoring="neg_mean_absolute_percentage_error",
            n_jobs=-1,
        )
        scores[name] = float(fold_scores.mean())
        print(f"{name}: CV MAPE = {scores[name] * 100:.2f}%")
    return scores


def category_values(data, column):
    return sorted(str(value) for value in data[column].dropna().unique())


def main():
    data = load_dataset()
    x = data[MODEL_FEATURES]
    y = data[TARGET]

    x_train, x_test, y_train, y_test = train_test_split(
        x,
        y,
        test_size=0.2,
        random_state=42,
        stratify=data["property_type"],
    )

    models = candidate_models()
    cross_validation_scores = evaluate_candidates(models, x_train, y_train)
    best_name = min(cross_validation_scores, key=cross_validation_scores.get)
    best_model = models[best_name]

    best_model.fit(x_train, y_train)
    predictions = best_model.predict(x_test)

    mae = mean_absolute_error(y_test, predictions)
    mape = mean_absolute_percentage_error(y_test, predictions)
    r2 = r2_score(y_test, predictions)

    print(f"Selected model: {best_name}")
    print(f"Test MAE: {mae:,.0f} AZN")
    print(f"Test MAPE: {mape * 100:.2f}%")
    print(f"Test R2: {r2:.4f}")

    best_model.fit(x, y)
    joblib.dump(best_model, MODEL_PATH)

    metadata = {
        "dataset_rows": int(len(data)),
        "selected_model": best_name,
        "mae_azn": round(float(mae), 2),
        "mape_percent": round(float(mape * 100), 2),
        "r2": round(float(r2), 4),
        "numeric_features": NUMERIC_FEATURES,
        "categorical_features": CATEGORICAL_FEATURES,
        "districts": category_values(data, "district"),
        "locations_by_district": {
            district: sorted(
                data.loc[data["district"] == district, "location_name"]
                .dropna()
                .astype(str)
                .unique()
                .tolist()
            )
            for district in category_values(data, "district")
        },
        "area_limits": {
            property_type: {
                "min": int(data.loc[data["property_type"] == property_type, "area_m2"].min()),
                "max": int(data.loc[data["property_type"] == property_type, "area_m2"].max()),
            }
            for property_type in category_values(data, "property_type")
        },
    }
    METADATA_PATH.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved model to {MODEL_PATH}")
    print(f"Saved metadata to {METADATA_PATH}")


if __name__ == "__main__":
    main()
