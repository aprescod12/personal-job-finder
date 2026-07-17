from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tracker", "0005_jobcalibration"),
    ]

    operations = [
        migrations.AddField(
            model_name="jobposting",
            name="deadline_status",
            field=models.CharField(
                choices=[
                    ("unknown", "Unknown"),
                    ("confirmed", "Confirmed date"),
                    ("rolling", "Rolling / open until filled"),
                    ("not_stated", "No deadline stated"),
                ],
                default="unknown",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="jobposting",
            name="listing_last_verified",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="jobposting",
            name="listing_status",
            field=models.CharField(
                choices=[
                    ("unverified", "Unverified"),
                    ("open", "Open"),
                    ("closed", "Closed by employer"),
                    ("expired", "Expired"),
                    ("link_broken", "Broken link"),
                    ("wrong_page", "Wrong company page"),
                ],
                default="unverified",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="jobposting",
            name="listing_verification_notes",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="jobcalibration",
            name="human_rating",
            field=models.CharField(
                choices=[
                    ("strong", "Strong match"),
                    ("good", "Good match"),
                    ("possible", "Possible match"),
                    ("weak", "Weak match"),
                    ("not_eligible", "Not eligible"),
                ],
                max_length=20,
            ),
        ),
    ]
