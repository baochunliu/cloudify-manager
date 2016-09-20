from flask import current_app

from .user_handler import unauthorized_user_handler


class TenantAuthorization(object):
    def authorize(self, user, request):
        authorized = True
        if not authorized:
            unauthorized_user_handler(
                'Tenant authorization error (user {0})'.format(user.username)
            )

        # TODO: actually get the tenant from the request
        current_app.config['tenant'] = 'default_tenant'

tenant_authorizer = TenantAuthorization()
