from pydantic import BaseModel, Field
from langchain.tools import tool


class SearchInput(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="The search query. Be specific for better results."
    )

    max_results: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of results to return. Between 1 and 20."
    )


@tool(args_schema=SearchInput)
def search_documents(query: str, max_results: int = 5) -> list:
    """Search the internal document store for relevant content."""

    return [
        {
            "id": f"doc-{i}",
            "title": f"Result {i} for '{query}'",
            "score": 0.9 - i * 0.1
        }
        for i in range(max_results)
    ]


# Test invalid query
try:
    search_documents.invoke({
        "query": "",
        "max_results": 5
    })
except Exception as e:
    print("Caught error:", e)


# Test valid input
result = search_documents.invoke({
    "query": "vacation policy",
    "max_results": 2
})

print("Results:", result)


# Show tool information
print("\n--- Tool Information ---")

print("Tool name:", search_documents.name)
print("Description:", search_documents.description)
print("Schema:", search_documents.args_schema.model_json_schema())


# Test max_results validation
print("\n--- Max Results Validation Test ---")

try:
    search_documents.invoke({
        "query": "vacation policy",
        "max_results": 25
    })
except Exception as e:
    print("Caught error:", e)