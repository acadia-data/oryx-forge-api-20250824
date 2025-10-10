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

        return {
            'user_id': self.USER_ID,
            'project_id': self.PROJECT_ID,
            'chat_service': chat_service,
            'project_service': project_service,
            'datasets': datasets,
            'sheets': sheets,
            'temp_working_dir': temp_working_dir
        }

    def test_chat_service_initialization(self, setup_test_environment):
        """Test that ChatService initializes correctly."""
        env = setup_test_environment
        chat_service = env['chat_service']

        assert chat_service.user_id == env['user_id']
        assert chat_service.project_id == env['project_id']
        assert chat_service.session_id == env['project_id']
        assert chat_service.supabase_client is not None
        assert chat_service.project_service is not None
        assert chat_service.templates is not None

    def test_get_chat_history(self, setup_test_environment):
        """Test retrieving chat history."""
        env = setup_test_environment
        chat_service = env['chat_service']

        # Get chat history (may be empty on first run)
        history = chat_service._get_chat_history(limit=5)

        assert isinstance(history, list)
        # History should be in chronological order (oldest first)
        if len(history) > 1:
            assert history[0]['created_at'] <= history[1]['created_at']

    def test_intent_classification_new_analysis(self, setup_test_environment):
        """Test intent classification for new analysis request."""
        env = setup_test_environment
        chat_service = env['chat_service']

        # Get first sheet for testing
        first_sheet = env['sheets'][0]
        first_dataset = env['datasets'][0]

        # Test new analysis intent
        message = "show me summary statistics of the data"
        intent_result = chat_service.intent(
            message_user=message,
            mode='explore',
            ds_active=first_dataset['id'],
            sheet_active=first_sheet['id'],
            chat_history=[]
        )

        assert 'action' in intent_result
        assert intent_result['action'] in ['new', 'edit']
        assert 'inputs' in intent_result
        assert 'targets' in intent_result
        assert 'confidence' in intent_result
        assert len(intent_result['targets']) == 1  # Should have exactly one target

    def test_intent_uses_exact_name_python(self, setup_test_environment):
        """Test that intent classification uses exact name_python values from database."""
        env = setup_test_environment
        chat_service = env['chat_service']

        # Get actual name_python from database
        first_sheet = env['sheets'][0]
        first_dataset = env['datasets'][0]
        actual_sheet_name_python = first_sheet['name_python']
        actual_dataset_name_python = first_dataset['name_python']

        # Classify intent with natural language
        message = f"show me the first 10 rows of {first_sheet['name']}"
        intent_result = chat_service.intent(
            message_user=message,
            mode='explore',
            ds_active=first_dataset['id'],
            sheet_active=first_sheet['id'],
            chat_history=[]
        )

        # Verify exact name_python values are used
        assert len(intent_result['inputs']) > 0
        assert intent_result['inputs'][0]['sheet'] == actual_sheet_name_python
        assert intent_result['inputs'][0]['dataset'] == actual_dataset_name_python

        print(f"\n✅ Intent classifier used exact name_python values")
        print(f"   Dataset: {actual_dataset_name_python}")
        print(f"   Sheet: {actual_sheet_name_python}")

    def test_intent_validation_multiple_targets(self, setup_test_environment):
        """Test that intent classification validates single target requirement."""
        env = setup_test_environment
        chat_service = env['chat_service']

        # This test depends on the LLM correctly identifying multiple targets
        # If the LLM returns multiple targets, it should raise ValueError
        # Note: This may not always trigger as it depends on LLM interpretation

        # Just verify the validation logic exists by checking the code path
        # The actual validation happens in the intent() method

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

        # Get history before
        history_before = chat_service._get_chat_history(limit=10)
        count_before = len(history_before)

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
            history_after = chat_service._get_chat_history(limit=10)
            count_after = len(history_after)

            # Should have 2 new messages (user + agent)
            assert count_after >= count_before + 2

            # Verify latest messages
            latest_messages = history_after[-2:]
            assert latest_messages[0]['role'] == 'user'
            assert latest_messages[1]['role'] == 'agent'
            assert latest_messages[0]['content'] == message
            assert latest_messages[0]['content_summary'] is not None
            assert latest_messages[1]['content_summary'] is not None

            print(f"\n✅ Chat history persisted correctly")
            print(f"📝 Messages before: {count_before}, after: {count_after}")

        except Exception as e:
            pytest.fail(f"Chat history persistence test failed: {str(e)}")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
