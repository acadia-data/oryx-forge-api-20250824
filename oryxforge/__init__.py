"""OryxForge - Task management and workflow orchestration library."""

__version__ = "25.10.15"
__author__ = "OryxForge Team"
__email__ = "dev@oryxintel.com"

from .services.workflow_service import WorkflowService
from .services.io_service import IOService
from .services.project_service import ProjectService

__all__ = ["WorkflowService", "IOService", "ProjectService"]