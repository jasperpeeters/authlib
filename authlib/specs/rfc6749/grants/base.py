from ..errors import (
    InvalidRequestError,
    InvalidScopeError,
)
from ..util import scope_to_list
from ..authenticate_client import authenticate_client


class BaseGrant(object):
    AUTHORIZATION_ENDPOINT = False
    TOKEN_ENDPOINT = False
    TOKEN_HTTP_METHODS = ['POST']
    TOKEN_ENDPOINT_AUTH_METHODS = [
        'client_secret_basic',
        'client_secret_post'
    ]
    RESPONSE_TYPE = None
    GRANT_TYPE = None

    # NOTE: there is no charset for application/json, since
    # application/json should always in UTF-8.
    # The example on RFC is incorrect.
    # https://tools.ietf.org/html/rfc4627
    TOKEN_RESPONSE_HEADER = [
        ('Content-Type', 'application/json'),
        ('Cache-Control', 'no-store'),
        ('Pragma', 'no-cache'),
    ]

    def __init__(self, request, query_client, token_generator):
        self.request = request
        self.redirect_uri = request.redirect_uri
        self.scopes = scope_to_list(request.scope)
        self.query_client = query_client
        self.token_generator = token_generator
        self._clients = {}

    @classmethod
    def check_token_endpoint(cls, request):
        return request.grant_type == cls.GRANT_TYPE

    @property
    def client(self):
        return self.get_client_by_id(self.request.client_id)

    def get_client_by_id(self, client_id):
        if client_id in self._clients:
            return self._clients[client_id]
        client = self.query_client(client_id)
        self._clients[client_id] = client
        return client

    def authenticate_token_endpoint_client(self):
        """Authenticate client with the given methods for token endpoint.

        For example, the client makes the following HTTP request using TLS:

        .. code-block:: http

            POST /token HTTP/1.1
            Host: server.example.com
            Authorization: Basic czZCaGRSa3F0MzpnWDFmQmF0M2JW
            Content-Type: application/x-www-form-urlencoded

            grant_type=authorization_code&code=SplxlOBeZQQYbYS6WxSbIA
            &redirect_uri=https%3A%2F%2Fclient%2Eexample%2Ecom%2Fcb

        Default available methods are: "none", "client_secret_basic" and
        "client_secret_post".

        :param methods: token_endpoint_auth_method for client, default
            value is ["client_secret_basic", "client_secret_post"].
        :return: client
        """
        return authenticate_client(
            self.get_client_by_id,
            request=self.request,
            methods=self.TOKEN_ENDPOINT_AUTH_METHODS,
        )

    def validate_requested_scope(self, client):
        scopes = self.scopes
        if scopes and not client.check_requested_scopes(set(scopes)):
            raise InvalidScopeError(state=self.request.state)


class RedirectAuthGrant(BaseGrant):
    @classmethod
    def check_authorization_endpoint(cls, request):
        return request.response_type == cls.RESPONSE_TYPE

    def validate_authorization_redirect_uri(self, client):
        if self.redirect_uri:
            if not client.check_redirect_uri(self.redirect_uri):
                raise InvalidRequestError(
                    'Invalid "redirect_uri" in request.',
                    state=self.request.state,
                )
        else:
            redirect_uri = client.get_default_redirect_uri()
            if not redirect_uri:
                raise InvalidRequestError(
                    'Missing "redirect_uri" in request.'
                )
            self.redirect_uri = redirect_uri
