# Evolution API + OpenClaw Multi-Agent Bridge

Multi-agent WhatsApp routing using Evolution API as the WhatsApp gateway and OpenClaw as the AI agent platform.

## Architecture

```
WhatsApp → Evolution API → Webhook Dispatcher → OpenClaw Agents
                              ↓
                    @pete → Pete (Grok)
                    @charlie → Charlie (Gemini)
                    @delta → Delta (Llama)
                    (none) → Clawd (Claude)
```

## Quick Start

### 1. Start Evolution API

```bash
cd ~/Desktop/OPENCLAW_WORKSPACE/evolution-api
source .env
docker-compose up -d
```

### 2. Start Webhook Dispatcher

```bash
python3 webhook-dispatcher.py &
```

### 3. Connect WhatsApp to Evolution API

1. Open http://localhost:8080/manager
2. Create instance with API key from `.env`
3. Scan QR code to link WhatsApp
4. Configure webhook URL: `http://host.docker.internal:3000/webhook`

### 4. Test Routing

Send WhatsApp messages:
- `@pete analyze this market data` → Routes to Pete
- `@charlie fix the deployment script` → Routes to Charlie
- `@delta research llama fine-tuning` → Routes to Delta
- `Hello Clawd, how are you?` → Routes to Clawd (default)

## How It Works

1. **Evolution API** receives all WhatsApp messages
2. **Webhook Dispatcher** inspects message content for `@keywords`
3. **Keyword Router** forwards to the appropriate OpenClaw agent:
   - `@pete` → openclaw-2 (Grok-2)
   - `@charlie` → openclaw-3 (Gemini)
   - `@delta` → openclaw-4 (Llama)
   - No keyword → openclaw-1 (Clawd/Claude)

## Configuration

Edit `.env` to change:
- `EVOLUTION_API_KEY` — API authentication
- `WEBHOOK_URL` — Dispatcher endpoint
- `OPENCLAW_*_URL` — Individual agent webhooks

## Troubleshooting

**WhatsApp not connecting:**
- Check Evolution logs: `docker-compose logs -f evolution-api`
- Ensure phone has internet and WhatsApp is updated

**Messages not routing:**
- Check dispatcher is running: `curl http://localhost:3000`
- Verify webhook URL in Evolution manager
- Check dispatcher logs for routing decisions

**Agent not responding:**
- Ensure OpenClaw gateway is running: `openclaw health`
- Check agent is configured: `openclaw agents list`

## Ports

| Service | Port | Description |
|---------|------|-------------|
| Evolution API | 8080 | WhatsApp gateway |
| Webhook Dispatcher | 3000 | Keyword router |
| OpenClaw Dashboard | 18789 | Clawd interface |

## References

- Evolution API: https://doc.evolution-api.com
- OpenClaw: https://docs.openclaw.ai
