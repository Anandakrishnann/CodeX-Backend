from django.db import models
from adminpanel.models import CourseCategory
from Accounts.models import TutorDetails

# Create your models here.


class Course(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(TutorDetails, on_delete=models.SET_NULL, null=True)
    category_id = models.ForeignKey(CourseCategory, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=600)
    requirements = models.CharField(max_length=600)
    benefits = models.CharField(max_length=600)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    created_at = models.DateField(auto_now=True)
    is_active = models.BooleanField(default=False)

    def __str__(self):
        return self.name


class Modules(models.Model):
    created_by = models.ForeignKey(TutorDetails, on_delete=models.SET_NULL, null=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=500)
    description = models.CharField(max_length=600)
    created_at = models.DateField(auto_now=True)
    is_active = models.BooleanField(default=True)


class Lessons(models.Model):
    created_by = models.ForeignKey(TutorDetails, on_delete=models.SET_NULL, null=True)
    module = models.ForeignKey(Modules, on_delete=models.SET_NULL, null=True)
    title = models.CharField(max_length=200)
    description = models.CharField(max_length=500)
    documents = models.URLField(blank=True, null=True)
    video = models.URLField(blank=True, null=True)
    created_at = models.DateField(auto_now=True)
    is_active = models.BooleanField(default=True)
