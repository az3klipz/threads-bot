import asyncio
import random
import json
import os
from datetime import datetime
from .browser import BrowserManager
from .config import load_config, save_config
from . import db
from .constants import STATS_FILE, CONTROL_FILE

from .utils import SpintaxParser

class ThreadsBot:
    def __init__(self, mode="keyword"):
        self.mode = mode
        self.config = load_config()
        self.browser = BrowserManager()
        self.stats = self.load_stats()
        self.running = True

    def load_stats(self):
        today = datetime.now().strftime("%Y-%m-%d")
        default_stats = {"date": today, "likes": 0, "follows": 0}
        
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, "r") as f:
                    stats = json.load(f)
                    if stats.get("date") == today:
                        return stats
            except: pass
        return default_stats

    def save_stats(self):
        try:
            with open(STATS_FILE, "w") as f:
                json.dump(self.stats, f, indent=4)
        except: pass

    def check_stop_signal(self):
        if os.path.exists(CONTROL_FILE):
            try:
                with open(CONTROL_FILE, "r") as f:
                    data = json.load(f)
                    if data.get("status") == "stopping":
                        return True
            except: pass
        return False

    async def run(self):
        print(f"Starting Bot in {self.mode} mode...")
        page = await self.browser.start(headless=False)
        
        try:
            while self.running:
                if self.check_stop_signal():
                    print("Stop signal received.")
                    break

                await self.browser.inject_interface(self.stats, self.mode)
                
                # Check for pending tasks (high priority)
                await self.process_pending_tasks()
                
                # Logic based on mode
                if self.mode == "manual":
                    await self.browser.human_delay(2, 3)
                elif self.mode == "competitor":
                    await self.perform_competitor_actions()
                elif self.mode == "pod":
                    await self.perform_pod_actions()
                else:
                    # Keyword automation mode
                    await self.perform_keyword_actions()
                
        except Exception as e:
            print(f"Bot Error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            await self.browser.stop()
            print("Bot Stopped.")

    async def perform_monitor_actions(self):
        """Monitor the feed for specific phrases"""
        try:
            phrases = self.config.get("monitor_phrases", [])
            if not phrases:
                print("[Monitor] No monitor_phrases configured!")
                return
            
            await self.browser.scan_feed_for_phrases(phrases)
            
            # After one scan loop, wait a bit
            print("[Monitor] Waiting 60s before next scan...")
            await self.browser.human_delay(60, 60)
            
        except Exception as e:
            print(f"[Monitor] Error: {e}")

    async def process_pending_tasks(self):
        """Check for and execute pending tasks from the database"""
        try:
            tasks = db.get_pending_tasks()
            if not tasks:
                return

            print(f"[Task] Found {len(tasks)} pending tasks")
            
            for task in tasks:
                print(f"[Task] Processing task: {task['type']} - {task['payload']}")
                
                success = False
                if task['type'] == 'unfollow':
                    username = task['payload']
                    # Navigate to profile and unfollow
                    success = await self.browser.unfollow_user(username)
                    
                    if success:
                        # Update lead status in DB to 'Unfollowed'
                        # This ensures it updates in the dashboard list
                        db.update_lead_status(username, "Unfollowed")
                        print(f"[Task] Updated status for @{username} to 'Unfollowed'")
                
                # Update task status
                status = 'completed' if success else 'failed'
                db.update_task_status(task['id'], status)
                
                await self.browser.human_delay(1, 2)
                
        except Exception as e:
            print(f"[Task] Error processing tasks: {e}")

    async def perform_competitor_actions(self):
        """Perform competitor-based automation: scrape followers and interact"""
        try:
            competitors = self.config.get("competitors", [])
            max_likes = self.config.get("max_likes", 20)
            max_follows = self.config.get("max_follows", 20)
            enable_follow = self.config.get("enable_follow", False)
            enable_like = self.config.get("enable_like", True)
            follow_range = self.config.get("probabilities", {}).get("follow_range", [0.8, 0.95])
            
            if not competitors:
                print("[Competitor] No competitors configured!")
                return

            # Check limits
            if self.stats["likes"] >= max_likes and self.stats["follows"] >= max_follows:
                print(f"[Limits] Daily limits reached")
                await self.browser.human_delay(10, 15)
                return

            competitor = random.choice(competitors)
            print(f"\n[Competitor] Selected competitor: @{competitor}")
            
            # Get followers from competitor
            followers = await self.browser.get_followers_list(competitor, max_count=20)
            
            if not followers:
                print(f"[Competitor] No followers found for @{competitor}")
                return

            print(f"[Competitor] Found {len(followers)} followers to process")
            
            for username in followers:
                if self.check_stop_signal(): break
                if self.stats["likes"] >= max_likes and self.stats["follows"] >= max_follows:
                    print(f"[Limits] Daily limits reached")
                    break
                
                # Check if we already interacted with this user
                # (You might want to add a DB check here if you have a 'seen_users' table, 
                # but for now we rely on 'leads' table for follows)
                
                print(f"\n[Competitor] Processing follower: @{username}")
                
                # Navigate to user profile
                # We can reuse follow_user which navigates to profile
                
                should_follow = enable_follow and self.stats["follows"] < max_follows and random.uniform(0, 1) <= random.uniform(*follow_range)
                
                if should_follow:
                    followed = await self.browser.follow_user(username)
                    if followed:
                        self.stats["follows"] += 1
                        self.save_stats()
                        db.add_lead(username, source="competitor")
                        db.log_interaction(username, "follow", f"Followed from competitor: {competitor}")
                        
                        # Post-follow engagement
                        follow_engagement = self.config.get("follow_engagement", {})
                        if follow_engagement.get("like_posts_after_follow", False):
                            min_posts = follow_engagement.get("min_posts", 2)
                            max_posts = follow_engagement.get("max_posts", 5)
                            liked_count = await self.browser.like_recent_posts(username, min_posts, max_posts)
                            if liked_count > 0:
                                self.stats["likes"] += liked_count
                                self.save_stats()
                                db.log_interaction(username, "engagement", f"Liked {liked_count} posts after follow")
                
                elif enable_like and self.stats["likes"] < max_likes:
                    # If not following, maybe just like some posts?
                    # Navigate to profile first
                    await self.browser.page.goto(f"https://www.threads.net/@{username}", wait_until="domcontentloaded")
                    await self.browser.human_delay(2, 3)
                    
                    liked_count = await self.browser.like_recent_posts(username, min_posts=1, max_posts=3)
                    if liked_count > 0:
                        self.stats["likes"] += liked_count
                        self.save_stats()
                        db.log_interaction(username, "like", f"Liked {liked_count} posts from competitor source")

                await self.browser.human_delay(3, 5)

            print(f"[Competitor] Finished processing followers for @{competitor}")

        except Exception as e:
            print(f"[Competitor] Error: {e}")
            import traceback
            traceback.print_exc()


    async def perform_pod_actions(self):
        """Iterate through pod members and engage with their latest posts"""
        try:
            pod_members = self.config.get("pod_members", [])
            enable_like = self.config.get("pod_enable_like", True)
            enable_comment = self.config.get("pod_enable_comment", True)
            comment_templates = self.config.get("pod_comment_templates", ["{Great|Nice} post!"])
            
            if not pod_members:
                print("[Pod] No members in pod list! Please configure config.")
                await self.browser.human_delay(5, 10)
                return

            print(f"[Pod] Starting cycle for {len(pod_members)} members...")
            
            # Use sequential order as requested
            
            for index, username in enumerate(pod_members):
                try:
                    username = username.replace("@", "").strip()
                    if not username: continue
                    
                    if self.check_stop_signal(): 
                        print("[Pod] Stop signal received.")
                        break

                    print(f"\n[Pod] ({index+1}/{len(pod_members)}) Visiting @{username}")
                    
                    # Navigate to profile
                    try:
                        await self.browser.page.goto(f"https://www.threads.net/@{username}", wait_until="domcontentloaded", timeout=60000)
                    except Exception as nav_e:
                        print(f"[Pod] Navigation failed for @{username}: {nav_e}")
                        continue

                    await self.browser.human_delay(3, 5)
                    
                    # Find posts
                    posts = await self.browser.get_posts_on_page()
                    if not posts:
                        print(f"[Pod] No posts found for @{username}")
                        continue
                    
                    print(f"[Pod] Found {len(posts)} visible posts. Processing waterfall...")
                    
                    posts_processed = 0
                    comment_made = False
                    max_depth = 10 # Check up to 10 posts to find where we left off

                    for i, post in enumerate(posts[:max_depth]):
                        if self.check_stop_signal(): break
                        
                        # Scroll into view
                        try:
                           await post.scroll_into_view_if_needed()
                           await self.browser.human_delay(0.5, 1)
                        except: pass
                        
                        # 1. LIKE
                        if enable_like:
                            liked = await self.browser.like_post(post)
                            
                            if not liked:
                                # like_post returns False if already liked OR error
                                # We assume it means we hit the history.
                                print(f"[Pod] Post {i+1} already liked (or failed). Catch-up complete for @{username}.")
                                break
                            
                            # Successfully liked
                            print(f"[Pod] Liked post {i+1}")
                            self.stats["likes"] += 1
                            self.save_stats()
                            db.log_interaction(username, "pod_like", "Liked via Pod Booster")
                            posts_processed += 1
                        
                        else:
                            # If liking is disabled, just check latest post for comment
                            print("[Pod] Liking disabled. Checking comments only on latest post.")
                            if i > 0: break

                        # 2. COMMENT (Only on the first new post we encounter)
                        if enable_comment and not comment_made:
                            # Ensure we have templates
                            if comment_templates:
                                template = random.choice(comment_templates)
                                comment_text = SpintaxParser.process_comment(template, username=username)
                                
                                commented = await self.browser.comment_on_post(post, comment_text)
                                if commented:
                                    print(f"[Pod] Commented: {comment_text}")
                                    db.log_interaction(username, "pod_comment", f"Comment: {comment_text}")
                                    comment_made = True
                            else:
                                print("[Pod] Comments enabled but no templates found.")

                        if posts_processed > 0:
                            await self.browser.human_delay(2, 4)

                    # End of user loop
                    print(f"[Pod] Finished @{username}. Processed {posts_processed} new posts.")
                    
                    # Slight delay before next user
                    await self.browser.human_delay(5, 10)

                except Exception as user_e:
                    print(f"[Pod] Error processing @{username}: {user_e}")
                    import traceback
                    traceback.print_exc()
                    continue

            print("[Pod] Cycle complete. Waiting before restart...")
            await self.browser.human_delay(60, 120)

        except Exception as e:
            print(f"[Pod] Critical Error in cycle: {e}")
            import traceback
            traceback.print_exc()
    async def perform_keyword_actions(self):
        """Perform keyword-based automation: search, filter, like, follow, comment"""
        try:
            keywords = self.config.get("keywords", [])
            negative_keywords = self.config.get("negative_keywords", [])
            max_likes = self.config.get("max_likes", 20)
            max_follows = self.config.get("max_follows", 20)
            enable_like = self.config.get("enable_like", True)
            enable_follow = self.config.get("enable_follow", False)
            enable_comment = self.config.get("enable_comment", False)
            comment_probability = self.config.get("comment_probability", 0.3)
            comment_templates = self.config.get("comment_templates", ["Great post!"])
            like_range = self.config.get("probabilities", {}).get("like_range", [0.4, 0.7])
            follow_range = self.config.get("probabilities", {}).get("follow_range", [0.8, 0.95])
            
            # New config: Follows per keyword
            follows_per_keyword = self.config.get("follows_per_keyword", 5)

            # Check limits
            if self.stats["likes"] >= max_likes and self.stats["follows"] >= max_follows:
                print(f"[Limits] Daily limits reached")
                await self.browser.human_delay(10, 15)
                return

            if not keywords:
                print("[Keyword] No keywords configured!")
                return

            keyword = random.choice(keywords)
            print(f"\n[Keyword] Selected keyword: '{keyword}' (Target follows: {follows_per_keyword})")

            success = await self.browser.search_keyword(keyword)
            if not success: return

            # Keep track of processed users in this session to avoid duplicates
            processed_users = set()
            
            keyword_follows_count = 0
            scroll_attempts_without_new_posts = 0
            max_scroll_retries = 10 # How many times to scroll if we don't find new posts before giving up

            # Loop until we reach the follow target for this keyword
            while keyword_follows_count < follows_per_keyword:
                if self.check_stop_signal(): break
                if self.stats["likes"] >= max_likes and self.stats["follows"] >= max_follows:
                    print(f"[Limits] Daily limits reached")
                    break
                
                # Get posts on current view
                posts = await self.browser.get_posts_on_page()
                if not posts:
                    print("[Keyword] No posts found on page")
                    break

                # Filter for NEW posts only
                new_posts_to_process = []
                for post in posts:
                    username = await self.browser.extract_username_from_post(post)
                    if username and username not in processed_users:
                        # Check own username
                        my_username = self.config.get("my_username", "").replace("@", "").lower()
                        if my_username and username.lower() == my_username:
                            continue
                        new_posts_to_process.append(post)

                if not new_posts_to_process:
                    print(f"[Keyword] No new posts found in current view. Scrolling... (Attempt {scroll_attempts_without_new_posts+1}/{max_scroll_retries})")
                    await self.browser.scroll_page()
                    await self.browser.human_delay(2, 3)
                    scroll_attempts_without_new_posts += 1
                    
                    if scroll_attempts_without_new_posts >= max_scroll_retries:
                        print("[Keyword] Max scroll retries reached without finding new posts. Moving to next keyword.")
                        break
                    continue
                
                # Reset scroll counter since we found posts
                scroll_attempts_without_new_posts = 0
                print(f"[Keyword] Found {len(new_posts_to_process)} new posts to process")

                # Process the new posts
                for post in new_posts_to_process:
                    if self.check_stop_signal(): break
                    if keyword_follows_count >= follows_per_keyword: break # Target reached
                    
                    username = await self.browser.extract_username_from_post(post)
                    # Double check (should be covered by filter above, but good for safety)
                    if not username or username in processed_users: continue
                    
                    processed_users.add(username)
                    
                    # Scroll post into view
                    try:
                        await post.scroll_into_view_if_needed()
                        await self.browser.human_delay(0.5, 1)
                    except: pass

                    post_text = await self.browser.get_post_text(post)
                    print(f"\n[Post] Processing post by @{username}")

                    # Filter negative keywords
                    if negative_keywords:
                        if any(neg_kw in post_text for neg_kw in negative_keywords):
                            print(f"[Filter] Skipping post - negative keyword")
                            continue

                    # Logic
                    should_follow = enable_follow and self.stats["follows"] < max_follows and random.uniform(0, 1) <= random.uniform(*follow_range)

                    if should_follow:
                        # Navigate to profile to follow
                        followed = await self.browser.follow_user(username)
                        
                        if followed:
                            self.stats["follows"] += 1
                            self.save_stats()
                            db.add_lead(username, source="keyword")
                            db.log_interaction(username, "follow", f"Followed from keyword: {keyword}")
                            keyword_follows_count += 1
                            print(f"[Keyword] Follows for this keyword: {keyword_follows_count}/{follows_per_keyword}")
                        
                        # Post-follow engagement (always try if configured)
                        follow_engagement = self.config.get("follow_engagement", {})
                        if follow_engagement.get("like_posts_after_follow", False):
                            min_posts = follow_engagement.get("min_posts", 2)
                            max_posts = follow_engagement.get("max_posts", 5)
                            
                            liked_count = await self.browser.like_recent_posts(username, min_posts, max_posts)
                            if liked_count > 0:
                                self.stats["likes"] += liked_count
                                self.save_stats()
                                db.log_interaction(username, "engagement", f"Liked {liked_count} posts after follow")
                        
                        # Navigate back to search results
                        await self.browser.search_keyword(keyword)
                        await self.browser.human_delay(2, 3)
                        
                        # BREAK inner loop to re-scan feed from top (and scroll down to new posts)
                        break 

                    else:
                        # Stay on feed logic
                        should_like = enable_like and self.stats["likes"] < max_likes and random.uniform(0, 1) <= random.uniform(*like_range)
                        
                        if should_like:
                            liked = await self.browser.like_post(post)
                            if liked:
                                self.stats["likes"] += 1
                                self.save_stats()
                                db.log_interaction(username, "like", f"Liked post for keyword: {keyword}")

                        should_comment = enable_comment and random.uniform(0, 1) <= comment_probability
                        if should_comment:
                            template = random.choice(comment_templates)
                            comment_text = SpintaxParser.process_comment(template, username=username)
                            commented = await self.browser.comment_on_post(post, comment_text)
                            if commented:
                                db.log_interaction(username, "comment", f"Commented: {comment_text}")

                    await self.browser.human_delay(2, 4)

            print(f"\n[Keyword] Finished processing keyword '{keyword}'. Total follows: {keyword_follows_count}")

        except Exception as e:
            print(f"[Keyword] Error: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "keyword"
    bot = ThreadsBot(mode)
    asyncio.run(bot.run())
