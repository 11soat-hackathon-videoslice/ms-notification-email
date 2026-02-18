import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

"""Testes unitários para app.py - Lambda Handler para notificações por e-mail"""
import pytest
import json
from unittest.mock import patch, MagicMock

from src.app import lambda_handler, _process_notification_email
from core.dtos import NotificationDto, NotificationContentDto, EmailPayloadDto, VdscMetadataDTO
from core.enums import EmailTemplateEnum, NotificationChannelsEnum
from core.domain import VdscMetadata


@pytest.fixture
def lambda_context():
    """Mock do contexto da Lambda"""
    context = MagicMock()
    context.get_remaining_time_in_millis.return_value = 30000
    return context


@pytest.fixture
def vdsc_metadata():
    """Fixture com metadados de vídeo"""
    return {
        'videoId': 'test-video-id',
        'userId': 'test-user-id',
        'fileName': 'test_video',
        'fileExtension': 'mp4',
        'startTime': 0,
        'endTime': 10,
        'totalTime': 10,
        'unitTime': 's',
        'intervalTime': [1],
        'resize': 'medium',
        'status': 'processing',
        'retries': 0,
        'maxRetries': 3,
        'created': '2026-01-13T00:00:00Z',
        'qualityOutputLevel': 75,
        'logs': []
    }


@pytest.fixture
def valid_notification_event(vdsc_metadata):
    """Fixture com evento válido de notificação por e-mail"""
    return {
        'Records': [
            {
                'body': json.dumps({
                    'detail': {
                        'id': 'notification-123',
                        'channels': ['EMAIL'],
                        'content': [
                            {
                                'email': {
                                    'user_id': 'test-user-id',
                                    'template': 'PROCESSING'
                                },
                                'web': None
                            }
                        ],
                        'metadata': vdsc_metadata
                    }
                })
            }
        ]
    }


@pytest.fixture
def notification_without_email(vdsc_metadata):
    """Fixture com notificação sem canal de e-mail"""
    return {
        'Records': [
            {
                'body': json.dumps({
                    'detail': {
                        'id': 'notification-123',
                        'channels': ['WEB'],
                        'content': [
                            {
                                'email': None,
                                'web': {
                                    'user_id': 'test-user-id',
                                    'message': 'Test message',
                                    'timestamp': '2026-01-13T00:00:00Z'
                                }
                            }
                        ],
                        'metadata': vdsc_metadata
                    }
                })
            }
        ]
    }


@pytest.fixture
def notification_without_email_content(vdsc_metadata):
    """Fixture com notificação sem conteúdo de e-mail"""
    return {
        'Records': [
            {
                'body': json.dumps({
                    'detail': {
                        'id': 'notification-123',
                        'channels': ['EMAIL', 'WEB'],
                        'content': [
                            {
                                'email': None,
                                'web': {
                                    'user_id': 'test-user-id',
                                    'message': 'Test message',
                                    'timestamp': '2026-01-13T00:00:00Z'
                                }
                            }
                        ],
                        'metadata': vdsc_metadata
                    }
                })
            }
        ]
    }


@pytest.fixture
def multiple_records_event(vdsc_metadata):
    """Fixture com múltiplos registros de notificação"""
    return {
        'Records': [
            {
                'body': json.dumps({
                    'detail': {
                        'id': 'notification-1',
                        'channels': ['EMAIL'],
                        'content': [
                            {
                                'email': {
                                    'user_id': 'user-1',
                                    'template': 'PROCESSING'
                                },
                                'web': None
                            }
                        ],
                        'metadata': vdsc_metadata
                    }
                })
            },
            {
                'body': json.dumps({
                    'detail': {
                        'id': 'notification-2',
                        'channels': ['EMAIL'],
                        'content': [
                            {
                                'email': {
                                    'user_id': 'user-2',
                                    'template': 'FINISHED'
                                },
                                'web': None
                            }
                        ],
                        'metadata': vdsc_metadata
                    }
                })
            }
        ]
    }


