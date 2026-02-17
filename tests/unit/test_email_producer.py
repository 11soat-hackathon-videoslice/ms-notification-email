import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

"""Testes unitários para email_producer.py - Produtor de notificações por e-mail"""
import pytest
from unittest.mock import patch, MagicMock, mock_open
from botocore.exceptions import ClientError

from aws.email.email_producer import EmailNotificationProducer
from core.dtos import NotificationDto, NotificationContentDto, EmailPayloadDto, VdscMetadataDTO
from core.enums import EmailTemplateEnum, NotificationChannelsEnum
from core.domain import VdscMetadata


@pytest.fixture
def mock_ses_client():
    """Mock do cliente SES da AWS"""
    with patch('boto3.client') as mock_boto:
        mock_client = MagicMock()
        mock_client.send_email.return_value = {
            'ResponseMetadata': {'HTTPStatusCode': 200},
            'MessageId': 'test-message-id'
        }
        mock_boto.return_value = mock_client
        yield mock_client


@pytest.fixture
def mock_cognito_client():
    """Mock do cliente Cognito da AWS"""
    with patch('boto3.client') as mock_boto:
        mock_client = MagicMock()
        mock_client.list_users.return_value = {
            'Users': [{
                'Attributes': [
                    {'Name': 'email', 'Value': 'test@example.com'},
                    {'Name': 'name', 'Value': 'Test User'}
                ]
            }]
        }
        mock_boto.return_value = mock_client
        yield mock_client


@pytest.fixture
def vdsc_metadata():
    """Fixture com metadados de vídeo"""
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
        status='processing',
        retries=0,
        max_retries=3,
        created='2026-01-13T00:00:00Z',
        quality_output_level=75,
        logs=[]
    )
    return VdscMetadata(dto=dto)


@pytest.fixture
def notification_dto(vdsc_metadata):
    """Fixture com DTO de notificação"""
    email_content = EmailPayloadDto(
        user_id='test-user-id',
        template=EmailTemplateEnum.PROCESSING
    )
    content = NotificationContentDto(
        email=email_content,
        web=None
    )
    # NotificationDto espera VdscMetadataDTO, não VdscMetadata domain
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
        status='processing',
        retries=0,
        max_retries=3,
        created='2026-01-13T00:00:00Z',
        quality_output_level=75,
        logs=[]
    )
    return NotificationDto(
        id='notification-123',
        channels=[NotificationChannelsEnum.EMAIL],
        content=[content],
        metadata=dto
    )


@pytest.fixture
def html_template():
    """Fixture com template HTML de e-mail"""
    return """
    <!DOCTYPE html>
    <html>
    <head><title>{{title}}</title></head>
    <body>
        <h1>{{title}}</h1>
        <p>{{message}}</p>
        <p>Vídeo: {{video_name}}</p>
        <p>Status: {{status}}</p>
        <p>Data: {{date}}</p>
        <p>ID: {{notification_id}}</p>
        <img src="{{logo_url}}" alt="Logo">
        <a href="{{dashboard_url}}">Dashboard</a>
    </body>
    </html>
    """


