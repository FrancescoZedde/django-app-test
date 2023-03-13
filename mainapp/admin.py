from django.contrib import admin
from mainapp.models import InventoryItem, Variant

admin.site.register(InventoryItem)
admin.site.register(Variant)