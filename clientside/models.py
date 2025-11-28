from django.db import models
import uuid
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Sum



# Create your models here.
class Region(models.Model):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Province(models.Model):
    region = models.ForeignKey(Region, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Municipality(models.Model):
    province = models.ForeignKey(Province, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Barangay(models.Model):
    municipality = models.ForeignKey(Municipality, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Address(models.Model):
    region = models.ForeignKey(Region, on_delete=models.SET_NULL, null=True, blank=True)
    province = models.ForeignKey(Province, on_delete=models.SET_NULL, null=True, blank=True)
    municipality = models.ForeignKey(Municipality, on_delete=models.SET_NULL, null=True, blank=True)
    barangay = models.ForeignKey(Barangay, on_delete=models.SET_NULL, null=True, blank=True)
    house_number_street = models.CharField(max_length=255, blank=True, default='') 

    def clean(self):
        if self.province and self.province.region != self.region:
            raise ValidationError("Selected province does not belong to selected region.")

        if self.municipality and self.municipality.province != self.province:
            raise ValidationError("Selected municipality does not belong to selected province.")

        if self.barangay and self.barangay.municipality != self.municipality:
            raise ValidationError("Selected barangay does not belong to selected municipality.")


    def __str__(self):
        return f"{self.house_number_street}, {self.barangay}, {self.municipality}, {self.province}, {self.region}"


# Project Models

class Client(models.Model):
    STATUS_CHOICES = [
        ("Active", "Active"),
        ("Inactive", "Inactive"),
        ("Disabled", "Disabled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50)
    trade_name = models.CharField(max_length=50)
    contact_number = models.IntegerField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES)

    primary_address = models.OneToOneField(
        Address, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='primary_client_address'
    )

    application_date = models.DateField()
    user_client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='clients'
    )

    @property
    def numbers_count(self):
        return self.number_set.count()
    
    @property
    def total_balance(self):
        # Sum of all current_balance for all numbers of this client
        total = 0
        for number in self.number_set.all():
            total += number.current_balance
        return total

    def __str__(self):
        return f"Client of { self.user_client.name } ----- { self.name } ----- { self.trade_name }"
    

class Handler(models.Model):
    name = models.CharField(max_length=50)
    contact = models.IntegerField()
    client_handler = models.ForeignKey(Client, on_delete=models.CASCADE)

    def __str__(self):
        return f"{ self.name } ----- { self.client_handler.trade_name }"


class Operator(models.Model):
    name = models.CharField(max_length=50)


class NumberOperatorIdentifier(models.Model):
    number = models.IntegerField()
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)

    def __str__(self):
        return f"{ self.operator.name } --- { self.number }"


class Number(models.Model):

    SIM_STATUS_CHOICES = [
        ("Active", "Active"),
        ("Inactive", "Inactive"),
        ("Disabled", "Disabled"),
    ]

    COLLECTION_DAY_CHOICES = [
        ('Monday', 'Monday'),
        ('Tuesday', 'Tuesday'),
        ('Wednesday', 'Wednesday'),
        ('Thursday', 'Thursday'),
        ('Friday', 'Friday'),
        ('Saturday', 'Saturday'),
        ('Sunday', 'Sunday')
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    number = models.IntegerField(unique=True)
    sim_status = models.CharField(max_length=10, choices=SIM_STATUS_CHOICES, default="Active")
    operator = models.ForeignKey(Operator, on_delete=models.CASCADE)
    client = models.ForeignKey(Client, on_delete=models.CASCADE)
    handler = models.ForeignKey(Handler, on_delete=models.CASCADE)
    collection_day = models.CharField(max_length=10, choices=COLLECTION_DAY_CHOICES)

    @property
    def current_balance(self):
        total_invoice = self.invoices.aggregate(total=Sum('balance'))['total'] or 0
        total_payment = self.payments.aggregate(total=Sum('paid_amount'))['total'] or 0
        return total_invoice - total_payment

    def __str__(self):
        return f"{ self.number } ----- { self.operator.name } ----- { self.client.name } -----{ self.client.user_client }"



# Computational
class Invoice(models.Model):
    number = models.ForeignKey(Number, on_delete=models.CASCADE, related_name="invoices")
    time = models.DateTimeField(auto_now_add=False)
    added_load = models.DecimalField(max_digits=10, decimal_places=2)
    balance = models.DecimalField(max_digits=10, decimal_places=2)
    reference_number = models.CharField(max_length=100)

    def __str__(self):
        return f"Invoice {self.id}"


class Payment(models.Model):
    number = models.ForeignKey(Number, on_delete=models.CASCADE, related_name="payments")
    time = models.DateTimeField(auto_now_add=False)
    paid_amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"Payment {self.id}"









