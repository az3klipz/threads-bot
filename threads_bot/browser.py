import asyncio
import random
from playwright.async_api import async_playwright
from .constants import THREADS_URL, USER_DATA_DIR, SELECTORS
from .config import load_config

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.config = load_config()

    async def _handle_add_lead(self, source, username):
        from . import db
        print(f"[Manual Mode] Received add request for: {username}")
        try:
            # Attempt to follow the user
            print(f"[Manual Mode] Attempting to follow @{username}...")
            followed = await self.follow_user(username)
            
            lead_id = db.add_lead(username, source="manual")
            if lead_id:
                status = "Followed" if followed else "New"
                db.update_lead_status(username, status)
                
                msg = f"Added via Browser Overlay. Followed: {followed}"
                db.log_interaction(username, "Manual Add", msg)
                
                print(f"[Manual Mode] Successfully added: {username}")
                
                ui_msg = f"Added & Followed @{username}" if followed else f"Added @{username} (Follow Failed)"
                return {"status": "success", "message": ui_msg}
                
            print(f"[Manual Mode] Failed to add (db returned None): {username}")
            return {"status": "error", "error": "Database error"}
        except Exception as e:
            print(f"[Manual Mode] Exception: {e}")
            return {"status": "error", "error": str(e)}

    # --- CRM Handlers ---
    # --- CRM Handlers Removed ---

    async def start(self, headless=False):
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            # Use None by default to use bundled Chromium (fixing VM issues). 
            # User can still override with "chrome" in config if needed.
            channel=self.config.get("browser_channel", None),  
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],

            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        
        # Expose binding for manual mode
        await self.page.expose_binding("py_add_lead", self._handle_add_lead)
        # CRM bindings removed
        # await self.page.expose_binding("py_get_saved_posts", self._handle_get_saved_posts)
        # await self.page.expose_binding("py_remove_saved_post", self._handle_remove_saved_post)
        # await self.page.expose_binding("py_update_tags", self._handle_update_tags)
        
        await self.page.goto(THREADS_URL)
        return self.page

    async def stop(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

    async def human_delay(self, min_seconds=None, max_seconds=None):
        delays = self.config.get("delays", {"min": 2, "max": 5})
        if min_seconds is None: min_seconds = delays["min"]
        if max_seconds is None: max_seconds = delays["max"]
        
        speed = self.config.get("speed_multiplier", 1.0)
        total_delay = random.uniform(min_seconds, max_seconds) / speed
        await asyncio.sleep(total_delay)

    async def inject_interface(self, stats, mode=""):
        try:
            # Simple injection to show stats
            script = f"""
            (function() {{
                let el = document.getElementById('bot-stats-tooltip');
                let contentEl = document.getElementById('bot-stats-content');
                let toastEl = document.getElementById('bot-stats-toasts');

                if (!el) {{
                    // Main Container
                    el = document.createElement('div');
                    el.id = 'bot-stats-tooltip';
                    el.style.position = 'fixed';
                    el.style.bottom = '20px';
                    el.style.left = '20px';
                    el.style.backgroundColor = 'rgba(0, 0, 0, 0.9)';
                    el.style.color = 'white';
                    el.style.padding = '15px';
                    el.style.borderRadius = '12px';
                    el.style.zIndex = '9999';
                    el.style.fontFamily = 'system-ui, -apple-system, sans-serif';
                    el.style.boxShadow = '0 4px 12px rgba(0,0,0,0.5)';
                    el.style.minWidth = '200px';
                    document.body.appendChild(el);

                    // Content Container (for stats)
                    contentEl = document.createElement('div');
                    contentEl.id = 'bot-stats-content';
                    el.appendChild(contentEl);

                    // Toast Container
                    toastEl = document.createElement('div');
                    toastEl.id = 'bot-stats-toasts';
                    toastEl.style.marginTop = '10px';
                    el.appendChild(toastEl);
                }}
                
                // Toast Notification Helper
                function showToast(msg, type='info') {{
                    let toast = document.createElement('div');
                    toast.textContent = msg;
                    toast.style.marginTop = '8px';
                    toast.style.padding = '8px';
                    toast.style.borderRadius = '6px';
                    toast.style.fontSize = '12px';
                    toast.style.backgroundColor = type === 'error' ? '#ff4444' : '#00C851';
                    toast.style.color = 'white';
                    toast.style.animation = 'fadeIn 0.3s';
                    toastEl.appendChild(toast); // Append to toast container
                    setTimeout(() => {{
                        toast.style.opacity = '0';
                        toast.style.transition = 'opacity 0.3s';
                        setTimeout(() => {{
                            if (toast.parentNode) toast.parentNode.removeChild(toast);
                        }}, 300);
                    }}, 4000);
                }}

                // Update Stats Content (Safe Clearing)
                while (contentEl.firstChild) {{
                    contentEl.removeChild(contentEl.firstChild);
                }}

                function createLine(text, isHeader=false) {{
                    const div = document.createElement('div');
                    if (isHeader) {{
                        const b = document.createElement('b');
                        b.textContent = 'Threads Companion';
                        div.textContent = '🤖 ';
                        div.appendChild(b);
                    }} else {{
                        div.textContent = text;
                    }}
                    return div;
                }}

                contentEl.appendChild(createLine('', true));
                contentEl.appendChild(createLine(`Mode: {mode}`));
                // Monitor / CRM UI Removed
                contentEl.appendChild(createLine(`Likes: {stats['likes']}`));
                contentEl.appendChild(createLine(`Follows: {stats['follows']}`));
                
                // Manual Mode Button
                if ('{mode}' === 'manual') {{
                    const btn = document.createElement('button');
                    btn.textContent = '+ Add Current Profile';
                    btn.style.marginTop = '5px';
                    btn.style.padding = '6px 12px';
                    btn.style.cursor = 'pointer';
                    btn.style.backgroundColor = '#0095f6';
                    btn.style.color = 'white';
                    btn.style.border = 'none';
                    btn.style.borderRadius = '6px';
                    btn.style.fontWeight = 'bold';
                    btn.style.width = '100%';
                    
                    btn.onclick = async function(e) {{
                        e.preventDefault();
                        const path = window.location.pathname;
                        const match = path.match(/^\\/@([^/]+)/);
                        
                        if (match && match[1]) {{
                            const username = match[1];
                            showToast('Adding @' + username + '...', 'info');
                            try {{
                                const data = await window.py_add_lead(username);
                                if(data.status === 'success') showToast('✅ ' + (data.message || 'Added'), 'success');
                                else showToast('❌ Error: ' + data.error, 'error');
                            }} catch(err) {{
                                showToast('❌ Bot Error: ' + err.message, 'error');
                            }}
                        }} else {{
                            showToast('❌ Not on a profile page', 'error');
                        }}
                    }};
                    contentEl.appendChild(btn);
                }}
                
                // Footer
                const footer = document.createElement('div');
                footer.style.marginTop = '15px';
                footer.style.fontSize = '10px';
                footer.style.textAlign = 'center';
                footer.style.opacity = '0.7';
                footer.innerHTML = 'Made with ❤️ <a href="https://BrandonDuff.com" target="_blank" style="color:white;text-decoration:none;">BrandonDuff.com</a>';
                el.appendChild(footer);

                // CRM Logic
                async function openCRM() {{
                    let modal = document.getElementById('bot-crm-modal');
                    if (!modal) {{
                        modal = document.createElement('div');
                        modal.id = 'bot-crm-modal';
                        modal.style.position = 'fixed';
                        modal.style.top = '50%';
                        modal.style.left = '50%';
                        modal.style.transform = 'translate(-50%, -50%)';
                        modal.style.backgroundColor = '#1a1a1a';
                        modal.style.color = 'white';
                        modal.style.padding = '20px';
                        modal.style.borderRadius = '12px';
                        modal.style.zIndex = '10000';
                        modal.style.width = '80%';
                        modal.style.maxWidth = '800px';
                        modal.style.maxHeight = '80%';
                        modal.style.overflowY = 'auto';
                        modal.style.boxShadow = '0 0 20px rgba(0,0,0,0.8)';
                        modal.style.border = '1px solid #333';
                        
                        const header = document.createElement('div');
                        header.style.display = 'flex';
                        header.style.justifyContent = 'space-between';
                        header.style.marginBottom = '20px';
                        header.innerHTML = '<h2 style="margin:0">Saved Posts</h2>';
                        
                        const closeBtn = document.createElement('button');
                        closeBtn.textContent = '✕';
                        closeBtn.style.background = 'transparent';
                        closeBtn.style.border = 'none';
                        closeBtn.style.color = 'white';
                        closeBtn.style.fontSize = '20px';
                        closeBtn.style.cursor = 'pointer';
                        closeBtn.onclick = () => modal.style.display = 'none';
                        header.appendChild(closeBtn);
                        modal.appendChild(header);
                        
                        const tableContainer = document.createElement('div');
                        tableContainer.id = 'crm-table-container';
                        modal.appendChild(tableContainer);
                        
                        document.body.appendChild(modal);
                    }}
                    
                    modal.style.display = 'block';
                    loadCRMData();
                }}

                async function loadCRMData() {{
                    const container = document.getElementById('crm-table-container');
                    container.innerHTML = 'Loading...';
                    
                    try {{
                        const result = await window.py_get_saved_posts();
                        if (result.status !== 'success') throw new Error(result.error);
                        
                        const posts = result.data;
                        if (!posts || posts.length === 0) {{
                            container.innerHTML = '<p>No saved posts found.</p>';
                            return;
                        }}
                        
                        let html = '<table style="width:100%; border-collapse: collapse; font-size:14px;">';
                        html += '<tr style="border-bottom: 2px solid #444; text-align:left;"><th>Date</th><th>User</th><th>Found Phrase</th><th>Tags</th><th>Action</th></tr>';
                        
                        posts.forEach(p => {{
                            // Escape quotes for onclick
                            const safeTags = (p.tags||'').replace(/'/g, "\\\\'");
                            html += `<tr style="border-bottom: 1px solid #333;">
                                <td style="padding:10px 5px;">${{new Date(p.created_at).toLocaleDateString()}}</td>
                                <td style="padding:10px 5px;">@${{p.username}}</td>
                                <td style="padding:10px 5px;">${{p.keyword_found || '-'}}</td>
                                <td style="padding:10px 5px; cursor:pointer; color:#aaa;" title="Click to edit" onclick="window.updateTags(${{p.id}}, '${{safeTags}}')">${{p.tags || '+ Add Tag'}}</td>
                                <td style="padding:10px 5px;">
                                    <a href="${{p.post_url}}" target="_blank" style="color:#0095f6; margin-right:10px; text-decoration:none;">Open</a>
                                    <button onclick="window.removePost(${{p.id}})" style="background:none; color:#ff4444; border:1px solid #ff4444; border-radius:4px; padding:2px 6px; cursor:pointer;">Del</button>
                                </td>
                            </tr>`;
                        }});
                        html += '</table>';
                        container.innerHTML = html;
                        
                    }} catch(err) {{
                        container.innerHTML = 'Error: ' + err.message;
                    }}
                }}

                // Attach helpers to window so HTML strings can call them
                window.updateTags = async (id, currentTags) => {{
                    const newTags = prompt('Enter tags:', currentTags);
                    if (newTags !== null) {{
                        await window.py_update_tags(null, id, newTags);
                        loadCRMData();
                    }}
                }};

                window.removePost = async (id) => {{
                    if (confirm('Delete this post?')) {{
                        await window.py_remove_saved_post(null, id);
                        loadCRMData();
                    }}
                }};

            }})();
            """
            await self.page.evaluate(script)
        except Exception as e:
            print(f"Interface injection failed: {e}")

    async def debug_screenshot(self, name="debug"):
        """Take a screenshot for debugging purposes"""
        try:
            import os
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"debug_{name}_{timestamp}.png"
            await self.page.screenshot(path=filename)
            print(f"[Debug] Screenshot saved: {filename}")
        except Exception as e:
            print(f"[Debug] Could not save screenshot: {e}")

    async def search_keyword(self, keyword):
        """Navigate to Threads search for a specific keyword"""
        try:
            search_url = f"https://www.threads.net/search?q={keyword}&serp_type=default"
            print(f"[Search] Navigating to: {search_url}")
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await self.human_delay(2, 3)
            
            # Try to click the "Recent" tab to show latest posts
            try:
                print(f"[Search] Looking for Recent tab...")
                # Wait for the tab to be available
                await self.page.wait_for_timeout(2000)
                
                # Try multiple selectors for the Recent tab
                recent_clicked = False
                
                # Method 1: Look for text "Recent"
                recent_tab = await self.page.query_selector('span:has-text("Recent")')
                if recent_tab:
                    # Click the parent div/button
                    await recent_tab.click()
                    print(f"[Search] Clicked Recent tab (method 1)")
                    recent_clicked = True
                    await self.human_delay(2, 3)
                
                # Method 2: Try role-based selector
                if not recent_clicked:
                    tabs = await self.page.query_selector_all('div[role="tab"]')
                    for tab in tabs:
                        text = await tab.inner_text()
                        if "recent" in text.lower():
                            await tab.click()
                            print(f"[Search] Clicked Recent tab (method 2)")
                            recent_clicked = True
                            await self.human_delay(2, 3)
                            break
                
                if not recent_clicked:
                    print(f"[Search] Recent tab not found, continuing with default view")
                    
            except Exception as e:
                print(f"[Search] Could not click Recent tab: {e}")
            
            return True
        except Exception as e:
            print(f"[Search] Error navigating to keyword '{keyword}': {e}")
            return False

    async def get_posts_on_page(self):
        """Extract post elements from the current page"""
        try:
            print(f"[Posts] Waiting for posts to load...")
            # Wait a bit for content to load
            await self.page.wait_for_timeout(3000)
            
            # Threads posts don't always use role="article", so let's try a different approach
            # Look for the main feed container and find post-like structures
            candidates = []
            
            # Try method 1: Look for divs that contain both a username link and like button
            print(f"[Posts] Trying to find posts by structure...")
            all_sections = await self.page.query_selector_all('div')
            
            # Limit to first 500 divs to ensure we scan enough content but don't hang
            # We first collect ALL potential candidates
            for section in all_sections[:500]: 
                try:
                    # Check if this div contains a username link (/@username)
                    username_link = await section.query_selector('a[href^="/@"]')
                    # Check if it contains a like button (heart SVG)
                    like_svg = await section.query_selector('svg[aria-label*="Like"], svg[aria-label*="Unlike"]')
                    
                    if username_link and like_svg:
                        candidates.append(section)
                except:
                    continue
            
            # Now filter candidates to find the "innermost" ones
            # If Candidate A contains Candidate B, then A is a wrapper and B is the actual post (or closer to it).
            # We want to keep B and discard A.
            posts = []
            if candidates:
                print(f"[Posts] Found {len(candidates)} candidates. Filtering for innermost posts...")
                
                # We can do this efficiently in the browser context
                # Pass the list of handles to the browser
                posts = await self.page.evaluate_handle('''
                    (elements) => {
                        const posts = [];
                        for (let i = 0; i < elements.length; i++) {
                            let isContainer = false;
                            for (let j = 0; j < elements.length; j++) {
                                if (i !== j && elements[i].contains(elements[j])) {
                                    isContainer = true;
                                    break;
                                }
                            }
                            if (!isContainer) {
                                posts.push(elements[i]);
                            }
                        }
                        return posts;
                    }
                ''', candidates)
                
                # Convert JSHandle back to ElementHandles
                # The result is a JSHandle pointing to an array of elements
                # We need to iterate it to get ElementHandles
                properties = await posts.get_properties()
                posts = [v.as_element() for k, v in properties.items() if v.as_element()]
                
                # Sort by position in document to ensure logical order
                # (Though get_properties usually returns in order for arrays, let's be safe if needed, 
                # but usually the order from query_selector_all is preserved in candidates and then filtered)
                
            if not posts:
                # Fallback: try the article selector
                print(f"[Posts] Trying article selector...")
                posts = await self.page.query_selector_all(SELECTORS["article"])
            
            if not posts:
                # Debug: Let's see what's on the page
                print(f"[Posts] Still no posts found. Checking page content...")
                try:
                    # Get page title
                    title = await self.page.title()
                    print(f"[Posts] Page title: {title}")
                    
                    # Check if we're logged in
                    login_button = await self.page.query_selector('text="Log in"')
                    if login_button:
                        print(f"[Posts] WARNING: Not logged in! Please log in to Threads first.")
                    
                    # Count elements
                    all_divs = await self.page.query_selector_all('div')
                    all_links = await self.page.query_selector_all('a[href^="/@"]')
                    all_svgs = await self.page.query_selector_all('svg')
                    print(f"[Posts] Total divs: {len(all_divs)}, username links: {len(all_links)}, SVGs: {len(all_svgs)}")
                    
                    # Save a screenshot for debugging
                    await self.debug_screenshot("no_posts_found")
                    
                except Exception as debug_e:
                    print(f"[Posts] Debug error: {debug_e}")
            
            # Limit to 20 posts to avoid processing too many at once
            posts = posts[:20]
            print(f"[Posts] Found {len(posts)} unique posts on page")
            return posts
        except Exception as e:
            print(f"[Posts] Error getting posts: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def extract_username_from_post(self, post_element):
        """Extract username from a post element"""
        try:
            # Try to find the username link in the post
            username_link = await post_element.query_selector('a[href^="/@"]')
            if username_link:
                href = await username_link.get_attribute('href')
                if href:
                    # Extract username from href like "/@username"
                    username = href.split('/@')[1].split('/')[0] if '/@' in href else None
                    return username
        except Exception as e:
            print(f"[Extract] Error extracting username: {e}")
        return None

    async def get_post_text(self, post_element):
        """Extract text content from a post"""
        try:
            text_element = await post_element.query_selector('div[dir="auto"]')
            if text_element:
                text = await text_element.inner_text()
                return text.lower() if text else ""
        except Exception as e:
            print(f"[Extract] Error getting post text: {e}")
        return ""

    # --- Feed Monitor Methods Removed ---

    async def like_post(self, post_element):
        """Click the like button on a post"""
        try:
            # Check if already liked first
            unlike_svg = await post_element.query_selector('svg[aria-label="Unlike"]')
            if unlike_svg:
                print(f"[Like] Post already liked, skipping")
                return False
            
            # Method 1: Try to find the Like SVG and click its parent
            like_svg = await post_element.query_selector('svg[aria-label="Like"]')
            if like_svg:
                try:
                    # Get the clickable parent (usually a div with role=button or just a div)
                    parent = await like_svg.evaluate_handle('''
                        (svg) => {
                            let el = svg;
                            // Go up the DOM tree to find a clickable element
                            for (let i = 0; i < 5; i++) {
                                el = el.parentElement;
                                if (!el) break;
                                // Check if this element looks clickable
                                const role = el.getAttribute('role');
                                const cursor = window.getComputedStyle(el).cursor;
                                if (role === 'button' || cursor === 'pointer') {
                                    return el;
                                }
                            }
                            // If no specific clickable parent found, return the immediate parent
                            return svg.parentElement;
                        }
                    ''')
                    
                    if parent:
                        await parent.as_element().click()
                        print(f"[Like] Successfully clicked like button (method 1)")
                        await self.human_delay(0.5, 1)
                        return True
                except Exception as e:
                    print(f"[Like] Method 1 failed: {e}")
            
            # Method 2: Try finding by aria-label directly on a clickable element
            like_button = await post_element.query_selector('[aria-label="Like"]')
            if like_button:
                try:
                    await like_button.click()
                    print(f"[Like] Successfully clicked like button (method 2)")
                    await self.human_delay(0.5, 1)
                    return True
                except Exception as e:
                    print(f"[Like] Method 2 failed: {e}")
            
            print(f"[Like] Could not find like button")
            return False
            
        except Exception as e:
            print(f"[Like] Error liking post: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def follow_user(self, username):
        """Navigate to a user profile and click follow"""
        try:
            profile_url = f"https://www.threads.net/@{username}"
            print(f"[Follow] Navigating to profile: {profile_url}")
            await self.page.goto(profile_url, wait_until="domcontentloaded", timeout=15000)
            await self.human_delay(2, 3)
            
            # Method 1: Try to find button with text "Follow"
            try:
                follow_button = await self.page.wait_for_selector('text="Follow"', timeout=3000)
                if follow_button:
                    # Make sure it's not "Following" button
                    button_text = await follow_button.inner_text()
                    if button_text.strip() == "Follow":
                        await follow_button.click()
                        print(f"[Follow] Successfully followed @{username} (method 1)")
                        await self.human_delay(1, 2)
                        return True
            except Exception as e:
                print(f"[Follow] Method 1 failed: {e}")
            
            # Method 2: Try to find any button containing "Follow" text
            try:
                buttons = await self.page.query_selector_all('button')
                for button in buttons:
                    text = await button.inner_text()
                    if text.strip() == "Follow":
                        await button.click()
                        print(f"[Follow] Successfully followed @{username} (method 2)")
                        await self.human_delay(1, 2)
                        return True
            except Exception as e:
                print(f"[Follow] Method 2 failed: {e}")
            
            # Method 3: Try div with role=button containing Follow
            try:
                divs = await self.page.query_selector_all('div[role="button"]')
                for div in divs:
                    text = await div.inner_text()
                    if "Follow" in text and "Following" not in text:
                        await div.click()
                        print(f"[Follow] Successfully followed @{username} (method 3)")
                        await self.human_delay(1, 2)
                        return True
            except Exception as e:
                print(f"[Follow] Method 3 failed: {e}")
            
            print(f"[Follow] Follow button not found (may already be following @{username})")
            return False
            
        except Exception as e:
            print(f"[Follow] Error following @{username}: {e}")
            import traceback
            traceback.print_exc()
            return False

    async def like_recent_posts(self, username, min_posts=2, max_posts=5):
        """Like a random number of recent posts on a user's profile"""
        try:
            # Determine how many posts to like
            num_posts_to_like = random.randint(min_posts, max_posts)
            print(f"[Engagement] Attempting to like {num_posts_to_like} recent posts from @{username}")
            
            # Wait for posts to load
            await self.human_delay(2, 3)

            # Check for Private Profile or No Posts
            is_private = await self.page.query_selector('div:has-text("This account is private")')
            if is_private:
                # Double check it's not just a comment or post text
                # Usually it's a prominent message
                print(f"[Engagement] @{username} is private. Skipping post engagement.")
                return 0

            no_posts = await self.page.query_selector('div:has-text("No posts yet")')
            if no_posts:
                 print(f"[Engagement] @{username} has no posts. Skipping.")
                 return 0
            
            liked_count = 0
            processed_posts = set() # Track processed posts to avoid duplicates
            scroll_attempts = 0
            max_scrolls = 5
            
            while liked_count < num_posts_to_like and scroll_attempts < max_scrolls:
                # Find posts on the profile
                # Use a more specific selector for posts on profile
                # Usually posts are in a feed container. 
                # We can look for divs that contain the Like/Unlike button
                
                # Get all potential post containers
                potential_posts = await self.page.query_selector_all('div:has(svg[aria-label="Like"]), div:has(svg[aria-label="Unlike"])')
                
                found_new_posts = False
                
                for post in potential_posts:
                    if liked_count >= num_posts_to_like:
                        break
                        
                    # Generate a unique ID for the post (e.g. text content snippet)
                    try:
                        text_content = await post.inner_text()
                        post_id = hash(text_content[:50]) # Simple hash of start of text
                        
                        if post_id in processed_posts:
                            continue
                            
                        processed_posts.add(post_id)
                        found_new_posts = True
                        
                        # Check if already liked
                        unlike_svg = await post.query_selector('svg[aria-label="Unlike"]')
                        if unlike_svg:
                            print(f"[Engagement] Post already liked, skipping")
                            continue
                        
                        # Try to like the post
                        # Scroll into view first
                        await post.scroll_into_view_if_needed()
                        await self.human_delay(0.5, 1)
                        
                        liked = await self.like_post(post)
                        if liked:
                            liked_count += 1
                            print(f"[Engagement] Liked post {liked_count}/{num_posts_to_like}")
                            await self.human_delay(1, 2)
                            
                    except Exception as e:
                        continue

                if liked_count >= num_posts_to_like:
                    break
                    
                # If we need more posts, scroll down
                print(f"[Engagement] Need more posts (Liked {liked_count}/{num_posts_to_like}). Scrolling...")
                await self.scroll_page()
                await self.human_delay(2, 3)
                scroll_attempts += 1
            
            print(f"[Engagement] Finished. Liked {liked_count}/{num_posts_to_like} posts on @{username}'s profile")
            return liked_count
            
        except Exception as e:
            print(f"[Engagement] Error liking posts on @{username}'s profile: {e}")
            import traceback
            traceback.print_exc()
            return 0

    async def comment_on_post(self, post_element, comment_text):
        """Add a comment to a post"""
        try:
            print(f"[Comment] Attempting to comment on post...")
            # Find the reply button
            reply_button = await post_element.query_selector('svg[aria-label="Reply"]')
            if reply_button:
                button = await reply_button.evaluate_handle('el => el.closest("div[role=\'button\']")')
                if button:
                    await button.as_element().click()
                    await self.human_delay(1, 2)
                    
                    # Wait for the comment input to appear
                    # Try multiple selectors for the input
                    try:
                        comment_input = await self.page.wait_for_selector('div[contenteditable="true"][role="textbox"]', timeout=5000)
                    except:
                        comment_input = await self.page.wait_for_selector('div[contenteditable="true"]', timeout=2000)

                    if comment_input:
                        # Click to focus
                        await comment_input.click()
                        await self.human_delay(0.5, 1)
                        
                        # Type the comment (more natural than fill)
                        await self.page.keyboard.type(comment_text, delay=50)
                        await self.human_delay(1, 2)
                        
                        # Click the Post button - Look for it specifically in the modal/dialog
                        # The modal usually has role="dialog"
                        modal = await self.page.query_selector('div[role="dialog"]')
                        if modal:
                            post_button = await modal.query_selector('div[role="button"]:has-text("Post")')
                        else:
                            # Fallback to global search if modal not found
                            post_button = await self.page.query_selector('div[role="button"]:has-text("Post")')
                            
                        if post_button:
                            await post_button.click()
                            print(f"[Comment] Successfully commented: {comment_text}")
                            await self.human_delay(2, 3)
                            return True
                        else:
                            print("[Comment] Post button not found")
                    else:
                        print("[Comment] Comment input field not found")
            else:
                print("[Comment] Reply button not found")
        except Exception as e:
            print(f"[Comment] Error commenting: {e}")
            import traceback
            traceback.print_exc()
        return False

    async def get_followers_list(self, username, max_count=50):
        """
        Navigate to user profile, open followers list, and scrape usernames.
        Returns a list of usernames.
        """
        try:
            profile_url = f"https://www.threads.net/@{username}"
            print(f"[Competitor] Navigating to @{username}")
            await self.page.goto(profile_url, wait_until="domcontentloaded", timeout=15000)
            await self.human_delay(2, 3)
            
            # Click "Followers" link/button
            # Usually it's a link with "followers" in text or href
            # Try specific selectors first
            followers_link = await self.page.query_selector('a[href$="/followers"]')
            
            if not followers_link:
                # Try finding by text but ensure it's clickable (button or link)
                followers_link = await self.page.query_selector('div[role="button"]:has-text("followers")')
                
            if not followers_link:
                # Fallback to any element with "followers" text, but try to find the clickable parent
                element = await self.page.query_selector('span:has-text("followers")')
                if element:
                    followers_link = await element.evaluate_handle('el => el.closest("a") || el.closest("div[role=\'button\']")')

            if not followers_link:
                print(f"[Competitor] Could not find followers link for @{username}")
                return []
                
            # Click and wait for dialog
            if isinstance(followers_link, dict): # Handle if it's not an element handle (shouldn't happen with query_selector)
                 await followers_link.click()
            else:
                 await followers_link.as_element().click() if hasattr(followers_link, 'as_element') else await followers_link.click()

            print(f"[Competitor] Clicked followers link, waiting for dialog...")
            await self.human_delay(2, 3)
            
            # The followers are in a modal/dialog. We need to scroll it.
            # Find the dialog
            try:
                dialog = await self.page.wait_for_selector('div[role="dialog"]', timeout=5000)
            except:
                dialog = None

            if not dialog:
                print(f"[Competitor] Followers dialog not found - Click might have failed")
                return []
                
            followers = set()
            scroll_attempts = 0
            max_scrolls = max_count // 5  # Approx 5 users per scroll
            
            while len(followers) < max_count and scroll_attempts < max_scrolls:
                # Scrape current visible followers
                # Look for links to profiles: a[href^="/@"]
                # But we need to be careful not to get the user's own profile link if it's there
                # Usually followers list items have a specific structure.
                
                # In the dialog, look for user rows
                user_links = await dialog.query_selector_all('a[href^="/@"]')
                
                for link in user_links:
                    href = await link.get_attribute('href')
                    if href:
                        u = href.replace('/@', '').replace('/', '')
                        if u != username: # Exclude the competitor themselves
                            followers.add(u)
                            
                print(f"[Competitor] Found {len(followers)} followers so far...")
                
                if len(followers) >= max_count:
                    break
                    
                # Scroll the dialog
                # We need to find the scrollable element within the dialog
                # Often it's the dialog itself or a child div
                # A simple hack is to press PageDown or ArrowDown
                await self.page.keyboard.press('PageDown')
                await self.human_delay(1, 2)
                scroll_attempts += 1
                
            return list(followers)
            
        except Exception as e:
            print(f"[Competitor] Error getting followers for @{username}: {e}")
            return []

    async def unfollow_user(self, username):
        """Navigate to profile and unfollow"""
        try:
            profile_url = f"https://www.threads.net/@{username}"
            print(f"[Task] Navigating to @{username} to unfollow")
            await self.page.goto(profile_url, wait_until="domcontentloaded")
            await self.human_delay(2, 3)
            
            # Look for "Following" button
            # It usually says "Following"
            following_button = await self.page.query_selector('div[role="button"]:has-text("Following")')
            if not following_button:
                # Try finding by text directly
                following_button = await self.page.query_selector('text="Following"')
                
            if following_button:
                await following_button.click()
                await self.human_delay(1, 2)
                
                # Confirm unfollow in popup
                # Usually a menu appears with "Unfollow"
                unfollow_confirm = await self.page.wait_for_selector('div[role="menuitem"]:has-text("Unfollow")', timeout=3000)
                if unfollow_confirm:
                    await unfollow_confirm.click()
                    print(f"[Task] Successfully unfollowed @{username}")
                    await self.human_delay(1, 2)
                    return True
            
            print(f"[Task] Could not find Following button or Unfollow option for @{username}")
            return False
        except Exception as e:
            print(f"[Task] Error unfollowing @{username}: {e}")
            return False

    async def scroll_page(self):
        """Scroll down the page to load more content"""
        try:
            await self.page.evaluate("window.scrollBy(0, window.innerHeight)")
            await self.human_delay(1, 2)
        except Exception as e:
            print(f"[Scroll] Error scrolling: {e}")
