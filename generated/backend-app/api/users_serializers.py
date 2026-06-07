from rest_framework import serializers


class UsersSerializer(serializers.ModelSerializer):
    class Meta:
        model = None  # replace with your model
        fields = "__all__"
        read_only_fields = ("id", "owner", "created_at", "updated_at")
