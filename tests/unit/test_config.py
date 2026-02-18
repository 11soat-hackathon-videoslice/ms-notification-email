import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

"""Testes unitários para config.py - Configurações do serviço de notificação por e-mail"""
import pytest

from aws.config.config import NotificationEmailConfig


@pytest.mark.unit
class TestNotificationEmailConfig:
    """Testes para NotificationEmailConfig"""

    def test_config_with_default_values(self):
        """Testa configuração com valores padrão"""
        config = NotificationEmailConfig()

        assert config.config['aws_cognito_user_pool_id'] is not None
        assert config.config['aws_region'] is not None
        assert config.config['ses_from_email'] is not None
        assert config.config['logo_url'] is not None
        assert config.config['dashboard_url'] is not None
        assert config.config['timezone'] is not None
        assert config.config['template_path'] is not None
        assert config.config['email_regex'] == r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    def test_email_regex_format(self):
        """Testa formato do regex de validação de e-mail"""
        config = NotificationEmailConfig()

        import re
        # Testa emails válidos
        assert re.fullmatch(config.config['email_regex'], 'test@example.com')
        assert re.fullmatch(config.config['email_regex'], 'user.name+tag@example.co.uk')

        # Testa emails inválidos
        assert not re.fullmatch(config.config['email_regex'], 'invalid-email')
        assert not re.fullmatch(config.config['email_regex'], '@example.com')
        assert not re.fullmatch(config.config['email_regex'], 'test@')
