"""Repository Service for managing GitLab repositories and git operations."""

import os
import time
from pathlib import Path
from typing import Optional
import pygit2
import gitlab
import adtiam
from loguru import logger
from .utils import init_supabase_client, get_project_data
from .iam import CredentialsManager


class RepoService:
    """
    Service class for GitLab repository operations and git management.
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        user_id: Optional[str] = None,
        working_dir: Optional[str] = None
    ):
        """
        Initialize RepoService for a specific project.

        Gets user_id and project_id from CredentialsManager if not provided.

        Args:
            project_id: Project ID (if None, read from profile)
            user_id: User ID (if None, read from profile)
            working_dir: Working directory (if None, get from ProjectContext)

        Raises:
            ValueError: If project doesn't exist or profile is not configured
        """
        # Get working_dir from ProjectContext if not provided
        if working_dir is None:
            from .env_config import ProjectContext
            self.working_dir = ProjectContext.get()
        else:
            self.working_dir = working_dir

        # Convert to Path for git operations
        self.working_dir_abspath = Path(self.working_dir).resolve()

        # Get profile from CredentialsManager if not provided
        if project_id is None or user_id is None:
            creds_manager = CredentialsManager(working_dir=self.working_dir)
            profile = creds_manager.get_profile()
            self.project_id = project_id or profile['project_id']
            self.user_id = user_id or profile['user_id']
        else:
            self.project_id = project_id
            self.user_id = user_id

        # Initialize clients
        self.supabase_client = init_supabase_client()
        self._gitlab_client = None
        self._project_data = None

    def create_repo(self) -> bool:
        """
        Creates a new GitLab repository for the project if it doesn't exist.

        Returns:
            bool: True if repo was created, False if already exists

        Raises:
            ValueError: If project not found or GitLab creation fails
        """
        try:
            # Check if repository already exists on GitLab
            if self._repo_exists_on_gitlab():
                logger.info(f"Repository already exists on GitLab")
                return False

            # Get project data from Supabase
            project_data = self._get_project_data()
            repo_name = project_data['name_git']

            # Prepare GitLab project data
            gitlab_project_data = {
                'name': repo_name,
                'visibility': 'private',
                'namespace_id': self._namespace_id,
                'import_url': f'https://gitlab-ci-token:{self._get_gitlab_token()}@gitlab.com/oryx-forge/oryx-forge-template-20250923.git'
            }

            logger.debug(f"Creating GitLab project: {gitlab_project_data}")

            # Create GitLab project
            gl = self._get_gitlab_client()
            gitlab_project = gl.projects.create(gitlab_project_data)

            logger.success(f"Created GitLab project: {gitlab_project.name} (ID: {gitlab_project.id})")
            logger.debug(f"Project namespace: {gitlab_project.namespace['full_path']}")

            # Save git_path to database
            git_path = gitlab_project.path_with_namespace
            self.supabase_client.table("projects").update({
                "git_path": git_path
            }).eq("id", self.project_id).execute()
            logger.debug(f"Saved git_path to database: {git_path}")

            # Invalidate cached project data so it gets refreshed
            self._project_data = None

            return True

        except gitlab.GitlabCreateError as e:
            if "has already been taken" in str(e):
                logger.info("Repository already exists on GitLab")
                return False
            else:
                raise ValueError(f"Failed to create GitLab repository: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to create repository: {str(e)}")

    def clone(self, target_path: Optional[str] = None) -> str:
        """
        Clone the project repository to specified path.

        Args:
            target_path: Directory to clone into (default: cwd)

        Returns:
            str: Path to cloned repository

        Raises:
            ValueError: If clone operation fails or repo doesn't exist
        """
        try:
            # Get project data and construct URL
            project_data = self._get_project_data()
            git_path = project_data.get('git_path')

            if not git_path:
                raise ValueError("Project does not have a GitLab repository (git_path is empty). Create repository first.")

            # Construct repository URL with authentication using git_path
            token = self._get_gitlab_token()
            project_url = f"https://gitlab-ci-token:{token}@gitlab.com/{git_path}.git"

            # Determine target path
            if target_path:
                clone_path = Path(target_path)
            else:
                clone_path = self.working_dir_abspath

            # Ensure parent directory exists
            clone_path.parent.mkdir(parents=True, exist_ok=True)

            # Clone repository
            logger.info(f"Cloning repository to {clone_path}")
            repo = pygit2.clone_repository(project_url, str(clone_path))

            logger.success(f"Successfully cloned repository to {clone_path}")
            return str(clone_path)

        except pygit2.GitError as e:
            raise ValueError(f"Git clone operation failed: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to clone repository: {str(e)}")

    def ensure_repo(self) -> str:
        """
        Ensure repository exists locally - clone if missing, pull if exists.

        Returns:
            str: Path to repository

        Raises:
            ValueError: If repo operations fail
        """
        try:
            if self.repo_exists_locally():
                logger.info("Repository exists locally, pulling latest changes")
                self.pull()
                return str(self.working_dir_abspath)
            else:
                logger.info("Repository not found locally, cloning")
                return self.clone()

        except Exception as e:
            raise ValueError(f"Failed to ensure repository: {str(e)}")

    def pull(self) -> None:
        """
        Pull latest changes from remote repository.

        Raises:
            ValueError: If pull operation fails or no local repo
        """
        try:
            if not self.repo_exists_locally():
                raise ValueError("No local repository found. Use clone() or ensure_repo() first.")

            git_dir = self.working_dir_abspath / ".git"
            repo = pygit2.Repository(str(git_dir))

            # Get the remote and fetch
            remote = repo.remotes["origin"]
            remote.fetch()

            # Get the remote main branch reference
            try:
                remote_branch = repo.lookup_reference("refs/remotes/origin/main")
            except KeyError:
                # Try master if main doesn't exist
                remote_branch = repo.lookup_reference("refs/remotes/origin/master")

            remote_commit = repo.get(remote_branch.target)

            # Merge the remote commit into the current branch
            repo.checkout_tree(remote_commit)
            repo.head.set_target(remote_commit.id)

            logger.success("Successfully pulled latest changes")

        except pygit2.GitError as e:
            raise ValueError(f"Git pull operation failed: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to pull repository: {str(e)}")

    def push(self, message: str) -> str:
        """
        Add, commit, and push all changes to remote repository.

        Args:
            message: Commit message

        Returns:
            str: Commit hash

        Raises:
            ValueError: If push operation fails
        """
        try:
            if not self.repo_exists_locally():
                raise ValueError("No local repository found. Use clone() or ensure_repo() first.")

            git_dir = self.working_dir_abspath / ".git"
            repo = pygit2.Repository(str(git_dir))

            # Create a temporary file to ensure there are changes
            tmp_file = self.working_dir_abspath / 'tmp.txt'
            with open(tmp_file, 'a', encoding='utf-8') as f:
                f.write(f'{time.time()}\n')

            # Add all changes
            index = repo.index
            index.add_all()
            index.write()

            # Create commit
            author = pygit2.Signature("OryxForge", "dev@oryxintel.com")
            tree = index.write_tree()
            commit_id = repo.create_commit('HEAD', author, author, message, tree, [repo.head.target])

            # Push to remote
            remote = repo.remotes["origin"]
            remote.push(['refs/heads/main'])

            commit_hash = str(commit_id)
            logger.success(f"Successfully pushed commit: {commit_hash}")

            return commit_hash

        except pygit2.GitError as e:
            raise ValueError(f"Git push operation failed: {str(e)}")
        except Exception as e:
            raise ValueError(f"Failed to push repository: {str(e)}")

    def repo_exists_locally(self) -> bool:
        """
        Check if a valid oryx-forge repository exists in current directory.

        Returns:
            bool: True if valid repo exists, False if directory is not a git repo

        Raises:
            ValueError: If repo exists but is invalid (missing origin or wrong remote)
        """
        git_dir = self.working_dir_abspath / ".git"
        if not git_dir.exists():
            return False  # Not a git repo, can proceed with clone

        repo = pygit2.Repository(str(git_dir))

        # Check if origin remote exists
        if "origin" not in list(repo.remotes.names()):
            raise ValueError(
                f"Git repository exists at {self.working_dir_abspath} but has no 'origin' remote. "
                f"Available remotes: {list(repo.remotes.names())}"
            )

        origin = repo.remotes["origin"]
        if "oryx-forge/" not in origin.url:
            raise ValueError(
                f"Git repository exists but origin URL doesn't match oryx-forge pattern. "
                f"Found: {origin.url}"
            )

        return True


    def _repo_exists_on_gitlab(self) -> bool:
        """
        Check if repository exists on GitLab by checking git_path field in database.

        Returns:
            bool: True if repo exists on GitLab (git_path is populated)
        """
        try:
            project_data = self._get_project_data()
            git_path = project_data.get('git_path')

            # If git_path is populated, repo exists on GitLab
            return git_path is not None and git_path != ''

        except Exception as e:
            logger.warning(f"Failed to check GitLab repository existence: {str(e)}")
            return False

    def _get_project_data(self) -> dict:
        """
        Fetch project data from Supabase.

        Returns:
            dict: Project data including name_git

        Raises:
            ValueError: If project not found
        """
        if not self._project_data:
            self._project_data = get_project_data(
                self.supabase_client,
                self.project_id,
                self.user_id,
                fields="*"
            )

        return self._project_data

    def _get_gitlab_client(self):
        """
        Initialize GitLab client with credentials.

        Returns:
            gitlab.Gitlab: Authenticated GitLab client
        """
        if not self._gitlab_client:
            token = self._get_gitlab_token()
            self._gitlab_client = gitlab.Gitlab('https://gitlab.com', private_token=token)

        return self._gitlab_client

    def _get_gitlab_token(self) -> str:
        """
        Get GitLab personal access token from adtiam (cached).

        Returns:
            str: GitLab token
        """
        if not hasattr(self, '_gitlab_token'):
            try:
                adtiam.load_creds('adt-devops')
                self._gitlab_token = adtiam.creds['devops']['gitlab']['pat']
            except Exception as e:
                raise ValueError(f"Failed to load GitLab credentials: {str(e)}")
        return self._gitlab_token

    @property
    def _namespace_id(self) -> int:
        """
        GitLab namespace ID based on environment.

        Returns:
            int: Namespace ID
        """
        cfg_env = os.getenv('CFG_ENV', 'prod')
        return 115926998 if cfg_env == 'utest' else 115926811
        # 115926998: https://gitlab.com/oryx-forge/utest-projects
        # 115926811: https://gitlab.com/groups/oryx-forge/projects/-/edit