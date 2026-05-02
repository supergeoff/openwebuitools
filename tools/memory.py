"""title: Honcho Memory (Global Per User)
author: supergeoff
version: 1.0
description: Persistent Honcho memory for all of OpenWebUI – proactive and per-user
requirements: honcho-ai
"""

from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from honcho import Honcho

class UserValves(BaseModel):
    HONCHO_API_KEY: str = Field(
        default="",
        description="🔑 Your Honcho API key (https://app.honcho.dev → API Keys)"
    )
    HONCHO_USERNAME: str = Field(
        default="",
        description="👤 Your Honcho identifier (e.g., your email or username). Used as Peer ID."
    )
    HONCHO_WORKSPACE: str = Field(
        default="openwebui",
        description="Honcho workspace name (leave as 'openwebui' by default)"
    )

class Tools:
    def __init__(self):
        self.user_valves = UserValves()

    async def get_honcho_context(self, __user__: dict = None) -> str:
        """
        Retrieves the relevant Honcho memory context (the most relevant from ALL your conversations).
        Call this systematically at the start of a conversation.
        """
        if not __user__ or not self.user_valves.HONCHO_API_KEY:
            return "[Honcho] API key not configured for this user."

        try:
            honcho = Honcho(
                api_key=self.user_valves.HONCHO_API_KEY,
                workspace=self.user_valves.HONCHO_WORKSPACE
            )

            # One peer per unique user
            username = self.user_valves.HONCHO_USERNAME or __user__.get("email") or __user__.get("id", "anonymous")
            peer = honcho.peer(f"user_{username}")

            # Global unique session (memory shared across all of OpenWebUI)
            session = peer.session("global_openwebui_memory")

            # Intelligent context (Honcho handles filtering + summarization)
            context = session.context(tokens=2200)
            return context.to_openai() if hasattr(context, "to_openai") else str(context)

        except Exception as e:
            return f"[Honcho Error] {str(e)}"

    async def store_in_honcho(self, user_message: str, assistant_response: str, __user__: dict = None) -> str:
        """
        Stores the full exchange in Honcho.
        Call this at the end of each response.
        """
        if not self.user_valves.HONCHO_API_KEY:
            return "[Honcho] API key not configured."

        try:
            honcho = Honcho(
                api_key=self.user_valves.HONCHO_API_KEY,
                workspace=self.user_valves.HONCHO_WORKSPACE
            )

            username = self.user_valves.HONCHO_USERNAME or __user__.get("email") or __user__.get("id", "anonymous")
            peer = honcho.peer(f"user_{username}")
            session = peer.session("global_openwebui_memory")

            session.add_messages([
                {"role": "user", "content": user_message},
                {"role": "assistant", "content": assistant_response}
            ])
            return "✅ Honcho memory updated (global per user)."
        except Exception as e:
            return f"[Honcho Error] {str(e)}"
