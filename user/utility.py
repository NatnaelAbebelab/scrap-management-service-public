from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.tokens import Token
from rest_framework_simplejwt.exceptions import TokenError
from datetime import datetime

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'access': str(refresh.access_token),
        'refresh': str(refresh)
    }
class TokenCheckView(APIView):
    def get(self, request):
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Bearer '):
            return Response({'detail': 'Authorization header missing or invalid'}, status=status.HTTP_401_UNAUTHORIZED)

        token_str = auth_header.split(' ')[1]

        try:
            # Skip expiration check
            token = Token(token=token_str, verify=False)

            # Get expiration info
            exp_timestamp = token['exp']
            exp_datetime = datetime.fromtimestamp(exp_timestamp)
            is_expired = datetime.utcnow() > exp_datetime

            return Response({
                'valid': True,
                'user_id': token.get('user_id'),
                'exp': exp_datetime,
                'expired': is_expired,
            })

        except TokenError as e:
            return Response({'valid': False, 'reason': str(e)}, status=status.HTTP_401_UNAUTHORIZED)
