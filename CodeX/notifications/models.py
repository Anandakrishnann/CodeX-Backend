from django.db import models
from Accounts.models import *

class Notification(models.Model):
    user = models.ForeignKey(Accounts, on_delete=models.CASCADE)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.message[:20]}"