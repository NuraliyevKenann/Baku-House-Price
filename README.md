Baku Home Value 🏠

A machine learning project that estimates the market price of apartments and houses in Baku, Azerbaijan. It includes a trained model and an interactive Streamlit web app with a district map, available in Azerbaijani and Russian.



Features
Price prediction for apartments and houses in 12 Baku districts
Interactive map of districts (Folium) with click-to-select and zoom on the chosen district
Expected price range based on the model's average error
Bilingual interface: AZ / RU
Trained on 51,619 real estate sale listings
Model
Item	Value
Selected model	Random Forest
Dataset size	51,619 listings
R²	0.72
MAE	~53,439 AZN
MAPE	~15.9%

Numeric features: area_m2, rooms, floor, total_floors

Categorical features: property_type, building_type, district, location_name, metro_near, repair_quality, has_parking

Districts covered: Absheron, Binagadi, Garadagh, Khatai, Khazar, Narimanov, Nasimi, Nizami, Sabail, Sabunchu, Surakhani, Yasamal

Tech Stack
Python
pandas, scikit-learn, joblib
Streamlit
Folium, streamlit-folium
requests
Project Structure
Baku-House-Price/
├── .streamlit/                # Streamlit configuration
├── assets/                    # Images and district GeoJSON for the map
├── data/                      # Dataset
├── scripts/                   # Helper scripts
├── app.py                     # Streamlit web app
├── project.py                 # Main project / model pipeline
├── baku_price_model.joblib    # Trained model
├── model_evaluation.json      # Evaluation metrics
├── model_metadata.json        # Features, districts, locations, area limits
└── requirements.txt           # Dependencies
Getting Started
Clone the repository
bash
   git clone https://github.com/NuraliyevKenann/Baku-House-Price.git
   cd Baku-House-Price
Install dependencies
bash
   pip install -r requirements.txt
Run the app
bash
   streamlit run app.py

Then open the local URL shown in the terminal (usually http://localhost:8501).

How to Use
Choose the property type (apartment or house)
Select the district and the location inside it
Enter area, rooms, floor, building type, repair quality, metro and parking
Click Calculate to get the estimated price and expected range
Limitations
Prices come from listing data, which may differ from final sale prices
Average error is around 16%, so the result is a rough guide only
The model only knows the districts and locations in the training data
Future Improvements
Try gradient boosting models (XGBoost, LightGBM) and compare results
Add more features, such as distance to metro and building age
Keep the dataset up to date with fresh listings
Deploy the app online
Author

Kenan Nuraliyev, Computer Engineering student at ADNSU, interested in Machine Learning, AI and Data Analysis.

GitHub: NuraliyevKenann
