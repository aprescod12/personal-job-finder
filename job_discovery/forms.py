from django import forms

from .services import approved_provider_choices


class DiscoveryRunForm(forms.Form):
    provider_key = forms.ChoiceField(
        label="Approved provider",
        choices=(),
        help_text=(
            "Only providers registered in the controlled discovery service can run."
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["provider_key"].choices = approved_provider_choices()


class DiscoveryDecisionForm(forms.Form):
    notes = forms.CharField(
        required=False,
        max_length=1000,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Decision notes",
    )
