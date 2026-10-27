"""OpenAPI pieces for drf-spectacular (R19): the Bearer scheme and the contract's error body."""

from typing import Any

from drf_spectacular.extensions import OpenApiAuthenticationExtension
from drf_spectacular.openapi import AutoSchema
from rest_framework import serializers


class BearerTokenScheme(OpenApiAuthenticationExtension):
    target_class = "tokenauth.drf.BearerTokenAuthentication"
    name = "bearerAuth"

    def get_security_definition(self, auto_schema: AutoSchema) -> dict[str, Any]:
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "An access token from the auth service (access-token contract).",
        }


class ErrorDetailSerializer(serializers.Serializer[object]):
    code = serializers.CharField()
    message = serializers.CharField()

    def get_fields(self) -> dict[str, serializers.Field[Any, Any, Any, Any]]:
        # Added here because a `fields` attribute would shadow Serializer.fields.
        fields = super().get_fields()
        fields["fields"] = serializers.DictField(
            child=serializers.ListField(child=serializers.CharField()), allow_null=True
        )
        return fields


class ErrorSerializer(serializers.Serializer[object]):
    error = ErrorDetailSerializer()
