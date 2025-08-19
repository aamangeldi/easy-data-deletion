"""Broker processing service for managing data deletion workflows."""
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ProcessingResult:
    """Result of broker processing operation."""
    success: bool
    broker_name: str
    message: str
    error_details: Optional[Dict] = None


class BrokerConfigurationError(Exception):
    """Raised when broker configuration is invalid or missing."""

    def __init__(self,
                 message: str,
                 broker_name: str = None,
                 recovery_suggestions: List[str] = None):
        super().__init__(message)
        self.broker_name = broker_name
        self.recovery_suggestions = recovery_suggestions or []


class BrokerProcessor:
    """Processes data deletion requests across multiple brokers."""

    def __init__(self, config_directory: Optional[Path] = None):
        """Initialize with optional config directory override."""
        self.config_directory = config_directory or (
            Path(__file__).parent.parent / 'broker_configs')

    def get_all_configurations(self) -> List[Dict]:
        """Load all broker configurations from directory.
        
        Returns:
            List of broker configuration dictionaries
            
        Raises:
            BrokerConfigurationError: If config directory issues found
        """
        if not self.config_directory.exists():
            raise BrokerConfigurationError(
                f"Configuration directory not found: {self.config_directory}",
                recovery_suggestions=[
                    "Create the broker_configs directory",
                    "Add at least one broker configuration JSON file"
                ])

        configs = []
        config_files = list(self.config_directory.glob('*.json'))

        if not config_files:
            raise BrokerConfigurationError(
                "No broker configuration files found",
                recovery_suggestions=[
                    "Add broker configuration JSON files to broker_configs/",
                    "Check file permissions on configuration directory"
                ])

        for config_file in config_files:
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)

                # Basic validation
                if not config.get('name'):
                    raise BrokerConfigurationError(
                        f"Configuration missing 'name' field: {config_file.name}",
                        recovery_suggestions=[
                            f"Add 'name' field to {config_file.name}",
                            "Refer to existing configurations for examples"
                        ])

                configs.append(config)

            except json.JSONDecodeError as e:
                raise BrokerConfigurationError(
                    f"Invalid JSON in {config_file.name}: {str(e)}",
                    recovery_suggestions=[
                        f"Fix JSON syntax in {config_file.name}",
                        "Use a JSON validator to check format"
                    ])
            except Exception as e:
                raise BrokerConfigurationError(
                    f"Error loading {config_file.name}: {str(e)}",
                    recovery_suggestions=[
                        f"Check file permissions for {config_file.name}",
                        "Verify file is not corrupted"
                    ])

        return configs

    def filter_configurations(
            self,
            configs: List[Dict],
            broker_filter: Optional[str] = None) -> List[Dict]:
        """Filter configurations by broker name if specified.
        
        Args:
            configs: List of all configurations
            broker_filter: Optional broker name to filter by
            
        Returns:
            Filtered list of configurations
            
        Raises:
            BrokerConfigurationError: If filtered broker not found
        """
        if not broker_filter:
            return configs

        filtered = [
            c for c in configs
            if c.get('name', '').lower() == broker_filter.lower()
        ]

        if not filtered:
            available_brokers = [c.get('name', 'Unknown') for c in configs]
            raise BrokerConfigurationError(
                f"No configuration found for broker: {broker_filter}",
                broker_name=broker_filter,
                recovery_suggestions=[
                    f"Available brokers: {', '.join(available_brokers)}",
                    f"Create configuration file for {broker_filter}",
                    "Check spelling of broker name"
                ])

        return filtered

    def is_minimal_configuration(self, config: Dict) -> bool:
        """Determine if a broker config is minimal (requires AI fallback).
        
        Args:
            config: Broker configuration dictionary
            
        Returns:
            True if config is minimal and needs AI fallback
        """
        form_config = config.get('form_config', {})
        submission = form_config.get('submission', {})

        # Minimal config if missing key submission components
        if not submission.get('method') or not submission.get('endpoint'):
            return True

        # Minimal config if missing field mappings
        if not form_config.get('field_mappings'):
            return True

        return False

    def get_processing_summary(self, successful: List[str],
                               failed: List[str]) -> Dict:
        """Generate processing summary report.
        
        Args:
            successful: List of successfully processed broker names
            failed: List of failed broker names
            
        Returns:
            Summary dictionary with statistics and recommendations
        """
        total = len(successful) + len(failed)
        success_rate = (len(successful) / total) * 100 if total > 0 else 0

        summary = {
            'total_brokers': total,
            'successful_count': len(successful),
            'failed_count': len(failed),
            'success_rate': round(success_rate, 1),
            'successful_brokers': successful,
            'failed_brokers': failed
        }

        # Add recommendations based on results
        if failed:
            summary['recommendations'] = [
                "Review error logs for failed brokers",
                "Check network connectivity and API availability",
                "Verify user data format matches broker requirements"
            ]

        return summary
