# core/llm_utils.py
import openai
import json
import re # Ensure re is imported
from config import (
    OPENROUTER_API_KEY,
    OPENROUTER_LLM_MODEL,
    OPENROUTER_API_BASE,
    OPENROUTER_REFERRER_URL,
    OPENROUTER_APP_NAME
)

if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY not found in .env file or environment variables.")

client = openai.OpenAI(
    api_key=OPENROUTER_API_KEY,
    base_url=OPENROUTER_API_BASE,
)

def get_llm_response(prompt, system_message="You are a helpful assistant.", model=None):
    selected_model = model if model else OPENROUTER_LLM_MODEL
    
    extra_headers = {}
    if OPENROUTER_REFERRER_URL:
        extra_headers["HTTP-Referer"] = OPENROUTER_REFERRER_URL
    if OPENROUTER_APP_NAME:
        extra_headers["X-Title"] = OPENROUTER_APP_NAME

    print(f"\nDEBUG LLM CALL ATTEMPT: Model='{selected_model}'")
    print(f"DEBUG LLM CALL System Message (first 100 chars): \"{system_message[:100]}...\"")
    print(f"DEBUG LLM CALL User Prompt (first 100 chars): \"{prompt[:100]}...\"")

    try:
        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3, # Lower temperature for more deterministic classification/extraction
            extra_headers=extra_headers if extra_headers else None
        )
        llm_output = response.choices[0].message.content.strip()
        print(f"DEBUG LLM CALL SUCCESS: Model='{selected_model}'. Output (first 100 chars): \"{llm_output[:100]}...\"")
        return llm_output
    except openai.APIConnectionError as e:
        print(f"LLM_UTIL_ERROR: OpenRouter APIConnectionError for model '{selected_model}': {e}")
    except openai.RateLimitError as e:
        print(f"LLM_UTIL_ERROR: OpenRouter RateLimitError for model '{selected_model}': {e}")
    except openai.APIStatusError as e:
        print(f"LLM_UTIL_ERROR: OpenRouter APIStatusError for model '{selected_model}': Status Code: {e.status_code}. Response: {e.response}")
    except Exception as e:
        print(f"LLM_UTIL_ERROR: Error calling OpenRouter API with model '{selected_model}': {e.__class__.__name__}: {e}")
    
    print(f"DEBUG LLM CALL FAILED or Errored for model '{selected_model}'. Returning None.")
    return None

