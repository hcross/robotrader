from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from .agents.orchestrator import OrchestratorAgent
from .strands.a2a import Message
import asyncio
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Orchestrator
orchestrator = OrchestratorAgent()
orchestrator.start()

@app.websocket("/ws/chat")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            # Send to Orchestrator
            # In a real app, we'd need a way to route the response back to this specific websocket
            # For now, we'll just mock the interaction or assume the Orchestrator returns immediately
            
            print(f"Received from UI: {data}")
            
            # Simulate Orchestrator processing
            orchestrator.receive(Message(sender="User", recipient="Orchestrator", msg_type="USER_COMMAND", content=data))
            
            # Mock response back to UI (since Orchestrator is async/threaded and doesn't return here)
            # In a real Strands implementation, we'd have a callback or a queue to listen to
            await websocket.send_text(json.dumps({"role": "agent", "content": f"I received: {data}. (Backend connected)"}))
            
    except WebSocketDisconnect:
        print("Client disconnected")
