import logging
from functools import lru_cache

from langchain_core.runnables import ConfigurableField
from langchain_openai import ChatOpenAI

from common.constants import IK_ACCESS_TOKEN, IK_API_URL, IK_PRODUCT_ID


@lru_cache
def get_langchain_openai_client() -> ChatOpenAI:
    logging.debug("Initializing Langchain OpenAI client")
    return ChatOpenAI(
            openai_api_base=f"{IK_API_URL}/2/ai/{IK_PRODUCT_ID}/openai/v1",
            openai_api_key=IK_ACCESS_TOKEN,
            ).configurable_fields(
            temperature=ConfigurableField(
                    id="temperature",
                    name="LLM Temperature",
                    ),
            top_p=ConfigurableField(
                    id="top_p",
                    name="LLM top_p",
                    ),
            model_name=ConfigurableField(
                    id="model",
                    name="LLM model_name",
                    ),
            max_tokens=ConfigurableField(
                    id="max_tokens",
                    name="LLM max_tokens",
                    ),
            frequency_penalty=ConfigurableField(
                    id="frequency_penalty",
                    name="LLM frequency_penalty",
                    ),
            seed=ConfigurableField(
                    id="seed",
                    name="LLM seed",
                    ),
            )
def client_from_config(**kwargs):
    """Creates and returns a configured LangChain OpenAI client.

    This function initializes a LangChain OpenAI client and applies configuration
    parameters provided as keyword arguments.

    Args:
        **kwargs: Arbitrary keyword arguments used to configure the LangChain
            OpenAI client.

    Returns:
        LangChainOpenAIClient: A configured instance of the LangChain OpenAI client.
    """
    return get_langchain_openai_client().with_config(**kwargs)