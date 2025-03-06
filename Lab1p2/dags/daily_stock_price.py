import os
import yfinance as yf
import snowflake.connector
import pandas as pd
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python_operator import PythonOperator

# default settings for DAG tasks
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

def get_snowflake_connection():
    # Establish a connection to Snowflake.
    conn = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse="COMPUTE_WH",
        database="FINANCE_DB",
        schema="ANALYTICS"
    )
    return conn

def save_stock_price_as_file(symbol, start_date, file_path):
    """
    Populate a table with data from a given CSV file using Snowflake's COPY INTO command.
    """
    data = yf.download([symbol], start=start_date, progress=False)

    # if data has multi-index cols drop the ticker level
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.droplevel(1)

    # add stock symbol column
    data["stock_symbol"] = symbol
    data = data.reset_index()

    # rename cols to match Snowflake table
    data.rename(columns={
        "Date": "date",
        "Open": "open",
        "High": "max",   
        "Low": "min",    
        "Close": "close",
        "Volume": "volume"
    }, inplace=True)

    # make sure the table matches snowflake table
    data = data[["stock_symbol", "date", "open", "close", "min", "max", "volume"]]
    data.to_csv(file_path, index=False)

def populate_table_via_stage(conn, schema, table, file_path):
    """
    Populate a table with data from a given CSV file using Snowflake's COPY INTO command.
    """
    cur = conn.cursor()

    try:
        # Create a temporary named stage instead of using the table stage
        stage_name = f"TEMP_STAGE_{table}"
        file_name = os.path.basename(file_path)

        # Create temporary stage
        cur.execute(f"CREATE OR REPLACE TEMPORARY STAGE {stage_name}")

        # Copy the given file to the temporary stage
        cur.execute(f"PUT file://{file_path} @{stage_name}")

        # Run copy into command with fully qualified table name
        copy_sql = f"""
            COPY INTO {schema}.{table} (stock_symbol, date, open, close, min, max, volume)
            FROM @{stage_name}/{file_name}
            FILE_FORMAT = (
                TYPE = 'CSV',
                FIELD_OPTIONALLY_ENCLOSED_BY = '"',
                SKIP_HEADER = 1
            )
        """
        cur.execute(copy_sql)

        print(f"Successfully loaded {file_path} into {schema}.{table}")

    finally:
        cur.close()

# fetch and load data
def fl_data(**context):
    conn = get_snowflake_connection()
    symbols = ["TSLA", "SPY"]

    for symbol in symbols:
        cursor = conn.cursor()

        # find latest date in Snowflake for specific sympbol
        cursor.execute("""
            SELECT MAX(date)
            FROM FINANCE_DB.ANALYTICS.stock_prices
            WHERE stock_symbol = %s
        """, (symbol,))
        result = cursor.fetchone()
        latest_date = result[0]

        # if table is empty fetch last 180 days
        if latest_date is None:
            start_date = datetime.today() - timedelta(days=180)

        # fetch new data from the day after latest date 
        else:
            start_date = latest_date + timedelta(days=1)

        file_path = f"/tmp/{symbol}_data.csv"
        save_stock_price_as_file(symbol, start_date.strftime("2023-06-01"), file_path)

        # populate Snowflake table from staged file
        populate_table_via_stage(conn, "ANALYTICS", "stock_prices", file_path)

        cursor.close()

    conn.close()

# cleanup old data and keep only last 180 days
def cu_data(**context):
    conn = get_snowflake_connection()
    cursor = conn.cursor()

    cleanup_sql = """
        DELETE FROM FINANCE_DB.ANALYTICS.stock_prices
        WHERE (stock_symbol, date) IN (
            SELECT stock_symbol, date
            FROM (
                SELECT stock_symbol, date,
                       ROW_NUMBER() OVER (PARTITION BY stock_symbol ORDER BY date DESC) AS rn
                FROM FINANCE_DB.ANALYTICS.stock_prices
            ) sub
            WHERE sub.rn > 180
        );
    """

    try:
        cursor.execute("BEGIN;")
        cursor.execute(cleanup_sql)
        cursor.execute("COMMIT;")
        print("Successfully cleaned up old rows.")
    except Exception as e:
        cursor.execute("ROLLBACK;")
        print("Failed to clean up old rows")
    finally:
        cursor.close()
        conn.close()

# Define DAG
with DAG(
    dag_id='daily_stock_price',
    default_args=default_args,
    schedule_interval='@daily',
    catchup=False
) as dag:

    load_task = PythonOperator(
        task_id='load_data',
        python_callable=fl_data,
        provide_context=True
    )

    cleanup_task = PythonOperator(
        task_id='cleanup_data',
        python_callable=cu_data,
        provide_context=True
    )

    load_task >> cleanup_task
