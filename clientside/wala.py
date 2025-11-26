# htmx-enhanced views for search, sort, pagination
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Number, Invoice, Payment
from django.utils import timezone

# Helper to merge history

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


def number_detail(request, number_id):
    number = get_object_or_404(Number, id=number_id)

    # Initial load, htmx will replace the table body
    return render(request, 'number/number_detail.html', {
        'number': number,
        'current_balance': number.current_balance,
    })


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

    return render(request, 'number/payment_invoice_history.html', {
        'page_obj': page_obj,
        'sort': sort,
        'search': search,
    })


# ===================== TEMPLATE: number/payment_invoice_history.html =====================
"""
<div>
    <input 
        type="text" 
        name="search"
        placeholder="Search reference or date..."
        hx-get="."
        hx-trigger="keyup changed delay:300ms"
        hx-target="#history-table"
        value="{{ search }}"
        class="form-control mb-3"
    >

    <table class="table table-striped">
        <thead>
            <tr>
                <th>
                    <a hx-get="?sort={% if sort=='time_desc' %}time_asc{% else %}time_desc{% endif %}&search={{ search }}" hx-target="#history-table" hx-push-url="false">Date</a>
                </th>
                <th>
                    <a hx-get="?sort={% if sort=='type_desc' %}type_asc{% else %}type_desc{% endif %}&search={{ search }}" hx-target="#history-table" hx-push-url="false">Type</a>
                </th>
                <th>
                    <a hx-get="?sort={% if sort=='amount_desc' %}amount_asc{% else %}amount_desc{% endif %}&search={{ search }}" hx-target="#history-table" hx-push-url="false">Amount (₱)</a>
                </th>
                <th>Reference</th>
            </tr>
        </thead>
        <tbody>
            {% for row in page_obj.object_list %}
                <tr>
                    <td>{{ row.time }}</td>
                    <td>{{ row.type }}</td>
                    <td>₱ {{ row.amount }}</td>
                    <td>{{ row.reference|default:"—" }}</td>
                </tr>
            {% empty %}
                <tr>
                    <td colspan="4" class="text-center">No results found.</td>
                </tr>
            {% endfor %}
        </tbody>
    </table>

    <nav>
        <ul class="pagination">
            {% if page_obj.has_previous %}
                <li class="page-item">
                    <a class="page-link" hx-get="?page={{ page_obj.previous_page_number }}&sort={{ sort }}&search={{ search }}" hx-target="#history-table">Previous</a>
                </li>
            {% endif %}

            {% for num in page_obj.paginator.page_range %}
                <li class="page-item {% if num == page_obj.number %}active{% endif %}">
                    <a class="page-link" hx-get="?page={{ num }}&sort={{ sort }}&search={{ search }}" hx-target="#history-table">{{ num }}</a>
                </li>
            {% endfor %}

            {% if page_obj.has_next %}
                <li class="page-item">
                    <a class="page-link" hx-get="?page={{ page_obj.next_page_number }}&sort={{ sort }}&search={{ search }}" hx-target="#history-table">Next</a>
                </li>
            {% endif %}
        </ul>
    </nav>
</div>
"""

# ===================== TEMPLATE SNIPPET: number/number_detail.html =====================
"""
<h2>Transaction History</h2>
<div id="history-table" hx-get="{% url 'hx-history-table' number.id %}" hx-trigger="load"></div>
"""
