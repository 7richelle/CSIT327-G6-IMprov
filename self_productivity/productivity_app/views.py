from django.shortcuts import render, redirect
from django.contrib import messages
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from django.views.decorators.csrf import csrf_exempt
#CHANGED
import json
import requests
from django.http import JsonResponse
from urllib.parse import unquote
import os, json, datetime
from django.utils import timezone
from django.contrib.auth.models import User
import random
from django.contrib.auth.hashers import make_password, check_password
from django.core.mail import send_mail
from .models import PasswordResetOTP
from .forms import ForgotPasswordForm, OTPVerificationForm, ResetPasswordForm
from django.contrib.auth.hashers import make_password, check_password  # ✅ ADD THIS
from supabase import create_client
from django.conf import settings
from .utils.achievements import create_user_achievements, check_achievements  # <--- ADD THIS
# --- SUPABASE CONFIG ---
load_dotenv()
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


#  REGISTER FUNCTION
def register(request):
    if request.method == "POST":
        name = request.POST.get("name")
        email = request.POST.get("email")
        password = request.POST.get("password")

        # 1️⃣ Create Supabase Auth user (safe wrapped)
        try:
            auth_res = supabase.auth.sign_up({
                "email": email,
                "password": password
            })
        except Exception as e:
            messages.error(request, str(e))
            return render(request, "register.html")

        if auth_res.user is None:
            messages.error(request, "Failed to create account in Supabase Auth.")
            return render(request, "register.html")

        auth_uid = auth_res.user.id  

        # 2️⃣ Save into your user table
        supabase.table("user").insert({
            "name": name,
            "email": email,
            "auth_uid": auth_uid,
            "is_staff": False,
            "is_superuser": False
        }).execute()

        messages.success(request, "Registration successful! You can now log in.")
        return redirect("register")

    return render(request, "register.html")





#  LOGIN FUNCTION
def login_user(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        try:
            auth_login = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })

            user = auth_login.user
            auth_uid = user.id

            #  Fetch custom user info
            profile = supabase.table("user").select("*").eq("auth_uid", auth_uid).execute()

            if not profile.data:
                messages.error(request, "User profile not found.")
                return render(request, "login.html")

            profile = profile.data[0]

            request.session["user_id"] = profile.get("user_id")
            request.session["user_email"] = profile.get("email")
            request.session["user_name"] = profile.get("name")
            request.session["is_staff"] = profile.get("is_staff", False)
            request.session["is_superuser"] = profile.get("is_superuser", False)

            if profile.get("is_superuser") or profile.get("is_staff"):
                return redirect("admin_dashboard")
            else:
                return redirect("task_dashboard")

        except Exception as e:
            messages.error(request, "Invalid login. Check email or password.")
            return render(request, "login.html")

    return render(request, "login.html")


def logout_user(request):
    request.session.flush()  # Deletes all session data
    messages.success(request, "You have been logged out.")
    return redirect("login")



