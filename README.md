# lab1
Analyzing the finance data from yfinance API and titled as ‘Building a Finance Data Analytics'

Steps to run code:

Make sure to run the code in its own folder and not a folder inside a folder; Should look like this 
<img width="337" alt="image" src="https://github.com/user-attachments/assets/1044147f-4b9c-490e-92b1-5ef80f7beeb6" />

You also want to create your own .env as shown in the image above

SNOWFLAKE_USER=yourown
SNOWFLAKE_PASSWORD=yourown
SNOWFLAKE_ACCOUNT=yourown

(obviously instead of yourown please put your own creditials)
Snowflake account 
In vscode terminal run:

docker-compose down (to make sure you reset it)

docker-compose up -d 

Wait a bit then you will need to use http://localhost:8080/home (make sure its not already being used by anything else!)

Open up snowflake and run every sql line (in the sql file) up until the select statements aka just create db schema and table;
Then press the play button on the right hand side 
![image](https://github.com/user-attachments/assets/6510814d-14eb-43d5-b7cd-bb90f3f61f1f)

Then run the select statements in the sql file. 

