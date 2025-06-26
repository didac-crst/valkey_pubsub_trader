# 🪙 Valkey Trading Simulation (Jupyter Version)

This project simulates a real-time trading environment using [Valkey](https://valkey.io/) (an open-source, Redis-compatible in-memory database) and Python, implemented in Jupyter notebooks.

It includes:

- **`valkey_pub.ipynb`** — a simulated publisher that sends randomized crypto trade batches using Valkey Pub/Sub.
- **`valkey_sub.ipynb`** — a subscriber that listens, buffers, and processes all incoming trade actions in bulk.

---

## 🐋 Install and Run Valkey with Docker

Run Valkey locally using Docker:

```bash
docker run -d \
  --name valkey \
  -p 6379:6379 \
  valkey/valkey
```