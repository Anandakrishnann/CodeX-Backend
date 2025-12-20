from django.db import models
from datetime import date
from django.conf import settings
from django.core.exceptions import ValidationError



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
    
    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['account']),
            models.Index(fields=['created_at']),
            models.Index(fields=['email']),
            models.Index(fields=['status', 'created_at']),
        ]
 
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

    class Meta:
        indexes = [
            models.Index(fields=['application']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Rejection for {self.application.full_name} at {self.created_at}"
    
    

class CourseRejectionHistory(models.Model):
    course = models.ForeignKey("tutorpanel.Course", on_delete=models.CASCADE, related_name="rejection_logs")
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['course']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        from tutorpanel.models import Course  
        return f"Rejection for {self.course.title} at {self.created_at}"
    
    
    
class ModuleRejectionHistory(models.Model):
    module = models.ForeignKey("tutorpanel.Modules", on_delete=models.CASCADE, related_name="rejection_logs")
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['module']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        from tutorpanel.models import Modules  
        return f"Rejection for {self.module.title} at {self.created_at}"
    
    
    
class LessonRejectionHistory(models.Model):
    lesson = models.ForeignKey("tutorpanel.Lessons", on_delete=models.CASCADE, related_name="rejection_logs")
    admin = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['lesson']),
            models.Index(fields=['created_at']),
        ]

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

    class Meta:
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['plan_type']),
            models.Index(fields=['plan_category']),
            models.Index(fields=['is_active', 'plan_type']),
        ]

    def __str__(self):
        return f"{self.name} - {self.plan_type}"



class CourseCategory(models.Model):
    name = models.CharField(max_length=200)
    description = models.CharField(max_length=500)
    created_at = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
            models.Index(fields=['is_active', 'created_at']),
        ]

    def __str__(self):
        return self.name



class PayoutRequest(models.Model):
    tutor = models.ForeignKey("Accounts.TutorDetails", on_delete=models.CASCADE)
    wallet = models.ForeignKey("tutorpanel.Wallet", on_delete=models.CASCADE, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    upi_id = models.CharField(max_length=100)
    bank_name = models.CharField(max_length=100, null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=[
            ("PENDING", "Pending"),
            ("PAID", "Paid"),
            ("REJECTED", "Rejected"),
        ],
        default="PENDING"
    )

    requested_at = models.DateTimeField(auto_now_add=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    admin_note = models.TextField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['tutor']),
            models.Index(fields=['status']),
            models.Index(fields=['requested_at']),
            models.Index(fields=['tutor', 'status']),
            models.Index(fields=['status', 'requested_at']),
        ]



class PlatformWallet(models.Model):
    total_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.pk = 1  

        if PlatformWallet.objects.exclude(pk=1).exists():
            raise ValidationError("Only one PlatformWallet instance is allowed.")

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("PlatformWallet cannot be deleted.")

    def __str__(self):
        return "Platform Wallet (Singleton)"



class PlatformWalletTransaction(models.Model):
    wallet = models.ForeignKey(PlatformWallet, on_delete=models.CASCADE, related_name="transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    TRANSACTION_TYPES = [
        ("COURSE_PURCHASE", "Course Purchase Revenue"),
        ("SUBSCRIPTION", "Subscription Revenue"),
        ("OTHER", "Other Revenue"),
    ]
    transaction_type = models.CharField(max_length=30, choices=TRANSACTION_TYPES)

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="platform_transactions")
    tutor = models.ForeignKey("Accounts.TutorDetails", on_delete=models.SET_NULL, null=True, blank=True, related_name="tutor_commission_source")

    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['wallet']),
            models.Index(fields=['transaction_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['user']),
            models.Index(fields=['tutor']),
            models.Index(fields=['transaction_type', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.transaction_type} - ${self.amount}"
