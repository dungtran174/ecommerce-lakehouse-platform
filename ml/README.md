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

## 4. Model Training & Evaluation (Commit #77)

### Algorithm: Binary Logistic Regression with ElasticNet/L2 Regularization
- **Algorithm:** `pyspark.ml.classification.LogisticRegression`
- **Features Input:** Normalized 12-dimensional vector (`features`)
- **Label Column:** `label_purchase_tomorrow`
- **Hyperparameters:**
  - `maxIter`: 100
  - `regParam`: 0.01 (L2 regularization penalty)
  - `elasticNetParam`: 0.0 (Pure Ridge regression)
- **Train/Test Split:** 80% Training, 20% Holdout Testing (Random seed: 42)

### Target Performance Metrics
- **AUC-ROC:** $\ge 0.78$ (Excellent discrimination between propensity classes)
- **AUC-PR:** $\ge 0.72$ (Handles natural conversion class imbalance)
- **F1-Score:** $\ge 0.74$ (Harmonic balance of Precision and Recall)
- **Model Storage:** Persisted to MinIO S3A at `s3a://lakehouse/models/customer_propensity_lr/`

---

## 5. Daily Batch Inference & Marketing Campaign Export (Commit #78)

The batch inference pipeline scores active customer records and segments them into 3 distinct marketing tiers:

| Tier | Probability Range | Customer Segment | Primary Touchpoint Action | Marketing Channel |
| :--- | :---: | :--- | :--- | :--- |
| **Tier 1** | $P \ge 0.70$ | `Hot Lead` | `Send Premium Offer SMS` | `SMS_AND_PUSH` |
| **Tier 2** | $0.40 \le P < 0.70$ | `Medium Intent` | `Personalized Email Recommendation` | `EMAIL` |
| **Tier 3** | $P < 0.40$ | `Low Intent` | `Retargeting Display Ad` | `DISPLAY_ADS` |

### Target Campaign Mart: `marketing.high_value_purchase_campaign`
- **Storage Path:** `s3a://lakehouse/gold/marketing/high_value_purchase_campaign`
- **Partitioning:** `PARTITIONED BY (year, month, day)`
- **Key Columns:** `customer_id`, `campaign_date`, `purchase_probability`, `customer_segment`, `campaign_action`, `first_name`, `last_name`, `email`, `phone`, `predicted_at`, `created_at`.

---

## 6. Execution & Verification

### Interactive Notebooks (Apache Zeppelin)
Navigate to `http://localhost:8082`:
1. `01_Behavioral_Feature_Engineering_and_Exploration`
2. `02_Logistic_Regression_Propensity_Model_Training_and_Evaluation`

### Headless Batch Execution

#### 1. Feature Engineering:
```bash
python ml/src/feature_engineering.py \
    --input-table lakehouse.gold_ml.ml_user_behavior_3d_agg_feature \
    --output-path s3a://lakehouse/features/customer_propensity_3d/ \
    --model-output-path s3a://lakehouse/models/feature_pipeline_scaler/
```

#### 2. Model Training & Evaluation:
```bash
python ml/src/train_model.py \
    --input-table lakehouse.gold_ml.ml_user_behavior_3d_agg_feature \
    --model-output-path s3a://lakehouse/models/customer_propensity_lr/ \
    --max-iter 100 \
    --reg-param 0.01
```

#### 3. Daily Batch Scoring & Campaign Cohort Export:
```bash
python ml/src/inference.py \
    --input-table lakehouse.gold_ml.ml_user_behavior_3d_agg_feature \
    --customer-table lakehouse.sale_mart.dim_customer \
    --output-path s3a://lakehouse/gold/marketing/high_value_purchase_campaign \
    --output-table lakehouse.marketing.high_value_purchase_campaign
```
