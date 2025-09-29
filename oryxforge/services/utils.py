"""Utility functions for services."""

import warnings
from supabase import create_client, Client

# Suppress Supabase deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="supabase")


def init_supabase_client() -> Client:
    """
    Initialize Supabase client with credentials from adtiam.

    Returns:
        Client: Configured Supabase client

    Raises:
        ValueError: If credentials cannot be loaded or client initialization fails
    """
    try:
        import adtiam
        adtiam.load_creds('adt-db')
        return create_client(adtiam.creds['db']['supabase']['url'], adtiam.creds['db']['supabase']['key-admin'])
    except Exception as e:
        raise ValueError(f"Failed to initialize Supabase client with adtiam: {str(e)}")