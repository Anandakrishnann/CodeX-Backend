import profile
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.utils import timezone
from datetime import timedelta
from random import randint
from datetime import date
from adminpanel.models import *

# Create your models here.


class AccountsManager(BaseUserManager):
    def create_user(self, email, first_name, last_name, phone, leetcode_id, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')

        email = self.normalize_email(email)
        extra_fields.setdefault('role', 'user')
        user = self.model(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            leetcode_id=leetcode_id,
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
    phone = models.CharField(max_length=10, null=False)
    leetcode_id = models.CharField(max_length=200)
    password = models.CharField(max_length=255)
    profile_picture = models.URLField(blank=True, null=True)

    created_at = models.DateField(auto_now_add=True)
    last_login = models.DateTimeField(auto_now=True, null=True, blank=True)
    isblocked = models.BooleanField(default=False)

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

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'phone', 'leetcode_id']


class TutorDetails(models.Model):
    id = models.BigAutoField(primary_key=True)
    account = models.ForeignKey(Accounts, related_name="tutor_details", on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255)
    dob = models.DateField()
    about = models.TextField(null=True, blank=True)
    education = models.CharField(max_length=255, null=True, blank=True)
    expertise = models.CharField(max_length=255, null=True, blank=True)
    occupation = models.CharField(max_length=255, null=True, blank=True)
    experience = models.CharField(max_length=255, null=True, blank=True)
    profile_picture = models.URLField(blank=True, null=True)
    verification_file = models.URLField(blank=True, null=True)
    verification_video = models.URLField(blank=True, null=True)

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
    expires_on = models.DateTimeField()
    is_active = models.BooleanField(default=False)
    
    # Stripe integration
    stripe_subscription_id = models.CharField(max_length=255, null=True, blank=True)
    stripe_customer_id = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"{self.tutor.account.email} - {self.plan.name}"



class OTP(models.Model):
    user = models.ForeignKey('Accounts', on_delete=models.CASCADE)
    otp = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=timezone.now)

    def is_expired(self):
        return timezone.now() > self.expires_at
    
    @staticmethod
    def generate_otp():
        return randint(100000, 999999)