@pytest.mark.unit
class TestEmailNotificationProducer:
    """Testes para EmailNotificationProducer"""

    def test_send_success(self, notification_dto):
        """Testa envio de e-mail com sucesso"""
        producer = EmailNotificationProducer()

        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_client.send_email.return_value = {
                'ResponseMetadata': {'HTTPStatusCode': 200},
                'MessageId': 'test-message-id'
            }
            mock_boto.return_value = mock_client

            with patch.object(producer, '_get_user_details', return_value={'email': 'test@example.com', 'name': 'Test User'}):
                with patch.object(producer, '_get_body_template', return_value='<html>Test Body</html>'):
                    with patch.object(producer, '_get_subject_template', return_value='Test Subject'):
                        producer.send(notification_dto)

                        # Verifica se o método send_email foi chamado
                        assert mock_client.send_email.called

    def test_send_error_response(self, notification_dto):
        """Testa envio de e-mail com erro na resposta do SES (HTTPStatusCode != 200)"""
        producer = EmailNotificationProducer()

        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_client.send_email.return_value = {
                'ResponseMetadata': {'HTTPStatusCode': 500}
            }
            mock_boto.return_value = mock_client

            with patch.object(producer, '_get_user_details', return_value={'email': 'test@example.com', 'name': 'Test User'}):
                with patch.object(producer, '_get_body_template', return_value='<html>Test</html>'):
                    with patch.object(producer, '_get_subject_template', return_value='Test'):
                        with pytest.raises(Exception, match="Erro ao enviar email"):
                            producer.send(notification_dto)

    def test_send_client_error(self, notification_dto):
        """Testa envio de e-mail com ClientError do boto3"""
        producer = EmailNotificationProducer()

        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_client.send_email.side_effect = ClientError(
                {'Error': {'Code': 'MessageRejected', 'Message': 'Email rejected'}},
                'SendEmail'
            )
            mock_boto.return_value = mock_client

            with patch.object(producer, '_get_user_details', return_value={'email': 'test@example.com', 'name': 'Test User'}):
                with patch.object(producer, '_get_body_template', return_value='<html>Test</html>'):
                    with patch.object(producer, '_get_subject_template', return_value='Test'):
                        with pytest.raises(ClientError):
                            producer.send(notification_dto)

    def test_get_body_template(self, vdsc_metadata, html_template):
        """Testa geração do corpo HTML do e-mail"""
        producer = EmailNotificationProducer()

        with patch.object(producer, '_get_html_template', return_value=html_template):
            with patch.object(producer, '_get_current_datetime', return_value='13/01/2026 00:00:00'):
                body = producer._get_body_template(
                    'resources/email_template.html',
                    EmailTemplateEnum.PROCESSING,
                    vdsc_metadata,
                    'notification-123',
                    'Test User'
                )

                assert 'test_video.mp4' in body
                assert 'notification-123' in body
                assert '13/01/2026 00:00:00' in body

    def test_get_html_template_success(self, html_template):
        """Testa leitura do template HTML com sucesso"""
        producer = EmailNotificationProducer()

        with patch('builtins.open', mock_open(read_data=html_template)):
            result = producer._get_html_template('resources/email_template.html')
            assert result == html_template

    def test_get_html_template_file_not_found(self):
        """Testa leitura do template HTML quando arquivo não existe"""
        producer = EmailNotificationProducer()

        with patch('builtins.open', side_effect=FileNotFoundError()):
            with pytest.raises(FileNotFoundError, match="Template HTML não encontrado no caminho"):
                producer._get_html_template('invalid_path.html')

    def test_get_html_template_generic_error(self):
        """Testa leitura do template HTML com erro genérico"""
        producer = EmailNotificationProducer()

        with patch('builtins.open', side_effect=Exception('Generic error')):
            with pytest.raises(Exception, match="Generic error"):
                producer._get_html_template('resources/email_template.html')

    def test_get_message_template_processing(self, vdsc_metadata):
        """Testa geração de mensagem para template PROCESSING"""
        producer = EmailNotificationProducer()
        message = producer._get_message_template(EmailTemplateEnum.PROCESSING, 'Test User', vdsc_metadata)

        assert 'Olá Test User!' in message
        assert 'processamento do seu vídeo foi iniciado' in message

    def test_get_message_template_retrying(self, vdsc_metadata):
        """Testa geração de mensagem para template RETRYING"""
        producer = EmailNotificationProducer()
        vdsc_metadata.retries = 1
        message = producer._get_message_template(EmailTemplateEnum.RETRYING, 'Test User', vdsc_metadata)

        assert 'Olá Test User!' in message
        assert 'novo processamento foi agendado' in message
        assert 'Tentativa 1 de 3' in message

    def test_get_message_template_failed(self, vdsc_metadata):
        """Testa geração de mensagem para template FAILED"""
        producer = EmailNotificationProducer()
        message = producer._get_message_template(EmailTemplateEnum.FAILED, 'Test User', vdsc_metadata)

        assert 'Olá Test User!' in message
        assert 'processamento do vídeo falhou' in message
        assert 'após 3 tentativas' in message

    def test_get_message_template_finished(self, vdsc_metadata):
        """Testa geração de mensagem para template FINISHED"""
        producer = EmailNotificationProducer()
        message = producer._get_message_template(EmailTemplateEnum.FINISHED, 'Test User', vdsc_metadata)

        assert 'Olá Test User!' in message
        assert 'vídeo foi processado com sucesso' in message

    def test_get_status_template_processing(self):
        """Testa geração de status para template PROCESSING"""
        producer = EmailNotificationProducer()
        status = producer._get_status_template(EmailTemplateEnum.PROCESSING)
        assert status == "PROCESSANDO ▶️"

    def test_get_status_template_retrying(self):
        """Testa geração de status para template RETRYING"""
        producer = EmailNotificationProducer()
        status = producer._get_status_template(EmailTemplateEnum.RETRYING)
        assert status == "NOVA TENTATIVA AGENDADA 🔄"

    def test_get_status_template_failed(self):
        """Testa geração de status para template FAILED"""
        producer = EmailNotificationProducer()
        status = producer._get_status_template(EmailTemplateEnum.FAILED)
        assert status == "FALHOU! ❌"

    def test_get_status_template_finished(self):
        """Testa geração de status para template FINISHED"""
        producer = EmailNotificationProducer()
        status = producer._get_status_template(EmailTemplateEnum.FINISHED)
        assert status == "CONCLUÍDO! ✅"

    def test_get_subject_template_processing(self, vdsc_metadata):
        """Testa geração de assunto para template PROCESSING"""
        producer = EmailNotificationProducer()
        subject = producer._get_subject_template(EmailTemplateEnum.PROCESSING, vdsc_metadata)

        assert '[PROCESSANDO]' in subject
        assert 'test_video.mp4' in subject

    def test_get_subject_template_retrying(self, vdsc_metadata):
        """Testa geração de assunto para template RETRYING"""
        producer = EmailNotificationProducer()
        subject = producer._get_subject_template(EmailTemplateEnum.RETRYING, vdsc_metadata)

        assert '[REPROCESSAMENTO AGENDADO]' in subject
        assert 'test_video.mp4' in subject

    def test_get_subject_template_failed(self, vdsc_metadata):
        """Testa geração de assunto para template FAILED"""
        producer = EmailNotificationProducer()
        subject = producer._get_subject_template(EmailTemplateEnum.FAILED, vdsc_metadata)

        assert '[FALHOU]' in subject
        assert 'test_video.mp4' in subject

    def test_get_subject_template_finished(self, vdsc_metadata):
        """Testa geração de assunto para template FINISHED"""
        producer = EmailNotificationProducer()
        subject = producer._get_subject_template(EmailTemplateEnum.FINISHED, vdsc_metadata)

        assert '[CONCLUÍDO]' in subject
        assert 'test_video.mp4' in subject

    def test_get_template_content_invalid(self):
        """Testa get_template_content com template inválido"""
        producer = EmailNotificationProducer()

        # Criar um enum mock inválido
        class InvalidEnum:
            value = 'INVALID'

        invalid_template = InvalidEnum()
        template_dict = {'PROCESSING': 'Test'}

        with pytest.raises(ValueError):
            producer._get_template_content(invalid_template, template_dict)

    def test_get_title_template_processing(self):
        """Testa geração de título para template PROCESSING"""
        producer = EmailNotificationProducer()
        title = producer._get_title_template(EmailTemplateEnum.PROCESSING)
        assert title == "Processamento Iniciado"

    def test_get_title_template_retrying(self):
        """Testa geração de título para template RETRYING"""
        producer = EmailNotificationProducer()
        title = producer._get_title_template(EmailTemplateEnum.RETRYING)
        assert title == "Reprocessamento Agendado"

    def test_get_title_template_failed(self):
        """Testa geração de título para template FAILED"""
        producer = EmailNotificationProducer()
        title = producer._get_title_template(EmailTemplateEnum.FAILED)
        assert title == "Processamento Falhou"

    def test_get_title_template_finished(self):
        """Testa geração de título para template FINISHED"""
        producer = EmailNotificationProducer()
        title = producer._get_title_template(EmailTemplateEnum.FINISHED)
        assert title == "Processamento Concluído"

    def test_get_user_details_success(self):
        """Testa obtenção de detalhes do usuário com sucesso"""
        producer = EmailNotificationProducer()

        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_client.list_users.return_value = {
                'Users': [{
                    'Attributes': [
                        {'Name': 'email', 'Value': 'test@example.com'},
                        {'Name': 'name', 'Value': 'Test User'}
                    ]
                }]
            }
            mock_boto.return_value = mock_client

            result = producer._get_user_details('test-user-id')

            assert result['email'] == 'test@example.com'
            assert result['name'] == 'Test User'

    def test_get_user_details_user_not_found(self):
        """Testa obtenção de detalhes quando usuário não é encontrado"""
        producer = EmailNotificationProducer()

        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_client.list_users.return_value = {'Users': []}
            mock_boto.return_value = mock_client

            with pytest.raises(ValueError, match="Usuário com id .* não encontrado"):
                producer._get_user_details('invalid-user-id')

    def test_get_user_details_invalid_email(self):
        """Testa obtenção de detalhes quando email é inválido"""
        producer = EmailNotificationProducer()

        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_client.list_users.return_value = {
                'Users': [{
                    'Attributes': [
                        {'Name': 'email', 'Value': 'invalid-email'},
                        {'Name': 'name', 'Value': 'Test User'}
                    ]
                }]
            }
            mock_boto.return_value = mock_client

            with pytest.raises(ValueError, match="Usuário com id .* não encontrado ou sem email válido"):
                producer._get_user_details('test-user-id')

    def test_get_user_details_no_name(self):
        """Testa obtenção de detalhes quando usuário não tem nome"""
        producer = EmailNotificationProducer()

        with patch('boto3.client') as mock_boto:
            mock_client = MagicMock()
            mock_client.list_users.return_value = {
                'Users': [{
                    'Attributes': [
                        {'Name': 'email', 'Value': 'test@example.com'}
                    ]
                }]
            }
            mock_boto.return_value = mock_client

            with pytest.raises(ValueError, match="Usuário com id .* não encontrado ou sem email válido"):
                producer._get_user_details('test-user-id')

    def test_get_current_datetime(self):
        """Testa formatação de data e hora atual"""
        producer = EmailNotificationProducer()
        result = producer._get_current_datetime('America/Sao_Paulo')

        # Verifica formato dd/mm/yyyy HH:MM:SS
        import re
        pattern = r'\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2}'
        assert re.match(pattern, result)

