from core.agent import Agent
from core.gemini import GeminiModelHandler
from core.interface import ModelHandler
from core.openai import OpenAIModelHandler


def get_model_handler(agent: Agent) -> ModelHandler:
    if agent.model.startswith("google"):
        return GeminiModelHandler(agent)
    elif agent.model.startswith("openai"):
        return OpenAIModelHandler(agent)
    else:
        raise ValueError("Unsupported model type")
