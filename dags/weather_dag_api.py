from datetime import datetime
import logging
import json
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.postgres.operators.postgres import PostgresOperator
from airflow.providers.http.operators.http import SimpleHttpOperator
from airflow.providers.http.sensors.http import HttpSensor
from airflow.utils.task_group import TaskGroup

weather_date = "2023-04-26T08:20:00.000+03:00"
weather_parameter = "t_2m:C,precip_1h:mm,wind_speed_10m:ms"
locations = {"Lviv": "49.841952,24.0315921", "Kyiv": "50.4500336,30.5241361", "Kharkiv": "49.9923181,36.2310146",
"Odesa": "46.4843023,30.7322878", "Zhmerynka": "49.0354593,28.1147317"}
weather_format = "json"

def start():
	logging.info("Starting db creation")

def end():
	logging.info("All done!")

def process_weather_data(ti, city):
	info = ti.xcom_pull(f"cities.extract_data_{city}")
	print(info["data"][0]["coordinates"][0]["dates"][0]["value"])
	timestamp = info["data"][0]["coordinates"][0]["dates"][0]["date"]
	temp = info["data"][0]["coordinates"][0]["dates"][0]["value"]
	precipitation = info["data"][1]["coordinates"][0]["dates"][0]["value"]
	wind_speed = info["data"][2]["coordinates"][0]["dates"][0]["value"]
	return timestamp, temp, precipitation, wind_speed, city

with DAG(dag_id="weather_dag_api", schedule_interval="@daily", start_date=datetime(2023, 4, 26)) as dag:
	start = PythonOperator(
		task_id="python_task1",
		python_callable=start)

	table_create = PostgresOperator(
		task_id='create_table_postgres',
		postgres_conn_id='postgres_conn',
		sql=""" CREATE TABLE IF NOT EXISTS measurements (
			timestamp TIMESTAMP,
			temp FLOAT,
			precipitation FLOAT,
			wind_speed FLOAT,
			location VARCHAR);""")

	with TaskGroup(group_id=f'cities') as cities:
		for location in locations.keys():
			weather_location = locations.get(f"{location}")
			extract_data = SimpleHttpOperator(
	 			task_id=f"extract_data_{location}",
	 			http_conn_id="weather_conn", 
				endpoint = f"{weather_date}/{weather_parameter}/{weather_location}/{weather_format}", 
				method="GET",
	 			response_filter=lambda x: json.loads(x.text),
	 			log_response=True)
			process_data = PythonOperator(
				task_id=f"process_data_{location}",
				python_callable= process_weather_data,
				op_kwargs={"city": f"{location}"})
			insert_data = PostgresOperator(
				task_id=f"insert_data_{location}",
				postgres_conn_id ="postgres_conn",
				sql=f"""INSERT INTO measurements (timestamp, temp, precipitation, wind_speed, location) 
				VALUES ('{{{{ti.xcom_pull(task_ids="cities.process_data_{location}")[0]}}}}',
				{{{{ti.xcom_pull(task_ids="cities.process_data_{location}")[1]}}}},
				{{{{ti.xcom_pull(task_ids="cities.process_data_{location}")[2]}}}},
				{{{{ti.xcom_pull(task_ids="cities.process_data_{location}")[3]}}}},
				'{{{{ti.xcom_pull(task_ids="cities.process_data_{location}")[4]}}}}');""")

			extract_data >> process_data >>	insert_data	
	
	end = PythonOperator(
		task_id="python_task2",
		python_callable=end)
		


	#
	# api_adress = """https://api.meteomatics.com/2023-04-25T13:20:00.000+03:00/t_2m:C/49.841952,24.0315921/html?model=mix"""
	# https://api.meteomatics.com/2023-04-25T13:20:00.000+03:00/t_2m:C,precip_1h:mm,wind_speed_10m:ms/49.841952,24.0315921/json
	#

	start >> table_create >> cities >> end


