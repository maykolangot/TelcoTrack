from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate
from django.contrib.auth.models import auth
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.utils import OperationalError
from django.db import connection

from .models import (
    Region,
    Province,
    Municipality,
    Barangay,
    Client,
    Handler,
    NumberOperatorIdentifier,
    Operator,
    Number,
    Payment,
    Invoice,
)

from .forms import (
    LoginForm,
    CreateClientForm,
    HandlerForm,
    AddNumberForm,
    InvoiceForm,
    PaymentForm,
    )
# Create your views here.





def index(request):
    # Default assumption
    db_connected = True
    
    try:
        # Attempt a simple operation to verify the connection is active
        # 'connection.ensure_connection()' attempts to make a new connection if none exists.
        connection.ensure_connection()
    except OperationalError:
        # This exception fires if the database server can't be reached
        db_connected = False

    # Pass the connection status to the template context
    context = {
        'db_connected': db_connected
    }
    
    return render(request, "index.html", context)
def my_login(request):
    form = LoginForm()

    if request.method == "POST":

        form = LoginForm(request, data=request.POST)
        if form.is_valid():

            username = request.POST.get('username')
            password = request.POST.get('password')
            user = authenticate(request, username=username, password=password)

            if user is not None:
                auth.login(request, user)
                messages.success(request, "You Have logged in successfully")

                return redirect("dashboard")
    
    context = {'form':form}

    return render(request, 'login.html', context=context)


@login_required(login_url='my-login')
def dashboard(request):
    return render(request, 'client/dashboard.html')


def user_logout(request):
    auth.logout(request)
    messages.success(request, "User logout successfull!!y")

    return redirect('login')


def load_provinces(request):
    region_id = request.GET.get("region")
    provinces = Province.objects.filter(region_id=region_id).order_by("-id")
    return render(request, "client/partials/province_dropdown.html", {
        "provinces": provinces
    })


def load_municipalities(request):
    province_id = request.GET.get("province")
    municipalities = Municipality.objects.filter(province_id=province_id).order_by('-id')
    return render(request, "client/partials/municipality_dropdown.html", {
        "municipalities": municipalities
    })


def load_barangays(request):
    municipality_id = request.GET.get("municipality")
    barangays = Barangay.objects.filter(municipality_id=municipality_id).order_by('name')
    return render(request, "client/partials/barangay_dropdown.html", {
        "barangays": barangays
    })


@login_required
def create_client(request):
    form = CreateClientForm(request.POST or None, user=request.user)
    regions = Region.objects.all().order_by('-id')


    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "A client is created successfully!!")

        return redirect("clients")

    return render(request, "client/create_client.html", {
        "form": form,
        "regions": regions,
    })


#list all Client
def search_clients(request):
    query = request.GET.get("search", "")

    clients = Client.objects.filter(
        user_client=request.user,
        name__icontains=query
    ).order_by("name")

    return render(request, "client/partials/client_list.html", {
        "clients": clients
    })


def list_client(request):
    # show all clients by default
    clients = Client.objects.filter(
        user_client=request.user
    ).order_by("name")

    return render(request, "client/list-client.html", {
        "clients": clients
    })


def client_detail(request, client_id):
    client = Client.objects.get(id=client_id, user_client=request.user)
    handlers = Handler.objects.filter(client_handler=client)
    numbers = Number.objects.filter(client=client).select_related("operator")
    operators = Operator.objects.all()


    return render(request, "client/client-detail.html", {
        "client": client,
        "handlers": handlers,
        "numbers": numbers,
        "operators": operators,
    })


def add_handler(request, client_id):
    client = get_object_or_404(Client, id=client_id)

    if request.method == "POST":
        form = HandlerForm(request.POST)
        if form.is_valid():
            handler = form.save(commit=False)
            handler.client_handler = client
            handler.save()
            messages.success(request, "A client's handler is created successfully!!")

            return redirect("client-detail", client_id=client.id)
    else:
        form = HandlerForm()

    return render(request, "client/handlers/add_handler.html", {
        "form": form,
        "client": client
    })


def edit_handler(request, client_id, handler_id):
    client = Client.objects.get(id=client_id, user_client=request.user)
    handler = Handler.objects.get(id=handler_id, client_handler=client)

    if request.method == "POST":
        form = HandlerForm(request.POST, instance=handler)
        if form.is_valid():
            form.save()
            return redirect("client-detail", client_id=client.id)
    else:
        form = HandlerForm(instance=handler)

    return render(request, "client/handlers/edit_handler.html", {
        "form": form,
        "client": client,
        "handler": handler
    })


def list_handler(request, client_id):
    client = Client.objects.get(id=client_id, user_client=request.user)
    handlers = Handler.objects.filter(client_handler=client)

    return render(request, "client/handlers/list_handler.html", {
        "client": client,
        "handlers": handlers
    })


