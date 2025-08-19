"""Integration tests for DataDeletionOrchestrator."""
import pytest
from unittest.mock import Mock, patch
import os

from broker_agent import DataDeletionOrchestrator


class TestDataDeletionOrchestrator:
    """Integration tests for the main orchestrator."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator instance for testing."""
        return DataDeletionOrchestrator()

    @pytest.fixture
    def sample_user_args(self):
        """Sample user arguments for testing."""
        return {
            'broker_filter': None,
            'first_name': 'John',
            'last_name': 'Doe',
            'email': 'john.doe@example.com',
            'date_of_birth': '01/01/1990',
            'address': '123 Main St',
            'city': 'Anytown',
            'state': 'CA',
            'zip_code': '12345'
        }

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    def test_run_deletion_workflow_no_api_key_error(self, orchestrator):
        """Test error when OPENAI_API_KEY is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                orchestrator.run_deletion_workflow({})

            assert "Please set OPENAI_API_KEY environment variable" in str(
                exc_info.value)

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    @patch('broker_agent.BrokerProcessor')
    def test_run_deletion_workflow_config_error(self, mock_processor_class,
                                                orchestrator,
                                                sample_user_args):
        """Test handling of configuration errors."""
        from services.broker_processor import BrokerConfigurationError

        # Mock the processor to raise configuration error
        mock_processor = Mock()
        mock_processor.get_all_configurations.side_effect = BrokerConfigurationError(
            "Test config error", recovery_suggestions=["Test suggestion"])
        orchestrator.broker_processor = mock_processor

        result = orchestrator.run_deletion_workflow(sample_user_args)

        assert 'error' in result
        assert "Test config error" in result['error']

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'test-key'})
    @patch('broker_agent.BrokerProcessor')
    def test_run_deletion_workflow_success(self, mock_processor_class,
                                           orchestrator, sample_user_args):
        """Test successful workflow execution."""
        # Mock the processor
        mock_processor = Mock()
        mock_processor.get_all_configurations.return_value = [{
            "name":
            "Test Broker",
            "type":
            "web_form"
        }]
        mock_processor.filter_configurations.return_value = [{
            "name": "Test Broker",
            "type": "web_form"
        }]
        mock_processor.is_minimal_configuration.return_value = False
        mock_processor.get_processing_summary.return_value = {
            'total_brokers': 1,
            'successful_count': 1,
            'failed_count': 0,
            'success_rate': 100.0,
            'successful_brokers': ['Test Broker'],
            'failed_brokers': []
        }

        orchestrator.broker_processor = mock_processor

        # Mock the processing method
        with patch.object(orchestrator,
                          '_process_single_broker',
                          return_value=True):
            result = orchestrator.run_deletion_workflow(sample_user_args)

        assert result['total_brokers'] == 1
        assert result['successful_count'] == 1
        assert result['success_rate'] == 100.0
