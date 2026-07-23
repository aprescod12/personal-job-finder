from django.db.models.signals import post_save
from django.dispatch import receiver

from candidate_profile.snapshot_models import CandidateProfileSnapshot

from .models import CareerProfile, JobPosting, JobRequirement
from .services.job_evaluations import mark_evaluations_stale


@receiver(post_save, sender=CareerProfile)
def stale_on_profile_change(sender, instance, **kwargs):
    mark_evaluations_stale(
        profile=instance,
        reason="Manual career profile changed",
    )


@receiver(post_save, sender=CandidateProfileSnapshot)
def stale_on_snapshot_activation(sender, instance, **kwargs):
    if instance.status == CandidateProfileSnapshot.Status.ACTIVE:
        mark_evaluations_stale(
            profile=instance.profile,
            reason=f"Candidate profile v{instance.version} activated",
        )


@receiver(post_save, sender=JobPosting)
def stale_on_job_change(sender, instance, **kwargs):
    mark_evaluations_stale(
        job=instance,
        reason="Job details changed",
    )


@receiver(post_save, sender=JobRequirement)
def stale_on_requirements_change(sender, instance, **kwargs):
    mark_evaluations_stale(
        job=instance.job,
        reason="Structured job requirements changed",
    )
