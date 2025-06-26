from dataclasses import dataclass, field
from typing import List, Dict
import redis
import threading
import random
import time
import json
import asyncio
from queue import Queue


@dataclass
class TradePublisherDemo:
    """
    A dataclass-based publisher that simulates sending trade batches to a Valkey Pub/Sub channel.

    - Uses threading to simulate multiple traders
    - Sends randomized trade actions with delay
    - Publishes JSON-encoded batches to Valkey
    """
    host: str = 'localhost'
    port: int = 6379
    channel: str = 'trades'
    cryptos: List[str] = field(default_factory=lambda: ['BTC', 'ETH', 'SOL', 'ADA', 'XRP'])
    actions: List[str] = field(default_factory=lambda: ['buy', 'sell'])
    traders: List[str] = field(default_factory=lambda: ['Asteroid', 'Exoplanet'])
    frequency: int = 20  # Seconds between full trader batch rounds

    def __post_init__(self):
        # Connect to Valkey
        self.client = redis.Redis(host=self.host, port=self.port)
        print(f"📤 Connected to Valkey at {self.host}:{self.port}. Publishing on '{self.channel}'...")

    def send_batch(self, trader: str):
        """
        Constructs and publishes a trade batch for a specific trader.
        Introduces a random delay and sends 1–2 randomized trade actions.
        """
        time.sleep(random.uniform(0.5, 3.0))  # Simulated delay

        batch = {
            "timestamp": int(time.time()),
            "trader": trader,
            "actions": [
                {
                    "crypto": random.choice(self.cryptos),
                    "action": random.choice(self.actions),
                    "quantity": round(random.uniform(0.01, 10.0), 2)
                }
                for _ in range(random.randint(1, 2))
            ]
        }

        payload = json.dumps(batch)
        self.client.publish(self.channel, payload)
        print(f"🆕 Published batch from {trader}: {payload}")

    def run(self):
        """
        Main loop that runs the publisher in rounds.
        Each trader sends a batch, and the loop waits before repeating.
        """
        try:
            while True:
                threads = []

                for trader in self.traders:
                    t = threading.Thread(target=self.send_batch, args=(trader,), daemon=True)
                    t.start()
                    threads.append(t)

                for t in threads:
                    t.join()

                time.sleep(self.frequency)
        except KeyboardInterrupt:
            print("\n❌ Publisher stopped gracefully.")


