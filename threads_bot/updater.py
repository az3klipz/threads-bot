import requests
import re
from threads_bot.version import __version__ as local_version

# Supabase Configuration
SUPABASE_URL = "https://aiousaucmvjdnuusyqid.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFpb3VzYXVjbXZqZG51dXN5cWlkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjU0Nzc3NzksImV4cCI6MjA4MTA1Mzc3OX0.17JFY1GMY392DFoCTlWXu1_I7cb6K6b1VfQkWYsW1X4".strip()

class UpdateManager:
    def check_for_update(self):
        """
        Checks Supabase for a newer version.
        Returns: (update_info_dict, error_message)
        """
        try:
            print(f"[Updater] Checking for updates via Supabase...")
            
            url = f"{SUPABASE_URL}/rest/v1/updates"
            headers = {
                "apikey": SUPABASE_KEY,
                "Authorization": f"Bearer {SUPABASE_KEY}"
            }
            params = {
                "id": "eq.latest",
                "select": "*"
            }

            resp = requests.get(url, headers=headers, params=params, timeout=10)
            
            if resp.status_code != 200:
                print(f"[Updater] Failed to fetch update info: {resp.status_code} - {resp.text}")
                return None, f"HTTP {resp.status_code}"
            
            data = resp.json()
            if not data:
                print("[Updater] No 'latest' record found in updates table.")
                return {"available": False, "local": local_version}, None

            # Parse record
            row = data[0]
            remote_version = row.get("version", "0.0.0")
            download_url = row.get("download_url", "")
            
            if not remote_version or not download_url:
                return None, "Invalid update config in database"

            print(f"[Updater] Local: {local_version}, Remote: {remote_version}")
            
            if self._is_newer(remote_version, local_version):
                return {
                    "available": True,
                    "local": local_version,
                    "remote": remote_version,
                    "download_url": download_url
                }, None
            else:
                    return {"available": False, "local": local_version}, None

        except Exception as e:
            print(f"[Updater] Error: {e}")
            return None, str(e)

    def _is_newer(self, remote, local):
        """Compare semantic version strings."""
        try:
            r_parts = [int(x) for x in remote.split('.')]
            l_parts = [int(x) for x in local.split('.')]
            return r_parts > l_parts
        except:
            # Fallback for non-standard versions
            return remote != local

update_manager = UpdateManager()
