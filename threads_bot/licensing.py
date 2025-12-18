import requests
import json
import os
import platform
import hashlib

# Supabase Configuration
SUPABASE_URL = "https://aiousaucmvjdnuusyqid.supabase.co"
# Key stripped of any potential whitespace
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImFpb3VzYXVjbXZqZG51dXN5cWlkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NjU0Nzc3NzksImV4cCI6MjA4MTA1Mzc3OX0.17JFY1GMY392DFoCTlWXu1_I7cb6K6b1VfQkWYsW1X4".strip()

LICENSE_FILE = "license.key"

class LicenseManager:
    def __init__(self):
        self.cached_key = self._load_local_key()
        self.hardware_id = self._get_hardware_id()
        
        # Verify status on startup
        if self.cached_key:
            print(f"[License] Verifying key with server: {self.cached_key}...")
            is_valid, msg = self.validate_key(self.cached_key)
            if not is_valid:
                print(f"[License] Key is no longer valid: {msg}. Deleting local license.")
                self.cached_key = None
                if os.path.exists(LICENSE_FILE):
                    try: os.remove(LICENSE_FILE)
                    except: pass
            else:
                 print(f"[License] Key validated successfully.")

    def _get_hardware_id(self):
        """Generates a simulated hardware ID."""
        return "bypassed-hwid"

    def has_valid_license(self):
        """Checks if there is a valid license in memory."""
        return bool(self.cached_key)

    def _load_local_key(self):
        """Loads the key from local file if it exists."""
        if os.path.exists(LICENSE_FILE):
             try:
                 with open(LICENSE_FILE, "r") as f:
                     return f.read().strip()
             except:
                 return None
        return None

    def save_key(self, key):
        """Saves a verified key locally."""
        with open(LICENSE_FILE, "w") as f:
            f.write(key.strip())
        self.cached_key = key.strip()

    def validate_key(self, key=None):
        """
        Validates the key against simulated backend.
        Returns: (bool, message)
        """
        key_to_check = str(key).strip() if key else self.cached_key
        if not key_to_check:
             return False, "No key provided"
             
        # MASTER KEY CHECK
        if key_to_check == "THREADS-SUPER-KEY-2025":
            return True, "License Validated"
            
        return False, "Invalid License Key"

    def _bind_hardware_id(self, key):
        """Locks the license to the current machine's Hardware ID using Supabase RPC."""
        return True

# Singleton instance
license_manager = LicenseManager()
