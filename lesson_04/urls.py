from django.urls import path
from lesson_04.views import audio, video_gen, image, report, sendit

urlpatterns = [
    # Audio transcription + LLM summary
    path("audio/",       audio.audio_view,           name="l04_audio"),
    path("audio/api/",   audio.audio_api,             name="l04_audio_api"),

    # Video generation (HTMX polling pattern)
    path("video/",            video_gen.video_gen_view,  name="l04_video_gen"),
    path("video/api/",        video_gen.video_gen_api,   name="l04_video_gen_api"),
    path("video/status/<str:task_id>/", video_gen.video_status, name="l04_video_status"),

    # Image generation (DALL-E 3)
    path("image/",       image.image_view,            name="l04_image"),
    path("image/api/",   image.image_api,              name="l04_image_api"),

    # PDF report generation
    path("report/",             report.report_view,          name="l04_report"),
    path("report/preview/",     report.report_preview_api,   name="l04_report_preview"),
    path("report/download/",    report.report_download,      name="l04_report_download"),

    # SPK transport declaration quest
    path("sendit/",      sendit.sendit_view,          name="l04_sendit"),
    path("sendit/api/",  sendit.sendit_api,            name="l04_sendit_api"),
]
