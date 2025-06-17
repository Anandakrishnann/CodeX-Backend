from django.shortcuts import get_object_or_404, render
from django.contrib.auth import get_user_model
from rest_framework.views import APIView 
from rest_framework.response import Response 
from rest_framework import status 
from .models import *
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import IsAuthenticated
from django.http import JsonResponse
import traceback
from Accounts.models import *
import stripe # type: ignore
from django.conf import settings
from .serializers import *
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from django.utils.timezone import now, timedelta
from rest_framework.permissions import AllowAny
from tutorpanel.models import *
import cloudinary.uploader

stripe.api_key = settings.STRIPE_SECRET_KEY
endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

User = get_user_model()


class ListUsers(APIView):
    def get(self, request):
        try:
            users = User.objects.filter(role="user")

            user_data = [{"id": user.id, "email": user.email, "first_name": user.first_name, "last_name":user.last_name, "phone":user.phone, "status": bool(user.isblocked), "role":user.role } for user in users]

            response = Response({"users": user_data}, status=200)  # ✅ Ensure we return a Response
            print(response)  # Optional: Debugging

            return response 
        except:
            return Response({"Unauthorized": "Token expired"}, status=401)



class ListTutors(APIView):
    def get(self, request):
        try:
            # Get active subscriptions
            subscribed_tutors = TutorSubscription.objects.filter(is_active=True)

            # Get the associated Accounts objects from each subscription
            accounts = [sub.tutor.account for sub in subscribed_tutors]

            tutor_data = [{"id": tutor.id, "email": tutor.email, "first_name": tutor.first_name, "last_name":tutor.last_name, "phone":tutor.phone, "status": bool(tutor.isblocked), "role":tutor.role } for tutor in accounts]

            return Response({"users": tutor_data}, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"❌ Error: {e}")
            return Response({"error": "Something went wrong"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class Status(APIView):

    def post(self, request):
        try:
            user_id = request.data.get('id')

            if not user_id:
                return Response({"error": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            user = get_object_or_404(User, id=user_id)

            user.isblocked = not user.isblocked
            user.save()

            return Response({"message": "Status updated successfully", "status": user.isblocked}, status=status.HTTP_200_OK)
        except:
            return Response({"Unauthorized": "Token expired"}, status=401)
        


class TutorStatus(APIView):

    def post(self, request):
        try:
            user_id = request.data.get('id')

            if not user_id:
                return Response({"error": "User ID is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            user = get_object_or_404(User, id=user_id)

            user.isblocked = not user.isblocked
            user.save()

            return Response({"message": "Status updated successfully", "status": user.isblocked}, status=status.HTTP_200_OK)
        except:
            return Response({"Error": "Error While Chaning the status"}, status=status.HTTP_400_BAD_REQUEST)



class TutorApplicationView(APIView):
    parser_classes = (MultiPartParser, FormParser)

    def post(self, request):
        data = request.data.dict()  # <-- Change here

        # Convert to strings for these fields (to prevent type errors)
        for field in ['full_name', 'email', 'phone', 'education', 'expertise', 'occupation', 'experience', 'about', 'dob']:
            if field in data:
                data[field] = str(data[field])
        
        # Upload files to Cloudinary
        try:
            if 'profile_picture' in request.FILES:
                profile_pic = request.FILES['profile_picture']
                upload_result = cloudinary.uploader.upload(profile_pic, folder="profile_picture", resource_type="image")
                data['profile_picture'] = upload_result.get('secure_url')

            if 'verification_file' in request.FILES:
                verification_file = request.FILES['verification_file']
                upload_result = cloudinary.uploader.upload(verification_file, folder="verification_docs", resource_type="raw")
                data['verification_file'] = upload_result.get('secure_url')

            if 'verification_video' in request.FILES:
                verification_video = request.FILES['verification_video']
                upload_result = cloudinary.uploader.upload(verification_video, folder="verification_videos", resource_type="video")
                data['verification_video'] = upload_result.get('secure_url')
        except Exception as e:
            return Response({"error": "File upload failed", "details": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TutorApplicationSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            print(serializer.errors)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class TutorApplicationsOverView(APIView):

    def get(self, request, userId):
        try:
            user_application = get_object_or_404(TutorApplications, id=int(userId))  # Ensure ID is an int
            print(f"Found application: {user_application}")
            print(f"userId: {userId}")

            data = {
                "username": user_application.full_name,
                "email": user_application.email,
                "date_of_birth": user_application.dob,
                "education": user_application.education,
                "expertise": user_application.expertise,
                "occupation": user_application.occupation,
                "experience": user_application.experience,
                "about":user_application.about,
                "age":user_application.get_age(),
                "phone": user_application.phone,
                "presentation_video": user_application.verification_video if user_application.verification_video else None,
                "verification_file": user_application.verification_file if user_application.verification_file else None,
                "profile_picture": user_application.profile_picture if user_application.profile_picture else None,
                "status":user_application.status
            }
            print(f"data: {data}")

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            print("❌ ERROR OCCURRED:")
            return Response({"error": str(e)}, status=500)  # Return actual error



class TutorOverView(APIView):

    def get(self, request, userId):
        try:
            tutor = get_object_or_404(Accounts, email=userId)  # Ensure ID is an int
            print(f"Found application: {tutor}")

            deatils = get_object_or_404(TutorDetails, account=tutor)

            data = {
                "username": deatils.full_name,
                "email": tutor.email,
                "date_of_birth": deatils.dob,
                "education": deatils.education,
                "expertise": deatils.expertise,
                "occupation": deatils.occupation,
                "experience": deatils.experience,
                "about":deatils.about,
                "age":deatils.get_age(),
                "phone": tutor.phone,
                "presentation_video": deatils.verification_video if deatils.verification_video else None,
                "verification_file": deatils.verification_file if deatils.verification_file else None,
                "profile_picture": deatils.profile_picture if deatils.profile_picture else None,
                "status":deatils.status
            }
            print(f"data: {data}")

            return Response(data, status=status.HTTP_200_OK)

        except Exception as e:
            print("❌ ERROR OCCURRED:")
            traceback.print_exc()  # Prints full error traceback in logs
            return Response({"error": str(e)}, status=500)  # Return actual error



class AcceptApplicationView(APIView):

    def post(self, request, applicationId):
        try:
            application = get_object_or_404(TutorApplications, id=applicationId)
            
            user = get_object_or_404(Accounts, email=application.email)
            print(f"user object: {user}")

            if not application.dob:
                return Response({"error": "Date of Birth is required"}, status=status.HTTP_400_BAD_REQUEST)

            try:
                tutor = TutorDetails.objects.create(
                    account=user,
                    full_name=application.full_name,
                    dob=application.dob,
                    about=application.about,
                    education=application.education,
                    expertise=application.expertise,
                    occupation=application.occupation,
                    experience=application.experience,
                    profile_picture=application.profile_picture,
                    verification_file=application.verification_file,
                    verification_video=application.verification_video,
                    status="verified"
                )
                print(f"Tutor Created: {tutor}")
            except Exception as e:
                print(f"Error While Creating Tutor: {e}")
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

            user.role = "tutor"
            user.save()
            application.status = "verified"
            application.save()

            return Response({"success": "Tutor Data added successfully"}, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)



class RejectApplicationView(APIView):

    def post(self, request, applicationId):
        try:
            print(applicationId)
            application = get_object_or_404(TutorApplications, id=applicationId)
            print(application)

            if not application:
                return Response({"error":"Application not found"}, status=status.HTTP_404_NOT_FOUND)
            
            application.status = "rejected"
            application.save()

            return Response({"success":"Application Rejected"}, status=status.HTTP_201_CREATED)
        
        except:

            return Response({"error":"Something went wrong"}, status=status.HTTP_400_BAD_REQUEST)



class ListApplicationsView(APIView):
    def get(self, request):
        try:
            applications = TutorApplications.objects.all()
            serializer = TutorApplicationSerializer(applications, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class EditUserView(APIView):

    def put(self, request, email):
        try:
            try:
                user = User.objects.get(email=email)
            except Accounts.DoesNotExist:
                return Response({"error":"Account not found"}, status=status.HTTP_404_NOT_FOUND)
            
            # serializer =  
        except Exception as e:
            return Response({"error":str(e)}, status=status.HTTP_400_BAD_REQUEST)



class CreateCategoryView(APIView):
    def post(self, request):
        try:
            serializer = CategorySerializer(data=request.data)
            if serializer.is_valid():
                category = serializer.save()
                return Response(ListCategorySerializer(category).data, status=status.HTTP_201_CREATED)
            # Combine errors with custom message
            return Response(
                {"detail": "Data Already Exists.", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            print(f"CreateCategoryView Error: {e}")
            return Response({"detail": "Something went wrong."}, status=status.HTTP_406_NOT_ACCEPTABLE)



class EditCategoryView(APIView):
    def put(self, request, id):
        try:
            try:
                category = CourseCategory.objects.get(id=id)
            except CourseCategory.DoesNotExist:
                return Response({"detail": "Category Does Not Exist"}, status=status.HTTP_404_NOT_FOUND)

            serializer = EditCategorySerializer(instance=category, data=request.data)
            if serializer.is_valid():
                serializer.save()
                category_data = CourseCategory.objects.all()
                return Response(ListCategorySerializer(category_data, many=True).data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {"detail": "Category Name Already Exists", "errors": serializer.errors},
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
            print("EditCategoryView Error:", str(e))
            return Response({"detail": "Error While Editing Category"}, status=status.HTTP_400_BAD_REQUEST)



class ListCategoryView(APIView):

    def get(self, request):
        try:
            categorys = CourseCategory.objects.all()
            serializer = ListCategorySerializer(categorys, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response({"error": "Data does not exist"}, status=status.HTTP_404_NOT_FOUND)



class CategoryStatusView(APIView):

    def post(self, request):
        try:
            category_id = request.data.get('id')
            print(f"category_id   {category_id}")
            if not category_id:
                return Response({"Error":"Id is Required"}, status=status.HTTP_400_BAD_REQUEST)
            category = get_object_or_404(CourseCategory, id=category_id)

            category.is_active = not category.is_active
            category.save()
            return Response({"message": "Status updated successfully", "status": category.is_active}, status=status.HTTP_200_OK)
        except:
            return Response({"Error": "Error While Chaning the status"}, status=status.HTTP_400_BAD_REQUEST)



def create_stripe_product_and_price(plan):
    product = stripe.Product.create(name=plan.name)

    interval = "month" if plan.plan_type == "MONTHLY" else "year"

    price = stripe.Price.create(
        unit_amount=int(plan.price * 100),  # in cents
        currency="inr",
        recurring={"interval": interval},
        product=product.id
    )

    return price.id



class CreatePlanView(APIView):

    def post(self, request):
        serializer = PlanSerializer(data=request.data)
        if serializer.is_valid():
            plan = serializer.save()
            price_id = create_stripe_product_and_price(plan)
            plan.stripe_price_id = price_id
            plan.save()
            return Response(PlanSerializer(plan).data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=400)



class ListPlanView(APIView):

    def get(self, request):
        try:
            plans = Plan.objects.all()
            serializer = PlanListSerializer(plans, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except:
            return Response({"error": "Data does not exist"}, status=status.HTTP_404_NOT_FOUND)



class CreateCheckoutSessionView(APIView):
    def post(self, request, plan_id):
        plan = get_object_or_404(Plan, id=plan_id)
        domain = "http://localhost:3000"

        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': plan.stripe_price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f'{domain}/success?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f'{domain}/cancel',
            customer_email=request.user.email,
            expand=["line_items"],
        )

        return Response({'checkout_url': session.url})



class StripeWebhookView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError:
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            return HttpResponse(status=400)

        
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            customer_email = session.get('customer_email')
            subscription_id = session.get('subscription')

            try:
                checkout_session = stripe.checkout.Session.retrieve(
                    session['id'],
                    expand=['line_items']
                )

                plan_price_id = checkout_session['line_items']['data'][0]['price']['id']
                user = Accounts.objects.get(email=customer_email)
                plan = Plan.objects.get(stripe_price_id=plan_price_id)

                expires_on = now() + timedelta(days=30) if plan.plan_type == 'MONTHLY' else now() + timedelta(days=365)
                tutor = TutorDetails.objects.get(account=user)
                TutorSubscription.objects.update_or_create(
                    tutor=tutor,
                    defaults={
                        'plan': plan,
                        'subscribed_on': now(),
                        'expires_on': expires_on,
                        'is_active': True,
                        'stripe_subscription_id': subscription_id,
                        'stripe_customer_id': session.get('customer'),
                    }
                )
                tutor.status = "verified"
                tutor.save()
                print("✅ TutorSubscription successfully created or updated")
                print(f"✅ Subscription updated for: {user.email}")
            except Exception as e:
                print(f"⚠️ Error processing webhook: {e}")

        
        elif event['type'] == 'customer.subscription.deleted':
            sub = event['data']['object']
            try:
                sub_id = sub['id']
                TutorSubscription.objects.filter(stripe_subscription_id=sub_id).update(is_active=False)
                print(f"❌ Subscription canceled: {sub_id}")
            except:
                pass

        
        elif event['type'] == 'customer.subscription.updated':
            sub = event['data']['object']
            sub_id = sub['id']
            status = sub['status']

            is_active = status == 'active'
            TutorSubscription.objects.filter(stripe_subscription_id=sub_id).update(is_active=is_active)

        return HttpResponse(status=200)  
    


class CourseRequestsView(APIView):

    def get(self, request):
        try:
            course_requests = Course.objects.exclude(status="accepted")
            data = []

            for reqeusts in course_requests:
                data.append({
                    "id":reqeusts.id,
                    "name": reqeusts.name,
                    "created_by":reqeusts.created_by.full_name,
                    "category": reqeusts.category_id.name if reqeusts.category_id else None,
                    "category_id":reqeusts.category_id.id if reqeusts.category_id else None,
                    "title": reqeusts.title,
                    "description": reqeusts.description,
                    "requirements": reqeusts.requirements,
                    "benefits": reqeusts.benefits,
                    "price": reqeusts.price,
                    "created_at": reqeusts.created_at,
                    "is_active": reqeusts.is_active,
                    "level": reqeusts.level,
                    "status":reqeusts.status,
                })

            return Response(data, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Fetching Course Request"}, status=status.HTTP_400_BAD_REQUEST)



class CourseStatusView(APIView):

    def post(self, requests, id):
        try:
            course = get_object_or_404(Course, id=id)

            if not course:
                return Response({"Error":"Course Does Not Exists"}, status=status.HTTP_400_BAD_REQUEST)
            
            course.is_active = not course.is_active
            course.save()
            return Response({"message": "Status updated successfully", "status": course.is_active}, status=status.HTTP_200_OK)
        except:
            return Response({"Error": "Error While Updating the status"}, status=status.HTTP_400_BAD_REQUEST)



class ListCoursesView(APIView):

    def get(self, requests):
        try:
            course_requests = Course.objects.filter(status="accepted")
            data = []

            for reqeusts in course_requests:
                data.append({
                    "id":reqeusts.id,
                    "name": reqeusts.name,
                    "created_by":reqeusts.created_by.full_name,
                    "category": reqeusts.category_id.name if reqeusts.category_id else None,
                    "category_id":reqeusts.category_id.id if reqeusts.category_id else None,
                    "title": reqeusts.title,
                    "description": reqeusts.description,
                    "requirements": reqeusts.requirements,
                    "benefits": reqeusts.benefits,
                    "price": reqeusts.price,
                    "created_at": reqeusts.created_at,
                    "is_active": reqeusts.is_active,
                    "level":reqeusts.level,
                    "status":reqeusts.status,
                })

            return Response(data, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Fetching Course Request"}, status=status.HTTP_400_BAD_REQUEST)


class CoureseStatusView(APIView):
    
    def post(self, request, id):
        try:
            course = get_object_or_404(Course, id=id)

            if not course:
                return Response({"Error":"Course Does Not Exists"}, status=status.HTTP_400_BAD_REQUEST)
            
            course.is_active = not course.is_active
            course.save()
            return Response({"message": "Status updated successfully", "status": course.is_active}, status=status.HTTP_200_OK)
        except:
            return Response({"Error": "Error While Updating the status"}, status=status.HTTP_400_BAD_REQUEST)
        


class AcceptCourseRequestView(APIView):

    def post(self, request, courseId):
        try:
            course = get_object_or_404(Course, id=courseId)

            if not course:
                return Response({"error":"Course Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            course.status = "accepted"
            course.is_active = True
            course.save()
            return Response({})
        except:
            return Response({"Error": "Error While Accepting Course Request"}, status=status.HTTP_400_BAD_REQUEST)
        

class RejectCourseRequestView(APIView):

    def post(self, request, courseId):
        try:
            course = get_object_or_404(Course, id=courseId)

            if not course:
                return Response({"error":"Course Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            course.status = "rejected"
            course.is_active = False
            course.save()
            return Response({})
        except:
            return Response({"Error": "Error While Rjecting Course Request"}, status=status.HTTP_400_BAD_REQUEST)



class AcceptModuleView(APIView):

    def post(self, request, id):
        try:
            module = get_object_or_404(Modules, id=id)

            if not module:
                return Response({"error":"Module Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            module.status = "accepted"
            module.is_active = True
            module.save()
            return Response({})
        except:
            return Response({"Error": "Error While Accepting Course Request"}, status=status.HTTP_400_BAD_REQUEST)
        



class RejectModuleView(APIView):

    def post(self, request, id):
        try:
            module = get_object_or_404(Modules, id=id)

            if not module:
                return Response({"error":"Module Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            module.status = "rejected"
            module.is_active = False
            module.save()
            return Response({})
        except:
            return Response({"Error": "Error While Accepting Course Request"}, status=status.HTTP_400_BAD_REQUEST)


class ListCourseModulesView(APIView):
    def get(self, request, id):
        try:
            try:
                course = get_object_or_404(Course, id=id)
            except Course.DoesNotExist:
                return Response({"error": "Course Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            try:
                modules = Modules.objects.filter(course=course)
            except:
                return Response({"error": "Modules Not Found"}, status=status.HTTP_404_NOT_FOUND)

            serializer = CourseModuleSerializer(modules, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error fetching course overview: {e}")
            return Response({"error": "Something went wrong"}, status=status.HTTP_400_BAD_REQUEST)


class CourseOverView(APIView):

    def get(self, request, id):
        try:
            try:
                course = get_object_or_404(Course, id=id)
            except Course.DoesNotExist:
                return Response({"error": "Course Not Found"}, status=status.HTTP_404_NOT_FOUND)

            return Response(CourseRequestSerializer(course).data, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error fetching course overview: {e}")
            return Response({"error": "Something went wrong"}, status=status.HTTP_400_BAD_REQUEST)


class ModuleDetailView(APIView):

    def get(self, request, id):
        try:
            module = get_object_or_404(Modules, id=id)

            if not module:
                return Response({"error":"Module Does not found"}, status=status.HTTP_404_NOT_FOUND)
            
            return Response(CourseModuleSerializer(module).data, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Fetching Module"}, status=status.HTTP_400_BAD_REQUEST)



class ModuleStatusView(APIView):

    def post(self, request, id):
        try:
            module = get_object_or_404(Modules, id=id)

            if not module:
                return Response({"error":"Module Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            module.is_active = not module.is_active
            module.save()
            return Response({"detail":"Status Changed Successfully"}, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Changing Module Status"}, status=status.HTTP_400_BAD_REQUEST)



class ListCourseLessonView(APIView):

    def get(self, request, id):
        try:
            print(id)
            module = get_object_or_404(Modules, id=id)
            lessons = Lessons.objects.filter(module=module)
            
            serializer = LessonOverviewSerializer(lessons, many=True)
            print(serializer)
            return Response(serializer.data, status=status.HTTP_200_OK)

        except Modules.DoesNotExist:
            return Response({"error": "Module Not Found"}, status=status.HTTP_404_NOT_FOUND)

        except Lessons.DoesNotExist:
            return Response({"error": "Lessons Not Found"}, status=status.HTTP_404_NOT_FOUND)

        except Exception as e:
            return Response({"error": f"Error While Fetching Lessons: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)


class AcceptLessonView(APIView):

    def post(self, request, lessonId):
        try:
            lesson = get_object_or_404(Lessons, id=lessonId)
            if not lesson:
                return Response({"error":"Lesson Not Found"}, status=status.HTTP_404_NOT_FOUND)
            lesson.status = "accepted"
            lesson.is_active = True
            lesson.save()
            return Response({"detail":"Lesson Accepted Successfully"}, status=status.HTTP_200_OK) 
        except:
            return Response({"error":"Error While Accepting Lesson"}, status=status.HTTP_400_BAD_REQUEST)
        


class RejectLessonView(APIView):

    def post(self, request, lessonId):
        try:
            lesson = get_object_or_404(Lessons, id=lessonId)
            if not lesson:
                return Response({"error":"Lesson Not Found"}, status=status.HTTP_404_NOT_FOUND)
            lesson.status = "rejected"
            lesson.is_active = False
            lesson.save()
            return Response({"detail":"Lesson Rejected Successfully"}, status=status.HTTP_200_OK) 
        except:
            return Response({"error":"Error While Rejecting Lesson"}, status=status.HTTP_400_BAD_REQUEST)



class LessonStatusView(APIView):

    def post(self, request, lessonId):
        try:
            lesson = get_object_or_404(Lessons, id=lessonId)

            if not lesson:
                return Response({"error":"Lesson Not Found"}, status=status.HTTP_404_NOT_FOUND)
            
            lesson.is_active = not lesson.is_active
            lesson.save()
            return Response({"detail":"Status Changed Successfully"}, status=status.HTTP_200_OK)
        except: 
            return Response({"error":"Error While Changing Lesson Status"}, status=status.HTTP_400_BAD_REQUEST)



class LessonOverview(APIView):

    def get(self, request, lessonId):
        try:
            lesson = get_object_or_404(Lessons, id=lessonId)
            
            if not lesson:
                return Response({"error":"Lesson Not Found"}, status=status.HTTP_404_NOT_FOUND)

            return Response(LessonOverviewSerializer(lesson).data, status=status.HTTP_200_OK)
        except:
            return Response({"error":"Error While Fetching Lesson Details"}, status=status.HTTP_400_BAD_REQUEST)