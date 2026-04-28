import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
import uvicorn
import webbrowser
import threading
import time

app = FastAPI()

html_content = """
<!DOCTYPE html>
<html>
<head>
    <title>Amplified Vault</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; background: #0f0f14; color: #fff; }
        h2 { color: #10b981; margin-bottom: 30px; letter-spacing: 1px; }
        input { width: 100%; box-sizing: border-box; padding: 20px; font-size: 18px; border: 1px solid #333; background: #1a1a24; color: #fff; border-radius: 8px; margin-bottom: 30px; }
        input:focus { outline: none; border-color: #10b981; }
        .result { background: #1a1a24; padding: 25px; border-radius: 8px; margin-bottom: 20px; border-left: 4px solid #3b82f6; position: relative; }
        .filename { color: #60a5fa; font-weight: bold; margin-bottom: 15px; font-size: 14px; word-break: break-all; }
        pre { white-space: pre-wrap; font-family: inherit; margin: 0; color: #d1d5db; font-size: 15px; line-height: 1.5; }
        button { background: #374151; color: #fff; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; font-weight: bold; margin-top: 15px; transition: background 0.2s; }
        button:hover { background: #10b981; color: #000; }
        .copied { background: #10b981 !important; color: #000 !important; }
    </style>
</head>
<body>
    <h2>VAULT SEARCH</h2>
    <input type="text" id="query" placeholder="Type a keyword, idea, or concept and press Enter..." onkeyup="if(event.key === 'Enter') search()">
    <div id="results"></div>

    <script>
        async function search() {
            const q = document.getElementById('query').value;
            if(!q) return;
            document.getElementById('results').innerHTML = '<p style="color: #9ca3af;">Searching the Vault...</p>';
            
            try {
                const res = await fetch('/search', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({query: q})
                });
                const data = await res.json();
                let html = '';
                
                data.results.forEach(r => {
                    const safeText = r.text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
                    html += `<div class="result">
                        <div class="filename">${r.path}</div>
                        <pre id="text-${r.id}">${safeText}</pre>
                        <button id="btn-${r.id}" onclick="copyText('${r.id}')">Copy to Clipboard</button>
                    </div>`;
                });
                
                if(data.results.length === 0) html = '<p style="color: #9ca3af;">No results found in any document.</p>';
                document.getElementById('results').innerHTML = html;
            } catch (e) {
                document.getElementById('results').innerHTML = '<p style="color: #ef4444;">Search engine offline.</p>';
            }
        }

        function copyText(id) {
            const text = document.getElementById('text-' + id).innerText;
            navigator.clipboard.writeText(text);
            const btn = document.getElementById('btn-' + id);
            btn.innerText = 'Copied!';
            btn.classList.add('copied');
            setTimeout(() => {
                btn.innerText = 'Copy to Clipboard';
                btn.classList.remove('copied');
            }, 2000);
        }
    </script>
</body>
</html>
"""

@app.get("/")
def get_ui():
    return HTMLResponse(content=html_content)

class Query(BaseModel):
    query: str

@app.post("/search")
def search_vault(q: Query):
    query_lower = q.query.lower()
    results = []
    
    dirs = [
        "/Users/ewansair/clean-build/00_authority",
        "/Users/ewansair/clean-build/01_truth",
        "/Users/ewansair/clean-build/03_shadow",
        "/Users/ewansair/corpus-raw"
    ]
    
    result_id = 0
    for d in dirs:
        if not os.path.exists(d): continue
        for root, _, files in os.walk(d):
            if ".git" in root or "node_modules" in root: continue
            for file in files:
                if file.endswith(".md") or file.endswith(".txt"):
                    path = os.path.join(root, file)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            if query_lower in content.lower():
                                # Extract a massive chunk of text around the match so he can actually read the context
                                idx = content.lower().find(query_lower)
                                start = max(0, idx - 1000)
                                end = min(len(content), idx + 1000)
                                snippet = content[start:end]
                                results.append({
                                    "id": result_id,
                                    "path": path,
                                    "text": f"...{snippet}..."
                                })
                                result_id += 1
                                if len(results) >= 30: # Limit to 30 massive blocks
                                    return {"results": results}
                    except: pass
    return {"results": results}

def open_browser():
    time.sleep(1.0)
    webbrowser.open("http://127.0.0.1:8002")

if __name__ == "__main__":
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run(app, host="127.0.0.1", port=8002)
