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


def get_user_id() -> str:
    """
    Get user ID from adtiam credentials.

    Returns:
        str: User ID

    Raises:
        ValueError: If user ID cannot be loaded
    """
    try:
        import adtiam
        adtiam.load_creds('adt-db')
        return adtiam.creds['db']['user_id']
    except Exception as e:
        raise ValueError(f"Failed to get user ID from adtiam: {str(e)}")


def get_project_id() -> str:
    """
    Get project ID from adtiam credentials.

    Returns:
        str: Project ID

    Raises:
        ValueError: If project ID cannot be loaded
    """
    try:
        import adtiam
        adtiam.load_creds('adt-db')
        return adtiam.creds['db']['project_id']
    except Exception as e:
        raise ValueError(f"Failed to get project ID from adtiam: {str(e)}")