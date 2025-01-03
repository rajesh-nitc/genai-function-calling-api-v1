import logging

from vertexai.generative_models import GenerativeModel, Part

from config.exceptions import PromptExceededError, QuotaExceededError
from config.registry import FUNCTION_REGISTRY
from utils.gcs import get_same_day_chat_messages
from utils.llm import extract_function_calls, extract_text
from utils.postchecks import postchecks
from utils.prechecks import prechecks

logger = logging.getLogger(__name__)


async def generate_model_response(
    prompt: str, model: GenerativeModel, user_id: str
) -> str:
    """
    Generate model response.
    """
    logger.info(f"Received prompt from user {user_id}: {prompt}")

    # Perform prechecks
    try:
        await prechecks(prompt, model, user_id)
    except QuotaExceededError as e:
        logger.error(f"Quota check failed for user {user_id}: {str(e)}")
        return f"Error: {str(e)}"
    except PromptExceededError as e:
        logger.error(f"Prompt check failed for user {user_id}: {str(e)}")
        return f"Error: {str(e)}"

    # Retrieve user's chat history for the same day
    history = get_same_day_chat_messages(user_id)

    # Start a new chat session with history
    chat = model.start_chat(history=history)

    # Send new prompt to the model
    response = await chat.send_message_async(prompt)

    # Log Model response to prompt
    logger.info(f"Model response to prompt: {response}")

    # Function calling loop
    function_calling_in_process = True
    while function_calling_in_process:

        # Extract function call(s)
        function_calls = extract_function_calls(response)
        if function_calls:
            # Hold the api response(s)
            api_responses = []

            for function_call in function_calls:
                function_name, function_args = next(iter(function_call.items()))
                logger.info(
                    f"function_name: {function_name}, function_args: {function_args}"
                )

                # Call the function handler and store the response
                api_response = await FUNCTION_REGISTRY[function_name](function_args)

                # Append api response(s)
                api_responses.append(
                    Part.from_function_response(
                        name=function_name,
                        response={"content": api_response},
                    )
                )

            # Number of function call(s) and number of api response(s) should match.
            if len(api_responses) != len(function_calls):
                logger.error(
                    "Number of function call(s) and number of api response(s) should match."
                )
                raise ValueError(
                    "Number of function call(s) and number of api response(s) should match."
                )

            # Send api response(s) back to model
            response = await chat.send_message_async(api_responses)

            # Log Model response to api response(s)
            logger.info(f"Model response to api response(s): {response}")

        else:
            function_calling_in_process = False
            final_response = extract_text(response)

    # Perform postchecks
    await postchecks(prompt, final_response, response, user_id)

    return final_response
