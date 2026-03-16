from django.db import models


class ChatMessage(models.Model):
    session_id = models.CharField(max_length=64, db_index=True)
    role       = models.CharField(max_length=8)   # "human" | "ai"
    content    = models.TextField()
    timestamp  = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["timestamp"]

    def __str__(self):
        return f"[{self.role}] {self.content[:60]}"
