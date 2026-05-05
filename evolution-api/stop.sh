#!/bin/bash
# Stop Evolution API + OpenClaw Multi-Agent Bridge

echo "🛑 Stopping Multi-Agent Bridge..."

# Stop dispatcher
if [ -f .dispatcher.pid ]; then
    DISPATCHER_PID=$(cat .dispatcher.pid)
    if ps -p $DISPATCHER_PID > /dev/null 2>&1; then
        kill $DISPATCHER_PID
        echo "✓ Dispatcher stopped (PID: $DISPATCHER_PID)"
    else
        echo "⚠️  Dispatcher not running"
    fi
    rm .dispatcher.pid
else
    # Fallback: find and kill by port
    DISPATCHER_PID=$(lsof -Pi :3000 -sTCP:LISTEN -t 2>/dev/null || true)
    if [ -n "$DISPATCHER_PID" ]; then
        kill $DISPATCHER_PID
        echo "✓ Dispatcher stopped (PID: $DISPATCHER_PID)"
    fi
fi

# Stop Evolution API
if docker-compose ps 2>/dev/null | grep -q "Up"; then
    docker-compose down
    echo "✓ Evolution API stopped"
else
    echo "⚠️  Evolution API not running"
fi

echo ""
echo "✅ All services stopped"
