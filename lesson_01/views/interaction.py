import uuid
from django.shortcuts import render
from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from lesson_01.models import ChatMessage
from lesson_01.services.interaction_service import chat_with_agent


@require_GET
def interaction_view(request: HttpRequest) -> HttpResponse:
    """Render the full chat workspace partial."""
    session_id = request.session.setdefault("l01_chat_session", str(uuid.uuid4()))
    messages   = ChatMessage.objects.filter(session_id=session_id)
    return render(request, "lesson_01/interaction.html",
                  {"messages": messages, "session_id": session_id})


@require_POST
def interaction_api(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint — returns only the new message pair HTML snippet."""
    session_id  = request.session.setdefault("l01_chat_session", str(uuid.uuid4()))
    user_input  = request.POST.get("message", "").strip()
    if not user_input:
        return HttpResponse("")

    ai_response = chat_with_agent(session_id, user_input)
    return render(request, "lesson_01/partials/chat_message.html",
                  {"user_msg": user_input, "ai_msg": ai_response})
