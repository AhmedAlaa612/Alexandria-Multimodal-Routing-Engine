from google import genai
import os

class GeminiClient:
    """Class responsible for communicating with the Gemini model via Google AI Studio"""
    
    def __init__(self, api_key, model_name=None):
        # Initialize the client with the new SDK
        self.client = genai.Client(api_key=api_key)
        # Allow passing the model explicitly, fallback to environment or default
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        
    def generate(self, prompt):
        """Send a prompt to the model and receive a response"""
        try:
            # Send Prompt and receive the reply
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text
        except Exception as e:
            print(f"An error occurred in Gemini API: {e}")
            return None
