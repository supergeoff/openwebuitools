"""
title: Vision Bridge
author: Classic298
author_url: https://github.com/Classic298
funding_url: https://github.com/Classic298
version: 1.0.0
source: https://github.com/Classic298/open-webui-plugins/tree/2adbef74cad4c8ab907d612fcbf51d26374734b7/vision-bridge (vendored; skip_if_vision_capable default flipped to True for global deploy)
description: Let a text-only model handle images without core changes: strips each image in the request to a file-id marker (pair with the analyze_image tool), or in describe mode swaps it for a text description.
"""

import re
import asyncio
import logging
from typing import Optional, Callable, Any

from pydantic import BaseModel, Field

from open_webui.models.users import Users
from open_webui.models.files import Files
from open_webui.models.chats import Chats
from open_webui.storage.provider import Storage
from open_webui.socket.main import get_event_emitter
from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.files import get_image_base64_from_file_id

log = logging.getLogger(__name__)

_FILE_ID_RE = re.compile(r"/files/([^/]+)/content")


def _file_id_of(url: str) -> Optional[str]:
    m = _FILE_ID_RE.search(url or "")
    return m.group(1) if m else None


class Filter:
    class Valves(BaseModel):
        strip_only: bool = Field(
            default=True,
            description="Just remove images from the request (replaced by a file-id marker), leaving them in the chat. Pair with the analyze_image tool for on-demand re-analysis. When false, the filter instead analyzes and swaps the image for text (needs vision_model_id).",
        )
        vision_model_id: str = Field(
            default="",
            description="Vision model used in describe mode (strip_only = false).",
        )
        analysis_prompt: str = Field(
            default="Describe this image in full detail. Transcribe any text verbatim.",
            description="Instruction sent to the vision model (describe mode).",
        )
        label: str = Field(default="Image description", description="Heading for the description (describe mode).")
        purge_from_history: bool = Field(default=True, description="Describe mode: replace the saved image with its description.")
        delete_file_record: bool = Field(default=True, description="Describe mode: delete the image file after analysis.")
        skip_if_vision_capable: bool = Field(
            default=True,
            description="If the target model is already vision-capable, do nothing (for global use).",
        )
        max_images: int = Field(default=4, description="Max images per message (describe mode).")

    def __init__(self):
        self.valves = self.Valves()

    async def inlet(
        self,
        body: dict,
        __request__: Any = None,
        __user__: Optional[dict] = None,
        __model__: Optional[dict] = None,
        __chat_id__: Optional[str] = None,
        __event_emitter__: Optional[Callable[[dict], Any]] = None,
    ) -> dict:
        if self.valves.skip_if_vision_capable and __model__:
            caps = (__model__.get("info", {}).get("meta", {}) or {}).get("capabilities") or {}
            if caps.get("vision"):
                return body

        messages = body.get("messages") or []

        # strip_only: replace each image in the request with a marker naming its file id, so the
        # text-only model never receives the image but can call analyze_image to inspect it. The
        # image is left untouched in the chat and can be re-queried with new questions later.
        if self.valves.strip_only:
            for msg in messages:
                content = msg.get("content")
                if not isinstance(content, list):
                    continue
                texts, markers = [], []
                for p in content:
                    if not isinstance(p, dict):
                        continue
                    if p.get("type") == "text":
                        texts.append(p.get("text", ""))
                    elif p.get("type") == "image_url":
                        fid = _file_id_of((p.get("image_url") or {}).get("url", ""))
                        markers.append(
                            f'[Image attached — file_id: {fid}. Call analyze_image(file_id="{fid}", query="…") to inspect it.]'
                            if fid else "[Image attached — no file id available.]"
                        )
                if markers:
                    msg["content"] = "\n\n".join([*(t for t in texts if t), *markers]).strip()
            return body

        # Describe-and-replace mode needs a configured vision model.
        if not self.valves.vision_model_id:
            return body

        target = None
        for msg in reversed(messages):
            if msg.get("role") == "user" and isinstance(msg.get("content"), list):
                if any(isinstance(p, dict) and p.get("type") == "image_url" for p in msg["content"]):
                    target = msg
                    break
        if target is None:
            return body

        if not __user__ or not __user__.get("id"):
            return body
        user = await Users.get_user_by_id(__user__["id"])
        if not user:
            return body

        async def status(d, done=False):
            if __event_emitter__:
                await __event_emitter__({"type": "status", "data": {"description": d, "done": done}})

        texts, data_urls, file_ids = [], [], []
        for part in target["content"]:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text":
                texts.append(part.get("text", ""))
            elif part.get("type") == "image_url":
                url = (part.get("image_url") or {}).get("url", "")
                if url.startswith("data:"):
                    data_urls.append(url)
                else:
                    fid = _file_id_of(url)
                    if fid:
                        file_ids.append(fid)
                        du = await get_image_base64_from_file_id(fid, user=user)
                        if du:
                            data_urls.append(du)

        data_urls = data_urls[: self.valves.max_images]
        if not data_urls:
            return body

        await status(f"Analyzing {len(data_urls)} image(s) with {self.valves.vision_model_id}…")
        try:
            parts = [{"type": "text", "text": self.valves.analysis_prompt}]
            parts += [{"type": "image_url", "image_url": {"url": du}} for du in data_urls]
            resp = await generate_chat_completion(
                __request__,
                {"model": self.valves.vision_model_id, "messages": [{"role": "user", "content": parts}], "stream": False},
                user=user, bypass_filter=True,
            )
            description = resp["choices"][0]["message"]["content"]
        except Exception as e:
            log.exception("Vision Bridge analysis failed")
            description = f"(image analysis failed: {e})"

        user_text = "\n\n".join(t for t in texts if t).strip()
        merged = f"{user_text}\n\n[{self.valves.label}]\n{description}".strip()
        target["content"] = merged
        await status("Done", done=True)

        if __chat_id__ and not __chat_id__.startswith(("local:", "channel:")) and file_ids:
            await self._persist(__chat_id__, user, set(file_ids), merged)
        return body

    async def _persist(self, chat_id, user, target_ids, new_content):
        def matches(f):
            return (f.get("id") or _file_id_of(f.get("url", ""))) in target_ids
        if self.valves.purge_from_history:
            owned = await Chats.get_chat_by_id_and_user_id(chat_id, user.id)
            if owned:
                mm = await Chats.get_messages_map_by_chat_id(chat_id) or {}
                for mid, msg in mm.items():
                    files = msg.get("files") or []
                    if not any(isinstance(f, dict) and matches(f) for f in files):
                        continue
                    kept = [f for f in files if not (isinstance(f, dict) and matches(f))]
                    await Chats.upsert_message_to_chat_by_id_and_message_id(chat_id, mid, {"files": kept, "content": new_content})
                    try:
                        emit = await get_event_emitter({"chat_id": chat_id, "message_id": mid, "user_id": user.id}, update_db=False)
                        await emit({"type": "files", "data": {"files": kept}})
                        await emit({"type": "replace", "data": {"content": new_content}})
                    except Exception:
                        log.exception("Vision Bridge: client sync failed for %s", mid)
                    break
        if self.valves.delete_file_record:
            for fid in target_ids:
                try:
                    f = await Files.get_file_by_id(fid)
                    if f and (f.user_id == user.id or user.role == "admin"):
                        if await Files.delete_file_by_id(fid) and f.path:
                            await asyncio.to_thread(Storage.delete_file, f.path)
                except Exception:
                    log.exception("Vision Bridge: delete failed for %s", fid)
