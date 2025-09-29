"""Repository Service for managing GitLab repositories and git operations."""

import os
import time
from pathlib import Path
from typing import Optional
import pygit2
import gitlab
import adtiam
from loguru import logger
from .utils import init_supabase_client


class RepoService:
    """
    Service class for GitLab repository operations and git management.
    """

    def __init__(self, project_id: str, cwd: str = '.'):
        """
        Initialize RepoService for a specific project.

        Args:
            project_id: Supabase project ID
            cwd: Current working directory (default: '.')
        """
        self.project_id = project_id
        self.cwd = Path(cwd).resolve()
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
                'namespace_id': self._get_namespace_id(),
                'import_url': f'https://gitlab-ci-token:{self._get_gitlab_token()}@gitlab.com/oryx-forge/d6tflow-template-minimal.git'
            }

            logger.debug(f"Creating GitLab project: {gitlab_project_data}")

            # Create GitLab project
            gl = self._get_gitlab_client()
            gitlab_project = gl.projects.create(gitlab_project_data)

            logger.success(f"Created GitLab project: {gitlab_project.name} (ID: {gitlab_project.id})")
            logger.debug(f"Project namespace: {gitlab_project.namespace['full_path']}")

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
            repo_name = project_data['name_git']

            # Construct repository URL with authentication
            token = self._get_gitlab_token()
            project_url = f"https://gitlab-ci-token:{token}@gitlab.com/oryx-forge/{repo_name}.git"

            # Determine target path
            if target_path:
                clone_path = Path(target_path)
            else:
                clone_path = self.cwd

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
                return str(self.cwd)
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

            git_dir = self.cwd / ".git"
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

            git_dir = self.cwd / ".git"
            repo = pygit2.Repository(str(git_dir))

            # Create a temporary file to ensure there are changes
            tmp_file = self.cwd / 'tmp.txt'
            with open(tmp_file, 'a', encoding='utf-8') as f:
                f.write(f'{time.time()}\n')

            # Add all changes
            index = repo.index
            index.add_all()
            index.write()

            # Create commit
            author = pygit2.Signature("CI Bot", "ci@oryx.dev")
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
            bool: True if valid repo exists
        """
        try:
            git_dir = self.cwd / ".git"
            if not git_dir.exists():
                return False

            repo = pygit2.Repository(str(git_dir))
            origin = repo.remotes.get("origin")

            if origin and "oryx-forge/" in origin.url:
                return True
            return False

        except pygit2.GitError:
            return False
        except Exception:
            return False

    def _repo_exists_on_gitlab(self) -> bool:
        """
        Check if repository exists on GitLab by name.

        Returns:
            bool: True if repo exists on GitLab
        """
        try:
            project_data = self._get_project_data()
            repo_name = project_data['name_git']

            gl = self._get_gitlab_client()
            namespace_id = self._get_namespace_id()

            # Search for project by name in the namespace
            projects = gl.projects.list(search=repo_name, namespace_id=namespace_id)

            # Check if exact match exists
            for project in projects:
                if project.name == repo_name:
                    return True

            return False

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
            response = self.supabase_client.table("projects").select("*").eq("id", self.project_id).execute()

            if not response.data:
                raise ValueError(f"Project {self.project_id} not found")

            self._project_data = response.data[0]

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
        Get GitLab personal access token from adtiam.

        Returns:
            str: GitLab token
        """
        try:
            adtiam.load_creds('adt-devops')
            return adtiam.creds['devops']['gitlab']['pat']
        except Exception as e:
            raise ValueError(f"Failed to load GitLab credentials: {str(e)}")

    def _get_namespace_id(self) -> int:
        """
        Get GitLab namespace ID based on environment.

        Returns:
            int: Namespace ID
        """
        cfg_env = os.getenv('CFG_ENV', 'prod')
        return 115926998 if cfg_env == 'utest' else 115926811