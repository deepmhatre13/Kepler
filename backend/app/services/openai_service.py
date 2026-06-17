import httpx
from app.core.config import settings
import logging
from typing import Dict, Any

logger = logging.getLogger("app")

class OpenAIService:
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.api_url = "https://api.openai.com/v1/chat/completions"

    def explain_collision(self, details: Dict[str, Any]) -> str:
        """
        Queries GPT to explain the risk context of a conjunction prediction.
        """
        if self.api_key == "mock-key":
            return (
                f"Object A ({details.get('obj_a', 'ISS')}) and Object B ({details.get('obj_b', 'Debris')}) "
                f"are predicted to cross orbits at an altitude of {details.get('altitude', 408)}km. "
                f"The miss distance is estimated to be {details.get('miss', 42)}m with a relative velocity of "
                f"{details.get('speed', 14.2)} km/s. AI Agents recommend executing a station-keeping burn."
            )
        
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "gpt-4-turbo",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a senior aerospace system engineer briefing mission operations on an orbital conjunction risk."
                    },
                    {
                        "role": "user",
                        "content": f"Analyze this conjunction threat: Satellite: {details.get('obj_a')}, Debris: {details.get('obj_b')}, Probability: {details.get('prob')}, Miss Distance: {details.get('miss')}m. Provide a 2-sentence risk summary."
                    }
                ],
                "max_tokens": 150
            }
            resp = httpx.post(self.api_url, headers=headers, json=payload, timeout=10.0)
            if resp.status_code == 200:
                return resp.json()["choices"][0]["message"]["content"].strip()
            raise Exception(f"OpenAI API error: {resp.text}")
        except Exception as e:
            logger.error(f"OpenAI query failed, falling back: {e}")
            return f"Conjunction threat verified between {details.get('obj_a')} and {details.get('obj_b')}. Evacuation maneuver recommended."

openai_service = OpenAIService()
