from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status

from Accounts.models import Accounts, OTP


class AuthenticationTests(APITestCase):

    def setUp(self):
        self.signup_url = reverse("signup")
        self.login_url = reverse("login")

        self.user_data = {
            "first_name": "John",
            "last_name": "Doe",
            "email": "john@example.com",
            "phone": "9876543210",
            "password": "testpass123"
        }

    # ---------------------------------------------------------
    # 1️⃣ Test User Registration
    # ---------------------------------------------------------
    def test_user_registration(self):
        response = self.client.post(self.signup_url, self.user_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        user = Accounts.objects.get(email="john@example.com")

        # Your model has no is_active → so user should be active by default
        self.assertNotEqual(user, None)

        # OTP should be created
        otp_obj = OTP.objects.filter(user=user).first()
        self.assertIsNotNone(otp_obj)

    # ---------------------------------------------------------
    # 2️⃣ Test Login Works Normally (No inactive user logic)
    # ---------------------------------------------------------
    def test_login_user(self):
        # Create user by registering
        self.client.post(self.signup_url, self.user_data)

        # Login should succeed
        response = self.client.post(self.login_url, {
            "email": "john@example.com",
            "password": "testpass123"
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["email"], "john@example.com")

    # ---------------------------------------------------------
    # 3️⃣ Test Login Fails With Wrong Password
    # ---------------------------------------------------------
    def test_login_wrong_password(self):
        Accounts.objects.create_user(
            email="active@example.com",
            first_name="A",
            last_name="B",
            phone="1234567890",
            password="correctpassword"
        )

        response = self.client.post(self.login_url, {
            "email": "active@example.com",
            "password": "wrongpassword"
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Invalid email or password", str(response.data))

    # ---------------------------------------------------------
    # 4️⃣ Test Login Works for Normal User
    # ---------------------------------------------------------
    def test_login_successful_user(self):
        Accounts.objects.create_user(
            email="login@example.com",
            first_name="Test",
            last_name="User",
            phone="1234567890",
            password="loginpass"
        )

        response = self.client.post(self.login_url, {
            "email": "login@example.com",
            "password": "loginpass"
        })

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user"]["email"], "login@example.com")

    # ---------------------------------------------------------
    # 5️⃣ Blocked User Cannot Login (Your real logic)
    # ---------------------------------------------------------
    def test_login_blocked_user(self):
        user = Accounts.objects.create_user(
            email="blocked@example.com",
            first_name="Block",
            last_name="User",
            phone="1234567890",
            password="mypassword"
        )
        user.isblocked = True
        user.save()

        response = self.client.post(self.login_url, {
            "email": "blocked@example.com",
            "password": "mypassword"
        })

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Account is Blocked", str(response.data))

    # ---------------------------------------------------------
    # 6️⃣ Google Verified User Cannot Login Normally
    # ---------------------------------------------------------
    def test_google_verified_user_login_fails(self):
        user = Accounts.objects.create_user(
            email="google@example.com",
            first_name="G",
            last_name="V",
            phone="1234567890",
            password="googlepass"
        )
        user.google_verified = True
        user.save()

        response = self.client.post(self.login_url, {
            "email": "google@example.com",
            "password": "googlepass"
        })

        self.assertEqual(response.status_code, status.HTTP_406_NOT_ACCEPTABLE)
        self.assertIn("Google account", str(response.data))
