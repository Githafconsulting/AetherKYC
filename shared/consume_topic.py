from confluent_kafka import Consumer

consumer = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'ocr-consumer-group',
    'auto.offset.reset': 'earliest'  # equivalent to --from-beginning
})

#consumer.subscribe(['kyc.document.ocr_processed','kyc.document.uploaded'])


consumer.subscribe(['kyc.document.ocr_request'])

print("🎧 Listening to kyc.document.ocr_processed from beginning...")
print("Press Ctrl+C to stop")

try:
    while True:
        msg = consumer.poll(1.0)
        
        if msg is None:
            continue
        if msg.error():
            print(f"❌ Error: {msg.error()}")
            continue
            
        value = msg.value().decode('utf-8') if msg.value() else None
        print(f"📝 {value}")
        
except KeyboardInterrupt:
    print("\n👋 Stopped")
    consumer.close()