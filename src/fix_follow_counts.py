from sqlalchemy.orm import Session
from src.database import SessionLocal
from src.models import User, Follow

def fix_follow_counts():
    db: Session = SessionLocal()
    try:
        # Only update users who have non-zero counts (optional optimization)
        users = db.query(User).filter(
            (User.followers_count > 0) | (User.following_count > 0)
        ).all()

        print(f"🔄 Fixing {len(users)} users with non-zero counts...")

        for idx, user in enumerate(users, start=1):
            # Recalculate actual values
            actual_followers = db.query(Follow).filter(Follow.following_id == user.id).count()
            actual_following = db.query(Follow).filter(Follow.follower_id == user.id).count()

            user.followers_count = actual_followers
            user.following_count = actual_following

            db.add(user)  # Mark as dirty

            print(f"[{idx}] {user.username} - followers: {actual_followers}, following: {actual_following}")

        db.commit()
        print("✅ All affected users updated successfully.")

    except Exception as e:
        db.rollback()
        print("❌ Error while updating users:", e)
    finally:
        db.close()

if __name__ == "__main__":
    fix_follow_counts()
