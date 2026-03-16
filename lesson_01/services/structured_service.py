from pydantic import BaseModel, Field
from django.conf import settings
from langchain_openai import ChatOpenAI


class EvaluationResult(BaseModel):
    score: int = Field(description="Score from 1 (worst) to 10 (best)")
    strengths: list[str] = Field(description="Key strengths of the text")
    weaknesses: list[str] = Field(description="Key weaknesses or areas for improvement")
    summary: str = Field(description="One-sentence overall assessment")


def evaluate_text(text: str) -> EvaluationResult:
    llm = ChatOpenAI(
        model=settings.OPENROUTER_DEFAULT_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )
    structured_llm = llm.with_structured_output(EvaluationResult)
    return structured_llm.invoke(
        f"Evaluate the following text on a scale from 1 to 10. "
        f"List its strengths and weaknesses, and give a one-sentence summary.\n\n{text}"
    )
