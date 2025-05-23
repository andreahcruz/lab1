# lab1
Analyzing the finance data from yfinance API and titled as ‘Building a Finance Data Analytics'

Steps to run code:

Make sure to run the code in its own folder and not a folder inside a folder; Should look like this 
<img width="337" alt="image" src="https://github.com/user-attachments/assets/1044147f-4b9c-490e-92b1-5ef80f7beeb6" />
<img width="1240" alt="image" src="https://github.com/user-attachments/assets/db26fccb-3a13-4907-841b-964fc1b166ed" />

You also want to create your own .env as shown in the image above

SNOWFLAKE_USER=yourown
SNOWFLAKE_PASSWORD=yourown
SNOWFLAKE_ACCOUNT=yourown

(instead of yourown please put your own creditials)
Snowflake account can be found here when you log in 

********THE SNOWFLAKE ACCOUNT CODE IS FOUND IN THE LINK AS SHOWN BELOW ITS BLURRED IN RED****
<account_identifier>.snowflakecomputing.com
<img width="1683" alt="image" src="https://github.com/user-attachments/assets/67261ddc-f045-4aec-ba00-f94d274a900a" />
snowflake user and password is what you used to log in 

You use the code provided that I lined out and put that code in SNOWFLAKE_ACCOUNT=

In vscode terminal run:

docker-compose down (to make sure you reset it)

docker-compose up -d 

Wait a bit then you will need to use http://localhost:8080/home (make sure its not already being used by anything else!)

Open up snowflake and run every sql line (in the snowflakesql file please refer to it for clarity) up until the select statements aka just create db schema and table;

CREATE DATABASE FINANCE_DB;
CREATE SCHEMA ANALYTICS;

USE DATABASE FINANCE_DB;
USE SCHEMA ANALYTICS;

CREATE TABLE IF NOT EXISTS FINANCE_DB.ANALYTICS.stock_prices (
    stock_symbol STRING NOT NULL,   
    date DATE NOT NULL,
    open FLOAT,
    close FLOAT,
    min FLOAT,                      
    max FLOAT,                      
    volume BIGINT,
    PRIMARY KEY (stock_symbol, date) 
);

Then press the play button on the right hand side 
![image](https://github.com/user-attachments/assets/6510814d-14eb-43d5-b7cd-bb90f3f61f1f)

Then run the select statements in the sql file (aka the rest). 