@pytest.mark.unit
class TestLambdaHandler:
    """Testes para o lambda_handler principal"""

    def test_lambda_handler_success(self, valid_notification_event, lambda_context):
        """Testa handler com evento válido"""
        with patch('src.app.controller.send') as mock_send:
            response = lambda_handler(valid_notification_event, lambda_context)

            assert response['statusCode'] == 202
            body = json.loads(response['body'])
            assert body['status'] == 'Recebido 1 evento(s) para processamento.'
            assert mock_send.called

    def test_lambda_handler_multiple_records(self, multiple_records_event, lambda_context):
        """Testa handler com múltiplos registros"""
        with patch('src.app.controller.send') as mock_send:
            response = lambda_handler(multiple_records_event, lambda_context)

            assert response['statusCode'] == 202
            body = json.loads(response['body'])
            assert body['status'] == 'Recebido 2 evento(s) para processamento.'
            assert mock_send.call_count == 2

    def test_lambda_handler_empty_records(self, lambda_context):
        """Testa handler com lista de registros vazia"""
        event = {'Records': []}

        response = lambda_handler(event, lambda_context)

        assert response['statusCode'] == 202
        body = json.loads(response['body'])
        assert body['status'] == 'Recebido 0 evento(s) para processamento.'

    def test_lambda_handler_invalid_notification(self, notification_without_email, lambda_context):
        """Testa handler com notificação sem canal de e-mail"""
        with pytest.raises(ValueError, match="Notificação inválida ou sem conteúdo  de e-mail"):
            lambda_handler(notification_without_email, lambda_context)

    def test_lambda_handler_without_email_content(self, notification_without_email_content, lambda_context):
        """Testa handler com notificação sem conteúdo de e-mail"""
        with pytest.raises(ValueError, match="Notificação inválida ou sem conteúdo  de e-mail"):
            lambda_handler(notification_without_email_content, lambda_context)

    def test_lambda_handler_invalid_json(self, lambda_context):
        """Testa handler com JSON inválido no body"""
        event = {
            'Records': [
                {
                    'body': 'invalid json'
                }
            ]
        }

        with pytest.raises(json.JSONDecodeError):
            lambda_handler(event, lambda_context)

    def test_lambda_handler_missing_detail(self, lambda_context):
        """Testa handler com body sem campo 'detail'"""
        event = {
            'Records': [
                {
                    'body': json.dumps({
                        'no_detail': 'value'
                    })
                }
            ]
        }

        with pytest.raises(Exception):
            lambda_handler(event, lambda_context)

    def test_lambda_handler_processing_error(self, valid_notification_event, lambda_context):
        """Testa handler quando há erro no processamento"""
        with patch('src.app._process_notification_email', side_effect=Exception('Processing error')):
            with pytest.raises(Exception, match='Processing error'):
                lambda_handler(valid_notification_event, lambda_context)

    def test_lambda_handler_notification_dto_from_dict_error(self, lambda_context):
        """Testa handler quando NotificationDto.from_dict falha"""
        event = {
            'Records': [
                {
                    'body': json.dumps({
                        'detail': {
                            'id': 'notification-123',
                            'channels': 'invalid',  # Deve ser lista
                            'content': []
                        }
                    })
                }
            ]
        }

        with pytest.raises(Exception):
            lambda_handler(event, lambda_context)


@pytest.mark.unit
class TestProcessNotificationEmail:
    """Testes para a função _process_notification_email"""

    def _create_vdsc_metadata(self, status='processing', retries=0):
        """Helper para criar VdscMetadata para testes"""
        dto = VdscMetadataDTO(
            video_id='test-video-id',
            user_id='test-user-id',
            file_name='test_video',
            file_extension='mp4',
            start_time=0,
            end_time=10,
            total_time=10,
            unit_time='s',
            interval_time=[1],
            resize='medium',
            status=status,
            retries=retries,
            max_retries=3,
            created='2026-01-13T00:00:00Z',
            quality_output_level=75,
            logs=[]
        )
        return VdscMetadata(dto=dto)

    def test_process_notification_email_success(self):
        """Testa processamento de notificação email com sucesso"""
        email_content = EmailPayloadDto(
            user_id='test-user-id',
            template=EmailTemplateEnum.PROCESSING
        )
        content = NotificationContentDto(
            email=email_content,
            web=None
        )
        metadata = self._create_vdsc_metadata()
        notification = NotificationDto(
            id='notification-123',
            channels=[NotificationChannelsEnum.EMAIL],
            content=[content],
            metadata=metadata
        )

        with patch('src.app.controller.send') as mock_send:
            _process_notification_email(notification)

            mock_send.assert_called_once_with(notification, NotificationChannelsEnum.EMAIL)

    def test_process_notification_email_controller_error(self):
        """Testa processamento quando controller.send falha"""
        email_content = EmailPayloadDto(
            user_id='test-user-id',
            template=EmailTemplateEnum.PROCESSING
        )
        content = NotificationContentDto(
            email=email_content,
            web=None
        )
        metadata = self._create_vdsc_metadata()
        notification = NotificationDto(
            id='notification-123',
            channels=[NotificationChannelsEnum.EMAIL],
            content=[content],
            metadata=metadata
        )

        with patch('src.app.controller.send', side_effect=Exception('Controller error')):
            # A função não deve propagar a exceção, apenas logar
            _process_notification_email(notification)

    def test_process_notification_email_logs_success(self):
        """Testa se os logs de sucesso são gerados corretamente"""
        email_content = EmailPayloadDto(
            user_id='test-user-id',
            template=EmailTemplateEnum.FINISHED
        )
        content = NotificationContentDto(
            email=email_content,
            web=None
        )
        metadata = self._create_vdsc_metadata(status='finished')
        notification = NotificationDto(
            id='notification-456',
            channels=[NotificationChannelsEnum.EMAIL],
            content=[content],
            metadata=metadata
        )

        with patch('src.app.controller.send'):
            with patch('src.app.logger') as mock_logger:
                _process_notification_email(notification)

                # Verifica se o log de recebimento foi chamado
                assert mock_logger.info.call_count >= 1

                # Verifica se alguma chamada contém o ID da notificação
                call_args = [str(call) for call in mock_logger.info.call_args_list]
                assert any('notification-456' in str(arg) for arg in call_args)

    def test_process_notification_email_logs_error(self):
        """Testa se os logs de erro são gerados corretamente"""
        email_content = EmailPayloadDto(
            user_id='test-user-id',
            template=EmailTemplateEnum.FAILED
        )
        content = NotificationContentDto(
            email=email_content,
            web=None
        )
        metadata = self._create_vdsc_metadata(status='failed', retries=3)
        notification = NotificationDto(
            id='notification-789',
            channels=[NotificationChannelsEnum.EMAIL],
            content=[content],
            metadata=metadata
        )

        with patch('src.app.controller.send', side_effect=Exception('Send error')):
            with patch('src.app.logger') as mock_logger:
                _process_notification_email(notification)

                # Verifica se o log de erro foi chamado
                assert mock_logger.error.called