@csrf_exempt
def generate_task(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            task_type = data.get("type")
            difficulty = data.get("difficulty")
            
            duration = data.get("duration")
            user_email = data.get("email")

            #  AI prompt
            prompt = (
                 f"Generate one unique {task_type} productivity task that matches these details:\n"
    f"- Difficulty: {difficulty}\n"
    f"- Duration: {duration}\n"
   
    f"- Task type: {task_type} (Active = movement, exercise, or cleaning. Stationary = reading, writing, organizing, or creative focus.)\n\n"
    
    f"The task must:\n"
    f"1. Be realistic and doable for that difficulty level and duration.\n"
    f"2. Match the type — if it's active, make it physical (e.g., walking, stretching, chores, exercise). "
    f"If it's stationary, make it calm or focus-based (e.g., reading, writing, organizing desk, doing creative work).\n"
    f"3. Speak directly to the user (use 'you').\n"
    f"4. Be short, specific, and easy to understand — 1 to 2 sentences only.\n"
    f"5. Avoid journaling, meditation, or emotional reflection.\n"
    f"6. Make each generation unique by varying the activity, not reusing old patterns.\n\n"
    
    f"After the task, add one short line starting with 'Why it helps:' or 'Why it works:' that gives a quick motivational reason."
    f"Add one short line explaining why it's helpful or satisfying."
            )

            #  Load OpenRouter API key securely
            OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

            # 🛰 Send request to OpenRouter
            response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    },
    json={
        "model": "nvidia/nemotron-nano-9b-v2:free",
        "messages": [
            {"role": "system", "content": "You are a helpful productivity coach."},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,  # controls randomness: 0=deterministic, 1=very creative
        "top_p": 0.9          # optional, adds extra variation
    },
)


            ai_result = response.json()
            if response.status_code != 200 or "choices" not in ai_result:
              print(" OpenRouter error:", ai_result)
              return JsonResponse({
                 "success": False,
                 "error": ai_result.get("error", ai_result)
             })


            #  Extract generated text
            generated_task = ai_result["choices"][0]["message"]["content"].strip()

            #  Extract generated text
            generated_task = ai_result["choices"][0]["message"]["content"].strip()

            #  Save to Supabase "task" table
            user_id = request.session.get("user_id")  # <-- add this line
            task_data = {
                "user_id": user_id, 
                "task_type": task_type,
                "difficulty": difficulty,
               
                "duration": duration,
                "description": generated_task,
                "status": "not started",
            }

            insert_response = supabase.table("task").insert(task_data).execute()
            print("🪄 Task saved:", insert_response)

            return JsonResponse({
                "success": True,
                "generated_task": generated_task,
                "task_id": insert_response.data[0]["task_id"] if insert_response.data else None
            })

        except Exception as e:
            print(" Error generating task:", e)
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"error": "Invalid request method"}, status=400)

def task_dashboard(request):
    # Ensure only logged-in users can access the dashboard
    if "user_email" not in request.session or "user_id" not in request.session:
        messages.warning(request, "Please log in first.")
        return redirect("login")

    user_email = request.session["user_email"]
    user_name = request.session["user_name"]
    user_id = request.session["user_id"]  # safe now

    return render(
        request,
        "task_dashboard.html",
        {
            "user_name": user_name,
            "user_email": user_email,
            "user_id": user_id,
        },
    )



def task_duration(request):
    # get data from previous selections
    task_type = request.GET.get('type')
    difficulty = request.GET.get('difficulty')
   

    if request.method == 'POST':
        duration = request.POST.get('duration')

        #  Example: generate a simple task description (you can replace this with your AI call later)
        generated_task = f"A {difficulty} {task_type} task for {duration} minutes."

        #  Redirect to the result page, passing the generated task as a query parameter
        return redirect(f'/result/?task={generated_task}')

    # if not POST, just show the duration selection page
    return render(request, "task_duration.html")

def task_result(request):
    task_param = request.GET.get("task", "")
    duration = request.GET.get("duration")
    generated_task = unquote(task_param)
    task_id = request.GET.get("task_id")  # add this line

    return render(request, "task_result.html", {
        "generated_task": generated_task,
        "duration": duration,  
        "task_id": task_id,  # pass it to template
        })


#  Start a task session
@csrf_exempt
def start_task_session(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            task_id = data.get("task_id")
            user_id = request.session.get("user_id")  # get from session

            if not user_id or not task_id:
                return JsonResponse({"success": False, "error": "Missing user or task ID"})

            start_time = timezone.localtime(timezone.now()).isoformat()

            response = supabase.table("tasksession").insert({
                "task_id": task_id,
                "user_id": user_id,
                "start_time": start_time,
                "status": "in_progress",
                "progress": 0
            }).execute()

            return JsonResponse({
                "success": True,
                "session_id": response.data[0]["session_id"]
            })

        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"success": False, "error": "Invalid request"})

