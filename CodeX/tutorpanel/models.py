from django.db import models
from adminpanel.models import CourseCategory



# Create your models here.


class Course(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey("Accounts.TutorDetails", on_delete=models.SET_NULL, null=True)
    category_id = models.ForeignKey(CourseCategory, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=600)
    requirements = models.CharField(max_length=600) 
    benefits = models.CharField(max_length=600)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateField(auto_now=True)
    is_active = models.BooleanField(default=False)
    is_complete = models.BooleanField(default=False)
    
    is_draft = models.BooleanField(default=False)

    STATUS_CHOICES = [('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')]
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    
    CHOICES = [('beginer', 'Beginer'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')]
    level = models.CharField(max_length=50, choices=CHOICES, default='beginer')

    class Meta:
        indexes = [
            models.Index(fields=['created_by']),
            models.Index(fields=['category_id']),
            models.Index(fields=['status']),
            models.Index(fields=['is_active']),
            models.Index(fields=['is_draft']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status', 'is_active']),
            models.Index(fields=['created_by', 'status']),
            models.Index(fields=['is_active', 'is_draft']),
        ]

    def __str__(self):
        return self.name



class Modules(models.Model):
    created_by = models.ForeignKey("Accounts.TutorDetails", on_delete=models.SET_NULL, null=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=500)
    description = models.CharField(max_length=600)

    STATUS_CHOICES = [('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')]
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    
    created_at = models.DateField(auto_now=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['created_by']),
            models.Index(fields=['course']),
            models.Index(fields=['status']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
            models.Index(fields=['course', 'status']),
            models.Index(fields=['status', 'is_active']),
        ]



class Lessons(models.Model):
    created_by = models.ForeignKey("Accounts.TutorDetails", on_delete=models.SET_NULL, null=True)
    module = models.ForeignKey(Modules, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=500)
    documents = models.URLField(blank=True, null=True)
    video = models.URLField(blank=True, null=True)
    thumbnail = models.URLField(blank=True, null=True )

    STATUS_CHOICES = [('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')]
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    
    created_at = models.DateField(auto_now=True)    
    is_active = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=['created_by']),
            models.Index(fields=['module']),
            models.Index(fields=['status']),
            models.Index(fields=['is_active']),
            models.Index(fields=['created_at']),
            models.Index(fields=['module', 'status']),
            models.Index(fields=['status', 'is_active']),
        ]



class Meetings(models.Model):
    tutor = models.ForeignKey("Accounts.TutorDetails", on_delete=models.SET_NULL, null=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True)
    date = models.DateField()
    time = models.TimeField()
    limit = models.PositiveIntegerField(help_text="Max number of participants or bookings for this time slot")
    left = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False, null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['tutor']),
            models.Index(fields=['course']),
            models.Index(fields=['date']),
            models.Index(fields=['is_completed']),
            models.Index(fields=['created_at']),
            models.Index(fields=['tutor', 'is_completed']),
            models.Index(fields=['date', 'is_completed']),
        ]

    def __str__(self):
        return f"Meeting with Tutor {self.tutor.id} on {self.date} at {self.time}"

    def current_booking_count(self):
        return self.bookings.count() 



class MeetingBooking(models.Model):
    meeting = models.ForeignKey(Meetings, related_name='bookings', on_delete=models.CASCADE)
    user = models.ForeignKey("Accounts.Accounts", on_delete=models.CASCADE)
    booked_at = models.DateTimeField(auto_now_add=True)
    meeting_completed = models.BooleanField(default=False)

    class Meta:
        unique_together = ['meeting', 'user']
        indexes = [
            models.Index(fields=['meeting']),
            models.Index(fields=['user']),
            models.Index(fields=['meeting_completed']),
            models.Index(fields=['booked_at']),
            models.Index(fields=['meeting', 'meeting_completed']),
            models.Index(fields=['user', 'meeting_completed']),
        ] 

    def __str__(self):
        return f"{self.user.email} booked meeting {self.meeting.id}"



class Wallet(models.Model):
    tutor = models.OneToOneField("Accounts.TutorDetails", on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_withdrawn = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    is_freeze = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['tutor']),
            models.Index(fields=['is_freeze']),
        ]



class WalletTransaction(models.Model):
    wallet = models.ForeignKey(Wallet, on_delete=models.CASCADE, related_name="transactions")
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.CharField(max_length=255, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['wallet']),
            models.Index(fields=['created_at']),
            models.Index(fields=['wallet', 'created_at']),
        ]



