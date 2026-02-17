import logging
import re
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

import boto3
from botocore.exceptions import ClientError

from core.interfaces import NotificationDatasourceInterface
from core.dtos import NotificationDto, EmailPayloadDto, NotificationContentDto
from core.enums import EmailTemplateEnum
from core.domain import VdscMetadata
from aws.config import NotificationEmailConfig

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
config = NotificationEmailConfig().config

class EmailNotificationProducer(NotificationDatasourceInterface):

    def send(self, notification: 'NotificationDto') -> None:
        content = notification.content[0] if isinstance(notification.content, list) else notification.content
        ses_client = boto3.client('ses', region_name=config['aws_region'])
        try:
            user_details = self._get_user_details(content.email.user_id)
            subject = self._get_subject_template(content.email.template, notification.metadata)
            body_html = self._get_body_template(config['template_path'], content.email.template, notification.metadata,
                                                notification.id, user_details['name'])

            response = ses_client.send_email(
                Source=config['ses_from_email'],
                Destination={'ToAddresses': [user_details['email']]},
                Message={
                    'Subject': {'Data': subject},
                    'Body': {
                        'Html': {'Data': body_html}
                    }
                }
            )
            if response and response.get('ResponseMetadata', {}).get('HTTPStatusCode') != 200:
                logger.error(f"Erro ao enviar email: {response}")
                raise ClientError(f"Erro ao enviar email: {response}")
            logger.info(f"Email enviado para {user_details['email']} com subject: {subject}")
        except ClientError as e:
            logger.error(f"Erro ao enviar email: {str(e)}")
            raise e

    def _get_body_template(self, template_path: str, email_template: EmailTemplateEnum, vdsc_metadata: VdscMetadata, notification_id: str, user_name: str) -> str:
        """Gera o corpo HTML do e-mail substituindo as variáveis do template."""
        html = self._get_html_template(template_path)

        #variáveis para substituição no template
        video_name = f"{vdsc_metadata.file_name}.{vdsc_metadata.file_extension}"
        title = self._get_title_template(email_template)
        message = self._get_message_template(email_template, user_name, vdsc_metadata)
        status = self._get_status_template(email_template)
        current_date = self._get_current_datetime(config['timezone'])

        # Substitui as variáveis no template
        html = html.replace('{{title}}', title)
        html = html.replace('{{message}}', message)
        html = html.replace('{{video_name}}', video_name)
        html = html.replace('{{status}}', status)
        html = html.replace('{{date}}', current_date)
        html = html.replace('{{notification_id}}', notification_id)
        html = html.replace('{{logo_url}}', config['logo_url'])
        html = html.replace('{{dashboard_url}}',config['dashboard_url'])

        return html

    def _get_current_datetime(self, timezone_info: str) -> str:
        """Retorna a data e hora atual no formato dd/mm/yyyy HH:MM:SS."""
        timezone = ZoneInfo(timezone_info)
        now = datetime.now(timezone)
        return now.strftime('%d/%m/%Y %H:%M:%S')

    def _get_html_template(self, template_path: str) -> str:
        """Lê o template HTML do caminho especificado e retorna seu conteúdo como string."""
        base_path = Path(__file__).parent.parent.parent
        template_path = base_path / template_path
        template_path = Path(template_path)

        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Template HTML não encontrado no caminho: {template_path}")
            raise FileNotFoundError(f"Template HTML não encontrado no caminho: {template_path}")
        except Exception as e:
            logger.error(f"Erro ao ler o template HTML: {str(e)}")
            raise e

    def _get_message_template(self, email_template: EmailTemplateEnum, user_name: str, metadata: VdscMetadata) -> str:
        """Retorna a mensagem do e-mail baseado no tipo de template."""
        message_templates = {
            'template_type': 'Mensagem do Email',
            'PROCESSING': f"Olá {user_name}! O processamento do seu vídeo foi iniciado. Você receberá uma notificação quando o processo for concluído.",
            'RETRYING': f"Olá {user_name}! O processamento do vídeo falhou, mas um novo processamento foi agendado. Tentativa {metadata.retries} de {metadata.max_retries}. Você receberá uma notificação quando o processamento for reiniciado.",
            'FAILED': f"Olá {user_name}! Infelizmente o processamento do vídeo falhou mesmo após {metadata.max_retries} tentativas. Por favor, verifique os logs no dashboard para mais detalhes.",
            'FINISHED': f"Olá {user_name}! Seu vídeo foi processado com sucesso e está pronto para download. Acesse o dashboard para baixar o arquivo processado."
        }
        email_template = self._get_template_content(email_template, message_templates)
        return email_template

    def _get_status_template(self, email_template: EmailTemplateEnum) -> str:
        """Retorna o status do processamento com emoji baseado no tipo de template."""
        status_templates = {
            'template_type': 'Status da mensagem',
            'PROCESSING': "PROCESSANDO ▶️",
            'RETRYING': "NOVA TENTATIVA AGENDADA 🔄",
            'FAILED': "FALHOU! ❌",
            'FINISHED': "CONCLUÍDO! ✅"
        }
        status_template = self._get_template_content(email_template, status_templates)
        return status_template

    def _get_subject_template(self, email_template: EmailTemplateEnum, vdsc_metadata: VdscMetadata) -> str:
        video_name = f"{vdsc_metadata.file_name}.{vdsc_metadata.file_extension}"
        subject_templates = {
            'template_type': 'Assunto do Email',
            'PROCESSING': f"[PROCESSANDO] Processamento iniciado: {video_name}",
            'RETRYING': f"[REPROCESSAMENTO AGENDADO] Processamento agendado: {video_name}",
            'FAILED': f"[FALHOU] Processamento falhou: {video_name}",
            'FINISHED': f"[CONCLUÍDO] Processamento concluído: {video_name}"
        }
        subject_template = self._get_template_content(email_template, subject_templates)
        return subject_template

    def _get_template_content(self, template: EmailTemplateEnum, template_content: dict, ) -> str:
        content = template_content.get(template.value)
        if content is None:
            logger.error(f"{template.value} para template {template} não encontrado.")
            raise ValueError(f"{template.value} para template {template} não encontrado.")
        return content

    def _get_title_template(self, email_template: EmailTemplateEnum) -> str:
        """Retorna o título do e-mail baseado no tipo de template."""
        title_templates = {
            'template_type': 'Título do Email',
            'PROCESSING': "Processamento Iniciado",
            'RETRYING': "Reprocessamento Agendado",
            'FAILED': "Processamento Falhou",
            'FINISHED': "Processamento Concluído"
        }
        email_template = self._get_template_content(email_template, title_templates)
        return email_template

    def _get_user_details(self, user_id: str) -> dict:
        client = boto3.client('cognito-idp')
        filter_user_id = f'sub = "{user_id}"'

        response = client.list_users(UserPoolId=config['aws_cognito_user_pool_id'],Filter=filter_user_id,Limit=1)
        if response['Users']:
            user = response['Users'][0]
            attrs = user['Attributes']
            email = next((attr['Value'] for attr in attrs if attr['Name'] == 'email'), None)
            name = next((attr['Value'] for attr in attrs if attr['Name'] == 'name'), None)
            if re.fullmatch(config['email_regex'], email) and name:
                return {
                    'email': email,
                    'name': name
                }
        raise ValueError(f"Usuário com id {user_id} não encontrado ou sem email válido.")