@csrf_exempt
def update_progress(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            session_id = data.get("session_id")
            progress = data.get("progress")

            if not session_id:
                return JsonResponse({"success": False, "error": "Missing session_id"})

            supabase.table("tasksession").update({"progress": progress}).eq("session_id", session_id).execute()
            return JsonResponse({"success": True})
        except Exception as e:
            return JsonResponse({"success": False, "error": str(e)})

    return JsonResponse({"error": "Invalid request method"}, status=400)


from datetime import date, timedelta

@csrf_exempt
def end_task_session(request):
    if request.method == "POST":
        data = json.loads(request.body)
        session_id = data.get("session_id")
        user_id = request.session.get("user_id")

        if not session_id or not user_id:
            return JsonResponse({"success": False, "error": "Missing session_id or user_id"})

        # 1. Mark session completed
        supabase.table("tasksession").update({
            "status": "completed",
            "end_time": timezone.now().isoformat()
        }).eq("session_id", session_id).execute()

        # 2. Get task_id → get difficulty
        session_res = supabase.table("tasksession").select("task_id").eq("session_id", session_id).execute()
        task_id = session_res.data[0]["task_id"]

        task_res = supabase.table("task").select("difficulty").eq("task_id", task_id).execute()
        difficulty = task_res.data[0]["difficulty"].lower()

        # 3. Difficulty → points mapping
        difficulty_points = {"easy": 50, "medium": 100, "hard": 150}
        earned_points = difficulty_points.get(difficulty, 0)

        # 4. Get existing points
        points_res = supabase.table("points").select("*").eq("user_id", user_id).execute()
        existing = points_res.data[0] if points_res.data else None

        if existing:
            new_total = (existing.get("total_points") or 0) + earned_points
            supabase.table("points").update({
                "total_points": new_total,
                "updated_at": timezone.now().isoformat()
            }).eq("points_id", existing["points_id"]).execute()
        else:
            supabase.table("points").insert({
                "user_id": user_id,
                "total_points": earned_points,
                "updated_at": timezone.now().isoformat()
            }).execute()

        # 5. Update streaks (keep your logic)
        today = datetime.now().date()
        streak_res = supabase.table("streaks").select("*").eq("user_id", user_id).execute()
        streak = streak_res.data[0] if streak_res.data else None

        points = 1
        if streak:
            last_completed = streak.get("last_completed")
            if last_completed:
                last_date = datetime.fromisoformat(last_completed).date()
                delta_days = (today - last_date).days
                if delta_days == 1:
                    points = streak["points"] + 1
                elif delta_days == 0:
                    points = streak["points"]
        if streak:
            supabase.table("streaks").update({
                "points": points,
                "last_completed": today.isoformat()
            }).eq("streak_id", streak["streak_id"]).execute()
        else:
            supabase.table("streaks").insert({
                "user_id": user_id,
                "points": points,
                "last_completed": today.isoformat()
            }).execute()

        # check achievements
        check_achievements(user_id)

        return JsonResponse({"success": True})

    return JsonResponse({"error": "Invalid request method"}, status=400)




#  Timer page (HTML)
def task_timer(request):
    task_id = request.GET.get("task_id")
    duration = request.GET.get("duration")
    generated_task = request.GET.get("task")  # may be None

    #  Safely handle missing 'task' parameter
    if generated_task:
        generated_task = unquote(generated_task)
    else:
        generated_task = "No task description provided."

    return render(request, "task_timer.html", {
        "task_id": task_id,
        "duration": duration,
        "generated_task": generated_task
    })


#PASSWORD RESET
#  PASSWORD RESET (Using Supabase + Gmail OTP)

def forgot_password(request):
    if request.method == "POST":
        email = request.POST.get("email")

        # Check if email exists in your custom table (optional but useful)
        user_exists = supabase.table("user").select("*").eq("email", email).execute()

        if not user_exists.data:
            messages.error(request, "No account found with that email.")
            return redirect("forgot_password")

        # 🔥 SUPABASE: Send password reset email
        try:
            supabase.auth.reset_password_email(
                email,
                options={
                    "redirect_to": "https://csit327-g6-improv.onrender.com/reset_password"
                }
            )

            messages.success(request, "A password reset link has been sent to your email.")
            return redirect("forgot_password")

        except Exception as e:
            print("Error:", e)
            messages.error(request, "Failed to send reset link. Try again later.")

    return render(request, "forgot_password.html")



def verify_otp(request):
    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            otp_entered = form.cleaned_data['otp']
            otp_saved = request.session.get('otp')

            if otp_entered == otp_saved:
                request.session["email_verified"] = True
                messages.success(request, "OTP verified! You can now reset your password.")
                return redirect("reset_password")
            else:
                messages.error(request, "Invalid OTP. Please try again.")
    else:
        form = OTPVerificationForm()

    return render(request, "verify_otp.html", {"form": form})


from .forms import ResetPasswordForm

def reset_password(request):
    form = ResetPasswordForm()

    if request.method == "POST":
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data["new_password"]

            access_token = request.POST.get("access_token")
            refresh_token = request.POST.get("refresh_token")

            if not access_token or not refresh_token:
                messages.error(request, "Invalid or expired password reset link.")
                return redirect("forgot_password")

            try:
                # 🔹 Set session using both tokens
                supabase.auth.set_session(access_token, refresh_token)

                # 🔹 Update password while client is "logged in"
                supabase.auth.update_user({"password": new_password})

                messages.success(request, "Your password has been reset. You can now log in.")
                return redirect("login")

            except Exception as e:
                print("RESET ERROR:", e)
                messages.error(request, "Failed to update password. Please try again.")

    return render(request, "reset_password.html", {"form": form})


#ADDED
def user_progress(request):
    # Ensure user is logged in (via Supabase session)
    if "user_id" not in request.session:
        messages.warning(request, "Please log in first.")
        return redirect("login")

    user_id = request.session["user_id"]
    user_name = request.session.get("user_name", "User")

    # Fetch this user’s tasks from Supabase
    response = supabase.table("task").select("task_type, difficulty").eq("user_id", user_id).execute()
    user_tasks = response.data or []

    # Count totals
    total_tasks = len(user_tasks)
    stationary_counts = {"easy": 0, "medium": 0, "hard": 0}
    active_counts = {"easy": 0, "medium": 0, "hard": 0}

    for task in user_tasks:
        task_type = task.get("task_type", "").lower()
        difficulty = task.get("difficulty", "").lower()

        if task_type == "stationary" and difficulty in stationary_counts:
            stationary_counts[difficulty] += 1
        elif task_type == "active" and difficulty in active_counts:
            active_counts[difficulty] += 1

    stationary_total = sum(stationary_counts.values())
    active_total = sum(active_counts.values())

    # Fetch user points
    points_res = supabase.table("points").select("total_points").eq("user_id", user_id).execute()
    total_points = points_res.data[0]["total_points"] if points_res.data else 0

    # Define context (DO THIS BEFORE using it)
    context = {
        "user_name": user_name,
        "total_tasks": total_tasks,
        "stationary_total": stationary_total,
        "stationary_counts": stationary_counts,
        "active_total": active_total,
        "active_counts": active_counts,
        "total_points": total_points,
    }

    return render(request, "user_progress.html", context)



#ADMIN

from django.conf import settings

# ✅ Create Supabase client
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def admin_dashboard(request):

    if not request.session.get("is_staff") and not request.session.get("is_superuser"):
        messages.error(request, "Access denied.")
        return redirect("task_dashboard")

    if request.method == "POST":
        action = request.POST.get("action")
        raw_user_id = request.POST.get("user_id")

        # Fix type mismatch
        try:
            user_id = int(raw_user_id)
        except:
            messages.error(request, "Invalid user ID.")
            return redirect("admin_dashboard")

        # Prevent self-deletionfr r g
        if user_id == request.session.get("user_id"):
            messages.error(request, "You cannot delete your own account.")
            return redirect("admin_dashboard")

        try:
            if action == "delete":
                result = supabase.table("user").delete().eq("user_id", user_id).execute()
                print("DELETE RESULT:", result)
                messages.success(request, "User deleted successfully.")

            elif action == "make_admin":
                supabase.table("user").update({
                    "is_staff": True,
                    "is_superuser": True
                }).eq("user_id", user_id).execute()
                messages.success(request, "Promoted to admin.")

            elif action == "remove_admin":
                supabase.table("user").update({
                    "is_staff": False,
                    "is_superuser": False
                }).eq("user_id", user_id).execute()
                messages.success(request, "Admin role removed.")

        except Exception as e:
            print("SUPABASE ERROR:", e)
            messages.error(request, f"Error: {str(e)}")

        return redirect("admin_dashboard")

    # Fetch users
    response = supabase.table("user").select("*").execute()
    users = response.data or []

    return render(request, "admin_dashboard.html", {"users": users})



def profile_user(request):
    return render(request, "profile_user.html")


#Profle added
import os
from django.conf import settings
import uuid

from supabase import create_client
import uuid

def profile_user(request):
    if "user_email" not in request.session:
        return redirect("login")

    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    user_id = request.session.get("user_id")
    user_email = request.session.get("user_email")

    # Fetch user data
    user_record = supabase.table("user").select("*").eq("user_id", user_id).execute()
    user_data = user_record.data[0]

    # ============================================================
    # 1. IMAGE UPLOAD
    # ============================================================
    if request.method == "POST" and "image" in request.FILES:
        image_file = request.FILES["image"]

        file_ext = image_file.name.split(".")[-1]
        filename = f"profile_{user_id}_{uuid.uuid4()}.{file_ext}"
        file_bytes = image_file.read()

        supabase.storage.from_(settings.SUPABASE_BUCKET).upload(
            path=filename,
            file=file_bytes,
            file_options={"content-type": image_file.content_type},
        )

        file_url = supabase.storage.from_(settings.SUPABASE_BUCKET).get_public_url(filename)
        supabase.table("user").update({"profile_image": file_url}).eq("user_id", user_id).execute()

        request.session["profile_image"] = file_url
        messages.success(request, "Profile picture updated!")
        return redirect("profile_user")

    # ============================================================
    # 2. CHANGE PASSWORD
    # ============================================================
    if request.method == "POST" and request.POST.get("action") == "change_password":
        old_pw = request.POST.get("old_password")
        new_pw = request.POST.get("new_password")
        confirm_pw = request.POST.get("confirm_password")

        if new_pw != confirm_pw:
            messages.error(request, "New passwords do not match.")
            return redirect("profile_user")

        # Verify old password using Supabase Auth
        try:
            auth_response = supabase.auth.sign_in_with_password({
                "email": user_email,
                "password": old_pw
            })
            if not auth_response.user:
                messages.error(request, "Old password is incorrect.")
                return redirect("profile_user")
        except Exception:
            messages.error(request, "Old password is incorrect.")
            return redirect("profile_user")

        # Update password in Supabase Auth
        try:
            supabase.auth.update_user({"password": new_pw})
            messages.success(request, "Password updated successfully!")
        except Exception:
            messages.error(request, "Failed to update password.")
        return redirect("profile_user")

    # ============================================================
    # 3. DELETE ACCOUNT
    # ============================================================
    if request.method == "POST" and request.POST.get("action") == "delete_account":

        # Delete image from Storage (optional)
        profile_image_url = user_data.get("profile_image")
        if profile_image_url:
            import urllib.parse
            path = urllib.parse.urlparse(profile_image_url).path.lstrip("/")
            try:
                supabase.storage.from_(settings.SUPABASE_BUCKET).remove([path])
            except Exception as e:
                print("Storage delete error:", e)

        # Delete from Supabase Auth
        auth_id = user_data.get("auth_id")
        if auth_id:
            try:
                supabase.auth.admin.delete_user(auth_id)
            except Exception as e:
                print("Auth delete error:", e)

        # Delete from custom table
        supabase.table("user").delete().eq("user_id", user_id).execute()

        request.session.flush()
        return redirect("login")

    # ============================================================
    # 4. DISPLAY PAGE
    # ============================================================
    profile_image = request.session.get(
        "profile_image",
        user_data.get("profile_image", "default_profile.png")
    )

    context = {
        "user_name": user_data["name"],
        "user_email": user_data["email"],
        "profile_image": profile_image,
    }

    return render(request, "profile_user.html", context)

def admin_profile(request):
    if "user_email" not in request.session:
        return redirect("login")

    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
    user_id = request.session.get("user_id")
    user_email = request.session.get("user_email")

    # Fetch user data from custom table
    user_record = supabase.table("user").select("*").eq("user_id", user_id).execute()
    user_data = user_record.data[0]

    # ============================================================
    # 1. IMAGE UPLOAD
    # ============================================================
    if request.method == "POST" and "image" in request.FILES:
        image_file = request.FILES["image"]

        file_ext = image_file.name.split(".")[-1]
        filename = f"profile_{user_id}_{uuid.uuid4()}.{file_ext}"
        file_bytes = image_file.read()

        supabase.storage.from_(settings.SUPABASE_BUCKET).upload(
            path=filename,
            file=file_bytes,
            file_options={"content-type": image_file.content_type},
        )

        file_url = supabase.storage.from_(settings.SUPABASE_BUCKET).get_public_url(filename)
        supabase.table("user").update({"profile_image": file_url}).eq("user_id", user_id).execute()
        request.session["profile_image"] = file_url
        messages.success(request, "Profile picture updated!")
        return redirect("admin_profile")

    # ============================================================
    # 2. CHANGE PASSWORD
    # ============================================================
    if request.method == "POST" and request.POST.get("action") == "change_password":
        old_pw = request.POST.get("old_password")
        new_pw = request.POST.get("new_password")
        confirm_pw = request.POST.get("confirm_password")

        if new_pw != confirm_pw:
            messages.error(request, "New passwords do not match.")
            return redirect("admin_profile")

        # ✅ Verify old password via Supabase Auth
        try:
            auth_response = supabase.auth.sign_in_with_password({
                "email": user_email,
                "password": old_pw
            })
            if not auth_response.user:
                messages.error(request, "Old password is incorrect.")
                return redirect("admin_profile")
        except Exception as e:
            messages.error(request, "Failed to verify old password.")
            return redirect("admin_profile")

        # ✅ Update password via Supabase Auth
        try:
            supabase.auth.update_user({"password": new_pw})
            messages.success(request, "Password updated successfully!")
        except Exception as e:
            messages.error(request, "Failed to update password.")
        return redirect("admin_profile")

    # ============================================================
    # 3. DELETE ACCOUNT
    # ============================================================
    if request.method == "POST" and request.POST.get("action") == "delete_account":

        # Delete profile image from Storage (optional)
        profile_image_url = user_data.get("profile_image")
        if profile_image_url:
            import urllib.parse
            path = urllib.parse.urlparse(profile_image_url).path.lstrip("/")
            try:
                supabase.storage.from_(settings.SUPABASE_BUCKET).remove([path])
            except Exception as e:
                print("Error deleting storage file:", e)

        # Delete user from Supabase Auth
        auth_id = user_data.get("auth_id")
        if auth_id:
            try:
                supabase.auth.admin.delete_user(auth_id)
            except Exception as e:
                print("Error deleting auth user:", e)

        # Delete user row from custom table
        supabase.table("user").delete().eq("user_id", user_id).execute()

        # Clear session
        request.session.flush()
        return redirect("login")

    # ============================================================
    # 4. DISPLAY PAGE
    # ============================================================
    profile_image = request.session.get(
        "profile_image",
        user_data.get("profile_image", "default_profile.png")
    )

    context = {
        "user_name": user_data["name"],
        "user_email": user_data["email"],
        "profile_image": profile_image,
    }

    return render(request, "admin_profile.html", context)




#CHANGED
from django.shortcuts import render

def task_summary(request):
    task = request.GET.get("task", "No task description available.")
    return render(request, "task_summary.html", {"task": task})

def leaderboard(request):
    if "user_id" not in request.session:
        messages.warning(request, "Please log in first.")
        return redirect("login")

    # --- NEW LEADERBOARD FOR POINTS ---
    points_res = (
        supabase.table("points")
        .select("user_id, total_points")
        .order("total_points", desc=True)
        .limit(3)
        .execute()
    )

    points_rows = points_res.data or []
    points_user_ids = [p["user_id"] for p in points_rows]

    if points_user_ids:
        user_res = (
            supabase.table("user")
            .select("user_id, name")
            .in_("user_id", points_user_ids)
            .execute()
        )
        user_data = {u["user_id"]: u["name"] for u in (user_res.data or [])}
    else:
        user_data = {}

    leaderboard_points = [
        {"name": user_data.get(p["user_id"], "Unknown"), "points": p["total_points"]}
        for p in points_rows
    ]

    # --- EXISTING STREAK LEADERBOARD (UNCHANGED) ---
    streak_res = supabase.table("streaks").select("user_id, points").order("points", desc=True).limit(3).execute()
    streak_rows = streak_res.data or []

    streak_user_ids = [s["user_id"] for s in streak_rows]

    if streak_user_ids:
        streak_user_response = supabase.table("user") \
            .select("user_id, name") \
            .in_("user_id", streak_user_ids) \
            .execute()
        streak_user_data = {u["user_id"]: u["name"] for u in (streak_user_response.data or [])}
    else:
        streak_user_data = {}

    leaderboard_streaks = [
        {"name": streak_user_data.get(s["user_id"], "Unknown"), "points": s["points"]}
        for s in streak_rows
    ]

    context = {
        "leaderboard": leaderboard_points,  # 🔥 now using points
        "streak_leaderboard": leaderboard_streaks
    }

    return render(request, "leaderboard.html", context)



from datetime import date, timedelta

def streak_dashboard(request):
    if "user_id" not in request.session:
        messages.warning(request, "Please log in first.")
        return redirect("login")

    user_id = request.session["user_id"]

    res = supabase.table("streaks").select("*").eq("user_id", user_id).execute()
    streak = res.data[0] if res.data else None

    points = streak["points"] if streak else 0

    return render(request, "streak_dashboard.html", {
        "points": points,
        "streak_updated": False
    })


from .models import Achievement
from supabase import create_client

from datetime import datetime, timedelta
from django.utils import timezone

def check_achievements(user_id):
    """Check and unlock achievements for a user."""
    # Get streak points
    streak_res = supabase.table("streaks").select("*").eq("user_id", user_id).execute()
    streak = streak_res.data[0] if streak_res.data else None
    streak_points = streak["points"] if streak else 0

    today = datetime.now().date()

    # Fetch all achievements for the user
    ach_res = supabase.table("achievements").select("*").eq("user_id", user_id).execute()
    achievements = ach_res.data

    for ach in achievements:
        if ach["unlocked"]:
            continue  # already unlocked

        unlock = False
        code = ach["code"]

        # 1️⃣ First step
        if code == "first_step":
            tasks = supabase.table("tasksession").select("*").eq("user_id", user_id).eq("status", "completed").execute()
            if len(tasks.data) >= 1:
                unlock = True

        # 2️⃣ Streak-based achievements
        elif code == "two_day_streak" and streak_points >= 2:
            unlock = True
        elif code == "week_warrior" and streak_points >= 7:
            unlock = True
        elif code == "two_week_champion" and streak_points >= 14:
            unlock = True
        elif code == "month_master" and streak_points >= 30:
            unlock = True
        elif code == "half_year_hero" and streak_points >= 180:
            unlock = True
        elif code == "year_of_focus" and streak_points >= 365:
            unlock = True

        # 3️⃣ Time-based achievements
        elif code == "early_bird":
            tasks_res = supabase.table("tasksession").select("*").eq("user_id", user_id).order("start_time", {"ascending": True}).limit(1).execute()
            if tasks_res.data:
                first_task_time = datetime.fromisoformat(tasks_res.data[0]["start_time"])
                if first_task_time.hour < 8:
                    unlock = True

        elif code == "night_owl":
            tasks_res = supabase.table("tasksession").select("*").eq("user_id", user_id).order("start_time", {"descending": True}).limit(1).execute()
            if tasks_res.data:
                last_task_time = datetime.fromisoformat(tasks_res.data[0]["start_time"])
                if last_task_time.hour >= 22:
                    unlock = True

        # 5️⃣ Update achievement in Supabase
        if unlock:
            supabase.table("achievements").update({
                "unlocked": True,
                "unlocked_at": timezone.now().isoformat()
            }).eq("achievement_id", ach["achievement_id"]).execute()


from supabase import create_client
from django.utils import timezone
from django.shortcuts import render, redirect
from django.contrib import messages

# Initialize Supabase client somewhere globally
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def achievements_dashboard(request):
    if "user_id" not in request.session:
        return redirect("login")

    user_id = request.session["user_id"]

    # Ensure default achievements exist
    create_user_achievements(user_id)

    # Fetch achievements
    res = supabase.table("achievements").select("*").eq("user_id", user_id).execute()
    achievements = res.data
    achievements.sort(key=lambda x: not x.get("unlocked", False))
    return render(request, "achievements_dashboard.html", {
        "achievements": achievements
    })





