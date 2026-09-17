# E-Commerce Lakehouse Machine Learning (ML) Framework

This directory contains the machine learning pipelines, feature engineering workflows, and exploratory notebooks for the **Modern E-Commerce Data Lakehouse Platform**.

---

## 1. Machine Learning Use Case: Customer Next-Day Purchase Propensity

The goal of this ML pipeline is to predict whether an active customer will complete an order on the following day ($T+1$) based on their rolling 3-day multi-channel digital engagement behaviors ($[T-3, T-1]$).

- **Target Label:** `label_purchase_tomorrow` $\in \{0, 1\}$
- **Prediction Cadence:** Daily batch inference
- **Downstream Action:** High-probability leads ($P > 0.7$) are exported to Delta Lake table `marketing.high_value_purchase_campaign` for personalized marketing activations (push notifications, SMS discounts, email vouchers).

---

## 2. Behavioral Feature Store Schema

The input dataset is sourced from the Gold Delta Lake table `gold_ml.ml_user_behavior_3d_agg_feature`.

### 12 Core Input Features

| # | Feature Name | Data Type | Description | Scaling / Transformation |
| :---: | :--- | :--- | :--- | :--- |
| **1** | `sessions_3d` | Integer | Total browsing sessions in past 3 days | `VectorAssembler` + `StandardScaler` |
| **2** | `total_duration_3d` | Double | Cumulative browsing time (seconds) | `VectorAssembler` + `StandardScaler` |
| **3** | `avg_session_duration_3d`| Double | Mean duration per browsing session | `VectorAssembler` + `StandardScaler` |
| **4** | `total_page_views_3d` | Integer | Total page views accumulated | `VectorAssembler` + `StandardScaler` |
| **5** | `total_actions_3d` | Integer | Granular user actions (clicks, views) | `VectorAssembler` + `StandardScaler` |
| **6** | `total_revenue_3d` | Double | Past 3-day order spending (VND) | `VectorAssembler` + `StandardScaler` |
| **7** | `view_count_3d` | Integer | Product detail view actions | `VectorAssembler` + `StandardScaler` |
| **8** | `add_to_cart_count_3d` | Integer | Cart additions in past 3 days | `VectorAssembler` + `StandardScaler` |
| **9** | `purchase_count_3d` | Integer | Orders placed in past 3 days | `VectorAssembler` + `StandardScaler` |
| **10**| `search_count_3d` | Integer | Product search queries executed | `VectorAssembler` + `StandardScaler` |
| **11**| `checkout_view_count_3d`| Integer | Checkout funnel page views | `VectorAssembler` + `StandardScaler` |
| **12**| `cart_conversion_rate_3d`| Double | Cart-to-order ratio (`purchases / carts`)| `VectorAssembler` + `StandardScaler` |

---

## 3. Directory Layout

```
ml/
├── README.md                      # ML framework documentation & architecture
├── notebooks/                     # Interactive Apache Zeppelin notebooks (.zpln)
│   ├── 01_feature_engineering.zpln# Behavioral EDA & VectorAssembler pipeline
│   └── 02_model_training.zpln     # Classifier training, ROC-AUC evaluation & export
└── src/                           # Production PySpark batch execution scripts
    ├── feature_engineering.py     # Vector packaging & StandardScaler pipeline
    ├── train_model.py             # LogisticRegression training & model evaluation
    └── inference.py               # Batch scoring & marketing campaign exporter
```

---

## 4. Execution & Verification

### Interactive Notebook (Apache Zeppelin)
Navigate to `http://localhost:8082` and open notebook:
`01_Behavioral_Feature_Engineering_and_Exploration`

### Headless Batch Execution
```bash
python ml/src/feature_engineering.py \
    --input-table lakehouse.gold_ml.ml_user_behavior_3d_agg_feature \
    --output-path s3a://lakehouse/features/customer_propensity_3d/ \
    --model-output-path s3a://lakehouse/models/feature_pipeline_scaler/
```
