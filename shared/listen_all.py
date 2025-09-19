from confluent_kafka.admin import AdminClient
import os

BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")

def list_topics():
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP})
    md = admin.list_topics(timeout=10)  # get cluster metadata
    print("📋 Topics in cluster:")
    for topic in md.topics.keys():
        print(f" - {topic}")

if __name__ == "__main__":
    list_topics()