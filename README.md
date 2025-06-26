# 🪙 Valkey Trading Simulation (Jupyter + Python)

This project simulates a real-time trading environment using [Valkey](https://valkey.io/) — an open-source, Redis-compatible in-memory data store — together with Python and Jupyter notebooks.

It demonstrates:
- **Publishing trade batches** using Valkey's Pub/Sub mechanism
- **Subscribing to trade batches**, buffering them safely, and processing all actions in timed bulk

---

## 📁 Project Structure

| File               | Description                                                             |
|--------------------|-------------------------------------------------------------------------|
| `valkey_pub.ipynb` | Jupyter notebook to simulate and publish random trade batches           |
| `valkey_sub.ipynb` | Jupyter notebook that subscribes and processes trade batches in bulk    |
| `valkey_trader.py` | Shared module with `TradePublisherDemo` and `TradeSubscriber` classes   |

---

## 🐋 Run Valkey with Docker

You can launch Valkey locally using the following Docker command:

```bash
docker run -d \
  --name valkey \
  -p 6379:6379 \
  valkey/valkey
