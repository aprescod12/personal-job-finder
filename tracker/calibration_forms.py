from django import forms

from .models import MatchCalibration


class MatchCalibrationForm(forms.ModelForm):
    class Meta:
        model = MatchCalibration
        fields = ["verdict", "notes"]
        labels = {
            "verdict": "Your judgment",
            "notes": "Why do you agree or disagree?",
        }
        widgets = {
            "notes": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": (
                        "Record the strongest reasons for your judgment, including "
                        "requirements the program overvalued or missed."
                    ),
                }
            )
        }
