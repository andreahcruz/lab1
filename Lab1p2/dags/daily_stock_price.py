from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime, timedelta
import os
import snowflake.connector
import yfinance as yf  
import pandas as pd

# default settings for dag tasks
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2023, 1, 1),
    'retries': 1,
    'retry_delay': timedelta(minutes=2),
}

# had error with conversion so getting scalar fixed it instead
def get_scalar(val):
    return val.item() if hasattr(val, "item") else val

# fetch and load last 180 days
def fl_data(**context):
    # snowflake connection
    conn = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse="COMPUTE_WH",
        database="FINANCE_DB",
        schema="ANALYTICS"
    )
    cursor = conn.cursor()

    symbols = ["TSLA", "SPY"] 

    for symbol in symbols:
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
            df = yf.download(symbol, period="180d", interval="1d", progress=False)

        # fetch new data from the day after latest date 
        else:
            start_date = latest_date + timedelta(days=1)
            end_date = datetime.today()
            df = yf.download(symbol, start=start_date, end=end_date, progress=False)

        # name cols to match the ones in snowflake
        df = df.rename(columns={
            "Open": "open",
            "Close": "close",
            "Low": "min",
            "High": "max",
            "Volume": "volume"
        })

        # rows that will be inserted onto snowflake
        rows_to_insert = []

        for idx, row in df.iterrows():
            # idx orginally a pandas timestamp so we want to convert it 
            date_obj = idx.date()  

            # if db is empty we insert all rows or if row is newer than latest date
            if (latest_date is None) or (date_obj > latest_date):
                open_val = float(get_scalar(row["open"]))
                close_val = float(get_scalar(row["close"]))
                min_val = float(get_scalar(row["min"]))
                max_val = float(get_scalar(row["max"]))
                volume_raw = get_scalar(row["volume"])
                volume_val = int(volume_raw) if not pd.isna(volume_raw) else 0

                rows_to_insert.append((
                    symbol,
                    date_obj.isoformat(),  
                    open_val,
                    close_val,
                    min_val,
                    max_val,
                    volume_val
                ))

        # sort rows by ascending date 
        rows_to_insert.sort(key=lambda x: x[1])

        # insert new rows
        insert_sql = """
            INSERT INTO FINANCE_DB.ANALYTICS.stock_prices
                (stock_symbol, date, open, close, min, max, volume)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        try:
            cursor.execute("BEGIN;")
            cursor.executemany(insert_sql, rows_to_insert)
            cursor.execute("COMMIT;")
            print(f"Inserted new rows.")
        except Exception as e:
            cursor.execute("ROLLBACK;")
            print(f"Failed to insert new rows")

    cursor.close()
    conn.close

# cleanup old data and keep only last 180 days
def cu_data(**context):
    conn = snowflake.connector.connect(
        user=os.getenv('SNOWFLAKE_USER'),
        password=os.getenv('SNOWFLAKE_PASSWORD'),
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        warehouse="COMPUTE_WH",
        database="FINANCE_DB",
        schema="ANALYTICS"
    )
    cursor = conn.cursor()

    cleanup_sql = """
        DELETE FROM FINANCE_DB.ANALYTICS.stock_prices
        WHERE (stock_symbol, date) IN (
            SELECT stock_symbol, date
            FROM (
                SELECT
                    stock_symbol,
                    date,
                    ROW_NUMBER() OVER (
                        PARTITION BY stock_symbol
                        ORDER BY date DESC
                    ) AS rn
                FROM FINANCE_DB.ANALYTICS.stock_prices
            ) sub
            WHERE sub.rn > 180
        );
    """

    try:
        cursor.execute("BEGIN;")
        cursor.execute(cleanup_sql)
        cursor.execute("COMMIT;")
        print("Cleaned up rows")
    except Exception as e:
        cursor.execute("ROLLBACK;")
        print(f"Failed to clean up old rows.")
    finally:
        cursor.close()
        conn.close()

# define dag
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
