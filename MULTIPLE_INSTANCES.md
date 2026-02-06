# Running Multiple Bot Instances

## Overview
To handle high message volume (10+ concurrent users), you can run **4-5 bot instances** in parallel. Each instance operates independently with its own browser, handling messages concurrently.

## Quick Start

### Method 1: Simple Multi-Terminal Approach

Open 4-5 separate terminal windows and run:

```powershell
# Terminal 1
python main.py

# Terminal 2
python main.py

# Terminal 3
python main.py

# Terminal 4
python main.py

# Terminal 5
python main.py
```

Each instance will:
- Launch its own browser
- Log in independently
- Process messages from different users
- Run in parallel with no coordination needed

## Benefits

### With 1 Instance (Current)
- Sequential processing with parallel AI generation
- **5 users** = ~12-20 seconds total
- **10 users** = ~25-40 seconds total

### With 4-5 Instances
- True parallel processing across browsers
- **5 users** = ~2-5 seconds (one per instance)
- **10 users** = ~4-8 seconds (2 per instance)
- **20 users** = ~8-16 seconds (4-5 per instance)

## Resource Requirements

Each instance uses:
- **~500MB RAM**
- **1 CPU core** (light usage)
- **1 browser window**

For 5 instances:
- **~2.5GB RAM** total
- Minimal CPU impact
- 5 browser windows

## Load Distribution

The instances automatically distribute the load:
- Instance 1 sees User A, B (replies to both)
- Instance 2 sees User C, D (replies to both)
- Instance 3 sees User E, F (replies to both)
- etc.

Each instance independently checks for unread messages and processes them with the parallel AI generation optimization.

## Monitoring

When running multiple instances:
1. Each terminal shows its own logs
2. All instances share the same stats tracking
3. User reply counts are tracked per instance (limitation - see below)

## Known Limitations

### User Reply Count Tracking
Currently, each instance maintains its own `user_reply_counts` dictionary in memory. This means:
- Instance 1 might reply to UserA 20 times
- Instance 2 might ALSO reply to UserA 20 times
- **Total**: UserA gets 40 replies instead of intended 20

### Future Enhancement (if needed)
To share reply counts across instances, we'd need:
- Shared database or Redis for state
- File-based locking mechanism
- More complex coordination

**For now**: If running multiple instances, consider reducing `max_replies_per_user` in config (e.g., from 20 to 10) to compensate.

## When to Use Multiple Instances

✅ **Use multiple instances when:**
- Regularly receiving 10+ messages simultaneously
- Single instance can't keep up
- Want <5 second response times even with high load

❌ **Stick with single instance when:**
- Receiving <5 concurrent messages typically
- Current performance (12-20s for 5 users) is acceptable
- Want to minimize resource usage

## Stopping All Instances

Press `Ctrl+C` in each terminal window to gracefully shut down each instance.

## Alternative: Process Management

For production use, consider using a process manager like:
- **PM2** (Node.js-based, works for Python)
- **Supervisor** (Python-based)
- **Windows Task Scheduler** (for automatic startup)

This allows automatic restart on crash and easier management of multiple instances.
