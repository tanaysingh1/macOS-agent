"""
Research Subagent Handler - Web Search Implementation

This handler performs web searches using OpenAI's web search tool.
It takes a prompt, searches for relevant information, and returns structured results.
"""

import os
from typing import Dict, Any
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables from parent directory
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

def handle(prompt: str, context: str) -> Dict[str, Any]:
    """
    Handle web search requests using OpenAI's web search tool.
    
    Args:
        prompt: The search query/prompt
        context: Context string from previous steps (not used in search but available)
    
    Returns:
        Dict containing prompt and search response
    """
    try:
        print(f"🔍 Searching for: {prompt}")
        
        # Initialize OpenAI client
        client = OpenAI()
        
        # Perform web search using OpenAI
        response = client.responses.create(
            model="gpt-5",
            tools=[{"type": "web_search"}],
            input=prompt
        )
        
        # Extract the search results from the response
        search_results = response.output_text
        
        result = {
            "prompt": prompt,
            "response": str(search_results),
            "handler_type": "web_search"
        }
        
        print(f"✅ Search completed successfully")
        return result
        
    except Exception as e:
        print(f"❌ Error during web search: {e}")
        # Return error result but don't crash the entire process
        return {
            "prompt": prompt,
            "response": f"Error performing search: {str(e)}",
            "handler_type": "web_search",
            "error": True
        }

def generateMarkdown(result: Dict[str, Any]) -> str:
    """
    Generate markdown summary of the web search results.
    
    Args:
        result: The result dictionary from handle()
    
    Returns:
        Markdown formatted string describing the search action and results
    """
    prompt = result.get("prompt", "Unknown query")
    response = result.get("response", "No response")
    
    if result.get("error"):
        return f"The agent attempted to search for the answer to \"{prompt}\" but encountered an error: {response}"
    
    return f"The agent searched for the answer to \"{prompt}\". It found the following information: \"{response}\"."