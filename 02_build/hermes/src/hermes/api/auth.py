# Purpose: Auth middleware — mTLS for service-to-service, HMAC-signed header-key for human/agent calls.
# Owner: U-31

def authenticate(request) -> dict:
    raise NotImplementedError("U-31")

# Signed-by: DeepSeek-Researcher | 2026-05-09 | session dsr-20260509-hermes-scaffold-v1