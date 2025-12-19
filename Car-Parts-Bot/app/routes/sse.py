# app/routes/sse.py
from flask import Blueprint, Response
from ..redis_client import redis_client
import json

sse_bp = Blueprint("sse", __name__)

@sse_bp.route("/events")
def events():
    def stream():
        pubsub = redis_client.pubsub()
        pubsub.subscribe("chatbot_events")

        # listen() blocks, yields messages as they arrive
        for message in pubsub.listen():
            if message is None:
                continue
            if message.get("type") != "message":
                continue
            data = message.get("data")
            # data is already a JSON string from publisher; send as SSE data
            yield f"data: {data}\n\n"

    return Response(stream(), mimetype="text/event-stream")