def add_number(request, client_id):
    client = get_object_or_404(Client, id=client_id)

    if request.method == "POST":
        form = AddNumberForm(request.POST, client=client)

        if form.is_valid():
            number_value = str(form.cleaned_data["number"])  # Convert to string
            normalized = number_value.lstrip("0")  # Remove leading zero (if any)

            # Try longest prefixes first (4-digit, then 3-digit)
            possible_prefixes = [
                normalized[:4],  # 4-digit prefix
                normalized[:3],  # 3-digit prefix
            ]

            number_identifier = None

            for prefix in possible_prefixes:
                try:
                    number_identifier = NumberOperatorIdentifier.objects.get(number=prefix)
                    break
                except NumberOperatorIdentifier.DoesNotExist:
                    continue

            # If no matching prefix found
            if not number_identifier:
                form.add_error('number', "No operator found for this number prefix.")
                return render(request, 'number/add_number.html', {"form": form, "client": client})

            # Create Number entry
            new_number = form.save(commit=False)
            new_number.operator = number_identifier.operator
            new_number.client = client
            new_number.save()

            return redirect("client-detail", client_id=client.id)

    else:
        form = AddNumberForm(client=client)

    return render(request, 'number/add_number.html', {"form": form, "client": client})


def number_search(request, client_id):

    client = get_object_or_404(Client, id=client_id)
    numbers = Number.objects.filter(client=client).select_related("operator")

    search = request.GET.get("search", "")
    operator_id = request.GET.get("operator", "")

    if search:
        numbers = numbers.filter(number__icontains=search)

    if operator_id:
        numbers = numbers.filter(operator_id=operator_id)

    html = render_to_string("number/partials/number_list.html", {
        "numbers": numbers
    })

    return HttpResponse(html)


def number_detail(request, number_id):
    number = get_object_or_404(Number, id=number_id)

    # Initial load, htmx will replace the table body
    return render(request, 'number/number_detail.html', {
        'number': number,
        'current_balance': number.current_balance,
    })


def edit_number(request, number_id):
    number = get_object_or_404(Number, id=number_id)

    if request.method == "POST":
        form = AddNumberForm(request.POST, instance=number, client=number.client)
        if form.is_valid():
            form.save()
            return redirect("number-detail", number_id=number.id)
    else:
        form = AddNumberForm(instance=number, client=number.client)

    return render(request, "number/edit_number.html", {
        "form": form,
        "number": number
    })


def number_page(request):
    return render(request, "number/number.html")


def normalize_number(raw):
    raw = str(raw).strip()

    # +63XXXXXXXXXX → remove +63
    if raw.startswith("+63"):
        raw = raw[3:]

    # 09XXXXXXXXX → drop leading 0
    if raw.startswith("0") and len(raw) == 11:
        raw = raw[1:]

    return raw


@login_required
def search_number_page(request):
    query = request.GET.get("q", "").strip()

    if query == "":
        # ⬅ default: list all numbers from this user's clients
        results = Number.objects.filter(
            client__user_client=request.user
        ).select_related("client", "operator")

    else:
        # ⬅ perform search
        normalized = normalize_number(query)

        results = Number.objects.filter(
            number__icontains=normalized,
            client__user_client=request.user
        ).select_related("client", "operator")

    return render(request, "number/partials/number_results.html", {
        "results": results
    })


def payment_invoice_page(request):
    return render(request, "payments/payment_invoice.html")


def add_invoice(request, number_id):
    number = get_object_or_404(Number, id=number_id)

    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.number = number  # attach invoice to the number
            invoice.save()
            return redirect(reverse('number-detail', args=[number_id]))
    else:
        form = InvoiceForm(initial={'time': timezone.now()})

    return render(request, 'payments/add_invoice.html', {
        'form': form,
        'number': number
    })


def add_payment(request, number_id):
    number = get_object_or_404(Number, id=number_id)

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.number = number  # attach payment to the number
            payment.save()
            return redirect(reverse('number-detail', args=[number_id]))
    else:
        form = PaymentForm(initial={'time': timezone.now()})

    return render(request, 'payments/add_payment.html', {
        'form': form,
        'number': number
    })


def build_history_queryset(number):
    # Convert invoices
    invoice_entries = [
        {
            "type": "Invoice",
            "time": inv.time,
            "amount": inv.balance,
            "reference": inv.reference_number,
        }
        for inv in number.invoices.all()
    ]

    # Convert payments
    payment_entries = [
        {
            "type": "Payment",
            "time": pay.time,
            "amount": pay.paid_amount,
            "reference": "",
        }
        for pay in number.payments.all()
    ]

    return invoice_entries + payment_entries


def hx_history_table(request, number_id):
    number = get_object_or_404(Number, id=number_id)
    history = build_history_queryset(number)

    # --- SEARCH ---
    search = request.GET.get('search', '').strip()
    if search:
        history = [h for h in history if search.lower() in str(h['reference']).lower() or search.lower() in str(h['time']).lower()]

    # --- SORT ---
    sort = request.GET.get('sort', 'time_desc')
    reverse = True
    key = 'time'

    if sort == 'time_asc':
        reverse = False
    elif sort == 'amount_desc':
        key = 'amount'
    elif sort == 'amount_asc':
        key = 'amount'
        reverse = False
    elif sort == 'type_asc':
        key = 'type'
        reverse = False
    elif sort == 'type_desc':
        key = 'type'
        reverse = True

    history = sorted(history, key=lambda x: x[key], reverse=reverse)

    # --- PAGINATION ---
    page_number = request.GET.get("page", 1)
    paginator = Paginator(history, 10)
    page_obj = paginator.get_page(page_number)

    return render(request, 'payments/payment_invoice_history.html', {
        'page_obj': page_obj,
        'sort': sort,
        'search': search,
        'number': number,              # ➜ added
    })



