# productivity_app/utils/achievements.py
from datetime import datetime, timedelta
from django.utils import timezone
from supabase import create_client
from django.conf import settings

# Supabase client
supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

def create_user_achievements(user_id):
    """Create default achievements for a user if not exist."""
    default_achievements = [
        {"code": "first_step", "title": "First Step", "description": "Complete 1 task"},
        {"code": "two_day_streak", "title": "Two-Day Streak", "description": "Complete tasks 2 days in a row"},
        {"code": "week_warrior", "title": "Week Warrior", "description": "7-day streak"},
        {"code": "two_week_champion", "title": "Two-Week Champion", "description": "14-day streak"},
        {"code": "month_master", "title": "Month Master", "description": "30-day streak"},
        {"code": "half_year_hero", "title": "Half-Year Hero", "description": "180-day streak"},
        {"code": "year_of_focus", "title": "Year of Focus", "description": "365-day streak"},
        {"code": "early_bird", "title": "Early Bird", "description": "Complete first task before 8 AM"},
        {"code": "night_owl", "title": "Night Owl", "description": "Complete task after 10 PM"},
        {"code": "multi_tasker", "title": "Multi-Tasker", "description": "Complete 3+ tasks in a single day"},
    ]

    # Insert default achievements if they don't exist
    for ach in default_achievements:
        exists = supabase.table("achievements").select("*").eq("user_id", user_id).eq("code", ach["code"]).execute()
        if not exists.data:
            supabase.table("achievements").insert({
                "user_id": user_id,
                "code": ach["code"],
                "title": ach["title"],
                "description": ach["description"],
                "unlocked": False
            }).execute()


def check_achievements(user_id):
    """Check and unlock achievements for a user."""
    streak_res = supabase.table("streaks").select("*").eq("user_id", user_id).execute()
    streak = streak_res.data[0] if streak_res.data else None
    streak_points = streak["points"] if streak else 0

    # Fetch all achievements for the user
    ach_res = supabase.table("achievements").select("*").eq("user_id", user_id).execute()
    achievements = ach_res.data

    today = datetime.now().date()

    for ach in achievements:
        unlock = False
        code = ach["code"]

        if ach["unlocked"]:
            continue

        # Achievement rules
        if code == "first_step":
            tasks = supabase.table("tasksession").select("*").eq("user_id", user_id).execute()
            if len(tasks.data) >= 1:
                unlock = True
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
        elif code == "multi_tasker":
            tasks_today = supabase.table("tasksession").select("*").eq("user_id", user_id).gte("start_time", today.isoformat()).lte("start_time", (today + timedelta(days=1)).isoformat()).execute()
            if len(tasks_today.data) >= 3:
                unlock = True

        # Update achievement if unlocked
        if unlock:
            supabase.table("achievements").update({
                "unlocked": True,
                "unlocked_at": timezone.now().isoformat()
            }).eq("achievement_id", ach["achievement_id"]).execute()
