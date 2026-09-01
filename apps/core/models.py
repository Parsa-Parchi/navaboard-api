from django.db import models

# Create your models here.
from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):

    def delete(self):
        return self.update(
            deleted_at=timezone.now()
        )

    def hard_delete(self):
        return super().delete()

    def alive(self):
        return self.filter(
            deleted_at__isnull=True
        )

    def dead(self):
        return self.filter(
            deleted_at__isnull=False
        )


class SoftDeleteManager(models.Manager):

    def get_queryset(self):
        return SoftDeleteQuerySet(
            self.model,
            using=self._db,
        ).filter(
            deleted_at__isnull=True
        )


class SoftDeleteModel(models.Model):
    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    objects = SoftDeleteManager()

    all_objects = models.Manager()

    class Meta:
        abstract = True

    def delete(self):
        self.deleted_at = timezone.now()
        self.save(
            update_fields=[
                "deleted_at",
            ]
        )

    def hard_delete(self):
        super().delete()

    def restore(self):
        self.deleted_at = None
        self.save(
            update_fields=[
                "deleted_at",
            ]
        )