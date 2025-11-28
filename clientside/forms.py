
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.forms.widgets import PasswordInput, TextInput
from .models import (
    Client,
    Address,
    Region,
    Province,
    Municipality,
    Barangay,
    Handler,
    Number,
    Payment,
    Invoice,
    )
from django.core.exceptions import ValidationError

class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=TextInput())
    password = forms.CharField(widget=PasswordInput())


class CreateClientForm(forms.ModelForm):
    # Extra address fields — NOT part of Client model
    region = forms.ModelChoiceField(queryset=Region.objects.all(), required=False)
    province = forms.ModelChoiceField(queryset=Province.objects.all(), required=False)
    municipality = forms.ModelChoiceField(queryset=Municipality.objects.all(), required=False)
    barangay = forms.ModelChoiceField(queryset=Barangay.objects.all(), required=False)

    house_number_street = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "House no., Street, Subdivision"
        })
    )

    # Correct application_date with HTML5 date picker
    application_date = forms.DateField(
        widget=forms.DateInput(attrs={
            "type": "date",
            "class": "form-control",
        })
    )

    class Meta:
        model = Client
        fields = [
            "name",
            "trade_name",
            "contact_number",
            "status",
            "application_date",
        ]

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        # Pre-fill address when editing
        if self.instance and self.instance.pk and self.instance.primary_address:
            addr = self.instance.primary_address
            self.fields["house_number_street"].initial = addr.house_number_street
            self.fields["region"].initial = addr.region
            self.fields["province"].initial = addr.province
            self.fields["municipality"].initial = addr.municipality
            self.fields["barangay"].initial = addr.barangay

    def clean_contact_number(self):
        cn = self.cleaned_data.get("contact_number")
        if cn and (len(str(cn)) < 7):
            raise ValidationError("Contact number looks too short.")
        return cn

    def clean(self):
        cleaned = super().clean()
        region = cleaned.get("region")
        province = cleaned.get("province")
        municipality = cleaned.get("municipality")
        barangay = cleaned.get("barangay")

        if province and region and province.region != region:
            self.add_error("province", "Selected province does not belong to selected region.")

        if municipality and province and municipality.province != province:
            self.add_error("municipality", "Selected municipality does not belong to selected province.")

        if barangay and municipality and barangay.municipality != municipality:
            self.add_error("barangay", "Selected barangay does not belong to selected municipality.")

        return cleaned
    
    def clean_name(self):
        name = self.cleaned_data.get("name", "").strip()  # remove leading/trailing spaces
        # Capitalize each word
        name = " ".join(word.capitalize() for word in name.split())
        return name

    def save(self, commit=True):
        client = super().save(commit=False)

        # Attach logged-in user
        if self.user:
            client.user_client = self.user

        # Extract address fields
        region = self.cleaned_data.get("region")
        province = self.cleaned_data.get("province")
        municipality = self.cleaned_data.get("municipality")
        barangay = self.cleaned_data.get("barangay")
        house_number_street = self.cleaned_data.get("house_number_street", "")

        # Reuse or create Address
        if self.instance and getattr(self.instance, "primary_address", None):
            address = self.instance.primary_address
            address.region = region
            address.province = province
            address.municipality = municipality
            address.barangay = barangay
            address.house_number_street = house_number_street
        else:
            address = Address(
                region=region,
                province=province,
                municipality=municipality,
                barangay=barangay,
                house_number_street=house_number_street,
            )

        if commit:
            address.save()
            client.primary_address = address
            client.save()

        return client


class HandlerForm(forms.ModelForm):
    class Meta:
        model = Handler
        fields = ["name", "contact"]


class AddNumberForm(forms.ModelForm):
    class Meta:
        model = Number
        fields = ['number', 'sim_status', 'collection_day', 'handler']

    def __init__(self, *args, **kwargs):
        client = kwargs.pop("client", None)
        super().__init__(*args, **kwargs)

        # Filter handlers belonging to this client only
        if client:
            self.fields['handler'].queryset = Handler.objects.filter(client_handler=client)


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['time', 'added_load', 'balance', 'reference_number']

    def clean(self):
        cleaned_data = super().clean()
        added_load = cleaned_data.get("added_load")
        balance = cleaned_data.get("balance")

        # Auto-sync backend
        if added_load is not None:
            cleaned_data["balance"] = added_load

        return cleaned_data


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['time', 'paid_amount']