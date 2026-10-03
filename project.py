import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.metrics import mean_absolute_percentage_error
from sklearn.metrics import r2_score
import joblib

DATA_PATH = "data/baku_housing_all_current.csv"


df = pd.read_csv(DATA_PATH)

print("First 5 rows:")
print(df.head())

print("\nDataset info:")
print(df.info())

print("\nNumeric columns summary:")
print(df.describe())

num_clm=df.select_dtypes(include='number') 
print("\nNumeric columns:")
print(num_clm.head())

obj_clm=df.select_dtypes(include='object')
print('\n values: objects')
print(obj_clm.head())

y=df['price_azn']
X=df.drop('price_azn' , axis=1)

X_train,X_test,y_train,y_test=train_test_split(
    X, y, test_size=0.2, train_size=0.8, random_state=42
)

print(X_train.shape)
print(X_test.shape)
print(y_train.shape)
print(y_test.shape)

numeric_features = [
    "area_m2",
    "rooms",
    "floor",
    "total_floors"
]

categorical_features = [
    "property_type",
    "building_type",
    "district",
    "location_name",
    "metro_near",
    "repair_quality",
    "has_parking"
]

print(numeric_features)
print(categorical_features)

numeric_transformer = Pipeline(
    steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler())
    ]
)

categorical_transformer = Pipeline(
    steps=[
        ("encoder", OneHotEncoder(handle_unknown="ignore"))
    ]
)

preprocessor = ColumnTransformer(
    transformers=[
        ("num", numeric_transformer, numeric_features),
        ("cat", categorical_transformer, categorical_features)
    ]
)


model = RandomForestRegressor(
    n_estimators=100,
    random_state=42,
    n_jobs=-1
)

final_model=Pipeline(
    steps=[
        ("preprocessor", preprocessor),
        ("model", model)
    ]
)

final_model.fit(X_train,y_train)
print(final_model)

y_pred=final_model.predict(X_test)

mae=mean_absolute_error(y_test,y_pred)
print("Mean Absolute Error:", mae)

mape=mean_absolute_percentage_error(y_test,y_pred) * 100
print("Mean Absolute Percentage Error:", mape)

r2=r2_score(y_test,y_pred)
print("The R2 score:" , r2 )

print(y_pred[0:5])
print(y_test[0:5])

final_model.fit(X,y)
print(final_model)

joblib.dump(final_model, 'baku_price_model.joblib', compress=("xz", 3))
