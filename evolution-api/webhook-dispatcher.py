#!/usr/bin/env python3
"""
Evolution API → OpenClaw Multi-Agent Dispatcher
Routes WhatsApp messages to different agents based on @keywords
"""

import os
import re
import json
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import Request, urlopen
from urllib.error import URLError
from urllib.parse import urljoin

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('dispatcher')

# Agent routing configuration
AGENT_ROUTES = {
    '@pete': {
        'name': 'Pete',
        'model': 'xai/grok-2-latest',
        'webhook_url': os.getenv('OPENCLAW_PETE_URL', 'http://localhost:18790/webhook'),
        'emoji': '⚡',
        'personality': 'fast, sharp, no thrashing'
    },
    '@charlie': {
        'name': 'Charlie',
        'model': 'google/gemini-1.5-pro',
        'webhook_url': os.getenv('OPENCLAW_CHARLIE_URL', 'http://localhost:18791/webhook'),
        'emoji': '🔧',
        'personality': 'plumber, fixer, worktree specialist'
    },
    '@delta': {
        'name': 'Delta',
        'model': 'together/meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo',
        'webhook_url': os.getenv('OPENCLAW_DELTA_URL', 'http://localhost:18792/webhook'),
        'emoji': '🦙',
        'personality': 'experimental, thorough'
    },
}

# Default agent (Clawd)
DEFAULT_AGENT = {
    'name': 'Clawd',
    'model': 'anthropic/claude-opus-4-6',
    'webhook_url': os.getenv('OPENCLAW_CLAWD_URL', 'http://localhost:18789/webhook'),
    'emoji': '🦞',
    'personality': 'orchestrator, default handler'
}

def extract_keyword(text: str) -> str | None:
    """Extract @keyword from message text"""
    if not text:
        return None

    # Match @word at start or after whitespace
    match = re.search(r'(?:^|\s)(@[a-zA-Z]+)', text)
    return match.group(1).lower() if match else None

def route_to_agent(message_data: dict) -> dict:
    """Determine which agent should handle this message"""
    text = message_data.get('body', '') or message_data.get('text', '')
    keyword = extract_keyword(text)

    if keyword and keyword in AGENT_ROUTES:
        agent = AGENT_ROUTES[keyword]
        logger.info(f"Routing to {agent['name']} ({agent['emoji']}) via keyword '{keyword}'")
        # Remove keyword from text before forwarding
        clean_text = re.sub(r'(?:^|\s)' + keyword + r'(?:\s|$)', ' ', text).strip()
        message_data['body'] = clean_text
        message_data['text'] = clean_text
        return agent

    logger.info(f"Routing to default agent {DEFAULT_AGENT['name']} ({DEFAULT_AGENT['emoji']})")
    return DEFAULT_AGENT

def forward_to_openclaw(agent: dict, message_data: dict) -> bool:
    """Forward the message to the appropriate OpenClaw agent webhook"""
    payload = json.dumps({
        'agent_id': agent['name'].lower(),
        'model': agent['model'],
        'message': message_data,
        'routing_metadata': {
            'via': 'evolution-api',
            'dispatcher': 'keyword-router',
            'agent_emoji': agent['emoji']
        }
    }).encode('utf-8')

    try:
        req = Request(
            agent['webhook_url'],
            data=payload,
            headers={
                'Content-Type': 'application/json',
                'X-Dispatcher': 'evolution-openclaw-bridge'
            },
            method='POST'
        )

        with urlopen(req, timeout=10) as response:
            if response.status == 200:
                logger.info(f"Successfully forwarded to {agent['name']}")
                return True
            else:
                logger.warning(f"Unexpected status {response.status} from {agent['name']}")
                return False
    except URLError as e:
        logger.error(f"Failed to forward to {agent['name']}: {e}")
        # Fallback: queue for retry or log for manual processing
        return False

class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler for Evolution API webhooks"""

    def log_message(self, format, *args):
        """Suppress default logging"""
        logger.debug(format % args)

    def do_POST(self):
        """Handle incoming webhook from Evolution API"""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        try:
            data = json.loads(post_data.decode('utf-8'))
            logger.info(f"Received webhook: {json.dumps(data, indent=2)[:200]}...")

            # Extract message data from Evolution format
            if 'data' in data:
                message_data = data['data']
            else:
                message_data = data

            # Route to appropriate agent
            agent = route_to_agent(message_data)

            # Forward to OpenClaw agent
            success = forward_to_openclaw(agent, message_data)

            # Respond to Evolution API
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {
                'status': 'success' if success else 'queued',
                'routed_to': agent['name'],
                'keyword_detected': extract_keyword(message_data.get('body', '')) is not None
            }
            self.wfile.write(json.dumps(response).encode())

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
            self.send_response(400)
            self.end_headers()
        except Exception as e:
            logger.error(f"Error processing webhook: {e}")
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        """Health check endpoint"""
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {
            'status': 'running',
            'dispatcher': 'evolution-openclaw-bridge',
            'agents': list(AGENT_ROUTES.keys()) + ['@clawd (default)'],
            'version': '1.0.0'
        }
        self.wfile.write(json.dumps(response).encode())

def run_server(port=3000):
    """Start the webhook dispatcher server"""
    server = HTTPServer(('0.0.0.0', port), WebhookHandler)
    logger.info(f"Dispatcher running on port {port}")
    logger.info(f"Routing rules:")
    logger.info(f"  @pete → Pete ({AGENT_ROUTES['@pete']['emoji']})")
    logger.info(f"  @charlie → Charlie ({AGENT_ROUTES['@charlie']['emoji']})")
    logger.info(f"  @delta → Delta ({AGENT_ROUTES['@delta']['emoji']})")
    logger.info(f"  (default) → Clawd ({DEFAULT_AGENT['emoji']})")
    logger.info("\nReady to receive webhooks from Evolution API")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("\nShutting down dispatcher...")
        server.shutdown()

if __name__ == '__main__':
    port = int(os.getenv('DISPATCHER_PORT', '3000'))
    run_server(port)
