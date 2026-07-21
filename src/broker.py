import asyncio
import logging
import sys
from amqtt.broker import Broker

config = {
    'listeners': {
        'default': {
            'type': 'tcp',
            'bind': '127.0.0.1:1883',
        },
    },
    'plugins': [
        'amqtt.plugins.authentication.AnonymousAuthPlugin'
    ]
}

async def run_broker():
    broker = Broker(config)
    await broker.start()
    print("MQTT Broker started on 127.0.0.1:1883", flush=True)
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    logging.basicConfig(level=logging.WARNING)
    try:
        asyncio.run(run_broker())
    except KeyboardInterrupt:
        print("Broker stopped.")
    except Exception as e:
        print(f"Broker error: {e}", file=sys.stderr, flush=True)