@dataclass
class TradeSubscriber:
    """
    TradeSubscriber listens to a Valkey/Redis PubSub channel and processes trading actions.

    - Uses two threads:
      - One for listening to the channel and buffering messages
      - One for batching and processing the buffered messages asynchronously

    - Ensures no messages are lost by buffering all received data and processing it in bulk.
    """
    host: str = 'localhost'
    port: int = 6379
    channel: str = 'trades'
    queue: Queue = field(default_factory=Queue)
    stop_event: threading.Event = field(default_factory=threading.Event)
    buffer: List[Dict] = field(default_factory=list)  # stores all received batches
    frequency: int = 5  # seconds between processing batches

    def __post_init__(self):
        """
        Initialize the Redis client and subscribe to the configured channel.
        """
        self.client = redis.Redis(host=self.host, port=self.port)
        self.pubsub = self.client.pubsub()
        self.pubsub.subscribe(self.channel)
    
    def _never_end(self):
        """
        Keeps the main thread alive to prevent early exit and allows keyboard interruption.
        """
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Stopping...")
            self.stop()

    def start(self):
        """
        Starts the subscriber by launching the listener and processor threads,
        then keeps the main thread alive.
        """
        threading.Thread(target=self._listen, daemon=True).start()
        threading.Thread(target=self._process, daemon=True).start()
        self._never_end()

    def _listen(self):
        """
        Background thread that listens for incoming PubSub messages.
        Gracefully exits on stop signal or Redis disconnection.
        """
        print(f"🔊 Listening on '{self.channel}'...")
        try:
            for message in self.pubsub.listen():
                if self.stop_event.is_set():
                    break
                if message['type'] != 'message':
                    continue
                try:
                    data = json.loads(message['data'].decode())

                    # Log the new incoming batch
                    trader = data.get("trader", "Unknown")
                    ts = data.get("timestamp")
                    actions = data.get("actions", [])
                    print(f"🆕 Incoming from {trader} at {ts}: {len(actions)} action(s)")
                    for action in actions:
                        crypto = action.get('crypto')
                        act = action.get('action')
                        quantity = action.get('quantity', 'N/A')
                        print(f"  - {act.upper()} → {crypto} (Quantity: {quantity})")

                    self.buffer.append(data)
                    self.queue.put(data)

                except json.JSONDecodeError as e:
                    print(f"❌ JSON decode error: {e}")
                except Exception as e:
                    print(f"❌ Unexpected message handling error: {e}")

        except redis.exceptions.ConnectionError as e:
            # Expected on shutdown: server closes connection
            if not self.stop_event.is_set():
                print(f"❌ Redis connection lost unexpectedly: {e}")
            else:
                print("🛑 Redis connection closed cleanly.")
        except Exception as e:
            print(f"❌ Listener thread crashed: {e}")

    def _process(self):
        """
        Background thread that runs the asynchronous processing logic.
        It wakes periodically, checks the buffer, and runs trading logic in bulk.
        """
        asyncio.run(self._run_async_orders())

    async def _run_async_orders(self):
        """
        Asynchronous loop that waits on a timer and the trigger queue.
        Once triggered, it processes all buffered batches together.
        """
        while not self.stop_event.is_set():
            time.sleep(self.frequency)  # ensure minimum time between batches
            try:
                self.queue.get(timeout=1)  # wakes processor
                await self.handle_all_buffered_batches()
            except Exception:
                continue  # in case of timeout or queue empty

    async def handle_all_buffered_batches(self):
        """
        Processes all buffered batches together:
        - Flattens all actions across traders
        - Logs the batch header
        - Executes all actions asynchronously
        """
        all_actions = []
        traders = set()
        timestamps = []

        # Collect all actions across all buffered batches
        for batch in self.buffer:
            timestamps.append(batch.get('timestamp'))
            traders.add(batch.get('trader', 'Unknown'))
            for action in batch.get('actions', []):
                all_actions.append({
                    "trader": batch.get('trader', 'Unknown'),
                    "timestamp": batch.get('timestamp'),
                    **action
                })

        self.buffer.clear()  # clear buffer after capturing its contents

        # Use the most recent timestamp to tag the batch
        batch_time = int(time.time())

        print(f"\n📦 Next trading batch at {batch_time} from {len(traders)} trader(s), {len(all_actions)} action(s):")

        tasks = []
        for i, action in enumerate(all_actions, 1):
            trader = action.get('trader')
            crypto = action.get('crypto')
            act = action.get('action')
            quantity = action.get('quantity', 'N/A')
            creation_timestamp = action.get('timestamp')
            print(f"  {i}. {act.upper()} → {crypto} (Quantity: {quantity}) from {trader} at {creation_timestamp}")
            tasks.append(self.execute_order(trader, act, crypto, quantity, timestamp=creation_timestamp))

        await asyncio.gather(*tasks)  # run all tasks concurrently

    async def execute_order(self, trader, action, crypto, quantity, timestamp):
        """
        Simulates the execution of a single trade order with latency.
        """
        await asyncio.sleep(5)  # simulate external I/O latency
        execution_time = time.time()
        print(f"✅ [Time:{execution_time}] Executed {action.upper()} for {crypto} ({quantity}) by {trader} at {timestamp}")

    def stop(self):
        """
        Triggers a clean shutdown of listener and processor threads.
        """
        self.stop_event.set()
        try:
            self.pubsub.close()
        except Exception as e:
            print(f"⚠️ Failed to close pubsub: {e}")
