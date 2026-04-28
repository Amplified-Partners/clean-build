import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from temporalio.client import Client
from temporal.workflows.sidecar_workflow import SidecarPickToLightWorkflow
from temporal.workflows.dogfood_workflow import CouncilWorkflow
import os
import glob

app = FastAPI(title="Sidecar Headless API")

# Allow React UI to talk to this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In prod, this is locked down
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMPORAL_ADDRESS = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")

class SignalRequest(BaseModel):
    decision: str

@app.post("/task/{workflow_id}/signal")
async def signal_task(workflow_id: str, request: SignalRequest):
    """
    Sends the YES/NO/SNOOZE signal to the waiting Temporal workflow.
    """
    try:
        client = await Client.connect(TEMPORAL_ADDRESS)
        handle = client.get_workflow_handle(workflow_id)
        # Send the signal to the workflow
        await handle.signal(SidecarPickToLightWorkflow.submit_decision, request.decision)
        return {"status": "success", "message": f"Signal '{request.decision}' sent to {workflow_id}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/task/dispatch")
async def dispatch_task(task_type: str, context: str, primary: str = "YES", secondary: str = "NO"):
    """
    Utility endpoint to manually dispatch a Sidecar task for testing the UI.
    """
    try:
        client = await Client.connect(TEMPORAL_ADDRESS)
        workflow_id = f"sidecar-task-{os.urandom(4).hex()}"
        await client.start_workflow(
            SidecarPickToLightWorkflow.run,
            args=[task_type, context, primary, secondary],
            id=workflow_id,
            task_queue="cove-task-queue",
        )
        return {"workflow_id": workflow_id, "message": "Task Dispatched"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class CouncilRequest(BaseModel):
    prompt: str
    perplexity_key: str = ""
    antigravity_key: str = ""
    claude_key: str = ""

@app.post("/council")
async def consult_council(request: CouncilRequest):
    """
    Consults the Tri-Council (Perplexity, Antigravity, Claude) in parallel.
    """
    try:
        client = await Client.connect(TEMPORAL_ADDRESS)
        workflow_id = f"council-{os.urandom(4).hex()}"
        
        # execute_workflow waits for it to finish and returns the result!
        result = await client.execute_workflow(
            CouncilWorkflow.run,
            args=[request.prompt, request.perplexity_key, request.antigravity_key, request.claude_key],
            id=workflow_id,
            task_queue="cove-task-queue",
        )
        return {
            "status": "success", 
            "perplexity": result.perplexity,
            "antigravity": result.antigravity,
            "claude": result.claude
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class VaultSearchRequest(BaseModel):
    query: str

@app.post("/vault/search")
async def search_vault(request: VaultSearchRequest):
    """
    Provides a searchable interface to the local markdown 'Vault'.
    """
    clean_build_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
    corpus_raw_dir = os.path.abspath(os.path.join(clean_build_dir, "../corpus-raw"))
    perplexity_export_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../perplexity-ai-export/exports"))
    search_dirs = [clean_build_dir, corpus_raw_dir, perplexity_export_dir]
    
    results = []
    query_lower = request.query.lower()
    
    for base_dir in search_dirs:
        if not os.path.exists(base_dir):
            continue
        for root, dirs, files in os.walk(base_dir):
            # Skip program files, only search the knowledge base
            if "02_build" in root or ".git" in root or "node_modules" in root or "flat_surface" in root:
                continue
            for file in files:
                if file.endswith(".md") or file.endswith(".txt"):
                    filepath = os.path.join(root, file)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if query_lower in content.lower():
                                idx = content.lower().find(query_lower)
                                start = max(0, idx - 60)
                                end = min(len(content), idx + 120)
                                snippet = content[start:end].replace('\n', ' ')
                                # Format for UI
                                results.append({
                                    "file": file,
                                    "path": filepath.replace(os.path.abspath(os.path.join(clean_build_dir, "..")), ""),
                                    "snippet": f"...{snippet}..."
                                })
                    except Exception:
                        continue
                    
    return {"status": "success", "results": results[:30]}

# Run with: uvicorn sidecar_api:app --reload --port 8001
