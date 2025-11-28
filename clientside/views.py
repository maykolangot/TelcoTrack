from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import auth
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import reverse
from django.core.paginator import Paginator
from django.db.utils import OperationalError
from django.db import connection
from django.core.cache import cache
from django.db.models.functions import Lower
from django.contrib.staticfiles import finders


from django.db.models import Prefetch, Count, Sum
from django.db.models.functions import Coalesce



# Time Aware using the TIME_ZONE on Settings
from django.utils import timezone
from django.utils.timezone import timedelta


# Printing:

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from datetime import datetime


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


MAX_ATTEMPTS = 5               # allowed failed attempts
LOCKOUT_TIME = 100             # seconds (5 minutes)


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


def get_client_ip(request):
    """Handles reverse-proxy / nginx / cloudflare scenarios."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")


def my_login(request):
    ip = request.META.get("REMOTE_ADDR")
    cache_key = f"login_attempts_{ip}"
    attempts = cache.get(cache_key, 0)

    form = LoginForm(request)

    # If locked out
    if attempts >= MAX_ATTEMPTS:
        messages.error(request, "Too many failed attempts. Try again in 5 minutes.")
        return render(request, 'login.html', {'form': form})

    if request.method == "POST":
        form = LoginForm(request, data=request.POST)

        username = request.POST.get("username")
        password = request.POST.get("password")

        # First check credentials (rate limiter applies to failed auth)
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            cache.delete(cache_key)
            messages.success(request, "You have logged in successfully.")
            return redirect("dashboard")

        # FAILED LOGIN → increment limiter
        attempts += 1
        cache.set(cache_key, attempts, LOCKOUT_TIME)

        remaining = MAX_ATTEMPTS - attempts

        if remaining <= 0:
            messages.error(request, "Too many failed attempts. Try again in 5 minutes.")
        else:
            messages.error(request, f"Invalid login. {remaining} attempts remaining.")

        # Still render invalid form with errors
        # IMPORTANT: Do not add extra message here

    return render(request, 'login.html', {'form': form})


@login_required(login_url='login')
def dashboard(request):
    user = request.user

    # A user may have multiple clients
    client_list = user.clients.all()

    if not client_list.exists():
        return render(request, "client/dashboard.html", {"numbers": []})

    # Use Django-aware local date (respects Asia/Manila timezone)
    today = timezone.localdate()

    today_name = today.strftime("%A")
    prev_day_name = (today - timedelta(days=1)).strftime("%A")
    next_day_name = (today + timedelta(days=1)).strftime("%A")

    # Read which day to filter
    requested_day = request.GET.get("day", "today")

    if requested_day == "prev":
        selected_day = prev_day_name
    elif requested_day == "next":
        selected_day = next_day_name
    else:
        selected_day = today_name  # default

    # Show all toggle
    show_all = request.GET.get("show") == "all"

    # Query numbers
    base_qs = Number.objects.filter(
        client__in=client_list,
        sim_status="Active",
        collection_day=selected_day
    )

    # Filter positive balance only unless show_all is ON
    if not show_all:
        base_qs = [n for n in base_qs if n.current_balance > 0]

    context = {
        "numbers": base_qs,
        "today": today_name,
        "prev_day": prev_day_name,
        "next_day": next_day_name,
        "selected_day": selected_day,
        "show_all": show_all,
    }

    return render(request, "client/dashboard.html", context)


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


@login_required(login_url='login')
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
@login_required(login_url='login')
def search_clients(request):
    query = request.GET.get("search", "")

    clients = Client.objects.filter(
        user_client=request.user,
        name__icontains=query
    ).annotate(
        client_numbers_count=Count('number')
    ).prefetch_related(
        Prefetch(
            'number_set',
            queryset=Number.objects.prefetch_related('invoices', 'payments')
        )
    ).order_by("name")

    # Calculate total_balance for each client (same as list_client view)
    for client in clients:
        client.client_total_balance = 0
        for number in client.number_set.all():
            client.client_total_balance += float(number.current_balance)

    return render(request, "client/partials/client_list.html", {
        "clients": clients
    })


@login_required(login_url='login')
def list_client(request):
    clients = Client.objects.filter(user_client=request.user)\
        .annotate(lower_name=Lower('name'))\
        .annotate(client_numbers_count=Count('number'))\
        .prefetch_related(
            Prefetch(
                'number_set',
                queryset=Number.objects.prefetch_related('invoices', 'payments')
            )
        )\
        .order_by('lower_name')

    # Calculate total_balance for each client
    for client in clients:
        client.client_total_balance = 0  # Changed name
        for number in client.number_set.all():
            client.client_total_balance += float(number.current_balance)

    return render(request, "client/list-client.html", {
        "clients": clients
    })


@login_required(login_url='login')
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


@login_required(login_url='login')
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


@login_required(login_url='login')
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


@login_required(login_url='login')
def list_handler(request, client_id):
    client = Client.objects.get(id=client_id, user_client=request.user)
    handlers = Handler.objects.filter(client_handler=client)

    return render(request, "client/handlers/list_handler.html", {
        "client": client,
        "handlers": handlers
    })


@login_required(login_url='login')
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


@login_required(login_url='login')
def number_detail(request, number_id):
    number = get_object_or_404(Number, id=number_id)

    # Initial load, htmx will replace the table body
    return render(request, 'number/number_detail.html', {
        'number': number,
        'current_balance': number.current_balance,
    })


@login_required(login_url='login')
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


@login_required(login_url='login')
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


@login_required(login_url='login')
def payment_invoice_page(request):
    return render(request, "payments/payment_invoice.html")


@login_required(login_url='login')
def add_invoice(request, number_id):
    number = get_object_or_404(Number, id=number_id)

    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.number = number
            invoice.save()

            if request.htmx:
                return HttpResponse("""
                    <script>
                        bootstrap.Modal.getInstance(
                            document.getElementById('mainModal')
                        ).hide();
                        htmx.trigger('#history-table', 'refresh');
                        location.reload();  // refresh totals
                    </script>
                """)

            return redirect(reverse('number-detail', args=[number_id]))

    else:
        form = InvoiceForm(initial={'time': timezone.now()})

    return render(request, 'payments/add_invoice.html', {
        'form': form,
        'number': number
    })


@login_required(login_url='login')
def add_payment(request, number_id):
    number = get_object_or_404(Number, id=number_id)

    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.number = number
            payment.save()

            if request.htmx:
                return HttpResponse("""
                    <script>
                        bootstrap.Modal.getInstance(
                            document.getElementById('mainModal')
                        ).hide();
                        htmx.trigger('#history-table', 'refresh');
                        location.reload();
                    </script>
                """)

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


def print_number_history(request, number_id, start, end):
    number = get_object_or_404(Number, id=number_id)

    # ---- Convert strings to datetime ----
    try:
        start_date = datetime.strptime(start, "%Y-%m-%d")
        end_date = datetime.strptime(end, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
    except:
        return HttpResponse("Invalid date format. Use YYYY-MM-DD")

    start_date = timezone.make_aware(start_date)
    end_date = timezone.make_aware(end_date)

    # ---- Build history ----
    history = build_history_queryset(number)
    filtered = [h for h in history if start_date <= h["time"] <= end_date]

    # ---- Sort chronologically ----
    filtered = sorted(filtered, key=lambda h: h["time"])

    # ---- PDF response ----
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="history-{number.number}.pdf"'

    doc = SimpleDocTemplate(
        response,
        pagesize=letter,
        leftMargin=40,
        rightMargin=40,
        topMargin=40,       # reduced padding
        bottomMargin=40
    )

    styles = getSampleStyleSheet()
    title_style = styles["Heading1"]
    title_style.fontSize = 18
    title_style.leading = 22
    title_style.spaceAfter = 12

    subtitle_style = styles["Normal"]
    subtitle_style.fontSize = 11
    subtitle_style.leading = 14
    subtitle_style.spaceAfter = 6

    elements = []

    # ---- Load logo ----
    logo_path = finders.find("images/logo.png")
    if logo_path:
        img = Image(logo_path, width=120, height=45)  # resize as needed
        elements.append(img)
        elements.append(Spacer(1, 8))


    # ---- Header Info (Option A) ----
    elements.append(Paragraph("History Report", title_style))

    client_name = number.client.name
    trade_name = number.client.trade_name

    header_html = f"""
        <b>Client Name:</b> {client_name}<br/>
        <b>Trade Name:</b> {trade_name}<br/>
        <b>Number:</b> {number.number}<br/>
        <b>Date Range:</b> {start} → {end}<br/>
    """

    elements.append(Paragraph(header_html, subtitle_style))
    elements.append(Spacer(1, 12))

    # ---- Table data ----
    table_data = [["Time", "Type", "Amount", "Reference"]]

    for h in filtered:
        time_str = (
            h["time"]
            .astimezone(timezone.get_current_timezone())
            .strftime("%Y-%m-%d %H:%M")
        )

        table_data.append([
            time_str,
            h["type"],
            f"{h['amount']}",
            h["reference"],
        ])

    # ---- Table styling ----
    table = Table(table_data, repeatRows=1,
        colWidths=[130, 90, 80, 200]
    )

    style = TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.Color(0.9, 0.9, 0.9)),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("TEXTCOLOR", (0,0), (-1,0), colors.black),

        ("ALIGN", (0,0), (-1,-1), "CENTER"),
        ("ALIGN", (2,1), (2,-1), "RIGHT"),

        ("GRID", (0,0), (-1,-1), 0.4, colors.grey),

        ("TOPPADDING", (0,0), (-1,0), 10),
        ("BOTTOMPADDING", (0,0), (-1,0), 10),
        ("TOPPADDING", (0,1), (-1,-1), 6),
        ("BOTTOMPADDING", (0,1), (-1,-1), 6),
    ])

    # ---- Color rows based on type ----
    for i, h in enumerate(filtered, start=1):  # row 0 = header
        t = h["type"].lower()

        if t == "invoice":
            style.add("BACKGROUND", (0, i), (-1, i), colors.Color(1, 0.88, 0.88))  # light red
        elif t == "payment":
            style.add("BACKGROUND", (0, i), (-1, i), colors.Color(0.88, 1, 0.88))  # light green

    table.setStyle(style)

    elements.append(table)

    # ---- Build PDF ----
    doc.build(elements)

    return response


