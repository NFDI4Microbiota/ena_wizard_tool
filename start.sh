#!/bin/bash
set -e

# Start Redis server as a background daemon
redis-server --daemonize yes

# Wait until Redis accepts connections
echo "Waiting for Redis..."
until redis-cli ping 2>/dev/null | grep -q PONG; do
    sleep 0.5
done
echo "Redis ready."

# Start RQ worker from the App folder (tasks.py resolves task_results.db relative to cwd)
cd /app/App
rq worker ena &

# Start Streamlit in the foreground so it receives container signals
exec streamlit run app.py --server.address=0.0.0.0
