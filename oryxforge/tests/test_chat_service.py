"""Integration tests for ChatService."""

import sys
import pytest
import tempfile
from pathlib import Path
from oryxforge.services.chat_service import ChatService
from oryxforge.services.project_service import ProjectService
from oryxforge.services.cli_service import CLIService
from oryxforge.services.iam import CredentialsManager

# Fix encoding on Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')


class TestChatServiceIntegration:
    """Integration tests for ChatService covering the core workflow."""

    # Test configuration
    USER_ID = '24d811e2-1801-4208-8030-a86abbda59b8'
    PROJECT_ID = 'fd0b6b50-ed50-49db-a3ce-6c7295fb85a2'

    @pytest.fixture
    def temp_working_dir(self):
        """Create temporary working directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def setup_test_environment(self, temp_working_dir):
        """
        Setup test environment with profile, project, and test data.

        Uses test IDs and temporary working directory to avoid interfering
        with actual user configuration.
        """
        from oryxforge.services.env_config import ProjectContext

        # Set up project context BEFORE creating services (disables auto-mounting)
        ProjectContext.set(
            user_id=self.USER_ID,
            project_id=self.PROJECT_ID,
            working_dir=temp_working_dir
        )

        # Set up profile in temp directory using CredentialsManager
        creds_manager = CredentialsManager(working_dir=temp_working_dir)
        creds_manager.set_profile(user_id=self.USER_ID, project_id=self.PROJECT_ID)

        # Initialize services with temp working dir
        project_service = ProjectService(working_dir=temp_working_dir)
        chat_service = ChatService(user_id=self.USER_ID, project_id=self.PROJECT_ID)

        # Get available datasets and sheets
        datasets = project_service.ds_list()
        sheets = project_service.sheet_list()

        if not datasets or not sheets:
            pytest.skip("No datasets or sheets available for testing. Please create test data in the test project.")

        yield {
            'user_id': self.USER_ID,
            'project_id': self.PROJECT_ID,
            'chat_service': chat_service,
            'project_service': project_service,
            'datasets': datasets,
            'sheets': sheets,
            'temp_working_dir': temp_working_dir
        }

        # Cleanup
        ProjectContext.clear()

    def test_chat_service_initialization(self, setup_test_environment):
        """Test that ChatService initializes correctly."""
        env = setup_test_environment
        chat_service = env['chat_service']

        assert chat_service.user_id == env['user_id']
        assert chat_service.project_id == env['project_id']
        assert chat_service.session_id == env['project_id']
        assert chat_service.supabase_client is not None
        assert chat_service.project_service is not None

    def test_chat_history_query(self, setup_test_environment):
        """Test querying chat history from database."""
        env = setup_test_environment
        chat_service = env['chat_service']

        # Query chat history directly from database
        response = chat_service.supabase_client.table("chat_messages")\
            .select("*")\
            .eq("project_id", env['project_id'])\
            .order("created_at", desc=True)\
            .limit(5)\
            .execute()

        assert isinstance(response.data, list)
        # History may be empty on first run, that's okay

    def test_extract_target_from_result(self, setup_test_environment):
        """Test target extraction from Claude's response."""
        env = setup_test_environment
        chat_service = env['chat_service']

        # Test primary pattern: "Target: dataset.sheet"
        result_text = "Analysis complete. Target: exploration.results"
        target = chat_service._extract_target_from_result(result_text)
        assert target['dataset'] == 'exploration'
        assert target['sheet'] == 'results'

        # Test fallback pattern: "saved to dataset.sheet"
        result_text = "Data has been saved to analysis.output"
        target = chat_service._extract_target_from_result(result_text)
        assert target['dataset'] == 'analysis'
        assert target['sheet'] == 'output'

        # Test default when no pattern found
        result_text = "Some response without target information"
        target = chat_service._extract_target_from_result(result_text)
        assert target['dataset'] == 'exploration'
        assert target['sheet'] == 'unknown'

    def test_chat_workflow_end_to_end(self, setup_test_environment):
        """
        Test complete chat workflow end-to-end.

        This is the main integration test covering:
        1. Chat history retrieval
        2. Intent classification
        3. Input validation
        4. Target creation/resolution
        5. Claude agent call
        6. Message summarization
        7. Database persistence
        8. Response return
        """
        env = setup_test_environment
        chat_service = env['chat_service']

        # Get first sheet for testing
        first_sheet = env['sheets'][0]
        first_dataset = env['datasets'][0]

        # Test a simple analysis request
        message = "What are the column names in this dataset?"

        try:
            result = chat_service.chat(
                message_user=message,
                mode='explore',
                ds_active=first_dataset['id'],
                sheet_active=first_sheet['id']
            )

            # Verify result structure
            assert 'message' in result
            assert 'target_dataset' in result
            assert 'target_sheet' in result
            assert 'cost_usd' in result
            assert 'duration_ms' in result

            # Verify result values
            assert isinstance(result['message'], str)
            assert len(result['message']) > 0
            assert isinstance(result['target_dataset'], str)
            assert isinstance(result['target_sheet'], str)
            assert isinstance(result['cost_usd'], (int, float))
            assert isinstance(result['duration_ms'], (int, float))

            print(f"\n✅ Chat workflow completed successfully")
            print(f"📊 Target: {result['target_dataset']}.{result['target_sheet']}")
            print(f"💰 Cost: ${result['cost_usd']:.4f}")
            print(f"⏱️  Duration: {result['duration_ms']}ms")

        except Exception as e:
            pytest.fail(f"Chat workflow failed: {str(e)}")

    def test_cli_service_chat_method(self, setup_test_environment):
        """Test CLIService.chat() method integration."""
        env = setup_test_environment

        # Initialize CLIService with temp working directory
        cli_service = CLIService(cwd=env['temp_working_dir'])

        # Simple message
        message = "Describe this dataset"

        try:
            result = cli_service.chat(message=message)

            # Verify result
            assert 'message' in result
            assert 'target_dataset' in result
            assert 'target_sheet' in result

            print(f"\n✅ CLIService chat completed")
            print(f"📊 Target: {result['target_dataset']}.{result['target_sheet']}")

        except ValueError as e:
            # Acceptable errors for test environment
            if "No mode set" in str(e) or "No active" in str(e):
                pytest.skip(f"Expected configuration missing: {str(e)}")
            else:
                raise

    def test_chat_history_persistence(self, setup_test_environment):
        """Test that chat messages are persisted correctly."""
        env = setup_test_environment
        chat_service = env['chat_service']

        # Get history before using direct database query
        response_before = chat_service.supabase_client.table("chat_messages")\
            .select("*")\
            .eq("project_id", env['project_id'])\
            .order("created_at", desc=True)\
            .limit(10)\
            .execute()
        count_before = len(response_before.data)

        # Send a chat message (simple one to minimize cost)
        first_sheet = env['sheets'][0]
        first_dataset = env['datasets'][0]

        message = "List the columns"

        try:
            result = chat_service.chat(
                message_user=message,
                mode='explore',
                ds_active=first_dataset['id'],
                sheet_active=first_sheet['id']
            )

            # Get history after
            response_after = chat_service.supabase_client.table("chat_messages")\
                .select("*")\
                .eq("project_id", env['project_id'])\
                .order("created_at", desc=True)\
                .limit(10)\
                .execute()
            count_after = len(response_after.data)

            # Should have 2 new messages (user + agent)
            assert count_after >= count_before + 2

            # Verify latest messages
            latest_messages = response_after.data[:2]  # Get first 2 (newest)
            roles = [msg['role'] for msg in latest_messages]
            assert 'user' in roles
            assert 'agent' in roles

            print(f"\n✅ Chat history persisted correctly")
            print(f"📝 Messages before: {count_before}, after: {count_after}")

        except Exception as e:
            pytest.fail(f"Chat history persistence test failed: {str(e)}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
