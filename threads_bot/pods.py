import requests
from .licensing import SUPABASE_URL, SUPABASE_KEY

def fetch_available_pods():
    """
    Fetches the list of all available pods from Supabase.
    Returns: List of dicts [{'id':..., 'display_name':..., 'description':...}]
    """
    url = f"{SUPABASE_URL}/rest/v1/rpc/get_available_pods"
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers)
        if response.status_code != 200:
            print(f"[Pod] List Error: {response.text}")
            return []
        return response.json()
    except Exception as e:
        print(f"[Pod] List Exception: {e}")
        return []

def fetch_cloud_pod(pod_id="default"):
    """
    Fetches the list of active pod members for a SPECIFIC pod.
    Returns: List of usernames (strings).
    """
    url = f"{SUPABASE_URL}/rest/v1/rpc/get_pod_members"
    
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "pod_id_param": pod_id
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code != 200:
            print(f"[Pod] Sync Error: {response.text}")
            return None

        # RPC returns SETOF text -> ["user1", "user2"]
        data = response.json()
        return data

    except Exception as e:
        print(f"[Pod] Sync Exception: {e}")
        return None
