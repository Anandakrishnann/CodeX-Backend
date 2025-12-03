from django.db import models
from datetime import date
from django.conf import settings



class TutorApplications(models.Model):
    account = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    id = models.BigAutoField(primary_key=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone = models.CharField(max_length=15)
    dob = models.DateField(null=True, blank=True)
    education = models.CharField(max_length=255, null=True, blank=True)
    expertise = models.CharField(max_length=255, null=True, blank=True)
    occupation = models.CharField(max_length=255, null=True, blank=True)
    experience = models.CharField(max_length=255, null=True, blank=True)
    about = models.TextField(null=True, blank=True)

    profile_picture = models.URLField(blank=True, null=True, max_length=500)
    verification_file = models.URLField(blank=True, null=True, max_length=500)
    verification_video = models.URLField(blank=True, null=True, max_length=500)  

    created_at = models.DateTimeField(auto_now_add=True) 
    STATUS_CHOICES = [('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')]
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
 
    def __str__(self):
        return self.full_name
    
    def get_age(self):
        """Returns the age of the tutor based on their date of birth."""
        if self.dob:
            today = date.today()
            return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
        return None  



class TutorRejectionHistory(models.Model):
    application = models.ForeignKey(TutorApplications, on_delete=models.CASCADE, related_name="rejection_logs")
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Rejection for {self.application.full_name} at {self.created_at}"
    
    

class CourseRejectionHistory(models.Model):
    course = models.ForeignKey("tutorpanel.Course", on_delete=models.CASCADE, related_name="rejection_logs")
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        from tutorpanel.models import Course  
        return f"Rejection for {self.course.title} at {self.created_at}"
    
    
    
class ModuleRejectionHistory(models.Model):
    module = models.ForeignKey("tutorpanel.Modules", on_delete=models.CASCADE, related_name="rejection_logs")
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        from tutorpanel.models import Modules  
        return f"Rejection for {self.module.title} at {self.created_at}"
    
    
    
class LessonRejectionHistory(models.Model):
    lesson = models.ForeignKey("tutorpanel.Lessons", on_delete=models.CASCADE, related_name="rejection_logs")
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        from tutorpanel.models import Lessons  
        return f"Rejection for {self.lesson.title} at {self.created_at}"



class Plan(models.Model):
    PLAN_TYPE_CHOICES = [('MONTHLY', 'Monthly'), ('YEARLY', 'Yearly')]
    PLAN_CATEGORY_CHOICES = [('BASIC', 'Basic'), ('PRO', 'Pro'), ('PREMIUM', 'Premium')]

    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=10, choices=PLAN_TYPE_CHOICES)
    plan_category = models.CharField(max_length=10, choices=PLAN_CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    description = models.TextField()
    stripe_price_id = models.CharField(max_length=100, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    deactivate = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.plan_type}"



class CourseCategory(models.Model):
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=500)
    created_at = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name