"""Screen vision: screenshot your chart and ask Claude what it sees.

Claude's read is used ONLY as a filter (it can veto a trade, never start one).
Each screenshot costs a few cents of API usage, so it runs every N polls.

Needs: `pip install anthropic mss` and an Anthropic API key
(`export ANTHROPIC_API_KEY=...` or `ant auth login`).
"""
from __future__ import annotations

import base64
import json
import re

PROMPT = """You are reviewing a screenshot of a crypto futures chart for {symbol}.
Describe only what is visible: trend direction, recent support/resistance, and
whether price action looks choppy or trending. Do not guess at things you can't see.

Reply with ONLY a JSON object, no other text:
{{"bias": "bullish" | "bearish" | "neutral", "confidence": 0.0-1.0, "notes": "<one sentence>"}}"""


def capture_screen(monitor_index: int = 1) -> bytes:
    """Return a PNG screenshot of one monitor."""
    import mss
    import mss.tools

    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[monitor_index])
        return mss.tools.to_png(shot.rgb, shot.size)


def parse_vision_reply(text: str) -> dict:
    """Pull the JSON object out of Claude's reply; fall back to neutral if unreadable."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    try:
        data = json.loads(match.group(0)) if match else {}
    except json.JSONDecodeError:
        data = {}
    bias = data.get("bias") if data.get("bias") in ("bullish", "bearish", "neutral") else "neutral"
    try:
        confidence = min(1.0, max(0.0, float(data.get("confidence", 0.0))))
    except (TypeError, ValueError):
        confidence = 0.0
    return {"bias": bias, "confidence": confidence, "notes": str(data.get("notes", ""))}


class ChartVision:
    def __init__(self, model: str = "claude-opus-5-5", monitor_index: int = 1):
        import anthropic

        self.client = anthropic.Anthropic()
        self.model = model
        self.monitor_index = monitor_index

    def analyze(self, symbol: str, png: bytes | None = None) -> dict:
        png = png or capture_screen(self.monitor_index)
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=2000,
            output_config={"effort": "low"},
            # If a safety check declines the request, retry on a fallback model automatically.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image", "source": {
                        "type": "base64", "media_type": "image/png",
                        "data": base64.standard_b64encode(png).decode("utf-8")}},
                    {"type": "text", "text": PROMPT.format(symbol=symbol)},
                ],
            }],
        )
        if response.stop_reason == "refusal":
            return {"bias": "neutral", "confidence": 0.0, "notes": "model declined"}
        text = "".join(b.text for b in response.content if b.type == "text")
        return parse_vision_reply(text)


def vision_allows(signal_side: str, read: dict, min_confidence: float = 0.6) -> bool:
    """Veto a trade only if Claude is confident the chart points the OTHER way."""
    if read["confidence"] < min_confidence:
        return True
    if signal_side == "long" and read["bias"] == "bearish":
        return False
    if signal_side == "short" and read["bias"] == "bullish":
        return False
    return True
