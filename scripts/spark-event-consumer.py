import pyspark
import os
from dotenv import load_dotenv
from pathlib import Path

from pyspark.sql.functions import from_json, col, avg, countDistinct, sum, count, max, window, current_timestamp, from_unixtime
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, LongType, TimestampType

# Getting variables from .env file
dotenv_path = Path("/opt/app/.env")
load_dotenv(dotenv_path=dotenv_path)

spark_hostname = os.getenv("SPARK_MASTER_HOST_NAME")
spark_port = os.getenv("SPARK_MASTER_PORT")
kafka_host = os.getenv("KAFKA_HOST")
kafka_topic = os.getenv("KAFKA_TOPIC_NAME")

spark_host = f"spark://{spark_hostname}:{spark_port}"

# Getting jars
os.environ["PYSPARK_SUBMIT_ARGS"] = (
    "--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.2 org.postgresql:postgresql:42.2.18"
)

# Spark Session
spark = (
    pyspark.sql.SparkSession.builder.appName("DibimbingStreaming")
    .master(spark_host)
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0,org.postgresql:postgresql:42.2.18")
    .config("spark.sql.shuffle.partitions", 4)
    .config("spark.sql.streaming.forceDeleteTempCheckpointLocation", True)
    .getOrCreate()
)

spark.sparkContext.setLogLevel("WARN")

# Schema for the table
schema = StructType(
    [
        StructField("transaction_id", StringType(), True),
        StructField("user_id", IntegerType(), True),
        StructField("item_category", StringType(), True),
        StructField("item_material", StringType(), True),
        StructField("purchase_value", IntegerType(), True),
        StructField("timestamp", LongType(), True)
    ]
)

# Reading from Kafka
stream_df = (
    spark.readStream.format("kafka")
    .option("kafka.bootstrap.servers", f"{kafka_host}:9092")
    .option("subscribe", kafka_topic)
    .option("startingOffsets", "latest")
    .option("failOnDataLoss", "false")
    .load()
)

# CAST(value AS STRING) to change binary writing of Kafka to string (json)
# Using schema to directly changed the metadata: type of each column
# Since timestamp is still in unix format, we need to cast it to timestamp
parsed_df = stream_df.selectExpr("CAST(value AS STRING)").select(from_json(col("value"), schema).alias("data")) \
                     .select(
                        "data.transaction_id",
                        "data.user_id",
                        "data.item_category",
                        "data.item_material",
                        "data.purchase_value",
                        from_unixtime(col("data.timestamp")).cast(TimestampType()).alias("timestamp")
                        )

# Making sure the schema
parsed_df.printSchema()

# In the producer, the late data can be arrived in max 15 minutes
# So, the watermark will be 10 minutes max
# To handle late data, window was used with length of 10 minutes and sliding interval 5 mins
total_purchase_df = (parsed_df
                    .withWatermark("timestamp","10 minutes")
                    .groupBy("item_category", window("timestamp","10 minutes","5 minutes"))
                    .agg(
                        count("transaction_id").alias("total_purchase"),
                        sum("purchase_value").alias("total_purchase_value"),
                        current_timestamp().alias("processing_time")
                        )
                    .select(
                        "item_category",
                        col("window.start").alias("window_start"),
                        col("window.end").alias("window_end"),
                        "total_purchase",
                        "total_purchase_value",
                        "processing_time"
                    )
                    )

# To write into postgres, foreachbatch was used
# Append was used to see the change in value from each item category
def foreach_batch_function(batch_df, batch_id):

    batch_df.write \
        .mode('append') \
        .format("jdbc") \
        .option("url", f"jdbc:postgresql://streaming-postgres:5432/postgres_db") \
        .option('driver', 'org.postgresql.Driver') \
        .option("dbtable", "streaming_test") \
        .option("user", "user") \
        .option("password", "password") \
        .save()

# Writing all data and defining trigger, checkpoint
query = total_purchase_df.writeStream \
    .outputMode("complete") \
    .trigger(processingTime="1 minute") \
    .option("checkpointLocation","/scripts/checkpoint/") \
    .foreachBatch(foreach_batch_function) \
    .start()

query.awaitTermination()