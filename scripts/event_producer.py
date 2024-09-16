import json
import uuid
import os
import json
from dotenv import load_dotenv
from pathlib import Path
from kafka import KafkaProducer
from faker import Faker
from time import sleep
from datetime import datetime, timedelta

# Getting variables
dotenv_path = Path("/opt/app/.env")
load_dotenv(dotenv_path=dotenv_path)

kafka_host = os.getenv("KAFKA_HOST")
kafka_topic = os.getenv("KAFKA_TOPIC_NAME")

# Making KafkaProducer and Fake Events
producer = KafkaProducer(bootstrap_servers=f"{kafka_host}:9092")
faker = Faker()

class DataGenerator(object):
    @staticmethod
    def get_data():
        now = datetime.now()
        return [
            uuid.uuid4().__str__(),
            faker.random_int(min=1, max=100),
            faker.random_element(elements=("Bracelet", "Ring", "Necklace", "Pendant", "Earrings", "Bangle", "Brooch")),
            faker.random_element(elements=("Gold", "Silver", "Platinum", "Palladium")),
            faker.random_int(min=100, max=50000),
            faker.unix_time(
                start_datetime=now - timedelta(minutes=15), end_datetime=now
            ),
        ]

while True:
    columns = [
        "transaction_id",
        "user_id",
        "item_category",
        "item_material",
        "purchase_value",
        "timestamp",
    ]

    data_list = DataGenerator.get_data()
    json_data = dict(zip(columns, data_list))
    _payload = json.dumps(json_data).encode("utf-8")
    print(_payload, flush=True)
    print("=-" * 5, flush=True)

    # Send data
    response = producer.send(topic=kafka_topic, value=_payload)
    print(response.get())
    print("=-" * 20, flush=True)
    sleep(3)
