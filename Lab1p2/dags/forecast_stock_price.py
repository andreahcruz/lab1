from airflow import DAG
from airflow.models import Variable
from airflow.decorators import task
from datetime import datetime
import os
import snowflake.connector

def get_snowflake_cursor():
    # Establish a Snowflake connection using environment variables.
    conn = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse="COMPUTE_WH",
        database="FINANCE_DB",
        schema="ANALYTICS"
    )
    return conn.cursor()

@task
def train():
    """
    - Create a view with training related columns
    - Create a model with the view above
    """
    train_input_table = "FINANCE_DB.ANALYTICS.stock_prices"
    train_view = "FINANCE_DB.ANALYTICS.stock_prices_view"
    forecast_function_name = "FINANCE_DB.ANALYTICS.forecast_stock_price"
    
    create_view_sql = f"""
        CREATE OR REPLACE VIEW {train_view} AS
        SELECT DATE, CLOSE, STOCK_SYMBOL AS SYMBOL
        FROM {train_input_table};
    """
    
    create_model_sql = f"""
        CREATE OR REPLACE SNOWFLAKE.ML.FORECAST {forecast_function_name} (
            INPUT_DATA => SYSTEM$REFERENCE('VIEW', '{train_view}'),
            SERIES_COLNAME => 'SYMBOL',
            TIMESTAMP_COLNAME => 'DATE',
            TARGET_COLNAME => 'CLOSE',
            CONFIG_OBJECT => {{'ON_ERROR': 'SKIP'}}
        );
    """
    
    cur = get_snowflake_cursor()
    try:
        cur.execute(create_view_sql)
        cur.execute(create_model_sql)
        # Inspect the accuracy metrics of your model.
        cur.execute(f"CALL {forecast_function_name}!SHOW_EVALUATION_METRICS();")
    except Exception as e:
        print(f"Error during training: {e}")
        raise
    finally:
        cur.close()

@task
def predict():
    """
    - Generate predictions and store the results to a table named forecast_table.
    - Union your predictions with your historical data, then create the final table
    """
    train_input_table = "FINANCE_DB.ANALYTICS.stock_prices"
    forecast_table = "FINANCE_DB.ANALYTICS.stock_price_forecasts"
    final_table = "FINANCE_DB.ANALYTICS.stock_prices_final"
    forecast_function_name = "FINANCE_DB.ANALYTICS.forecast_stock_price"
    
    # Use an Airflow Variable to set the number of forecasting periods (default: 7 days)
    forecast_period = Variable.get("forecast_period", default_var="7")
    
    # This is the step that creates your predictions.
    make_prediction_sql = f"""BEGIN
        CALL {forecast_function_name}!FORECAST(
            FORECASTING_PERIODS => {forecast_period},
            CONFIG_OBJECT => {{'prediction_interval': 0.95}}
        );
        LET x := SQLID;
        CREATE OR REPLACE TABLE {forecast_table} AS 
            SELECT * FROM TABLE(RESULT_SCAN(:x));
    END;"""
    
    # These steps store your predictions to a table.
    create_final_table_sql = f"""
        CREATE OR REPLACE TABLE {final_table} AS
        SELECT STOCK_SYMBOL, DATE, CLOSE AS ACTUAL, NULL AS FORECAST, NULL AS LOWER_BOUND, NULL AS UPPER_BOUND
        FROM {train_input_table}
        UNION ALL
        SELECT REPLACE(SERIES, '"', '') AS STOCK_SYMBOL,
               TS AS DATE,
               NULL AS ACTUAL,
               FORECAST,
               LOWER_BOUND,
               UPPER_BOUND
        FROM {forecast_table};
    """
    
    cur = get_snowflake_cursor()
    try:
        cur.execute(make_prediction_sql)
        cur.execute(create_final_table_sql)
    except Exception as e:
        print(f"Error during prediction: {e}")
        raise
    finally:
        cur.close()

with DAG(
    dag_id="forecast_stock_price",
    start_date=datetime(2025, 3, 2),
    schedule_interval="30 2 * * *",  
    catchup=False,
    tags=["ML", "Forecasting"]
) as dag:
    
    train_task = train()
    predict_task = predict()
    
    train_task >> predict_task
