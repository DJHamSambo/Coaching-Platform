from rest_framework import serializers


def validate_ordered_range(start_value, end_value, start_label: str, end_label: str) -> None:
    if start_value and end_value and start_value >= end_value:
        raise serializers.ValidationError(f"{start_label} must be earlier than {end_label}")
