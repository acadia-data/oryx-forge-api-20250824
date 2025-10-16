"""Utility functions for services."""

import warnings
from typing import Dict
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


def get_project_data(supabase_client: Client, project_id: str, user_id: str, fields: str = "*") -> Dict:
    """
    Fetch project data from Supabase.

    Shared utility function to avoid duplicate project queries across services.

    Args:
        supabase_client: Supabase client instance
        project_id: Project UUID
        user_id: User UUID who owns the project
        fields: Comma-separated field names to select (default: "*" for all fields)

    Returns:
        Dict: Project data with requested fields

    Raises:
        ValueError: If project not found or access denied

    Examples:
        >>> client = init_supabase_client()
        >>> # Get all fields
        >>> project = get_project_data(client, project_id, user_id)
        >>> # Get specific fields
        >>> project = get_project_data(client, project_id, user_id, "id, name, name_git")
    """
    try:
        response = (
            supabase_client.table("projects")
            .select(fields)
            .eq("id", project_id)
            .eq("user_owner", user_id)
            .execute()
        )

        if not response.data:
            raise ValueError(f"Project {project_id} not found or access denied")

        return response.data[0]

    except Exception as e:
        if "not found" in str(e) or "access denied" in str(e):
            raise
        raise ValueError(f"Failed to fetch project data: {str(e)}")

