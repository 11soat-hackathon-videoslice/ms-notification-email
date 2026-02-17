import json
import logging
from typing import Dict, Any

from core.adapters.notification.notification_controller import NotificationController
from core.dtos import NotificationDto
from core.enums import NotificationChannelsEnum

from src.aws.email.email_producer import EmailNotificationProducer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

controller = NotificationController(datasource=EmailNotificationProducer())


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Handler principal da Lambda para processamento de notificações por e-mail"""

    logger.info("=== Iniciando Lambda Handler ===")
    logger.info(f"Recebido novo evento: {json.dumps(event)}")
    records = list(event.get('Records', []))

    for record in records:
        try:
            notification_raw = json.loads(record['body'])['detail']
            notification_dto = NotificationDto.from_dict(notification_raw)

            # Validar se a notificação tem canal e conteúdo de e-mail
            has_email_channel = NotificationChannelsEnum.EMAIL in notification_dto.channels
            has_email_channel_content = any(content.email is not None for content in notification_dto.content)

            if not notification_dto or not has_email_channel or not has_email_channel_content:
                logger.error(f"Notificação inválida ou sem conteúdo de e-mail: {notification_raw}")
                raise ValueError("Notificação inválida ou sem conteúdo  de e-mail")

            _process_notification_email(notification_dto)

        except Exception as e:
            logger.error(f"Erro ao processar notificação: {e}", exc_info=True)
            raise e

    return {'statusCode': 202, 'body': json.dumps({"status": f"Recebido {len(records)} evento(s) para processamento."})}

def _process_notification_email(notification_dto: NotificationDto):

    try:
        logger.info(f"Recebendo notificação: {notification_dto}")
        controller.send(notification_dto, NotificationChannelsEnum.EMAIL)
        logger.info(f"Notificação por e-mail id: {notification_dto.id} processada com sucesso.")

    except Exception as e:
        logger.error(f"Erro ao processar Notificação web id: {notification_dto.id} - {str(e)}", exc_info=True)
