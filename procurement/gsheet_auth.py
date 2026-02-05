"""
Google Sheets Authentication Helper & CSV Data Loader
Supports both local file-based credentials/data and Cloud Secret Manager
"""
import os
import json
import csv
from io import StringIO
from google.oauth2.service_account import Credentials
from django.conf import settings


def get_google_sheets_credentials(scopes=None):
    """
    Get Google Sheets credentials from either:
    1. Secret Manager (for Cloud Run deployment) - reads GOOGLE_SHEETS_CREDENTIALS_JSON env var
    2. Local file (for local development) - reads settings.GOOGLE_SHEETS_CREDENTIALS_FILE
    
    Args:
        scopes: List of OAuth scopes needed
        
    Returns:
        google.oauth2.service_account.Credentials object
        
    Raises:
        ValueError: If credentials are not found in either location
    """
    if scopes is None:
        scopes = [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    
    # Try to get credentials from environment variable (Secret Manager in Cloud Run)
    creds_json = os.environ.get('GOOGLE_SHEETS_CREDENTIALS_JSON')
    
    if creds_json:
        # Running in Cloud Run with Secret Manager
        print("   [AUTH] Using Google Sheets credentials from Secret Manager")
        try:
            creds_dict = json.loads(creds_json)
            return Credentials.from_service_account_info(creds_dict, scopes=scopes)
        except json.JSONDecodeError as e:
            print(f"   [AUTH] ERROR: Failed to parse credentials JSON: {e}")
            raise ValueError(f"Invalid JSON in GOOGLE_SHEETS_CREDENTIALS_JSON: {e}")
        except Exception as e:
            print(f"   [AUTH] ERROR: Failed to create credentials from JSON: {e}")
            raise ValueError(f"Failed to create credentials from Secret Manager: {e}")
    
    # Fallback to local file (development environment)
    creds_path = getattr(settings, 'GOOGLE_SHEETS_CREDENTIALS_FILE', None)
    
    if creds_path and os.path.exists(creds_path):
        print(f"   [AUTH] Using Google Sheets credentials from file: {creds_path}")
        try:
            return Credentials.from_service_account_file(creds_path, scopes=scopes)
        except Exception as e:
            print(f"   [AUTH] ERROR: Failed to load credentials from file: {e}")
            raise ValueError(f"Failed to load credentials from {creds_path}: {e}")
    
    # Neither source available
    raise ValueError(
        "Google Sheets credentials not found. "
        "Set GOOGLE_SHEETS_CREDENTIALS_JSON environment variable (Cloud Run) or "
        "ensure GOOGLE_SHEETS_CREDENTIALS_FILE points to valid credentials file (local dev)."
    )


def get_suppliers_csv_data():
    """
    Get suppliers CSV data from either:
    1. Secret Manager (for Cloud Run deployment) - reads SUPPLIERS_CSV_DATA env var
    2. Local file (for local development) - reads settings.PREVIOUS_SUPPLIERS_CSV
    
    Returns:
        List of dictionaries representing CSV rows (normalized with lowercase keys)
    """
    # Try to get CSV content from environment variable (Secret Manager in Cloud Run)
    csv_content = os.environ.get('SUPPLIERS_CSV_DATA')
    
    if csv_content:
        # Running in Cloud Run with Secret Manager
        print("   [CSV] Loading suppliers data from Secret Manager")
        try:
            reader = csv.DictReader(StringIO(csv_content))
            rows = []
            for row in reader:
                # Normalize keys and strip values
                norm = {}
                for k, v in row.items():
                    if k is None:
                        continue
                    key = str(k).strip().lower()
                    val = (v.strip() if isinstance(v, str) else ('' if v is None else v))
                    norm[key] = val
                rows.append(norm)
            print(f"   [CSV] Loaded {len(rows)} rows from Secret Manager")
            return rows
        except Exception as e:
            print(f"   [CSV] ERROR: Failed to parse CSV from Secret Manager: {e}")
            return []
    
    # Fallback to local file (development environment)
    path = getattr(settings, 'PREVIOUS_SUPPLIERS_CSV', None)
    
    if not path:
        print("   [CSV] PREVIOUS_SUPPLIERS_CSV is not set; skipping historical suppliers.")
        return []
    
    if not os.path.exists(path):
        print(f"   [CSV] Historical suppliers CSV not found at: {path}")
        return []
    
    rows = []
    try:
        with open(path, 'rb') as f:
            raw = f.read()
        
        # Try different encodings
        text = None
        for enc in ('utf-8', 'utf-8-sig', 'latin-1', 'iso-8859-1'):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        
        if text is None:
            print(f"   [CSV] Could not decode CSV file: {path}")
            return []
        
        reader = csv.DictReader(text.splitlines())
        for row in reader:
            # Normalize keys and strip values
            norm = {}
            for k, v in row.items():
                if k is None:
                    continue
                key = str(k).strip().lower()
                val = (v.strip() if isinstance(v, str) else ('' if v is None else v))
                norm[key] = val
            rows.append(norm)
        
        print(f"   [CSV] Loaded {len(rows)} rows from file: {path}")
        return rows
        
    except Exception as e:
        print(f"   [CSV] Failed to load CSV from {path}: {e}")
        return []
