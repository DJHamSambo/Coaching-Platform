from rest_framework import serializers
from django.contrib.auth.models import User
from api.models import Resource


class ResourcesSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    owner_username = serializers.CharField(source="owner.username", read_only=True)
    plan_title = serializers.CharField(source="plan.title", read_only=True, default=None)
    shared_with = serializers.SlugRelatedField(
        slug_field="username",
        queryset=User.objects.all(),
        many=True,
        required=False,
    )

    class Meta:
        model = Resource
        fields = [
            "id",
            "title",
            "description",
            "category",
            "scope",
            "plan",
            "plan_title",
            "shared_with",
            "file",
            "file_url",
            "file_name",
            "owner",
            "owner_username",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ("id", "owner", "created_at", "updated_at")
        extra_kwargs = {"file": {"write_only": True, "required": False}}

    def get_file_url(self, obj):
        if not obj.file:
            return None
        request = self.context.get("request")
        url = obj.file.url
        return request.build_absolute_uri(url) if request else url

    def get_file_name(self, obj):
        if not obj.file:
            return None
        return obj.file.name.rsplit("/", 1)[-1]
