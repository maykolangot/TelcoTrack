from django.urls import path
from .views import (
    index,
    my_login,
    dashboard,
    user_logout,
    create_client,
    load_barangays,
    load_municipalities,
    load_provinces,
    list_client,
    search_clients,
    client_detail,
    add_handler,
    list_handler,
    edit_handler,

    add_number,
    number_search,
    number_detail,
    edit_number,


    number_page,
    search_number_page,


    payment_invoice_page,
    add_invoice,
    add_payment,
    hx_history_table,
    )

urlpatterns = [
    # Load Dropdown

    path("load-provinces/", load_provinces, name="load-provinces"),
    path("load-barangays/", load_barangays, name="load-barangays"),
    path("load-municipalities/", load_municipalities, name="load-municipalities"),


    path('', index, name='index'),
    path('login/', my_login, name='login'),
    path('dashboard/',dashboard, name='dashboard'),
    path('user-logout/', user_logout, name="user-logout"),


    path('clients/', list_client, name="clients"),
    path("clients/search/", search_clients, name="search-clients"),
    path('clients/create-client', create_client, name='create-client'),
    path("clients/<uuid:client_id>/", client_detail, name="client-detail"),


    path("clients/<uuid:client_id>/add-handler/", add_handler, name="add-handler"),
    path("clients/<uuid:client_id>/handlers/", list_handler, name="list-handler"),
    path("clients/<uuid:client_id>/handlers/<int:handler_id>/edit/", edit_handler, name="edit-handler"),



    path("clients/<uuid:client_id>/add-number/", add_number, name="add-number"),
    path("clients/<uuid:client_id>/numbers/search/", number_search, name="number-search"),

    path("numbers/", number_page, name="number-page"),
    path("numbers/<uuid:number_id>/", number_detail, name="number-detail"),
    path("numbers/<uuid:number_id>/add-invoice/", add_invoice, name="add-invoice"),
    path("numbers/<uuid:number_id>/add-payment/", add_payment, name="add-payment"),


    path("numbers/<uuid:number_id>/edit/", edit_number, name="edit-number"),

    path("numbers/search/", search_number_page, name="search-number"),


    path("payments/", payment_invoice_page, name='payment-page' ),
    path("numbers/<uuid:number_id>/history/", hx_history_table, name="hx-history-table"),






]