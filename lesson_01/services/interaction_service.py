from django.conf import settings
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from lesson_01.models import ChatMessage


def _get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.OPENROUTER_DEFAULT_MODEL,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
    )


def chat_with_agent(session_id: str, new_message: str) -> str:
    history = ChatMessage.objects.filter(session_id=session_id)

    messages = [SystemMessage(content="You are a helpful assistant.")]
    for msg in history:
        cls = HumanMessage if msg.role == "human" else AIMessage
        messages.append(cls(content=msg.content))
    messages.append(HumanMessage(content=new_message))

    response = _get_llm().invoke(messages)
    ai_content = response.content

    ChatMessage.objects.create(session_id=session_id, role="human", content=new_message)
    ChatMessage.objects.create(session_id=session_id, role="ai",    content=ai_content)
    return ai_content