def get_llm_json_response(prompt, system_message="You are a helpful assistant that always responds in JSON format.", model=None):
    selected_model = model if model else OPENROUTER_LLM_MODEL

    # Augment system message for better JSON output, especially for chatty models
    augmented_system_message = system_message
    if "json" not in system_message.lower(): # Add if not already explicitly stated
        augmented_system_message += " Your entire response must be a single, valid JSON object."
    # Stronger instruction for some models
    if any(m_name in selected_model.lower() for m_name in ["gemini", "claude", "deepseek", "llama"]):
        augmented_system_message += " Do not include any explanatory text, conversation, or markdown formatting (like ```json) around the JSON object. Output ONLY the JSON object itself, starting with '{' and ending with '}' or starting with '[' and ending with ']'."
    
    raw_response = get_llm_response(prompt, augmented_system_message, selected_model)

    if raw_response is None:
        print(f"DEBUG JSON PARSING: get_llm_json_response received NO raw_response (API call likely failed and error printed above) for model '{selected_model}'.")
        return None 

    print(f"DEBUG JSON PARSING: Raw Response from LLM (model '{selected_model}'):\n---BEGIN RAW---\n{raw_response}\n---END RAW---")

    # Initialize cleaned_response with the raw response
    cleaned_response = raw_response.strip()
    
    # Attempt 1: Look for markdown-wrapped JSON (```json ... ```)
    match_markdown_json = re.search(r"```json\s*([\s\S]*?)\s*```", cleaned_response, re.DOTALL)
    if match_markdown_json:
        cleaned_response = match_markdown_json.group(1).strip()
        print(f"DEBUG JSON PARSING: Extracted from ```json block.")
    else:
        # Attempt 2: Look for generic markdown block (``` ... ```) if specific json one wasn't found
        match_markdown_generic = re.search(r"```\s*([\s\S]*?)\s*```", cleaned_response, re.DOTALL)
        if match_markdown_generic:
            cleaned_response = match_markdown_generic.group(1).strip()
            print(f"DEBUG JSON PARSING: Extracted from generic ``` block.")
        else:
            # Attempt 3: If no markdown, try to find the last apparent JSON object
            # This is for chatty models that put JSON at the end without markdown
            last_brace = cleaned_response.rfind('{')
            last_square_bracket = cleaned_response.rfind('[')

            # Determine if the JSON likely starts with '{' or '[' based on which is last
            # and seems to be part of a potential JSON structure at the end.
            potential_json_start_index = -1
            if last_brace != -1 and (last_square_bracket == -1 or last_brace > last_square_bracket):
                # Check if the character before the last brace suggests it's not embedded (e.g., not part of a word)
                # This is a weak heuristic.
                if last_brace == 0 or not cleaned_response[last_brace-1].isalnum():
                    potential_json_start_index = last_brace
            elif last_square_bracket != -1:
                if last_square_bracket == 0 or not cleaned_response[last_square_bracket-1].isalnum():
                    potential_json_start_index = last_square_bracket
            
            if potential_json_start_index != -1:
                candidate_str = cleaned_response[potential_json_start_index:]
                # Test if this candidate string is valid JSON
                try:
                    json.loads(candidate_str) # Test load
                    cleaned_response = candidate_str # If it loads, this is our best bet
                    print(f"DEBUG JSON PARSING: Extracted candidate JSON from rfind: \"{cleaned_response[:100]}...\"")
                except json.JSONDecodeError:
                    # Candidate was not valid JSON, stick with the (potentially full) cleaned_response
                    print(f"DEBUG JSON PARSING: Candidate from rfind was not valid JSON. Original cleaned_response (after markdown attempt) will be used.")
                    pass # cleaned_response remains as it was after markdown checks
            # else: cleaned_response remains as it was (either full raw or after markdown)

    print(f"DEBUG JSON PARSING: Final Cleaned Response for JSON parsing (model '{selected_model}'):\n---BEGIN CLEANED---\n{cleaned_response}\n---END CLEANED---")

    try:
        if not cleaned_response.strip(): # Check if cleaned_response is empty or whitespace
            print(f"LLM_UTIL_ERROR: Cleaned response is EMPTY for model '{selected_model}'. Cannot parse as JSON.")
            return {"error": "LLM returned empty string after cleaning", "raw_response": raw_response, "cleaned_response": cleaned_response}

        # Attempt to parse the cleaned response
        parsed_json = json.loads(cleaned_response)
        print(f"DEBUG JSON PARSING: JSON.loads SUCCESSFUL for model '{selected_model}'.")
        return parsed_json
    except json.JSONDecodeError as e:
        # If "Extra data" error, it means we parsed a valid JSON object but there's trailing text.
        if "Extra data" in str(e):
            print(f"LLM_UTIL_WARNING: JSONDecodeError with 'Extra data' for model '{selected_model}': {e}. Attempting to extract leading JSON.")
            try:
                # Use json.JSONDecoder().raw_decode() to get the first valid JSON object and its end position
                decoder = json.JSONDecoder()
                obj, end_idx = decoder.raw_decode(cleaned_response) # cleaned_response should be the string that caused "Extra data"
                print(f"DEBUG JSON PARSING: Extracted leading JSON successfully after 'Extra data' error. End index: {end_idx}")
                return obj # Return the successfully decoded part
            except json.JSONDecodeError as e2:
                # This means that even raw_decode failed, which is less common if the first error was "Extra data"
                print(f"LLM_UTIL_ERROR: Failed to re-parse with raw_decode after 'Extra data' error for model '{selected_model}': {e2}")
                return {"error": "Failed to parse LLM response as JSON after 'Extra data' attempt (raw_decode failed)", "raw_response": raw_response, "cleaned_response": cleaned_response}
        
        # For other JSONDecodeErrors (e.g., "Expecting value", "Unterminated string")
        print(f"LLM_UTIL_ERROR: Failed to parse LLM JSON response (model '{selected_model}'): {e}")
        return {"error": "Failed to parse LLM response as JSON", "raw_response": raw_response, "cleaned_response": cleaned_response}
    except Exception as e: 
        # Catch any other unexpected errors during parsing
        print(f"LLM_UTIL_ERROR: An unexpected error occurred during JSON parsing from model '{selected_model}': {e.__class__.__name__}: {e}")
        return {"error": "Unexpected error during JSON parsing", "raw_response": raw_response}