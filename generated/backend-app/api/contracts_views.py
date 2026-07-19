from rest_framework import generics, permissions
from rest_framework.exceptions import PermissionDenied, ValidationError

from api.contracts_serializers import CoachingContractSerializer
from api.models import Coachee, CoachingContract
from api.notifications import notify


def _is_coachee_user(user) -> bool:
    return (
        Coachee.objects.filter(user=user).exists()
        or Coachee.objects.filter(user__isnull=True, name__iexact=user.username).exists()
    )


def _linked_coachee_profiles(user):
    by_user = Coachee.objects.filter(user=user)
    if by_user.exists():
        return by_user
    return Coachee.objects.filter(user__isnull=True, name__iexact=user.username)


class ContractsListView(generics.ListCreateAPIView):
    """List the signed-in user's coaching contracts (as coach or coachee,
    newest first) and create new contracts (coaches only)."""

    serializer_class = CoachingContractSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if _is_coachee_user(user):
            return CoachingContract.objects.filter(
                coachee__in=_linked_coachee_profiles(user)
            ).select_related("coach", "coachee", "coachee__user")
        return CoachingContract.objects.filter(coach=user).select_related(
            "coach", "coachee", "coachee__user"
        )

    def perform_create(self, serializer):
        user = self.request.user
        if _is_coachee_user(user):
            raise PermissionDenied("Coachees cannot create coaching contracts.")

        coachee = serializer.validated_data.get("coachee")
        if coachee is None:
            raise ValidationError({"coachee": ["Please select a coachee for this contract."]})

        data = serializer.validated_data.get("data") or {}
        if not data.get("coachSignature"):
            raise ValidationError({"data": ["Please sign the contract before saving."]})

        contract = serializer.save(coach=user, status=CoachingContract.STATUS_AWAITING_COACHEE)

        notify(
            coachee.user,
            user.username,
            "contract_awaiting_signature",
            f"{user.username} sent you a coaching contract to review and sign.",
            target_type="contract",
            target_id=contract.id,
        )


class ContractsDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CoachingContractSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if _is_coachee_user(user):
            return CoachingContract.objects.filter(
                coachee__in=_linked_coachee_profiles(user)
            ).select_related("coach", "coachee", "coachee__user")
        return CoachingContract.objects.filter(coach=user).select_related(
            "coach", "coachee", "coachee__user"
        )

    def perform_update(self, serializer):
        contract = self.get_object()
        user = self.request.user

        if contract.coach_id == user.id:
            raise PermissionDenied(
                "Coaches cannot edit a contract once it has been sent for signature."
            )
        linked_ids = set(_linked_coachee_profiles(user).values_list("id", flat=True))
        if contract.coachee_id is None or contract.coachee_id not in linked_ids:
            raise PermissionDenied("You do not have permission to update this contract.")
        if contract.status != CoachingContract.STATUS_AWAITING_COACHEE:
            raise PermissionDenied("This contract is not awaiting your signature.")

        incoming_data = serializer.validated_data.get("data")
        merged_data = {**contract.data, **(incoming_data or {})}
        accepted_terms = serializer.validated_data.get(
            "coachee_accepted_terms", contract.coachee_accepted_terms
        )

        new_status = contract.status
        if merged_data.get("coacheeSignature"):
            if not accepted_terms:
                raise ValidationError(
                    {"coachee_accepted_terms": ["Please accept the terms and conditions before signing."]}
                )
            new_status = CoachingContract.STATUS_EXECUTED

        contract = serializer.save(
            data=merged_data, coachee_accepted_terms=accepted_terms, status=new_status
        )

        if new_status == CoachingContract.STATUS_EXECUTED:
            notify(
                contract.coach,
                user.username,
                "contract_executed",
                f"{user.username} co-signed the coaching contract. It is now fully executed.",
                target_type="contract",
                target_id=contract.id,
            )

    def perform_destroy(self, instance):
        if instance.coach_id != self.request.user.id:
            raise PermissionDenied("Only the coach who created this contract can delete it.")
        instance.delete()
