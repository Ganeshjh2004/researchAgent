from datetime import datetime

from langchain_core.tools import tool
from langchain_community.tools import (
    WikipediaQueryRun,
    DuckDuckGoSearchResults,
)
from langchain_community.utilities import WikipediaAPIWrapper


@tool
def save_to_txt(
    data: str,
    filename: str = "research_output.txt"
) -> str:
    """Save research data to a text file."""

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    formatted_text = (
        f"--- Research Output ---\n"
        f"Timestamp: {timestamp}\n\n"
        f"{data}\n\n"
    )
    
    import os
    reports_dir = os.path.join(os.path.dirname(__file__), "reports")
    os.makedirs(reports_dir, exist_ok=True)
    file_path = os.path.join(reports_dir, filename)

    with open(file_path, "a", encoding="utf-8") as f:
        f.write(formatted_text)

    return f"Research saved successfully to {filename}"


# DuckDuckGo — structured output with title, snippet, and link per result
search = DuckDuckGoSearchResults(max_results=4, output_format="list")

search_tool = search


# Wikipedia
wiki = WikipediaQueryRun(
    api_wrapper=WikipediaAPIWrapper(
        top_k_results=1,
        doc_content_chars_max=2000,
    )
)

wiki_tool = wiki


# All tools
tools = [
    search_tool,
    wiki_tool,
    save_to_txt,
]