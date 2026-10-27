from django.contrib.auth.models import AbstractUser
from django.db import models
from tokenauth import Role as RoleName

ROLE_NAMES = [name.value for name in RoleName]


class Role(models.Model):
    """A token role. The rows are data (seeded by a migration); the names come from tokenauth."""

    name = models.CharField(max_length=32, unique=True, choices=[(n, n) for n in ROLE_NAMES])

    class Meta:
        ordering = ["name"]
        constraints = [
            models.CheckConstraint(condition=models.Q(name__in=ROLE_NAMES), name="role_name_known"),
        ]

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    # Null for users created here rather than imported from WordPress.
    wp_user_id = models.PositiveBigIntegerField(null=True, blank=True, unique=True)
    display_name = models.CharField(max_length=250, blank=True)
    roles = models.ManyToManyField(Role, blank=True, related_name="users")

    def role_names(self) -> list[str]:
        """The `roles` claim: current roles, sorted, read from the database every time."""
        return sorted(self.roles.values_list("name", flat=True))
