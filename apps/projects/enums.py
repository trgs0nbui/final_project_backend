from django.db import models


class ProjectRole(models.TextChoices):
    OWNER = 'owner', 'Owner'
    MEMBER = 'member', 'Member'


class ProjectType(models.TextChoices):
    SOFTWARE = 'software', 'Software'
    BUSINESS = 'business', 'Business'
    SERVICE = 'service', 'Service'


class ProjectCategory(models.TextChoices):
    WEB = 'web', 'Web Development'
    MOBILE = 'mobile', 'Mobile Development'
    DATA = 'data', 'Data & Analytics'
    DEVOPS = 'devops', 'DevOps & Infrastructure'
    MARKETING = 'marketing', 'Marketing'
    FINANCE = 'finance', 'Finance'
    HR = 'hr', 'Human Resources'
    OTHER = 'other', 'Other'
