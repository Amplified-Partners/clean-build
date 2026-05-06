import os
import json
import urllib.request
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("linear-reporter")

# The central Amplified Partners Team ID we just validated
TEAM_ID = "cbcddd63-c720-4997-b7ec-dcfa5cdf3b79"

def create_linear_ticket(title: str, description: str, priority: int = 0):
    """
    Creates a ticket in the Amplifiedpartners Linear workspace.
    priority: 0 (No Priority), 1 (Urgent), 2 (High), 3 (Normal), 4 (Low)
    """
    api_key = os.environ.get("LINEAR_API_KEY")
    if not api_key:
        logger.error("LINEAR_API_KEY environment variable not set. Cannot create ticket.")
        return None

    url = "https://api.linear.app/graphql"
    
    # GraphQL mutation to create an issue
    query = """
    mutation CreateIssue($title: String!, $description: String, $teamId: String!, $priority: Int) {
      issueCreate(input: {
        title: $title,
        description: $description,
        teamId: $teamId,
        priority: $priority
      }) {
        success
        issue {
          id
          title
          url
        }
      }
    }
    """
    
    variables = {
        "title": title,
        "description": description,
        "teamId": TEAM_ID,
        "priority": priority
    }
    
    payload = json.dumps({"query": query, "variables": variables}).encode("utf-8")
    
    req = urllib.request.Request(url, data=payload)
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", api_key)
    
    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            if result.get("data", {}).get("issueCreate", {}).get("success"):
                issue = result["data"]["issueCreate"]["issue"]
                logger.info(f"Successfully created Linear ticket: {issue['title']} ({issue['url']})")
                return issue
            else:
                logger.error(f"Failed to create ticket. Response: {result}")
                return None
    except Exception as e:
        logger.error(f"HTTP Request failed: {e}")
        return None

if __name__ == "__main__":
    # Test the connection if run directly
    print("Testing Linear Reporter...")
    create_linear_ticket(
        title="[SYSTEM] The Beast - Nervous System Online",
        description="The M5 local machine has successfully passed the API key. The Beast is now wired to report ingestion statuses, deduplication logs, and APDS profitable actions directly to this board.",
        priority=2 # High Priority for initial system check
    )
