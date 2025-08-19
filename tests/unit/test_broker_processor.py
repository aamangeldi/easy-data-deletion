"""Tests for BrokerProcessor service."""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch

from services.broker_processor import BrokerProcessor, BrokerConfigurationError


class TestBrokerProcessor:
    """Test BrokerProcessor service."""

    def test_initialization_default_path(self):
        """Test processor initializes with default config path."""
        processor = BrokerProcessor()
        expected_path = Path(
            __file__).parent.parent.parent / 'services' / 'broker_configs'
        # Path will be relative to the services directory
        assert 'broker_configs' in str(processor.config_directory)

    def test_initialization_custom_path(self, tmp_path):
        """Test processor initializes with custom config path."""
        custom_path = tmp_path / "custom_configs"
        processor = BrokerProcessor(custom_path)
        assert processor.config_directory == custom_path

    def test_get_all_configurations_directory_not_exists(self, tmp_path):
        """Test error when config directory doesn't exist."""
        non_existent = tmp_path / "nonexistent"
        processor = BrokerProcessor(non_existent)

        with pytest.raises(BrokerConfigurationError) as exc_info:
            processor.get_all_configurations()

        assert "Configuration directory not found" in str(exc_info.value)
        assert "Create the broker_configs directory" in exc_info.value.recovery_suggestions

    def test_get_all_configurations_no_files(self, tmp_path):
        """Test error when no config files found."""
        empty_dir = tmp_path / "empty_configs"
        empty_dir.mkdir()
        processor = BrokerProcessor(empty_dir)

        with pytest.raises(BrokerConfigurationError) as exc_info:
            processor.get_all_configurations()

        assert "No broker configuration files found" in str(exc_info.value)

    def test_get_all_configurations_success(self, temp_config_dir):
        """Test successful loading of configuration files."""
        processor = BrokerProcessor(temp_config_dir)
        configs = processor.get_all_configurations()

        assert len(configs) == 2
        config_names = [config['name'] for config in configs]
        assert 'Minimal Broker' in config_names
        assert 'Full Broker' in config_names

    def test_get_all_configurations_invalid_json(self, tmp_path):
        """Test error handling for invalid JSON."""
        config_dir = tmp_path / "bad_configs"
        config_dir.mkdir()

        # Create invalid JSON file
        bad_json_file = config_dir / "bad.json"
        bad_json_file.write_text("{ invalid json }")

        processor = BrokerProcessor(config_dir)

        with pytest.raises(BrokerConfigurationError) as exc_info:
            processor.get_all_configurations()

        assert "Invalid JSON" in str(exc_info.value)
        assert "Fix JSON syntax" in exc_info.value.recovery_suggestions[0]

    def test_get_all_configurations_missing_name(self, tmp_path):
        """Test error when config missing required name field."""
        config_dir = tmp_path / "invalid_configs"
        config_dir.mkdir()

        # Config without name field
        nameless_config = {"type": "web_form", "url": "https://example.com"}
        config_file = config_dir / "nameless.json"
        config_file.write_text(json.dumps(nameless_config))

        processor = BrokerProcessor(config_dir)

        with pytest.raises(BrokerConfigurationError) as exc_info:
            processor.get_all_configurations()

        assert "Configuration missing 'name' field" in str(exc_info.value)

    def test_filter_configurations_no_filter(self):
        """Test filter returns all configs when no filter specified."""
        processor = BrokerProcessor()
        configs = [{"name": "Broker1"}, {"name": "Broker2"}]

        result = processor.filter_configurations(configs, None)
        assert result == configs

    def test_filter_configurations_found(self):
        """Test filter returns matching broker."""
        processor = BrokerProcessor()
        configs = [{"name": "Broker1"}, {"name": "Broker2"}]

        result = processor.filter_configurations(configs, "Broker1")
        assert len(result) == 1
        assert result[0]["name"] == "Broker1"

    def test_filter_configurations_not_found(self):
        """Test error when filtered broker not found."""
        processor = BrokerProcessor()
        configs = [{"name": "Broker1"}, {"name": "Broker2"}]

        with pytest.raises(BrokerConfigurationError) as exc_info:
            processor.filter_configurations(configs, "NonExistent")

        assert "No configuration found for broker: NonExistent" in str(
            exc_info.value)
        assert "Broker1, Broker2" in exc_info.value.recovery_suggestions[0]

    def test_is_minimal_configuration_true(self, minimal_broker_config):
        """Test minimal config detection returns True."""
        processor = BrokerProcessor()
        assert processor.is_minimal_configuration(
            minimal_broker_config) is True

    def test_is_minimal_configuration_false(self, full_broker_config):
        """Test full config detection returns False."""
        processor = BrokerProcessor()
        assert processor.is_minimal_configuration(full_broker_config) is False

    def test_get_processing_summary(self):
        """Test processing summary generation."""
        processor = BrokerProcessor()
        successful = ["Broker1", "Broker2"]
        failed = ["Broker3"]

        summary = processor.get_processing_summary(successful, failed)

        assert summary['total_brokers'] == 3
        assert summary['successful_count'] == 2
        assert summary['failed_count'] == 1
        assert summary['success_rate'] == 66.7
        assert summary['successful_brokers'] == successful
        assert summary['failed_brokers'] == failed
        assert 'recommendations' in summary

    def test_get_processing_summary_all_success(self):
        """Test summary when all brokers succeed."""
        processor = BrokerProcessor()
        successful = ["Broker1", "Broker2"]
        failed = []

        summary = processor.get_processing_summary(successful, failed)

        assert summary['success_rate'] == 100.0
        assert 'recommendations' not in summary
