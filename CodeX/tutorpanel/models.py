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
    
    is_draft = models.BooleanField(default=False)

    STATUS_CHOICES = [('pending', 'Pending'), ('accepted', 'Accepted'), ('rejected', 'Rejected')]
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending')
    
    CHOICES = [('beginer', 'Beginer'), ('intermediate', 'Intermediate'), ('advanced', 'Advanced')]
    level = models.CharField(max_length=50, choices=CHOICES, default='beginer')

    users = models.IntegerField(default=0, null=True, blank=True)

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



class Meetings(models.Model):
    tutor = models.ForeignKey("Accounts.TutorDetails", on_delete=models.SET_NULL, null=True)
    date = models.DateField()
    time = models.TimeField()
    limit = models.PositiveIntegerField(help_text="Max number of participants or bookings for this time slot")
    left = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False, null=True, blank=True)
    

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

    def __str__(self):
        return f"{self.user.email} booked meeting {self.meeting.id}"



