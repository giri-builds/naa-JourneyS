import os
import json
import requests
from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def generate(self, messages: list[dict]) -> str:
        ...


class GroqProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.environ['GROQ_API_KEY']
        self.model = os.environ.get('GROQ_MODEL', 'llama-3.3-70b-versatile')

    def generate(self, messages: list[dict]) -> str:
        response = requests.post(
            'https://api.groq.com/openai/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': self.model,
                'messages': messages,
                'temperature': 0.3,
                'max_tokens': 1024,
            },
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']


class ClaudeProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.environ['ANTHROPIC_API_KEY']
        self.model = os.environ.get('CLAUDE_MODEL', 'claude-haiku-4-5-20251001')

    def generate(self, messages: list[dict]) -> str:
        system = next((m['content'] for m in messages if m['role'] == 'system'), '')
        user_messages = [m for m in messages if m['role'] != 'system']

        response = requests.post(
            'https://api.anthropic.com/v1/messages',
            headers={
                'x-api-key': self.api_key,
                'anthropic-version': '2023-06-01',
                'Content-Type': 'application/json',
            },
            json={
                'model': self.model,
                'max_tokens': 1024,
                'system': system,
                'messages': user_messages,
            },
        )
        response.raise_for_status()
        return response.json()['content'][0]['text']


class OpenAIProvider(LLMProvider):
    def __init__(self):
        self.api_key = os.environ['OPENAI_API_KEY']
        self.model = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

    def generate(self, messages: list[dict]) -> str:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
            },
            json={
                'model': self.model,
                'messages': messages,
                'temperature': 0.3,
                'max_tokens': 1024,
            },
        )
        response.raise_for_status()
        return response.json()['choices'][0]['message']['content']


class OllamaProvider(LLMProvider):
    def __init__(self):
        self.base_url = os.environ.get('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.model = os.environ.get('OLLAMA_MODEL', 'llama3.2')

    def generate(self, messages: list[dict]) -> str:
        response = requests.post(
            f'{self.base_url}/api/chat',
            json={
                'model': self.model,
                'messages': messages,
                'stream': False,
            },
        )
        response.raise_for_status()
        return response.json()['message']['content']


PROVIDERS = {
    'groq': GroqProvider,
    'claude': ClaudeProvider,
    'openai': OpenAIProvider,
    'ollama': OllamaProvider,
}


def get_llm_provider() -> LLMProvider:
    provider_name = os.environ.get('LLM_PROVIDER', 'groq')
    provider_class = PROVIDERS.get(provider_name)
    if not provider_class:
        raise ValueError(f"Unknown LLM provider: {provider_name}. Options: {list(PROVIDERS.keys())}")
    return provider_class()
