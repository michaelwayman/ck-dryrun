from typing import Any

from django.conf import settings
from rest_framework import serializers


class StrictCharField(serializers.CharField):
    """A CharField that rejects non-strings; DRF's own turns 123 into "123"."""

    def to_internal_value(self, data: Any) -> str:
        if not isinstance(data, str):
            self.fail("invalid")
        return super().to_internal_value(data)


class LoginSerializer(serializers.Serializer[None]):
    username = StrictCharField(trim_whitespace=False)
    password = StrictCharField(trim_whitespace=False, style={"input_type": "password"})


class RefreshSerializer(serializers.Serializer[None]):
    refresh = StrictCharField(trim_whitespace=False)


class TokenPairSerializer(serializers.Serializer[None]):
    access = serializers.CharField(help_text="Access JWT, see the access-token contract.")
    refresh = serializers.CharField(help_text="Opaque refresh token, valid for 24 h.")
    token_type = serializers.ChoiceField(choices=["Bearer"])
    expires_in = serializers.IntegerField(help_text="Seconds until `access` expires.")

    @staticmethod
    def pair(access: str, refresh: str) -> dict[str, Any]:
        return {
            "access": access,
            "refresh": refresh,
            "token_type": "Bearer",
            "expires_in": settings.ACCESS_TOKEN_TTL_SECONDS,
        }


class ErrorDetailSerializer(serializers.Serializer[None]):
    code = serializers.CharField()
    message = serializers.CharField()
    # The metaclass pops declared fields, so this doesn't replace Serializer.fields at runtime.
    fields = serializers.DictField(  # type: ignore[assignment]
        child=serializers.ListField(child=serializers.CharField()), allow_null=True
    )


class ErrorSerializer(serializers.Serializer[None]):
    error = ErrorDetailSerializer()
