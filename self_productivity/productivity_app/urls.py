# productivity_app/urls.py
from django.urls import path
from django.shortcuts import redirect  
from . import views

#changed
from django.contrib.auth import views as auth_views
urlpatterns = [
     path('', lambda request: redirect('login')), 
     path("register/", views.register, name="register"),
     path("login/", views.login_user, name="login"),
     path("dashboard/", views.task_dashboard, name="task_dashboard"),
     path("generate-task/", views.generate_task, name="generate_task"), 
 
     path('duration/', views.task_duration, name='task_duration'),
     path('result/', views.task_result, name='task_result'),  
     path("start-task-session/", views.start_task_session, name="start_task_session"),
     path("update-progress/", views.update_progress, name="update_progress"),
     path("end-task-session/", views.end_task_session, name="end_task_session"),
     path('timer/', views.task_timer, name='task_timer'),# 👈 add this

    path('forgot_password/', views.forgot_password, name='forgot_password'),
    path('verify_otp/', views.verify_otp, name='verify_otp'),
    path('reset_password/', views.reset_password, name='reset_password'),
    path("admin_dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("user_progress/", views.user_progress, name="user_progress"),
    path("profile_user/", views.profile_user, name="profile_user"),
    path("admin_profile/", views.admin_profile, name="admin_profile"),
    path("task_summary/", views.task_summary, name="task_summary"),
    path("leaderboard/", views.leaderboard, name="leaderboard"),
    path("streak_dashboard/", views.streak_dashboard, name="streak_dashboard"),
    path("achievements_dashboard/", views.achievements_dashboard, name="achievements_dashboard"),

]
