#!/bin/bash
# Evolution API + OpenClaw Multi-Agent Bridge Startup Script

set -e

echo "🦞 OpenClaw Multi-Agent Bridge"
echo "================================"

# Load environment
if [ -f .env ]; then
    set -a
    source .env
    set +a
    echo "✓ Environment loaded"
else
    echo "✗ .env file not found!"
    exit 1
fi

# Check if dispatcher is already running
if lsof -Pi :3000 -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "⚠️  Dispatcher already running on port 3000"
else
    echo "🔧 Starting Webhook Dispatcher..."
    python3 webhook-dispatcher.py > dispatcher.log 2>&1 &
    DISPATCHER_PID=$!
    echo $DISPATCHER_PID > .dispatcher.pid
    sleep 2

    # Check if dispatcher started successfully
    if curl -s http://localhost:3000 > /dev/null 2>&1; then
        echo "✓ Dispatcher running on port 3000 (PID: $DISPATCHER_PID)"
    else
        echo "✗ Dispatcher failed to start. Check dispatcher.log"
        exit 1
    fi
fi

# Start Evolution API
echo "🐳 Starting Evolution API..."
if docker-compose ps | grep -q "Up"; then
    echo "⚠️  Evolution API already running"
else
    docker-compose up -d
    echo "✓ Evolution API starting..."
    sleep 5
fi

# Check Evolution API health
echo "🏥 Health checks..."
if curl -s http://localhost:8080 > /dev/null 2>&1; then
    echo "✓ Evolution API responding on port 8080"
else
    echo "⚠️  Evolution API not responding yet (may still be starting)"
fi

echo ""
echo "🎯 Next Steps:"
echo "=============="
echo "1. Open http://localhost:8080/manager"
echo "2. Create instance with API key: ${EVOLUTION_API_KEY:0:20}..."
echo "3. Scan QR code to link WhatsApp"
echo "4. Set webhook URL: http://host.docker.internal:3000/webhook"
echo ""
echo "💬 Test messages:"
echo "   @pete analyze this"
echo "   @charlie fix the bug"
echo "   @delta research this"
echo "   Hello (routes to Clawd)"
echo ""
echo "📊 Monitoring:"
echo "   Evolution logs: docker-compose logs -f evolution-api"
echo "   Dispatcher logs: tail -f dispatcher.log"
echo ""
echo "🛑 To stop: ./stop.sh"
