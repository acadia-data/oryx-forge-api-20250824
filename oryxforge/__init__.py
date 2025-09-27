"""OryxForge - Task management and workflow orchestration library."""

__version__ = "0.1.0"
__author__ = "OryxForge Team"
__email__ = "team@oryxforge.dev"

from .services.workflow_service import WorkflowService

__all__ = ["WorkflowService"]