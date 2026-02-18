import os

class NotificationEmailConfig:
    config = {
        'aws_cognito_user_pool_id': os.getenv('AWS_COGNITO_USER_POOL', 'us-east-1_D05wBn3u7'),
        'aws_region': os.getenv('AWS_REGION','us-east-1'),
        'email_regex': r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$',
        'ses_from_email': os.getenv('NOTIFICATION_EMAIL_FROM_EMAIL','titoparizotto@gmail.com'),
        'logo_url': os.getenv('NOTIFICATION_EMAIL_LOGO_URL','https://develop.d3do9xqqovmquq.amplifyapp.com/logo.png'),
        'dashboard_url': os.getenv('NOTIFICATION_EMAIL_DASHBOARD_URL','https://develop.d3do9xqqovmquq.amplifyapp.com'),
        'timezone': os.getenv('NOTIFICATION_EMAIL_TIMEZONE','America/Sao_Paulo'),
        'template_path': os.getenv('NOTIFICATION_EMAIL_TEMPLATE','resources/email_template.html')
    }

    def __init__(self):
        #Validação de configurações obrigatórias
        required_keys = self.config.keys()
        for key in required_keys:
            if not self.config.get(key):
                raise ValueError(f"Configuração '{key}' é obrigatória e não foi encontrada.")
