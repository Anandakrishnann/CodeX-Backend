from django.db import models
from datetime import date

class TutorApplications(models.Model):
    id = models.BigAutoField(primary_key=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15)
    dob = models.DateField(null=True, blank=True)
    education = models.CharField(max_length=255, null=True, blank=True)
    expertise = models.CharField(max_length=255, null=True, blank=True)
    occupation = models.CharField(max_length=255, null=True, blank=True)
    experience = models.CharField(max_length=255, null=True, blank=True)
    about = models.TextField(null=True, blank=True)

    # Store both files in Cloudinary
    profile_picture = models.URLField(blank=True, null=True)
    verification_file = models.URLField(blank=True, null=True)  # Store Cloudinary URL
    verification_video = models.URLField(blank=True, null=True)  

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
        return None  # Return None if DOB is not provided



class Plan(models.Model):
    PLAN_TYPE_CHOICES = [('MONTHLY', 'Monthly'), ('YEARLY', 'Yearly')]
    PLAN_CATEGORY_CHOICES = [('BASIC', 'Basic'), ('PRO', 'Pro'), ('PREMIUM', 'Premium')]

    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=10, choices=PLAN_TYPE_CHOICES)
    plan_category = models.CharField(max_length=10, choices=PLAN_CATEGORY_CHOICES)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    description = models.TextField()
    stripe_price_id = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.name} - {self.plan_type}"
