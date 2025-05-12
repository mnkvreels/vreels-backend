from src.database import SessionLocal
from src.models import Post, Like, Comment, MediaInteraction # Adjust import paths as needed
from src.models import MediaInteraction


session = SessionLocal()

def safe_delete(query, label, chunk_size=500):
    total_deleted = 0
    while True:
        records = query.limit(chunk_size).all()
        if not records:
            break
        for record in records:
            session.delete(record)
        session.flush()
        session.commit()
        total_deleted += len(records)
        print(f"🧹 Deleted {len(records)} {label} (total: {total_deleted})")
    return total_deleted

try:
    author_id = 25479
    print(f"🔍 Fetching posts for author {author_id}")
    posts = session.query(Post).filter(Post.author_id == author_id).all()
    deleted_post_count = 0

    for post in posts:
        print(f"\n➡️ Processing post {post.id}")

        # Delete related Likes
        safe_delete(session.query(Like).filter(Like.post_id == post.id), "likes")

        # Delete related Comments
        safe_delete(session.query(Comment).filter(Comment.post_id == post.id), "comments")

        # Delete related MediaInteractions
        safe_delete(session.query(MediaInteraction).filter(MediaInteraction.post_id == post.id), "media_interactions")


        # Delete the Post itself
        try:
            session.delete(post)
            session.commit()
            print(f"✅ Deleted post {post.id}")
            deleted_post_count += 1
        except Exception as post_error:
            print(f"❌ Error deleting post {post.id}: {post_error}")
            session.rollback()

    print(f"\n🎉 Completed. Total posts deleted: {deleted_post_count}")

except Exception as e:
    session.rollback()
    print(f"❌ Fatal error: {e}")

finally:
    session.close()
