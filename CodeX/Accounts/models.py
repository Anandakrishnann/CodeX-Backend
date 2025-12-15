import profile
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.utils import timezone
from datetime import timedelta
from random import randint
from datetime import date
from adminpanel.models import *
from tutorpanel.models import *


# Create your models here.  


class AccountsManager(BaseUserManager):
    def create_user(self, email, first_name, last_name, phone, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')

        email = self.normalize_email(email)
        extra_fields.setdefault('role', 'user')
        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            **extra_fields
        )

        if password:
            user.set_password(password)

        user.save(using=self._db)
        return user


    def create_superuser(self, email, first_name, last_name, phone, leetcode_id, password=None, **extra_fields):
        extra_fields.setdefault('role', 'admin')
        extra_fields.setdefault('isblocked', False)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_staff', True)

        return self.create_user(email, first_name, last_name, phone, leetcode_id, password, **extra_fields)



class Accounts(AbstractBaseUser):
    id = models.BigAutoField(primary_key=True)
    first_name = models.CharField(max_length=200, null=False)
    last_name = models.CharField(max_length=200, null=False)
    email = models.EmailField(max_length=200, unique=True)
    phone = models.CharField(max_length=10, null=True)
    password = models.CharField(max_length=255, null=True)
    profile_picture = models.URLField(blank=True, null=True)

    created_at = models.DateField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True, null=True, blank=True)
    isblocked = models.BooleanField(default=False)

    google_verified = models.BooleanField(default=False)

    ROLE_CHOICES = [('user', 'User'), ('tutor', 'Tutor'), ('admin', 'Admin')]
    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default='user')
    
    streak = models.PositiveIntegerField(default=0)
    last_completed_task = models.DateField(null=True, blank=True)

    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    class Meta:
        db_table = 'Accounts_accounts'

    objects = AccountsManager()

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.role})"
    
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'phone']



class TutorDetails(models.Model):
    id = models.BigAutoField(primary_key=True)
    account = models.OneToOneField(Accounts, related_name="tutor_details", on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255)
    dob = models.DateField()
    about = models.TextField(null=True, blank=True)
    phone = models.CharField(max_length=10, null=True, default=None)
    education = models.CharField(max_length=255, null=True, blank=True)
    expertise = models.CharField(max_length=255, null=True, blank=True)
    occupation = models.CharField(max_length=255, null=True, blank=True)
    experience = models.CharField(max_length=255, null=True, blank=True)
    profile_picture = models.URLField(blank=True, null=True)
    verification_file = models.URLField(blank=True, null=True)
    verification_video = models.URLField(blank=True, null=True)

    review_count = models.IntegerField(default=0, null=True, blank=True)
    rating = models.IntegerField(default=0, null=True, blank=True)

    STATUS_CHOICE = [('pending', 'Pending'), ('verified', 'Verified'), ('rejected', 'Rejected')]
    status = models.CharField(max_length=50, choices=STATUS_CHOICE, default="pending")
    

    def __str__(self):
        return f"Tutor Details for {self.full_name}"
    
    def get_age(self):
        """Returns the age of the tutor based on their date of birth."""
        if self.dob:
            today = date.today()
            return today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
        return None  # Return None if DOB is not provided



class TutorSubscription(models.Model):
    tutor = models.OneToOneField(TutorDetails, on_delete=models.CASCADE)
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True)
    subscribed_on = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_on = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    
    # Stripe integration
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.tutor.account.email} - {self.plan.name}"
    


class UserCourseEnrollment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),        
        ('progress', 'Progress'),
        ('completed', 'Completed')     
    ]
    user = models.ForeignKey(Accounts, on_delete=models.CASCADE)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    payment_id = models.CharField(max_length=500)
    enrolled_on = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    progress = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    completed_at = models.DateTimeField(null=True, blank=True)
    


class ModuleProgress(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('progress', 'Progress'),
        ('completed', 'Completed'),
    )

    user = models.ForeignKey(Accounts, on_delete=models.CASCADE)
    module = models.ForeignKey(Modules, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'module')

    def __str__(self):
        return f"{self.user.username} - {self.module.title} - {self.status}"
    
    

class LessonProgress(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('progress', 'Progress'),
        ('completed', 'Completed'),
    )
    
    user = models.ForeignKey(Accounts, on_delete=models.CASCADE)
    lesson = models.ForeignKey(Lessons, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    started_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'lesson')



class TutorFeedback(models.Model):
    tutor = models.ForeignKey(TutorDetails, on_delete=models.CASCADE, related_name="feedback")
    user = models.ForeignKey(Accounts, on_delete=models.CASCADE, related_name="tutor_feedback")

    rating = models.PositiveSmallIntegerField(null=True, blank=True)  # 1–5 or null
    review = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "tutor_feedback"
        unique_together = ('tutor', 'user')



class CourseFeedback(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="feedback")
    user = models.ForeignKey(Accounts, on_delete=models.CASCADE, related_name="course_feedback")

    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    review = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "course_feedback"
        unique_together = ('course', 'user')



class TutorReport(models.Model):
    tutor = models.ForeignKey(TutorDetails, on_delete=models.CASCADE, related_name="reports")
    user = models.ForeignKey(Accounts, on_delete=models.CASCADE, related_name="tutor_reports")

    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    is_marked = models.BooleanField(default=False)

    class Meta:
        db_table = "tutor_reports"
        unique_together = ("tutor", "user")  # prevent duplicate reports

    def __str__(self):
        return f"Report by {self.user} on {self.tutor}"



class CourseReport(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="reports")
    user = models.ForeignKey(Accounts, on_delete=models.CASCADE, related_name="course_reports")

    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    is_marked = models.BooleanField(default=False)

    class Meta:
        db_table = "course_reports"
        unique_together = ("course", "user")  # prevent duplicate reports

    def __str__(self):
        return f"Report by {self.user} on {self.course}"